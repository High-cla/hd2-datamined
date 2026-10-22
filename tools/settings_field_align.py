#!/usr/bin/env python3
"""settings_field_align.py -- map a filediver plaintext dump's field names onto our row offsets.

WHY
    filediver publishes `generated_<table>.json` with **named fields** for a specific HD2 build, and
    we hold the same table sealed in our build.  The JSON gives meaning, our row gives the bytes; an
    alignment turns one into the other.  It is what turns "+28 = 27" into "+28 = cone_angle".

HOW THE ALIGNMENT IS FOUND
    1. PAIRING.  A field that exists in both sides is used as the anchor: every JSON item is matched
       to the row whose value at the anchor offset is equal.  Ties and misses are dropped, so the
       pairing is never guessed.
    2. SCORING.  For every other numeric JSON field and every 4-byte slot, count the rows whose value
       at that slot equals the JSON value.  Report the slot with the best rate.

    Two guards keep the result honest, because both failure modes otherwise produce a confident map:
      * CONSTANT FIELDS  - a JSON field that is 0 for every item matches every all-zero slot.  Fields
        with fewer than 3 distinct values are skipped.
      * CONSTANT SLOTS   - likewise a slot that never varies cannot be identified.  Skipped.
    A float field is compared with a relative tolerance; an integer field with exact equality.  An
    integer field is never allowed to match a near-zero float (0 and 1e-43 must not be "equal").

USAGE
    python tools/settings_field_align.py --sk <recipient.sk> \\
        --table projectile_settings --dump refs/helldiversdata/generated_projectile_settings.json \\
        --json-root ProjectileSettings --anchor name_upper=4

    python tools/settings_field_align.py --sk <recipient.sk> \\
        --table explosion_settings --dump refs/helldiversdata/generated_explosion_settings.json \\
        --json-root ExplosionSettings --anchor particle_effect_path=56 --anchor audio_event=64
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
from collections import defaultdict

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


def dominant(rows: list[bytes]) -> list[bytes]:
    by_width: dict[int, list[bytes]] = defaultdict(list)
    for row in rows:
        by_width[len(row)].append(row)
    return by_width[max(by_width, key=lambda w: len(by_width[w]))] if by_width else rows


def value_at(row: bytes, slot: int, is_float: bool):
    if slot + 4 > len(row):
        return None
    return struct.unpack_from("<f" if is_float else "<I", row, slot)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--table", required=True)
    ap.add_argument("--dump", required=True, help="filediver JSON for this table")
    ap.add_argument("--json-root", required=True, help="top-level key, e.g. ProjectileSettings")
    ap.add_argument("--anchor", action="append", required=True,
                    help="JSON field=our offset, repeatable (e.g. name_upper=4)")
    ap.add_argument("--min-rate", type=float, default=0.95)
    ap.add_argument("--json-out", default="")
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
        try:
            if len(members) == 1 and (members[0]["size64"] or 0) > 8:
                return types.free_runs(members[0]["type_id"], 1)[0]
            return types.free_runs(type_id, 1)[0]
        except Exception:                                        # noqa: BLE001
            return None

    plain = unseal((game / f"generated_{a.table}.dl_bin").read_bytes(), box)
    rows: list[bytes] = []
    for group in groups(plain):
        stride = stride_of(group["type_id"])
        if not stride:
            continue
        p0 = group["payload_at"]
        marker, count = struct.unpack_from("<QQ", plain, p0)
        if marker != DESCRIPTOR or count <= 0 or count * stride > group["payload"]:
            continue
        base = p0 + DESCRIPTOR
        rows.extend(plain[base + i * stride: base + (i + 1) * stride] for i in range(count))
    rows = dominant(rows)

    dump = json.loads(pathlib.Path(a.dump).read_text(encoding="utf-8"))
    root = dump[0][a.json_root] if isinstance(dump, list) else dump[a.json_root]
    items = root["items"]
    print(f"{a.table}: {len(rows)} rows x {len(rows[0])} B      dump: {len(items)} items")

    anchors = []
    for spec in a.anchor:
        field, _, offset = spec.partition("=")
        anchors.append((field.strip(), int(offset)))

    # ---- pairing on the anchor fields ----------------------------------------------------------
    index: dict[tuple, int] = defaultdict(list)
    for i, row in enumerate(rows):
        key = tuple(value_at(row, off, isinstance(items[0].get(f), float))
                    for f, off in anchors)
        index[key].append(i)
    pairs, ambiguous, missing = [], 0, 0
    for item in items:
        key = tuple(item.get(f) for f, _ in anchors)
        key = tuple(v[0] if isinstance(v, list) and v else v for v in key)
        hit = index.get(key, [])
        if len(hit) == 1:
            pairs.append((rows[hit[0]], item))
        elif len(hit) > 1:
            ambiguous += 1
        else:
            missing += 1
    print(f"pairing by {' + '.join(f for f, _ in anchors)}: {len(pairs)} unique, "
          f"{ambiguous} ambiguous, {missing} not present in our build")
    if len(pairs) < 20:
        print("!! too few pairs to align")
        return 1

    # ---- score every numeric field against every slot -------------------------------------------
    numeric = [k for k, v in items[0].items() if isinstance(v, (int, float))
               and not isinstance(v, bool)]
    mapping = []
    for field in numeric:
        values = []
        for _, item in pairs:
            v = item.get(field)
            if isinstance(v, list):
                v = v[0] if v else 0
            values.append(v)
        if len({type(v).__name__ + str(round(v, 6) if isinstance(v, float) else v)
                for v in values}) < 3:
            continue                                   # constant field: cannot be located
        is_float = any(isinstance(v, float) for v in values)
        best = None
        for slot in range(0, len(rows[0]) - 3, 4):
            column = [value_at(row, slot, is_float) for row, _ in pairs]
            if len(set(column)) < 3:
                continue                               # constant slot: cannot be identified
            ok = 0
            for got, want in zip(column, values):
                if got is None:
                    continue
                if is_float:
                    if abs(got - want) <= 1e-3 * max(1.0, abs(want)):
                        ok += 1
                elif got == want:
                    ok += 1
            rate = ok / len(pairs)
            if rate >= a.min_rate and (best is None or rate > best[1]):
                best = (slot, rate)
        if best:
            mapping.append({"field": field, "offset": best[0], "rate": round(best[1], 4),
                            "kind": "f32" if is_float else "u32"})

    mapping.sort(key=lambda m: (m["offset"], m["field"]))
    print(f"\n== field -> offset ({len(mapping)} mapped, rate >= {a.min_rate}) ==")
    print(f"{'offset':>8}  {'kind':<5}{'rate':>7}  field")
    for m in mapping:
        print(f"{'+' + str(m['offset']):>8}  {m['kind']:<5}{m['rate']:>7.3f}  {m['field']}")

    unmapped = [k for k in items[0] if k not in {m["field"] for m in mapping}]
    print(f"\nunmapped fields ({len(unmapped)}): {', '.join(unmapped)}")

    if a.json_out:
        out = pathlib.Path(a.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"table": a.table, "rows": len(rows),
                                   "pairs": len(pairs), "mapping": mapping}, indent=1),
                       encoding="utf-8")
        print(f"json -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
