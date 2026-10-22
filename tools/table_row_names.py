#!/usr/bin/env python3
"""table_row_names.py -- recover per-row display names that are stored INSIDE the table.

HOW THE NAMES ARE STORED (measured 2026-10-22, build 25988413)
    A group payload is

        u64 0x10 | u64 row_count | row_count * stride bytes | readable string blob

    There are TWO different mechanisms, and using the wrong one silently produces wrong names:

    (a) PARALLEL ARRAY - the blob holds exactly one printable string per row, in row order.
        The i-th string is row i's name.  This is only valid when len(strings) == row_count;
        `>=` is NOT good enough, because a blob holding several strings per row still satisfies
        `>=` and then hands out the first N strings, which are not names aligned to rows.

    (b) PER-ROW POINTERS - the row carries its own payload-relative u64 offsets into the blob.
        Used by generated_stratagem_settings.dl_bin, whose blob mixes display names,
        `nui_stratagem_*_name` keys and `_desc` keys (2-4 strings per row), measured as

            +16 -> display name   153/153 rows resolve, 151 distinct
            +24 -> _name key      128/153
            +32 -> _desc key      128/153

        tools/probe_row_name_offsets.py is what establishes this: it tests whether a slot resolves
        to a DIFFERENT string per row, which is what rules out a small integer landing in the blob.

    Each table's output records which mechanism was used, so a reader never has to guess whether
    "one name per row" was actually true.

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

# Tables whose rows carry their own string pointers, keyed by (file, stride): one file can hold
# groups with different strides (status_effect has stride-40 and stride-160 groups, and +8 is a name
# pointer only in the latter).  A value may be a tuple: the first offset that resolves wins.
POINTERS = {
    ("generated_weapon_customization_settings.dl_bin", 88): {"name": 0},
    ("generated_stratagem_settings.dl_bin", 400): {"name": 16, "name_key": 24, "desc_key": 32},
    ("generated_status_effect_settings.dl_bin", 160): {"name": 8},
    ("generated_planet_override_settings.dl_bin", 40): {"name": 0},
    ("generated_language_settings.dl_bin", 208): {"name": (32, 48), "locale": 48, "code": 8},
    ("generated_stratagem_upgrade_settings.dl_bin", 64): {"name": 0},
}


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
        used_pointers = False
        rows = 0
        exact = True
        for group in groups(plain):
            stride = stride_of(group["type_id"])
            if not stride:
                continue
            p0 = group["payload_at"]
            marker, count = struct.unpack_from("<QQ", plain, p0)
            if marker != DESCRIPTOR or count <= 0:
                continue
            rows += count                      # counted even without a pool, so `rows` is the file
            rows_end = DESCRIPTOR + count * stride
            pointer_spec = POINTERS.get((path.name, stride))
            if pointer_spec:
                used_pointers = True
                offsets = pointer_spec["name"]
                for index in range(count):
                    base = p0 + DESCRIPTOR + index * stride
                    text = ""
                    for offset in (offsets if isinstance(offsets, tuple) else (offsets,)):
                        target = struct.unpack_from("<Q", plain, base + offset)[0]
                        if 0 < target < group["payload"]:
                            text = read_cstr(plain, p0 + target)
                            if text:
                                break
                    names.append(text)
                continue
            if rows_end >= group["payload"]:
                exact = False              # rows fill the payload: no pool to read a name from
                continue
            found = strings_in(plain[p0 + rows_end: p0 + group["payload"]])
            if len(found) != count:
                exact = False        # several strings per row, or fewer: positional pairing is off
                continue
            names.extend(found)
        if not rows:
            continue
        method = "pointer" if used_pointers else "positional"
        resolved = sum(1 for n in names if n)
        if len(names) == rows and resolved == rows and (used_pointers or exact):
            entry = {"rows": rows, "named": resolved, "method": method, "names": names}
            if used_pointers:
                entry["pointer_offsets"] = {label: off for (_f, _s), spec in POINTERS.items()
                                            if _f == path.name for label, off in spec.items()}
            report[path.name] = entry
            print(f"{path.name:<48} rows {rows:>6}  named {resolved:>6}  COMPLETE ({method})")
        else:
            partial[path.name] = {"rows": rows, "strings_resolved": resolved,
                                  "method": method, "positional_exact": exact}
            print(f"{path.name:<48} rows {rows:>6}  resolved {resolved:>6}  "
                  f"(not one name per row)")

    if a.json:
        out = pathlib.Path(a.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "build": "25988413",
            "methods": {"positional": "blob holds exactly one string per row, in row order",
                        "pointer": "each row carries its own payload-relative u64 offsets"},
            "complete": report, "partial": partial}, indent=1, ensure_ascii=False),
            encoding="utf-8")
        print(f"json -> {out}  ({out.stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
