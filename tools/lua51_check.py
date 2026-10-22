"""Parse a Lua payload with a real Lua 5.1, so a dialect mistake cannot reach a game launch.

    python tools/lua51_check.py <file.lua> [...]
    python tools/lua51_check.py <file.lua> --dump out.bc     # also emit a real 5.1 binary chunk
    python tools/lua51_check.py --selftest                   # prove the checker bites

WHY (2026-10-12): the host LuaJIT accepts Lua 5.3 bitwise operators and the game's Lua refused them, so
a payload that loaded fine in the fixtures failed in game with "')' expected near '&'" and cost a launch.
No regex can settle that: the check has to be a real parser.

HOW THIS USED TO WORK, AND WHAT CHANGED (2026-10-20): it loaded the game's own `bin/lua51.dll` through
ctypes and called `luaL_loadbuffer` - the strongest possible evidence, the target VM itself.  Build
25988413 **removed that DLL from the distribution entirely**, which is also the cleanest single proof
that the VM changed: the old 469,080 B `lua51.dll` contained the string "LuaJIT 2"; the new build ships
no lua DLL at all and the VM is statically linked inside `helldivers2.exe` (its plaintext `.rdata`
carries "Lua 5.1.4").  So a parser is now loaded in this order:

  1. the game's `bin/lua51.dll`, if a future build ships one again - but ONLY after checking that the
     DLL is not LuaJIT, because validating a payload against LuaJIT is exactly the mistake this tool
     exists to prevent;
  2. `lupa.lua51` - a real stock Lua 5.1 embedded in a Python wheel (no compiler, no system install).

The parser actually used is printed, because "the gate passed" means nothing without knowing which VM
said so.

Exit codes: 0 = every file parses, 1 = at least one refused, 2 = no 5.1 parser available.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys
from pathlib import Path

GAME_DLL = Path(r"D:\SteamLibrary\steamapps\common\Helldivers 2\bin\lua51.dll")
LUA_OK = 0


def _open_game_dll(path: Path):
    """The target VM itself, when the build still ships it.  Refuses a LuaJIT DLL."""
    if not path.is_file():
        return None
    blob = path.read_bytes()
    if b"LuaJIT" in blob:
        print(f"!! {path} is LuaJIT, not stock Lua 5.1 - refusing to use it as the gate")
        return None
    lua = ctypes.CDLL(str(path))
    lua.luaL_newstate.restype = ctypes.c_void_p
    lua.luaL_loadbuffer.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
    lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    lua.lua_tolstring.restype = ctypes.c_char_p
    lua.lua_close.argtypes = [ctypes.c_void_p]
    state = lua.luaL_newstate()
    if not state:
        return None

    def parse(source: bytes, name: str) -> tuple[bool, str]:
        status = lua.luaL_loadbuffer(state, source, len(source), name.encode())
        if status == LUA_OK:
            return True, ""
        length = ctypes.c_size_t()
        message = lua.lua_tolstring(state, -1, ctypes.byref(length))
        return False, (message.decode("utf-8", "replace") if message else f"status {status}")

    def dump(source: bytes, name: str):            # noqa: ANN001 - the DLL path cannot dump
        return None, "the game DLL path does not implement --dump"

    print(f"parser: the game's own {path.name} (target VM)")
    return parse, dump


def _open_lupa():
    try:
        import lupa.lua51 as lua51
    except Exception as exc:                       # noqa: BLE001
        print(f"!! no Lua 5.1 parser: {GAME_DLL.name} is absent and lupa is not installed ({exc})")
        print("   install it with:  pip install lupa")
        return None
    rt = lua51.LuaRuntime(unpack_returned_tuples=True)
    compile_fn = rt.eval("""function(source, name)
        local fn, err = loadstring(source, name)
        if fn then return true, "" end
        return false, tostring(err)
    end""")
    dump_rt = lua51.LuaRuntime(unpack_returned_tuples=True, encoding=None)
    dump_fn = dump_rt.eval("""function(source, name)
        local fn, err = loadstring(source, name)
        if not fn then return nil, tostring(err) end
        return string.dump(fn), ""
    end""")

    def parse(source: bytes, name: str) -> tuple[bool, str]:
        try:
            text = source.decode("utf-8")
        except UnicodeDecodeError as exc:
            return False, f"not UTF-8: {exc}"
        ok, err = compile_fn(text, "@" + name)
        return bool(ok), str(err)

    def dump(source: bytes, name: str):
        # this runtime is created with encoding=None, so Lua strings are bytes on both sides - passing
        # a str here arrives as userdata and loadstring refuses it
        blob, err = dump_fn(source, ("@" + name).encode("utf-8"))
        return (bytes(blob) if blob is not None else None), (err.decode("utf-8", "replace") if err else "")

    print(f"parser: lupa.lua51 - stock Lua {rt.eval('_VERSION')} ({lua51.__name__})")
    return parse, dump


def selftest() -> int:
    """A gate that has never rejected anything has not been shown to work."""
    opener = _open_game_dll(GAME_DLL) or _open_lupa()
    if not opener:
        return 2
    parse, dump = opener
    failures = 0

    def expect(label: str, source: str, want: bool, want_in: str | None = None):
        nonlocal failures
        ok, err = parse(source.encode("utf-8"), label)
        good = ok == want and (want_in is None or want_in in err)
        print(("PASS " if good else "FAIL ") + f"{label}: accepted={ok} {err[:70]}")
        failures += 0 if good else 1

    expect("plain Lua 5.1", "local t={1,2} return #t + 1.5", True)
    expect("hex escape \\x41 (LuaJIT-only)", r"return \x41", False, "unexpected symbol")
    expect("integer division // (5.3)", "return 5 // 2", False, "unexpected symbol")
    expect("bitwise or | (5.2+)", "return 1 | 2", False, "expected")
    expect("goto (5.2+)", "goto skip ::skip::", False, "expected")

    blob, err = dump(b"return 1 + 1", "dumptest")
    if blob is None:
        print(f"SKIP dump unavailable here ({err})")
    else:
        good = blob[:4] == b"\x1bLua"
        print(("PASS " if good else "FAIL ") + f"string.dump magic {blob[:4]!r} (want b'\\x1bLua')")
        failures += 0 if good else 1
        disasm = Path(__file__).with_name("luac51_disasm.py")
        if disasm.is_file():
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".bc", delete=False) as handle:
                handle.write(blob)
                tmp = handle.name
            try:
                run = subprocess.run([sys.executable, str(disasm), tmp], capture_output=True, text=True)
                consumed = "residual 0" in run.stdout
                print(("PASS " if consumed else "FAIL ") + "luac51_disasm consumes a real-5.1 chunk exactly")
                failures += 0 if consumed else 1
            finally:
                os.unlink(tmp)

    print(f"-- {failures} self-check(s) failed" if failures else "-- all self-checks passed")
    return 1 if failures else 0


LUA51_ONLY_PATTERNS = (
    # (regex, explanation).  These do not fail to COMPILE on stock 5.1 - they either vanish or, worse,
    # produce a different value, so a parse check cannot see them.
    (r"\\x[0-9a-fA-F]{2}", r"`\x` hex escape: LuaJIT gives the byte, stock 5.1 drops the backslash and "
                           r"keeps the literal text, so the string silently changes"),
    (r"\bbit\.", "`bit` library: LuaJIT only, nil on stock 5.1"),
    (r"\bjit\.", "`jit` library: LuaJIT only, nil on stock 5.1"),
    (r"\bffi\.", "`ffi` library: LuaJIT only, nil on stock 5.1"),
    (r"\btable\.new\b", "`table.new`: LuaJIT only"),
    (r"\btable\.clear\b", "`table.clear`: LuaJIT only"),
    (r"\bstring\.buffer\b", "`string.buffer`: LuaJIT only"),
)


def lint_source(text: str) -> list[str]:
    """LuaJIT-only constructs that stock 5.1 accepts but interprets differently, or lacks entirely."""
    import re
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        code = line.split("--", 1)[0]
        for pattern, why in LUA51_ONLY_PATTERNS:
            for match in re.finditer(pattern, code):
                findings.append(f"line {number}: {why} ({match.group(0)})")
    return findings


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--dump", help="write the first file's compiled Lua 5.1 chunk here")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--lint", action="store_true",
                    help="also flag LuaJIT-only constructs that stock 5.1 accepts but reads differently")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.files:
        print(__doc__)
        return 2

    opener = _open_game_dll(GAME_DLL) or _open_lupa()
    if not opener:
        return 2
    parse, dump = opener

    failures = 0
    for name in args.files:
        path = Path(name)
        try:
            source = path.read_bytes()
        except OSError as exc:
            print(f"LUA51 FAIL  {path}: {exc}")
            failures += 1
            continue
        ok, err = parse(source, path.name)
        if ok:
            print(f"LUA51 OK    {path}")
        else:
            print(f"LUA51 FAIL  {path}: {err}")
            failures += 1
            continue
        if args.lint:
            try:
                text = source.decode("utf-8")
            except UnicodeDecodeError as exc:
                print(f"LUA51 LINT  {path}: not UTF-8 ({exc})")
                failures += 1
                continue
            findings = lint_source(text)
            for finding in findings:
                print(f"LUA51 LINT  {path}: {finding}")
            if findings:
                failures += 1

    if args.dump and args.files:
        blob, err = dump(Path(args.files[0]).read_bytes(), Path(args.files[0]).name)
        if blob is None:
            print(f"--dump failed: {err}", file=sys.stderr)
            return 1
        Path(args.dump).write_bytes(blob)
        print(f"dumped {len(blob)} B Lua 5.1 chunk -> {args.dump} (magic {blob[:4]!r})")
        # Measured 2026-10-20: the game's own chunks carry sizeof(size_t)=4, a chunk produced by a
        # 64-bit string.dump carries 8. They are not interchangeable, and whether the game's loader
        # checks that header field is unproven. SOURCE payloads are proven to load - prefer them.
        print("NOTE this chunk's header says sizeof(size_t)="
              f"{blob[6] if len(blob) > 6 else '?'}; the game's own chunks say 4.")

    if failures:
        print(f"\n{failures} file(s) refused by stock Lua 5.1, or flagged by the LuaJIT-only lint")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
