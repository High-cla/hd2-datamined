#!/usr/bin/env python3
"""stratagem_field_align.py -- locate a stratagem_settings field by its wiki-decoded value.

WHY
    `Module:Decodedata-Attacks/stratagems data.json` is a decoded view of the same table: it is
    keyed by the stratagem's upper-case display name (exactly the string our `+16` pointer yields)
    and lists `cooldown`, `uses`, `num_bombs`, `num_salvos`, `area_size`, `fire_height`, ...
    So for the stratagems present in both, a field's offset can be read off by matching values
    instead of guessing what the typelib's anonymous u32 at `+60` might be.

METHOD
    Rows are paired with wiki entries by normalised display name.  For each numeric wiki field and
    each 4-byte slot, the tool counts pairs where our value equals the wiki value -- as an unsigned
    int and as an f32, because the typelib does not say which a slot is.  A field only counts if it
    takes at least 3 distinct values across the paired rows (a constant field matches every constant
    slot) and the slot itself varies too.

LIMITATION
    Only the stratagems whose internal display names match the wiki keys can be paired -- currently
    14, all orbital/eagle.  A field that happens to be constant over just those 14 cannot be located
    even if it varies elsewhere in the table; the tool says so instead of guessing.

USAGE
    python tools/stratagem_field_align.py --sk <recipient.sk>
    python tools/stratagem_field_align.py --sk <recipient.sk> --field fire_height --constant-scan
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys

HEADER = 48
DESCRIPTOR = 16
STRIDE = 400
NAME_PTR = 16


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


def read_cstr(buf: bytes, at: int, limit: int = 250) -> str:
    if at <= 0 or at >= len(buf):
        return ""
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end <= at:
        return ""
    raw = buf[at:end]
    return "" if any(b < 32 or b > 126 for b in raw) else raw.decode("ascii")


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--wiki",
                    default="refs/wiki/modules/Decodedata-Attacks__stratagems_data.json.raw")
    ap.add_argument("--field", default="", help="only this wiki field")
    ap.add_argument("--constant-scan", action="store_true",
                    help="also try to locate a field that is constant across the paired rows")
    ap.add_argument("--min-rate", type=float, default=0.99)
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))
    plain = unseal((game / "generated_stratagem_settings.dl_bin").read_bytes(), box)

    rows: list[tuple[str, bytes]] = []
    for group in groups(plain):
        marker, count = struct.unpack_from("<QQ", plain, group["payload_at"])
        if marker != DESCRIPTOR or count <= 0 or count * STRIDE > group["payload"]:
            continue
        base, pool = group["payload_at"] + DESCRIPTOR, plain[group["payload_at"]:]
        for index in range(count):
            at = base + index * STRIDE
            name = read_cstr(pool, struct.unpack_from("<Q", plain, at + NAME_PTR)[0])
            rows.append((name, plain[at:at + STRIDE]))

    wiki = json.loads(pathlib.Path(a.wiki).read_text(encoding="utf-8"))["stratagems"]
    by_name = {norm(k): v for k, v in wiki.items()}
    pairs = [(raw, by_name[norm(display.replace(".", " "))]) for display, raw in rows
             if norm(display.replace(".", " ")) in by_name]
    print(f"wiki entries {len(wiki)}, our rows {len(rows)}, paired {len(pairs)}")
    if len(pairs) < 3:
        print("!! too few pairs")
        return 1

    # union over every pair: an eagle entry has no num_bombs/area_size, an orbital entry does
    numeric: list[str] = []
    for _, entry in pairs:
        for key, value in entry.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool)                     and key not in numeric:
                numeric.append(key)
    print(f"\n{'field':<14}{'present':>8}{'distinct':>9}  values over the paired rows")
    for field in numeric:
        values = [entry.get(field) for _, entry in pairs]
        distinct = len({v for v in values})
        present = [v for v in values if v is not None]
        distinct = len(set(present))
        shown = ", ".join(str(v) for v in values[:10])
        print(f"{field:<14}{len(present):>8}{distinct:>9}  {shown}"
              f"{' ...' if len(values) > 10 else ''}")

    print(f"\n== field -> offset (rate >= {a.min_rate}) ==")
    results = []
    for field in numeric:
        if a.field and field != a.field:
            continue
        values = [entry.get(field) for _, entry in pairs]
        present = [v for v in values if v is not None]
        distinct = len(set(present))
        is_float_hint = any(isinstance(v, float) for v in present)
        if distinct < 3 and not (a.constant_scan and field == a.field):
            continue
        best = None
        for slot in range(0, STRIDE - 3, 4):
            column_u = [struct.unpack_from("<I", raw, slot)[0] for raw, _ in pairs]
            column_f = [struct.unpack_from("<f", raw, slot)[0] for raw, _ in pairs]
            if len(set(column_u)) < 2:
                continue
            for kind, column in (("u32", column_u), ("f32", column_f)):
                ok = 0
                comparable = 0
                for got, want in zip(column, values):
                    if want is None:
                        continue
                    comparable += 1
                    if kind == "u32":
                        if got == want:
                            ok += 1
                    elif is_float_hint or isinstance(want, float):
                        if abs(got - want) <= 1e-3 * max(1.0, abs(want)):
                            ok += 1
                    elif abs(want) < 1e7 and abs(got - want) <= 1e-6 * max(1.0, abs(want)):
                        ok += 1
                if not comparable:
                    continue
                rate = ok / comparable
                if rate >= a.min_rate and (best is None or rate > best[1]):
                    best = (slot, rate, kind)
        if best:
            results.append((field, best[0], best[1], best[2], distinct))
    for field, slot, rate, kind, distinct in sorted(results, key=lambda r: r[1]):
        print(f"  +{slot:<4} {field:<14}{kind:<4}rate={rate:.2f}  distinct={distinct}")

    unmapped = [f for f in numeric if f not in {r[0] for r in results} and not a.field]
    if unmapped:
        print(f"\nnot located ({len(unmapped)}): {', '.join(unmapped)}")
        print("  (either constant over the 14 paired rows, or stored in a form none of the "
              "encodings covers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
