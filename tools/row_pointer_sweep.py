#!/usr/bin/env python3
"""row_pointer_sweep.py -- which tables carry per-row string pointers?

WHY
    Two mechanisms can give a row its name:
        positional  the trailing string pool is a parallel array (i-th string = row i), valid only
                    when the pool holds exactly one string per row
        pointer     the row itself holds payload-relative u64 offsets into the pool
    The pointer is the stronger one: it stays correct when the pool holds several strings per row
    (stratagem_settings: display name + `_name` key + `_desc` key) or when binary is interleaved
    with the strings (weapon_customization's paint-scheme group).  This tool finds it everywhere.

THE DISCRIMINATOR
    A slot whose value is 0 resolves for every row (to the pool's first string).  The test is
    therefore "does the slot resolve to a DIFFERENT string per row":
        hits     rows where the slot resolves to a printable NUL-terminated string
        distinct how many different strings those were
    hits ~ rows and distinct ~ hits  =>  pointer.  A small integer gives few, repeated strings.

CROSS-CHECK
    Where a group's pool happens to hold exactly one string per row, the positional and pointer
    readings can be compared.  They agree whenever both mechanisms are applicable (measured:
    weapon_customization 240/240), which is what validates the pointer reading.

USAGE
    python tools/row_pointer_sweep.py --sk <recipient.sk>
    python tools/row_pointer_sweep.py --sk <recipient.sk> --table weapon_customization_settings
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys
from collections import Counter, defaultdict

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
            out.append({"at": at, "type_id": type_id, "payload": payload, "payload_at": at + 24})


def strings_in(blob: bytes) -> list[str]:
    out, current = [], bytearray()
    for byte in blob:
        if byte == 0:
            if len(current) >= 3:
                out.append(current.decode("ascii"))
            current = bytearray()
        elif 32 <= byte < 127:
            current.append(byte)
        else:
            current = bytearray()
    if len(current) >= 3:
        out.append(current.decode("ascii"))
    return out


def read_cstr(buf: bytes, at: int, limit: int = 250) -> str:
    if at <= 0 or at >= len(buf):
        return ""
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end <= at:
        return ""
    raw = buf[at:end]
    if any(byte < 32 or byte > 126 for byte in raw):
        return ""
    return raw.decode("ascii")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--table", default="", help="one table name (default: every .dl_bin)")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import typelib                                              # noqa: E402

    types = typelib.TypeLib(unseal((game / "dl_library.dl_typelib").read_bytes(), box))

    def stride_of(type_id: int) -> int | None:
        try:
            members = types.members(type_id)
        except Exception:                                        # noqa: BLE001
            return None
        if len(members) == 1 and (members[0]["size64"] or 0) > 8:
            try:
                return types.free_runs(members[0]["type_id"], 1)[0]
            except Exception:                                    # noqa: BLE001
                return None
        try:
            return types.free_runs(type_id, 1)[0]
        except Exception:                                        # noqa: BLE001
            return None

    pattern = f"generated_{a.table}.dl_bin" if a.table else "*.dl_bin"
    found_any = False
    for path in sorted(game.glob(pattern)):
        plain = unseal(path.read_bytes(), box)
        rows_by_stride: dict[int, list[dict]] = defaultdict(list)
        for group in groups(plain):
            stride = stride_of(group["type_id"])
            if not stride:
                continue
            p0 = group["payload_at"]
            marker, count = struct.unpack_from("<QQ", plain, p0)
            if marker != DESCRIPTOR or count <= 0 or count * stride > group["payload"]:
                continue
            rows_by_stride[stride].append({"p0": p0, "count": count, "payload": group["payload"]})
        if not rows_by_stride:
            continue
        report = []
        for stride, gs in rows_by_stride.items():
            agg: dict[int, dict] = {}
            for g in gs:
                p0, count = g["p0"], g["count"]
                pool = plain[p0:]
                for slot in range(0, stride - 7, 8):
                    rec = agg.setdefault(slot, {"hits": 0, "rows": 0, "seen": set()})
                    for index in range(count):
                        off = struct.unpack_from("<Q", plain, p0 + DESCRIPTOR + index * stride
                                                 + slot)[0]
                        rec["rows"] += 1
                        text = read_cstr(pool, off) if off else ""
                        if text:
                            rec["hits"] += 1
                            rec["seen"].add(text)
            for slot in sorted(agg):
                rec = agg[slot]
                if rec["hits"] >= rec["rows"] * 0.9 and len(rec["seen"]) >= rec["hits"] * 0.9:
                    report.append((stride, slot, rec["hits"], rec["rows"], len(rec["seen"])))
        if not report:
            continue
        found_any = True
        print(f"{path.name:<48} stride {report[0][0]:>3}")
        for stride, slot, hits, total, distinct in report:
            print(f"    +{slot:<4} pointer  {hits}/{total} rows, {distinct} distinct")

        # cross-check against the positional rule on groups where it is applicable
        agree = differ = 0
        for stride, gs in rows_by_stride.items():
            for g in gs:
                p0, count = g["p0"], g["count"]
                pool = plain[p0:]
                pos = strings_in(plain[p0 + DESCRIPTOR + count * stride: p0 + g["payload"]])
                if len(pos) != count:
                    continue
                for index in range(count):
                    off = struct.unpack_from("<Q", plain,
                                             p0 + DESCRIPTOR + index * stride + report[0][1])[0]
                    ptr = read_cstr(pool, off) if off else ""
                    if ptr == pos[index]:
                        agree += 1
                    else:
                        differ += 1
        if agree or differ:
            print(f"    cross-check vs positional (only 1:1 groups): agree {agree}, differ {differ}")
    if not found_any:
        print("no per-row string pointers found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
