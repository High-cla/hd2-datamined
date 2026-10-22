"""Disassemble a stock Lua 5.1 binary chunk (``\\x1bLua`` + version 0x51).

Why this exists
---------------
The HD2 build shipped as 25480438 stored its ``lua`` resources as **LuaJIT**
bytecode (magic ``\\x1bLJ``), which this machine's LuaJIT can list directly.  The
25988413 build stores them as **stock Lua 5.1** chunks (magic ``\\x1bLua`` + 0x51),
which LuaJIT refuses ("cannot load incompatible bytecode") and there is no
``luac5.1`` here.  Without a disassembler the only readable part of a lua
resource is its string blob, which cannot tell ``require "x"`` from a comment.

SELF-PROOF: the parser must consume the chunk EXACTLY - no trailing bytes and no
overrun - and that is checked on every run (``--allow-trailing`` disables it, and
a truncated file must then fail).  A parser that silently stops early would
report plausible instructions for the part it happened to read, which is exactly
the failure mode this tool is built to avoid.

    python tools/luac51_disasm.py <chunk>                 # full listing
    python tools/luac51_disasm.py <chunk> --code-only      # instructions only
    python tools/luac51_disasm.py <chunk> --selftest       # prove the parser
"""
from __future__ import annotations

import argparse
import struct
import sys

MAGIC = b"\x1bLua"
VERSION = 0x51

OPNAMES = (
    "MOVE", "LOADK", "LOADBOOL", "LOADNIL", "GETUPVAL", "GETGLOBAL", "GETTABLE",
    "SETGLOBAL", "SETUPVAL", "SETTABLE", "NEWTABLE", "SELF", "ADD", "SUB", "MUL",
    "DIV", "MOD", "POW", "UNM", "NOT", "LEN", "CONCAT", "JMP", "EQ", "LT", "LE",
    "TEST", "TESTSET", "CALL", "TAILCALL", "RETURN", "FORLOOP", "FORPREP",
    "TFORLOOP", "SETLIST", "CLOSE", "CLOSURE", "VARARG",
)
# per-op operand format
IABX = {1, 5, 7, 36}
IASBX = {22, 31, 32}
# ops whose B/C are RK values (constant when >= 256)
RK_B = {6, 9, 11, 12, 13, 14, 15, 16, 17, 21, 23, 24, 25}
RK_C = {6, 9, 11, 12, 13, 14, 15, 16, 17, 21, 23, 24, 25}

KT_NIL, KT_BOOL, KT_NUMBER, KT_STRING = 0, 1, 3, 4


class Chunk:
    def __init__(self, data: bytes, sizet_size: int = 4):
        self.d = data
        self.p = 0
        self.endian = "<"
        self.sizet_size = sizet_size

    # ---- primitives --------------------------------------------------- #
    def take(self, n: int) -> bytes:
        if self.p + n > len(self.d):
            raise ValueError(f"chunk truncated: wanted {n} B at {self.p}, have {len(self.d) - self.p}")
        out = self.d[self.p:self.p + n]
        self.p += n
        return out

    def byte(self) -> int:
        return self.take(1)[0]

    def int(self) -> int:
        return struct.unpack(self.endian + "i", self.take(4))[0]

    def size_t(self) -> int:
        """Lua 5.1 writes sizeof(size_t) into the header and this tool honours it.

        Both widths occur in the wild here: the game's own chunks say 4, a chunk produced by a 64-bit
        `string.dump` says 8. Hardcoding either one makes the tool reject half the real files.
        """
        fmt = "I" if self.sizet_size == 4 else "Q"
        return struct.unpack(self.endian + fmt, self.take(self.sizet_size))[0]

    def number(self) -> float:
        return struct.unpack(self.endian + "d", self.take(8))[0]

    def string(self) -> bytes | None:
        n = self.size_t()
        if n == 0:
            return None
        return self.take(n)[:-1]          # drop the trailing NUL


