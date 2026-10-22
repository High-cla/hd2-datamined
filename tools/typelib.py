#!/usr/bin/env python3
"""Parse the HD2 DataLibrary type library (LTLD v4) and answer one question per table:

    "is there an 8-byte aligned, semantically empty word I can use to keep the content hash?"

Why this matters
    A modified ``.dl_bin`` plaintext is rejected unless ``MurmurHash64A(plaintext)`` still
    matches the value baked into the game, so every edit has to be paid for out of padding.
    The type library gives the exact member offsets of every record type, hence the exact
    byte ranges no member covers - that is the only place a correction word may live.

Layout (guide §5.2), all little-endian:
    0x00  LTLD, version, type_count, enum_count, member_count, enum_value_count,
          attribute_count, default_data_bytes, string_bytes          (36 bytes)
    then  type ids (4*nt) | enum ids (4*ne) | type descriptors (36*nt) |
          enum descriptors (32*ne) | member descriptors (72*nm) |
          enum values (16*nv) | attributes (8*na) | default data | string table
    type descriptor  = 9 u32: name_ref, flags, size32, size64, align32, align64, member_count, member_start, comment
    member descriptor= 18 u32: name_ref, ?, ?, type_flags, type_id, size32, size64, align32, align64, offset32, offset64, ...

Usage
    python typelib.py index  <dl_library.dl_typelib> [--json out.json]
    python typelib.py show   <typelib> <type-id-or-name>
    python typelib.py audit  <typelib> <plaintext.dl_bin> [--verbose]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys

from dlbin_seal import parse_ldld

TYPE_DESC = 36
MEMBER_DESC = 72
ENUM_DESC = 32
ENUM_VALUE = 16
ATTRIBUTE = 8


def type_hash(name: str) -> int:
    value = 5381
    for byte in name.encode("utf-8"):
        value = (value * 33 + byte) & 0xFFFFFFFF
    return (value - 5381) & 0xFFFFFFFF


class TypeLib:
    def __init__(self, data: bytes):
        if len(data) < TYPE_DESC:
            raise ValueError("truncated typelib header")
        magic, version, nt, ne, nm, nv, na, nd, ns = struct.unpack_from("<4s8I", data)
        if magic != b"LTLD" or version != 4:
            raise ValueError(f"not an LTLD v4 typelib (magic {magic!r}, version {version})")
        self.version, self.nt, self.ne, self.nm, self.nv, self.na, self.nd, self.ns = \
            version, nt, ne, nm, nv, na, nd, ns
        type_desc = TYPE_DESC + 4 * (nt + ne)
        enum_desc = type_desc + TYPE_DESC * nt
        member_desc = enum_desc + ENUM_DESC * ne
        strings_at = member_desc + MEMBER_DESC * nm + ENUM_VALUE * nv + ATTRIBUTE * na + nd
        if strings_at + ns != len(data):
            raise ValueError(f"typelib sections do not fit the input "
                             f"({strings_at}+{ns} != {len(data)})")
        self.data = data
        self.strings = data[strings_at:]
        self._type_desc = type_desc
        self._member_desc = member_desc
        self._ids = [struct.unpack_from("<I", data, TYPE_DESC + 4 * i)[0] for i in range(nt)]
        self._index = {tid: i for i, tid in enumerate(self._ids)}
        self._names: dict[int, str | None] = {}

    def name(self, ref: int) -> str | None:
        if ref == 0xFFFFFFFF or ref >= len(self.strings):
            return None
        end = self.strings.find(b"\0", ref)
        if end < 0:
            return None
        return self.strings[ref:end].decode("utf-8", "replace")

    def type_id_of(self, needle: str) -> int:
        needle = needle.strip()
        if needle.lower().startswith("0x"):
            return int(needle, 16)
        wanted = type_hash(needle)
        if wanted in self._index:
            return wanted
        for tid in self._ids:
            if self.name(self.desc(tid)[0]) == needle:
                return tid
        raise ValueError(f"no type named {needle!r} (hash 0x{wanted:08X})")

    def desc(self, tid: int) -> tuple:
        return struct.unpack_from("<9I", self.data, self._type_desc + TYPE_DESC * self._index[tid])

    def members(self, tid: int) -> list[dict]:
        d = self.desc(tid)
        count, start = d[6], d[7]
        out = []
        for j in range(start, start + count):
            m = struct.unpack_from("<18I", self.data, self._member_desc + MEMBER_DESC * j)
            out.append({"name": self.name(m[0]), "name_ref": m[0], "type_flags": m[3],
                        "type_id": m[4], "size32": m[5], "size64": m[6],
                        "align32": m[7], "align64": m[8],
                        "offset32": m[9], "offset64": m[10]})
        return out

    def free_runs(self, tid: int, wide: int = 1) -> tuple[int, list[tuple[int, int]]]:
        """(record_size, [(start, end)]) - byte ranges inside the root struct no member covers."""
        d = self.desc(tid)
        size = d[3] if wide else d[2]
        covered = bytearray(size)
        for m in self.members(tid):
            off = m["offset64"] if wide else m["offset32"]
            length = m["size64"] if wide else m["size32"]
            if off >= size or length == 0:
                continue
            end = min(off + length, size)
            covered[off:end] = b"\x01" * (end - off)
        runs, start = [], None
        for i, flag in enumerate(covered):
            if not flag and start is None:
                start = i
            elif flag and start is not None:
                runs.append((start, i))
                start = None
        if start is not None:
            runs.append((start, size))
        return size, runs


def aligned_words(runs: list[tuple[int, int]], base: int = 0) -> list[int]:
    """Absolute offsets of 8-byte words entirely inside the free runs."""
    out = []
    for start, end in runs:
        first = ((base + start) + 7) // 8 * 8
        position = first
        while position + 8 <= base + end:
            out.append(position)
            position += 8
    return out


def cmd_index(args) -> int:
    data = open(args.typelib, "rb").read()
    lib = TypeLib(data)
    print(f"{args.typelib}: LTLD v{lib.version}  types={lib.nt} enums={lib.ne} "
          f"members={lib.nm} enum_values={lib.nv} attributes={lib.na} "
          f"string_bytes={lib.ns}")
    named = 0
    rows = []
    for tid in lib._ids:
        d = lib.desc(tid)
        name = lib.name(d[0])
        named += 1 if name else 0
        rows.append({"type_id": f"0x{tid:08X}", "name": name, "size32": d[2], "size64": d[3],
                     "members": d[6], "member_start": d[7]})
    print(f"  named types: {named}/{lib.nt}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump({"header": {"version": lib.version, "type_count": lib.nt,
                                  "enum_count": lib.ne, "member_count": lib.nm},
                       "types": rows}, handle, indent=1, ensure_ascii=False)
        print(f"  wrote {args.json}")
    return 0


def cmd_show(args) -> int:
    lib = TypeLib(open(args.typelib, "rb").read())
    tid = lib.type_id_of(args.type)
    d = lib.desc(tid)
    print(f"type 0x{tid:08X}  name={lib.name(d[0])!r}  size32={d[2]} size64={d[3]} "
          f"align32={d[4]} align64={d[5]} members={d[6]}")
    print("  off64 size64 align  type_id      name")
    for m in lib.members(tid):
        print(f"  {m['offset64']:>5} {m['size64']:>6} {m['align64']:>5}  0x{m['type_id']:08X}  "
              f"{m['name']}")
    size, runs = lib.free_runs(tid)
    print(f"  root struct {size} B; uncovered runs: "
          + (", ".join(f"[{a},{b})" for a, b in runs) if runs else "none"))
    return 0


def cmd_audit(args) -> int:
    lib = TypeLib(open(args.typelib, "rb").read())
    data = open(args.dlbin, "rb").read()
    groups = parse_ldld(data)
    print(f"{args.dlbin}: {len(data):,} B, {len(groups)} group(s)")
    total_words = 0
    for g in groups:
        tid = g["type_id"]
        known = tid in lib._index
        name = lib.name(lib.desc(tid)[0]) if known else None
        wide = g["wide"]
        # (a) the group header's 8-byte word at +16: 1 byte Is64Bit (must stay 1 after the
        #     solve) + 7 reserved bytes.  Only usable when it is 8-byte aligned and not the
        #     first group (that one carries the free knob this solve needs).
        header_word = g["header_offset"] + 16
        header_words = [header_word] if header_word % 8 == 0 and header_word > 28 else []
        # (b) record-level padding: words entirely inside bytes no member covers
        if known:
            size, runs = lib.free_runs(tid, wide)
            payload_free = [(g["payload_offset"] + a, g["payload_offset"] + b) for a, b in runs]
        else:
            size, runs, payload_free = 0, [], []
        words = header_words + aligned_words(payload_free)
        total_words += len(words)
        print(f"  group {g['index']}: type 0x{tid:08X} {'(' + name + ')' if name else '(unknown type)'} "
              f"wide={wide} payload={g['payload_size']:,}")
        if known:
            print(f"      root {size} B, free runs {[(a, b) for a, b in runs]}")
        if header_words:
            print(f"      header word 0x{header_words[0]:X} (low byte must stay 1; needs a free knob earlier)")
        print(f"      usable 8-byte correction words: {len(words)}"
              + (f"  e.g. 0x{words[0]:X}" if words else "  -> NONE"))
        if args.verbose and words:
            print("      all:", ", ".join(f"0x{w:X}" for w in words[:20]))
    print(f"  TOTAL usable correction words: {total_words}"
          + ("  => hash-preserving edit possible" if total_words else
             "  => no padding for a hash correction: this table cannot be edited"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("index")
    p.add_argument("typelib")
    p.add_argument("--json")
    p.set_defaults(func=cmd_index)
    p = sub.add_parser("show")
    p.add_argument("typelib")
    p.add_argument("type")
    p.set_defaults(func=cmd_show)
    p = sub.add_parser("audit")
    p.add_argument("typelib")
    p.add_argument("dlbin")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_audit)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
