#!/usr/bin/env python3
"""table_export.py -- export one `.dl_bin` table as a human-readable, whole-table dump.

WHY
    Reading one field at a time is slow.  This turns a table into a table: every row, every field, the
    row's own name (when the table carries a parallel name array), plus per-field statistics that make
    the "what is this field" question answerable by eye instead of by grep.

WHAT GOES INTO THE OUTPUT
    * one CSV row per record, columns = the element type's members (offset + size in the header)
    * one Markdown file: the field legend, per-field statistics (distinct values, min/max, a few
      examples), and the first rows rendered as a table so the file stands on its own
    * values are printed twice for 4-byte slots - hexadecimal and the f32 reading - because the
      typelib marks primitives as type 0 and does not say which they are

HOW ROWS ARE FOUND (same model as the table dictionary)
    group payload = `u64 0x10 | u64 row_count | row_count * stride | string blob`
    and the blob's i-th printable string is row i's name (tables that carry names at all).

USAGE
    python tools/table_export.py --table weapon_customization_settings --sk <recipient.sk> \\
        --out out/weapon_customization
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import struct
import sys

HEADER = 48
DESCRIPTOR = 16

# Field names and enum values verified against xypwn/filediver's datalibrary/weapon_customization.go
# (rawWeaponCustomizableItem: 88 bytes, offsets match this table exactly) and datalibrary/enum/.
SLOTS = {0: "None", 1: "Underbarrel", 2: "Optics", 3: "PaintScheme", 4: "Muzzle", 5: "Magazine",
         6: "AmmoType", 7: "AmmoTypeAlt", 8: "Internals", 9: "Triggers"}
SORT_GROUPS = {0: "None", 1: "Paint_Default", 2: "Paint_Solid", 3: "Paint_Camo"}
LAYOUTS = {
    "weapon_customization_settings": {
        "stride": 88,
        "fields": {0: "DebugNameOffset", 8: "ID", 12: "NameUpper", 16: "NameCased",
                   20: "Description", 24: "Fluff", 32: "AddPath", 40: "Icon",
                   48: "SlotsOffset", 56: "SlotsCount", 64: "UIWidgetColorsOffset",
                   72: "UIWidgetColorsCount", 80: "SortGroups"},
        "slots_at": (48, 56),          # (offset field, count field) of the slot enum array
        "sort_at": 80,
    },
    # Field names from the typelib's own enum members; +80 = max_uses is corroborated by HD2Runtime
    # 0.26.0 release notes ("StratagemInfo +80 (u32), 0xFFFFFFFF = unlimited").  400 B x 153 rows.
    "stratagem_settings": {
        "stride": 400,
        "fields": {0: "StratagemType", 60: "StratagemCategoryType",
                   64: "StratagemButtonDirection", 80: "max_uses",
                   112: "StratagemOriginType", 116: "StratagemCallInType",
                   120: "StratagemCallInLogic", 124: "StratagemObjectiveDropRequirement",
                   148: "StratagemCooldownType", 184: "StratagemHUDType",
                   196: "StratagemType_196", 200: "StratagemType_200",
                   212: "StratagemBeaconColor", 260: "StratagemInfoFlag",
                   272: "StratagemCustomizationTypeInfo", 372: "UnitCustomizationCollectionType"},
    },
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


def render(blob: bytes) -> str:
    """Hex always; a float reading when the 4-byte slot reads like a sane float."""
    if len(blob) == 4:
        u = struct.unpack("<I", blob)[0]
        f = struct.unpack("<f", blob)[0]
        text = f"{u:#010x}"
        if f == f and abs(f) < 1e6:
            text += f" / {f:.6g}"
        return text
    if len(blob) == 8:
        u, f2 = struct.unpack("<Q", blob)[0], struct.unpack("<ff", blob)
        return f"{u:#018x} / {f2[0]:.6g},{f2[1]:.6g}"
    return "0x" + blob.hex()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True, help="e.g. weapon_customization_settings")
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--sk", required=True)
    ap.add_argument("--out", required=True, help="output basename (creates .csv and .md)")
    ap.add_argument("--preview", type=int, default=15, help="rows shown in the markdown")
    ap.add_argument("--names", default="", help="hash->name list (default: search next to the tool)")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    table_path = game / f"generated_{a.table}.dl_bin"
    if not table_path.is_file():
        print(f"!! no such table: {table_path}")
        return 2
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import typelib                                              # noqa: E402

    names = {}
    here = pathlib.Path(__file__).resolve().parent
    candidates = [pathlib.Path(a.names)] if a.names else [
        here.parent / "refs" / "dl-type-names.txt",
        here.parent / "filediver-dl-type-names.txt",
        pathlib.Path(r"D:\modilediver-dl-type-names.txt"),
    ]
    name_list = next((p for p in candidates if p and p.is_file()), None)
    if name_list is not None:
        for line in name_list.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("//"):
                names[typelib.type_hash(line)] = line
    types = typelib.TypeLib(unseal((game / "dl_library.dl_typelib").read_bytes(), box))

    def type_name(tid: int) -> str:
        return names.get(tid) or f"0x{tid:08X}"

    plain = unseal(table_path.read_bytes(), box)
    layout = LAYOUTS.get(a.table)
    records: list[dict] = []
    element_type = None
    stride = 0
    for group in groups(plain):
        members = types.members(group["type_id"])
        if len(members) == 1 and (members[0]["size64"] or 0) > 8:
            element_type = members[0]["type_id"]
        else:
            element_type = group["type_id"]
        stride = types.free_runs(element_type, 1)[0]
        fields = []
        for m in types.members(element_type):
            subs = []
            if 8 <= m["size64"] <= 64 and m["type_id"]:
                try:
                    inner = types.members(m["type_id"])
                except Exception:                                # noqa: BLE001
                    inner = []
                if inner and len(inner) <= 8:
                    subs = [{"offset": m["offset64"] + sub["offset64"],
                             "size": sub["size64"], "type_id": sub["type_id"]}
                            for sub in inner
                            if sub["offset64"] + sub["size64"] <= m["size64"]]
            # expanded sub-fields replace the parent column, so offsets never appear twice
            fields.extend(subs or [{"offset": m["offset64"], "size": m["size64"],
                                    "type_id": m["type_id"]}])
        p0 = group["payload_at"]
        marker, count = struct.unpack_from("<QQ", plain, p0)
        if marker != DESCRIPTOR or count <= 0:
            continue
        rows_at = p0 + DESCRIPTOR
        blob = plain[rows_at + count * stride: p0 + group["payload"]]
        row_names = strings_in(blob)
        for index in range(count):
            base = rows_at + index * stride
            record = {"row": index,
                      "name": row_names[index] if index < len(row_names) else ""}
            if layout:
                if "slots_at" in layout:
                    slot_off, slot_cnt = struct.unpack_from("<QQ", plain,
                                                            base + layout["slots_at"][0])
                    names_out = []
                    if 0 < slot_cnt <= 8 and 0 < slot_off < group["payload"]:
                        names_out = [SLOTS.get(struct.unpack_from("<I", plain,
                                                                  p0 + slot_off + k * 4)[0], "?")
                                     for k in range(slot_cnt)]
                    record["slots"] = "|".join(names_out)
                if "sort_at" in layout:
                    sort_value = struct.unpack_from("<I", plain, base + layout["sort_at"])[0]
                    record["sort_group"] = SORT_GROUPS.get(sort_value, f"0x{sort_value:08X}")
            for field in fields:
                key = f"+{field['offset']}"
                if field["offset"] + field["size"] <= stride:
                    record[key] = render(plain[base + field["offset"]:
                                                base + field["offset"] + field["size"]])
                else:
                    record[key] = ""
            records.append(record)

    extra = ([c for c in ("slots", "sort_group") if layout and (c == "slots" and "slots_at" in layout
             or c == "sort_group" and "sort_at" in layout)]) if layout else []
    columns = ["row", "name"] + extra + [f"+{f['offset']}" for f in fields]
    out_csv = pathlib.Path(a.out + ".csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    stats = []
    for field in fields:
        key = f"+{field['offset']}"
        values = [r[key] for r in records if r.get(key)]
        distinct = len(set(values))
        label = layout["fields"].get(field["offset"], "") if layout else ""
        stats.append((key, field["size"], (label + " / " if label else "") + type_name(field["type_id"]),
                      len(values), distinct, "; ".join(list(dict.fromkeys(values))[:3])))

    lines = [f"# `generated_{a.table}.dl_bin` — whole-table export", "",
             f"{len(records)} row(s), stride {stride} B, element **{type_name(element_type)}** "
             f"(`0x{element_type:08X}`), {len(fields)} field(s).", "",
             "Values are read from row 0..n; a 4-byte slot prints both readings (`hex / f32`) because",
             "the typelib does not say which one it is.", "",
             "## Fields", "", "| offset | size | type | filled | distinct | examples |",
             "|---:|---:|---|---:|---:|---|"]
    for key, size, tname, filled, distinct, examples in stats:
        lines.append(f"| {key} | {size} | {tname} | {filled} | {distinct} | {examples} |")
    lines += ["", f"## First {min(a.preview, len(records))} rows", "",
              "| row | name | " + " | ".join(f"+{f['offset']}" for f in fields) + " |",
              "|---:|---|" + "---|" * len(fields)]
    for record in records[:a.preview]:
        cells = " | ".join(record.get(f"+{f['offset']}", "") for f in fields)
        lines.append(f"| {record['row']} | {record['name']} | {cells} |")
    out_md = pathlib.Path(a.out + ".md")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{a.table}: {len(records)} row(s), {len(fields)} field(s), stride {stride}")
    print(f"  csv -> {out_csv}  ({out_csv.stat().st_size:,} B)")
    print(f"  md  -> {out_md}  ({out_md.stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