def kstr(k) -> str:
    if k is None:
        return "nil"
    if isinstance(k, bytes):
        try:
            return '"' + k.decode("utf-8") + '"'
        except UnicodeDecodeError:
            return "<" + k.hex() + ">"
    if isinstance(k, float) and k.is_integer():
        return str(int(k))
    return repr(k)


def rk(v: int, k: list) -> str:
    if v >= 256:
        i = v - 256
        return f"K{i}({kstr(k[i]) if i < len(k) else '?'})"
    return f"R{v}"


def parse_function(c: Chunk, depth: int, out: list) -> None:
    source = c.string()
    linedefined = c.int()
    lastlinedefined = c.int()
    nups = c.byte()
    numparams = c.byte()
    is_vararg = c.byte()
    maxstack = c.byte()

    code = [struct.unpack(c.endian + "I", c.take(4))[0] for _ in range(c.int())]

    nk = c.int()
    k = []
    for _ in range(nk):
        t = c.byte()
        if t == KT_NIL:
            k.append(None)
        elif t == KT_BOOL:
            k.append(bool(c.byte()))
        elif t == KT_NUMBER:
            k.append(c.number())
        elif t == KT_STRING:
            k.append(c.string())
        else:
            raise ValueError(f"unknown constant type {t} at {c.p}")

    protos = [None] * c.int()
    for i in range(len(protos)):
        protos[i] = len(out)
        parse_function(c, depth + 1, out)      # recurse; appends its own lines

    # debug info: lineinfo, locvars, upvalues
    for _ in range(c.int()):
        c.int()
    for _ in range(c.int()):
        c.string()
        c.int()
        c.int()
    for _ in range(c.int()):
        c.string()

    src = (source or b"?").decode("utf-8", "replace")
    out.append(
        f"-- proto depth={depth} {src}:{linedefined}-{lastlinedefined} "
        f"params={numparams} vararg={is_vararg} stack={maxstack} nups={nups} "
        f"code={len(code)} k={nk} protos={len(protos)}"
    )
    for pc, ins in enumerate(code, 1):
        op = ins & 0x3F
        a = (ins >> 6) & 0xFF
        cc = (ins >> 14) & 0x1FF
        b = (ins >> 23) & 0x1FF
        bx = (ins >> 14) & 0x3FFFF
        sbx = bx - 131071
        name = OPNAMES[op] if op < len(OPNAMES) else f"OP{op}"
        if op in IABX:
            extra = f"Bx={bx}"
            if op in (5, 7):                       # GETGLOBAL / SETGLOBAL
                extra += f" ; {kstr(k[bx]) if bx < nk else '?'}"
            elif op == 1:
                extra += f" ; {kstr(k[bx]) if bx < nk else '?'}"
            elif op == 36:
                extra += f" ; proto[{bx}]" if bx < len(protos) else " ; proto?"
            out.append(f"  {pc:04d} {name:<9} {a:<3} {extra}")
        elif op in IASBX:
            out.append(f"  {pc:04d} {name:<9} {a:<3} sBx={sbx:<7} -> {pc + 1 + sbx}")
        else:
            bb = rk(b, k) if op in RK_B else str(b)
            ccr = rk(cc, k) if op in RK_C else str(cc)
            tail = ""
            if op == 34:                            # SETLIST
                tail = f" ; n={cc or 'top'}"
            out.append(f"  {pc:04d} {name:<9} {a:<3} {bb:<18} {ccr}{tail}")


