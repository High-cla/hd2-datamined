#!/usr/bin/env python3
r"""make_loadlib_fixtures.py -- build the DLL fixtures for the in-process native-code test.

WHY NO COMPILER IS NEEDED
    The question is not "can we write C" but "can the game Lua load a DLL file that WE put on
    disk".  Error-message discrimination answers it: Lua's package.loadlib calls LoadLibraryA
    first and GetProcAddress second, so

        module missing      -> "The specified module could not be found."      (126)
        module loaded, symbol missing -> "The specified procedure could not be found." (127)
        image refused by the loader policy -> 577 / 193

    127 is the only code that proves LoadLibrary ran, i.e. our file got mapped into the process.
    A real DLL to load is therefore enough -- it does not need to be ours.

WHAT IT DROPS (into the game root, which is the process cwd and is `.\?.dll` in package.cpath)
    dshtest_signed.dll     byte copy of %SystemRoot%\System32\version.dll  (signed by Microsoft)
    dshtest_unsigned.dll   same file with IMAGE_DIRECTORY_ENTRY_SECURITY zeroed -> unsigned

    version.dll is chosen because its DllMain is inert: loading it twice (once from System32,
    once from the game folder under a new name) has no side effects.  Do NOT use something like
    bink2w64.dll or EOSSDK - their DllMain does real work.

    The unsigned copy is what matters first: if the process gates modules, the signed one gets a
    different code than the unsigned one, and the two messages say which gate refused.

--matrix: THE TWO REMAINING DIMENSIONS (2026-10-22)
    With signature settled (unsigned -> 577, Microsoft-signed but unknown -> 193, self-signed +
    trusted root -> still 577), two questions are open and each needs exactly one fixture:

      dshtest_bin.dll    byte copy of the SAME signed file, placed in <game>\bin\ instead of the
                         root.  Same bytes, different directory -> answers "is the gate path-based?"
      dshtest_copy.dll   byte copy of a game-shipped, Arrowhead-signed DLL under a new name.
                         Same bytes, same directory, new name -> answers "is the allowlist keyed on
                         content hash (expect 127 = mapped) or on name/path (expect 193)?"

    The copy fixture re-runs a shipped plugin's DllMain from a second path.  That is expected to be
    inert but is not guaranteed; it is opt-in and removable, and the game is restored by --remove.

    Honest label: NEITHER outcome is a route to running our own code.  A mapped copy is somebody
    else's signed bytes -- change one byte and the hash changes.  This is diagnostic only.

USAGE
    python tools/make_loadlib_fixtures.py                  # the two signature fixtures
    python tools/make_loadlib_fixtures.py --matrix         # + the two gate-granularity fixtures
    python tools/make_loadlib_fixtures.py --dry-run        # print the plan, write nothing
    python tools/make_loadlib_fixtures.py --remove         # delete every fixture it may have made
    python tools/make_loadlib_fixtures.py --game-root "D:\...\Helldivers 2"
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import struct
import sys

DEFAULT_GAME_ROOT = pathlib.Path(r"D:\SteamLibrary\steamapps\common\Helldivers 2")
SOURCE = pathlib.Path(r"C:\Windows\System32\version.dll")
PLUGIN_RELATIVE = pathlib.Path("bin") / "plugins" / "level_generation_pluginw64_release.dll"

DIR_ENTRY_SECURITY = 4


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def security_dir(data: bytes, label: str = "") -> tuple[int, int]:
    """Return (VirtualAddress, Size) of the certificate table, or raise if the PE is not understood."""
    if data[:2] != b"MZ":
        raise SystemExit(f"not a PE file (no MZ){' ' + label if label else ''}")
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise SystemExit(f"not a PE file (no PE signature){' ' + label if label else ''}")
    coff = e_lfanew + 4
    number_of_sections = struct.unpack_from("<H", data, coff + 2)[0]
    size_of_optional_header = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic == 0x20B:
        data_dir = opt + 112
    elif magic == 0x10B:
        data_dir = opt + 96
    else:
        raise SystemExit(f"unknown optional-header magic {magic:#x}")
    if size_of_optional_header < (data_dir - opt) + (DIR_ENTRY_SECURITY + 1) * 8:
        raise SystemExit("optional header too small to hold a security directory")
    va, size = struct.unpack_from("<II", data, data_dir + DIR_ENTRY_SECURITY * 8)
    print(f"  pe: {number_of_sections} section(s), magic {magic:#x}, "
          f"security dir = va {va:#x} size {size:#x}")
    return va, size


def strip_signature(data: bytes) -> bytes:
    """Zero IMAGE_DIRECTORY_ENTRY_SECURITY so the loader stops seeing a certificate."""
    out = bytearray(data)
    e_lfanew = struct.unpack_from("<I", out, 0x3C)[0]
    coff = e_lfanew + 4
    opt = coff + 20
    magic = struct.unpack_from("<H", out, opt)[0]
    data_dir = opt + (112 if magic == 0x20B else 96)
    off = data_dir + DIR_ENTRY_SECURITY * 8
    struct.pack_into("<II", out, off, 0, 0)
    return bytes(out)


def plan(game_root: pathlib.Path, matrix: bool) -> list[tuple[str, pathlib.Path, bytes, str]]:
    """Return [(label, destination, payload, why)] -- everything is decided before anything is written."""
    original = SOURCE.read_bytes()
    print(f"source {SOURCE}  {len(original):,} B  md5 {md5(original)}")
    _, size = security_dir(original)
    if size == 0:
        raise SystemExit("!! the source has no certificate table; the unsigned copy would equal the "
                         "signed one")

    items: list[tuple[str, pathlib.Path, bytes, str]] = [
        ("signed", game_root / "dshtest_signed.dll", original,
         "Microsoft-signed, unknown file -> expect 193 if the allowlist gate is live"),
        ("unsigned", game_root / "dshtest_unsigned.dll", strip_signature(original),
         "same bytes without a certificate -> expect 577"),
    ]
    if matrix:
        items.append(("bin", game_root / "bin" / "dshtest_bin.dll", original,
                      "same signed bytes, different directory -> 127 means the path does not matter"))
        plugin = game_root / PLUGIN_RELATIVE
        if not plugin.is_file():
            raise SystemExit(f"!! plugin fixture source not found: {plugin}")
        items.append(("copy", game_root / "dshtest_copy.dll", plugin.read_bytes(),
                      "game-shipped signed bytes under a NEW name -> 127 means hash-keyed allowlist"))
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-root", default=str(DEFAULT_GAME_ROOT))
    ap.add_argument("--matrix", action="store_true",
                    help="also build the path / allowlist fixtures (see the module docstring)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--remove", action="store_true", help="delete every fixture this tool can create")
    a = ap.parse_args()

    game_root = pathlib.Path(a.game_root)

    if a.remove:
        for rel in ("dshtest_signed.dll", "dshtest_unsigned.dll", "dshtest_copy.dll",
                    "bin/dshtest_bin.dll"):
            path = game_root / rel
            if path.exists():
                path.unlink()
                print(f"removed {path}")
            else:
                print(f"absent  {path}")
        return 0

    if not game_root.is_dir():
        print(f"!! game root not found: {game_root}")
        return 2
    if not SOURCE.is_file():
        print(f"!! source DLL not found: {SOURCE}")
        return 2
    if not (game_root / "bin").is_dir():
        print(f"!! {game_root / 'bin'} is not a directory")
        return 2

    items = plan(game_root, a.matrix)
    print("\nfixtures:")
    for label, dest, payload, why in items:
        print(f"  {label:<9} {dest}")
        print(f"            {len(payload):,} B  md5 {md5(payload)}")
        print(f"            {why}")

    if a.dry_run:
        print("\ndry run: nothing written. the game must be restarted so the probe can loadlib these.")
        return 0

    for label, dest, payload, _ in items:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        print(f"wrote {dest.name}  {len(payload):,} B  md5 {md5(dest.read_bytes())}"
              f"  security dir = {'SIGNED' if security_dir(dest.read_bytes())[1] else 'UNSIGNED'}")

    if md5(items[0][2]) == md5(items[1][2]):
        print("!! the signed and unsigned copies are identical - the strip did nothing")
        return 4

    print("\ndone. the game must be restarted so the probe can loadlib these.")
    print("clean up afterwards with --remove (the probe cannot delete them for you).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
