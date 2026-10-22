#!/usr/bin/env python3
"""table_xref_scan.py -- which slot in one table refers to rows of another table?

WHY
    `stratagem_settings` rows do not carry their projectiles / explosions inline: the catalog says a
    stratagem owns a tree of attack roles ("delivery_1_projectile", "..._impact", "_shrapnel", ...)
    whose kinds are ProjectileSettings / ExplosionSettings / DamageInfo / StatusEffectSettings.  The
    numbers that link a stratagem row to those rows have to live somewhere in the 400 bytes, and the
    same question applies to every other pair of tables.  This tool answers it empirically.

HOW A REFERENCE IS RECOGNISED
    Same discriminator as the row-name pointer work: a real reference must hit many rows and land on
    *different* target rows, because a per-row value that happens to equal some target id would hit
    few rows and repeat.  So for a candidate (source slot, target table):

        hits     source rows whose value at that slot exists in the target's id column
        distinct how many different target rows those hits land on

    source slot -> target id is a reference candidate when hits is a large fraction of rows and
    distinct is comparable to hits.

    Two guards keep the output honest:
      * the target id column must itself be unique per row (otherwise "hitting" it means nothing);
      * a slot filled with a constant, or with a value that only ever equals one target, is skipped.

USAGE
    python tools/table_xref_scan.py --sk <recipient.sk> --source stratagem_settings
    python tools/table_xref_scan.py --sk <recipient.sk> --source stratagem_settings \\
        --targets projectile_settings,explosion_settings --min-hits 8
"""
from __future__ import annotations

import argparse
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


def rows_of(plain: bytes, stride_of) -> list[bytes]:
    """Every row of every group whose length is implied by the group's element stride."""
    out = []
    for group in groups(plain):
        stride = stride_of(group["type_id"])
        if not stride:
            continue
        p0 = group["payload_at"]
        marker, count = struct.unpack_from("<QQ", plain, p0)
        if marker != DESCRIPTOR or count <= 0 or count * stride > group["payload"]:
            continue
        base = p0 + DESCRIPTOR
        out.extend(plain[base + i * stride: base + (i + 1) * stride] for i in range(count))
    return out


def dominant(rows: list[bytes]) -> list[bytes]:
    """Keep only the most common row width: one file can hold groups with different strides
    (status_effect_settings has 40 B and 160 B rows), and mixing them breaks slot addressing."""
    by_width: dict[int, list[bytes]] = defaultdict(list)
    for row in rows:
        by_width[len(row)].append(row)
    if not by_width:
        return rows
    return by_width[max(by_width, key=lambda w: len(by_width[w]))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--source", default="stratagem_settings")
    ap.add_argument("--targets", default="", help="comma list (default: every other table)")
    ap.add_argument("--min-hits", type=int, default=8, help="minimum source rows that must hit")
    ap.add_argument("--max-targets", type=int, default=0, help="only keep targets with <= N rows")
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

    def load(name: str) -> list[bytes] | None:
        path = game / f"generated_{name}.dl_bin"
        if not path.is_file():
            return None
        return rows_of(unseal(path.read_bytes(), box), stride_of)

    source_rows = dominant(load(a.source) or [])
    if not source_rows:
        print(f"!! no rows in source table {a.source}")
        return 2
    source_len = len(source_rows[0])
    print(f"source {a.source}: {len(source_rows)} rows x {source_len} B")

    if a.targets:
        targets = [t.strip() for t in a.targets.split(",") if t.strip()]
    else:
        targets = sorted(p.stem.replace("generated_", "") for p in game.glob("generated_*.dl_bin")
                         if p.stem != f"generated_{a.source}")

    # ---- for each target: pick the 4-byte slot that is unique per row --------------------------
    id_columns: dict[str, tuple[int, dict[int, int]]] = {}
    for name in targets:
        rows = dominant(load(name) or [])
        if not rows or len(rows) < 3:
            continue
        if a.max_targets and len(rows) > a.max_targets:
            continue
        width = len(rows[0])
        best = None
        for slot in range(0, width - 3, 4):
            values = [struct.unpack_from("<I", r, slot)[0] for r in rows]
            if len(set(values)) != len(values) or 0 in values:
                continue                      # not an id column
            best = (slot, {v: i for i, v in enumerate(values)})
            break                             # the first id-like column is the canonical one
        if best:
            id_columns[name] = best

    print(f"\ntargets with a usable id column: {len(id_columns)}")
    sample = ", ".join(f"{n}@+{s}" for n, (s, _) in list(id_columns.items())[:14])
    print(f"  {sample}")

    # ---- score every source slot against every target id set -----------------------------------
    print(f"\n== reference candidates (source slot -> target rows), min hits {a.min_hits} ==")
    print(f"{'slot':>6}  {'target':<34} {'hits':>6}{'/rows':>7} {'distinct':>9}")
    found = 0
    for slot in range(0, source_len - 3, 4):
        values = [struct.unpack_from("<I", r, slot)[0] for r in source_rows]
        if len(set(values)) <= 1:
            continue
        for name, (_id_slot, index) in id_columns.items():
            hit_targets = [index[v] for v in values if v in index]
            if len(hit_targets) < a.min_hits:
                continue
            distinct = len(set(hit_targets))
            if distinct < max(3, len(hit_targets) // 2):
                continue                      # repeats: coincidence, not a per-row reference
            print(f"{'+' + str(slot):>6}  {name:<34} {len(hit_targets):>6}"
                  f"{'/' + str(len(source_rows)):>7} {distinct:>9}")
            found += 1
    if not found:
        print("  none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