def disassemble(data: bytes, strict: bool = True) -> list[str]:
    if data[:4] != MAGIC:
        raise ValueError(f"not a Lua chunk (magic {data[:4]!r})")
    if len(data) < 12:
        raise ValueError("chunk shorter than the 12-byte header")
    if data[4] != VERSION:
        raise ValueError(f"Lua version {data[4]:#x} != 0x51 (not Lua 5.1)")
    c = Chunk(data)
    c.p = 4
    c.p += 1                                        # version
    fmt = c.byte()
    if fmt != 0:
        raise ValueError(f"format {fmt} != 0")
    endian = c.byte()
    c.endian = "<" if endian == 1 else ">"
    int_size, sizet_size, instr_size, num_size = c.byte(), c.byte(), c.byte(), c.byte()
    if (int_size, instr_size, num_size) != (4, 4, 8):
        raise ValueError(f"unexpected type sizes {(int_size, sizet_size, instr_size, num_size)}")
    if sizet_size not in (4, 8):
        raise ValueError(f"unsupported sizeof(size_t) {sizet_size}")
    c.sizet_size = sizet_size
    integral = c.byte()
    if integral:
        raise ValueError("integral-only build not supported")

    out: list[str] = [f"-- Lua 5.1 chunk, {len(data)} B, endian={'<=' if endian == 1 else '>='}, "
                      f"sizeof(size_t)={sizet_size}"]
    parse_function(c, 0, out)
    left = len(data) - c.p
    if strict and left != 0:
        raise ValueError(f"parser stopped {left} B short of the end ({c.p}/{len(data)}) - layout guess is wrong")
    out.append(f"-- consumed {c.p}/{len(data)} B (residual {left})")
    return out


def selftest() -> int:
    """Prove the checks that make the output trustworthy, without a luac here."""
    total = 0
    failed = 0

    def expect(name, cond):
        nonlocal total, failed
        total += 1
        failed += 0 if cond else 1
        print(("PASS " if cond else "FAIL ") + name)
        return cond

    good = (MAGIC + bytes([VERSION, 0, 1, 4, 4, 4, 8, 0])
            + struct.pack("<i", 0)                    # source: size_t 0
            + struct.pack("<ii", 0, 0) + bytes([0, 0, 2, 2])
            + struct.pack("<i", 0)                    # code: 0 instructions
            + struct.pack("<i", 0)                    # constants: 0
            + struct.pack("<i", 0)                    # protos: 0
            + struct.pack("<i", 0) + struct.pack("<i", 0) + struct.pack("<i", 0))
    r = disassemble(good)
    expect("minimal chunk parses and consumes every byte", "residual 0" in r[-1])

    # The game's own chunks carry sizeof(size_t)=4; a chunk from a 64-bit string.dump carries 8.
    # Hardcoding one width makes the tool reject half the real files, so both are exercised.
    wide = (MAGIC + bytes([VERSION, 0, 1, 4, 8, 4, 8, 0])
            + struct.pack("<Q", 0)
            + struct.pack("<ii", 0, 0) + bytes([0, 0, 2, 2])
            + struct.pack("<i", 0) * 6)
    r = disassemble(wide)
    expect("sizeof(size_t)=8 chunk parses and consumes every byte",
           "residual 0" in r[-1] and "sizeof(size_t)=8" in r[0])
    expect("sinfo: the game's 4-byte form is reported",
           any("sizeof(size_t)=4" in line for line in disassemble(good)))

    bad = good[:-4]
    try:
        disassemble(bad)
        expect("truncated chunk must fail", False)
    except ValueError as exc:
        expect(f"truncated chunk fails ({str(exc)[:48]}...)", True)

    try:
        disassemble(b"LuaJ\x02" + good[6:])
        expect("LuaJIT magic must be refused", False)
    except ValueError:
        expect("LuaJIT magic is refused", True)

    try:
        disassemble(good[:4] + bytes([0x50]) + good[5:])
        expect("non-5.1 version must be refused", False)
    except ValueError:
        expect("non-5.1 version is refused", True)

    print(f"-- {total - failed}/{total} self-checks passed")
    return 0 if failed == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chunk", nargs="?")
    ap.add_argument("--code-only", action="store_true")
    ap.add_argument("--allow-trailing", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.chunk:
        ap.error("a chunk path is required unless --selftest")
    data = open(args.chunk, "rb").read()
    try:
        for line in disassemble(data, strict=not args.allow_trailing):
            if args.code_only and not line.startswith("  "):
                continue
            print(line)
    except ValueError as exc:
        print(f"luac51_disasm: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
