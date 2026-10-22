#!/usr/bin/env python3
"""table_row_names.py -- recover per-row display names that are stored INSIDE the table.

HOW THE NAMES ARE STORED (measured 2026-10-22, build 25988413)
    A group payload is

        u64 0x10 | u64 row_count | row_count * stride bytes | readable string blob

    The blob is NOT addressed by offsets from the rows (an earlier attempt assumed that and produced
    truncated names: the row's leading u64 lands *inside* some string, at a varying delta, which is a
    coincidence).  For the tables below the blob is a **parallel array**: the i-th printable string
    belongs to row i, in row order.

    Fully covered (every row has a name):
        weapon_customization_settings   252 rows
        stratagem_settings              153 rows
        status_effect_settings           73 rows
        planet_override_settings         44 rows
        language_settings                15 rows
        stratagem_upgrade_settings        1 row

    Tables whose blob holds fewer strings than rows (credits, stamp, explosion, unit_effect,
    planet_types, animation_event_trigger, candidate_descs) are reported but NOT mapped: their blob
    carries something other than one name per row.

READ-ONLY
    Decrypts the sealed table with the caller's key and writes one JSON.  Never writes to the game.

USAGE
    python tools/table_row_names.py --sk <recipient.sk> --game "<...>/Helldivers 2" \\
        --json refs/table-row-names.json
"""
from __future__ import annotations

import argparse
import json
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
            out.append({"at": at, "type_id": type_id, "payload": payload, "payload_at": at + 24})


def strings_in(blob: bytes) -> list[str]:
    """Printable, NUL-delimited runs of at least 3 characters, in order."""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--sk", required=True, help="recipient.sk (32 B) - not shipped with this repo")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    if not game.is_dir():
        print(f"!! not a game data dir: {game}")
        return 2
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

    report, partial = {}, {}
    for path in sorted(game.glob("*.dl_bin")):
        plain = unseal(path.read_bytes(), box)
        names: list[str] = []
        rows = 0
        for group in groups(plain):
            stride = stride_of(group["type_id"])
            if not stride:
                continue
            p0 = group["payload_at"]
            marker, count = struct.unpack_from("<QQ", plain, p0)
            if marker != DESCRIPTOR or count <= 0:
                continue
            rows_end = DESCRIPTOR + count * stride
            if rows_end >= group["payload"]:
                continue
            blob = plain[p0 + rows_end: p0 + group["payload"]]
            found = strings_in(blob)
            rows += count
            if len(found) >= count:
                names.extend(found[:count])
        if not rows:
            continue
        if len(names) >= rows:
            report[path.name] = {"rows": rows, "named": len(names), "names": names}
            print(f"{path.name:<48} rows {rows:>6}  named {len(names):>6}  COMPLETE")
        else:
            partial[path.name] = {"rows": rows, "strings_in_blob": len(names)}
            print(f"{path.name:<48} rows {rows:>6}  strings {len(names):>6}  (not one name per row)")

    if a.json:
        out = pathlib.Path(a.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"build": "25988413", "complete": report, "partial": partial},
                                  indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"json -> {out}  ({out.stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
