#!/usr/bin/env python3
"""Read a virtual address out of a (multi-GB) full minidump without loading the dump.

Why this exists
    The old build's sealed-box key material lives at fixed RVAs of the *loaded* image
    (HD2-Mod-Developer-Guide §4.2): public 0x16532B0, private 0x1653160 in the 25480438
    helldivers2.exe.  The image on disk is aPLib-packed, but a **full memory dump** taken
    while the old build was running already holds the unpacked image - so the keys can be
    read straight out of the dump and the unpacking step is skipped entirely.

    Dumps are 10+ GB, so everything here seeks instead of reading whole files.

Usage
    python dump_read_rva.py <dump> --module helldivers2.exe --rva 0x1653160 --length 64
    python dump_read_rva.py <dump> --list-modules
"""
from __future__ import annotations

import argparse
import struct
import sys

M64 = 9            # Memory64ListStream
M32 = 5            # MemoryListStream
MODULE_LIST = 4


class Dump:
    def __init__(self, path: str):
        self.path = path
        self.f = open(path, "rb")
        header = self.f.read(32)
        if header[:4] != b"MDMP":
            raise SystemExit(f"{path}: not a minidump (magic {header[:4]!r})")
        _, _, nstreams, dir_rva = struct.unpack_from("<IIII", header, 0)
        self.f.seek(dir_rva)
        table = self.f.read(nstreams * 12)
        self.streams = {}
        for i in range(nstreams):
            stype, size, rva = struct.unpack_from("<III", table, i * 12)
            if stype and size:
                self.streams.setdefault(stype, (size, rva))
        self.modules = self._modules()
        self.ranges = self._ranges()
        self.ranges.sort()

    # ------------------------------------------------------------------ parse
    def _read_at(self, offset: int, size: int) -> bytes:
        self.f.seek(offset)
        return self.f.read(size)

    def _modules(self) -> list[tuple[str, int, int]]:
        if MODULE_LIST not in self.streams:
            return []
        size, rva = self.streams[MODULE_LIST]
        count = struct.unpack_from("<I", self._read_at(rva, 4), 0)[0]
        blob = self._read_at(rva + 4, count * 108)
        out = []
        for i in range(count):
            base, image_size = struct.unpack_from("<QI", blob, i * 108)
            name_rva = struct.unpack_from("<I", blob, i * 108 + 20)[0]
            name_len = struct.unpack_from("<I", self._read_at(name_rva, 4), 0)[0]
            raw = self._read_at(name_rva + 4, name_len)
            out.append((raw.decode("utf-16-le", "replace"), base, image_size))
        return out

    def _ranges(self) -> list[tuple[int, int, int]]:
        """[(start, size, file_offset)] for every captured memory range."""
        if M64 in self.streams:
            size, rva = self.streams[M64]
            head = self._read_at(rva, 16)
            count, base_rva = struct.unpack("<QQ", head)
            table = self._read_at(rva + 16, count * 16)
            out = []
            cursor = base_rva
            for i in range(count):
                start, dsize = struct.unpack_from("<QQ", table, i * 16)
                out.append((start, dsize, cursor))
                cursor += dsize
            return out
        if M32 in self.streams:
            size, rva = self.streams[M32]
            count = struct.unpack_from("<I", self._read_at(rva, 4), 0)[0]
            table = self._read_at(rva + 4, count * 16)
            out = []
            for i in range(count):
                start, dsize, drva = struct.unpack_from("<QII", table, i * 16)
                out.append((start, dsize, drva))
            return out
        raise SystemExit("dump has neither Memory64ListStream nor MemoryListStream")

    # ------------------------------------------------------------------- read
    def read_virtual(self, address: int, length: int) -> bytes | None:
        import bisect
        starts = [r[0] for r in self.ranges]
        index = bisect.bisect_right(starts, address) - 1
        if index < 0:
            return None
        start, size, offset = self.ranges[index]
        if address + length > start + size:
            return None
        return self._read_at(offset + (address - start), length)

    def find_module(self, name: str):
        for module_name, base, image_size in self.modules:
            if module_name.lower().endswith(name.lower()):
                return module_name, base, image_size
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--module", help="module whose base the RVA is relative to")
    ap.add_argument("--rva", help="hex RVA inside that module")
    ap.add_argument("--length", type=int, default=64)
    ap.add_argument("--absolute", help="read this absolute virtual address instead")
    ap.add_argument("--list-modules", action="store_true")
    args = ap.parse_args()

    dump = Dump(args.dump)
    print(f"{args.dump}: {len(dump.ranges):,} memory ranges, {len(dump.modules)} modules")
    if args.list_modules or not (args.rva or args.absolute):
        for name, base, size in dump.modules[:40]:
            print(f"  {base:#018x} {size:>12,}  {name}")
        return 0

    if args.absolute:
        address = int(args.absolute, 16)
    else:
        found = dump.find_module(args.module)
        if not found:
            print(f"module {args.module} not present"); return 1
        name, base, size = found
        address = base + int(args.rva, 16)
        print(f"module {name}: base {base:#x}, size {size:#x}; target {address:#x}")
    data = dump.read_virtual(address, args.length)
    if data is None:
        print(f"address {address:#x} is not covered by the dump"); return 1
    print(data.hex())
    for line in range(0, len(data), 16):
        chunk = data[line:line + 16]
        print(f"  +0x{line:04X}  {chunk.hex(' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
