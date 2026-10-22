#!/usr/bin/env python3
"""probe_row_name_offsets.py -- do rows carry their own pointers into the string pool?

BACKGROUND
    The parallel-array rule ("the blob's i-th string is row i's name") only holds for tables whose
    blob has exactly one string per row.  stratagem_settings breaks it: the pool mixes display names
    ("BACKPACK. SUPPLY BACKPACK"), `nui_stratagem_*_name` keys and `_desc` keys - 153 rows but ~3x
    that many strings.  So the pairing is not positional.  If each row carries its own offsets into
    the pool, the pairing is explicit and the problem is solved.

    The file also turns out to hold one group per *family*, not one group of 153 rows: 12 groups,
    13+2+11+9+2+36+13+7+36+9+2+13 = 153.  Each group has its own pool, so a pointer is only valid
    against the pool of the group the row belongs to.

THE DISCRIMINATOR THAT MATTERS
    A slot whose value is 0 always "resolves" - to the pool's first string - for every row.  So the
    test is not "does it resolve" but "does it resolve to a DIFFERENT string per row":
        hits     = rows where the slot resolves to a printable NUL-terminated string
        distinct = how many different strings those were
    A real pointer gives distinct ~ hits.  A small integer gives a handful of repeated strings.

USAGE
    python tools/probe_row_name_offsets.py --table stratagem_settings --stride 400 \\
        --sk refs/dlbin/keys/recipient.sk
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

HEADER = 48
DESCRIPTOR = 16


def unseal(blob: bytes, box) -> bytes:
    return box.decrypt(blob) if len(blob) > HEADER else blob


def groups(plain: bytes) -> list[dict]:
    out, start = [], 0
    while True:
        at = plain.find(b"LDLD", start)
        if at < 0:
            return out
        start = at + 4
        if at + 24 > len(plain):
            continue
        version, type_id, payload, wide = struct.unpack_from("<IIII", plain, at + 4)
        if version in (1, 2) and 0 < payload and at + 24 + payload <= len(plain):
            out.append({"at": at, "type_id": type_id, "version": version,
                        "payload": payload, "payload_at": at + 24})


def read_cstr(buf: bytes, at: int, limit: int = 250) -> str | None:
    if at < 0 or at >= len(buf):
        return None
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end < 0 or end == at:
        return None
    raw = buf[at:end]
    if any(b < 32 or b > 126 for b in raw):
        return None
    return raw.decode("ascii")


def kind(s: str) -> str:
    """Classify a resolved string.  Order matters: keys before display shapes."""
    if s.startswith("nui_"):
        return "descKey" if s.endswith("_desc") else "nameKey"
    if s.endswith("_desc"):
        return "descKey"
    if "." in s and (s.isupper() or all(ord(c) < 128 for c in s)):
        return "display"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--stride", type=int, required=True)
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--rows", type=int, default=4, help="rows echoed per group")
    ap.add_argument("--group", type=int, default=-1, help="only this group index")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    path = game / f"generated_{a.table}.dl_bin"
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))
    plain = unseal(path.read_bytes(), box)
    print(f"table   {path.name}")
    print(f"plain   {len(plain)} bytes")

    found = groups(plain)
    usable = []
    print(f"\n== {len(found)} group(s) ==")
    for i, g in enumerate(found):
        p0 = g["payload_at"]
        marker, count = struct.unpack_from("<QQ", plain, p0)
        ok = marker == DESCRIPTOR and count > 0 and count * a.stride <= g["payload"]
        blob_len = g["payload"] - DESCRIPTOR - count * a.stride if ok else -1
        print(f"  [{i}] at {g['at']:#08x} type=0x{g['type_id']:08X} v{g['version']} "
              f"payload={g['payload']:<7} rows={count if ok else '?':<5} "
              f"pool={blob_len}{'' if ok else '   (stride mismatch)'}")
        if ok:
            usable.append((i, g, count))
    total = sum(c for _, _, c in usable)
    print(f"  total rows = {total}")

    if a.group >= 0:
        usable = [u for u in usable if u[0] == a.group]

    # ---- aggregate the pointer test over every group -------------------------------------------
    agg: dict[int, dict] = {}
    for i, g, count in usable:
        p0 = g["payload_at"]
        rows_at = p0 + DESCRIPTOR
        pool = plain[p0:]
        for slot in range(0, a.stride - 7, 8):
            rec = agg.setdefault(slot, {"hits": 0, "rows": 0, "seen": set(), "kinds": {}})
            for index in range(count):
                off = struct.unpack_from("<Q", plain, rows_at + index * a.stride + slot)[0]
                rec["rows"] += 1
                s = read_cstr(pool, off) if off else None
                if s:
                    rec["hits"] += 1
                    rec["seen"].add(s)
                    k = kind(s)
                    rec["kinds"][k] = rec["kinds"].get(k, 0) + 1

    print("\n== u64 slots as payload-relative pointers, aggregated over all groups ==")
    print(f"{'slot':>6} {'hits':>6}{'/rows':>7} {'distinct':>9}  kinds")
    for slot in sorted(agg):
        r = agg[slot]
        if not r["hits"]:
            continue
        flag = "  <== pointer" if r["hits"] >= r["rows"] * 0.9 and len(r["seen"]) >= r["hits"] * 0.9 else ""
        print(f"{'+' + str(slot):>6} {r['hits']:>6}{'/' + str(r['rows']):>7} "
              f"{len(r['seen']):>9}  {r['kinds']}{flag}")

    ptrs = [s for s, r in agg.items()
            if r["hits"] >= r["rows"] * 0.9 and len(r["seen"]) >= r["hits"] * 0.9]
    if not ptrs:
        print("\n== VERDICT: no slot behaves like a per-row string pointer ==")
        return 1
    print(f"\n== VERDICT: pointer slots = {['+' + str(s) for s in ptrs]} ==")

    if a.rows:
        for i, g, count in usable:
            p0 = g["payload_at"]
            rows_at = p0 + DESCRIPTOR
            pool = plain[p0:]
            print(f"\n== group[{i}] ({count} rows) first {min(a.rows, count)} ==")
            for index in range(min(a.rows, count)):
                base = rows_at + index * a.stride
                parts = []
                for s in ptrs:
                    off = struct.unpack_from("<Q", plain, base + s)[0]
                    txt = read_cstr(pool, off) if off else None
                    parts.append(f"+{s}={txt!r}")
                print(f"  row {index:<3} " + "  ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
