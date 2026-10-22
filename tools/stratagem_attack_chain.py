#!/usr/bin/env python3
"""stratagem_attack_chain.py -- walk stratagem -> projectile -> explosion for one stratagem.

THE CHAIN (and which source each hop comes from)

    stratagem_settings row                      our decrypted table
      +16 pointer -> display name               our table
      +0          -> StratagemType enum value   our table
    StratagemType value -> StratagemType NAME   HD2Runtime `uiIcon.nativeType`
                                                == wiki `ref`  (38/42 agree, the other 4 are
                                                naming variants of the same object)
    StratagemType name -> item resource         engine/asset side, NOT in the 55 settings tables
      -> its weapon/backpack component's `projectile_type` name        wiki stratagemdata.json
    projectile_type name -> ProjectileType enum -> projectile row      filediver dump (name_upper)
                                                -> our projectile_settings row at +4
      +144 / +156 -> explosion row `+0`         our table
    explosion row +28 = cone_angle, +16/+20 radii                      our table

    So the stratagem table has NO foreign key to the projectile table: the join goes through the
    StratagemType name into the asset side and comes back via the projectile's own enum name.
    That is why scanning stratagem slots against projectile row ids finds nothing.

WHY IT IS PRESENTED AS A TOOL
    The interesting property is that every hop except "item resource" is checkable against local
    data, so a chain can be printed with its evidence instead of asserted.

USAGE
    python tools/stratagem_attack_chain.py --sk <recipient.sk> --all
    python tools/stratagem_attack_chain.py --sk <recipient.sk> --stratagem "Orbital Precision Strike"
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys
import zipfile

HEADER = 48
DESCRIPTOR = 16
STRATAGEM_STRIDE = 400

GAME_DEFAULT = r"D:\SteamLibrary\steamapps\common\Helldivers 2"


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
    by_width: dict[int, list[bytes]] = {}
    for row in rows:
        by_width.setdefault(len(row), []).append(row)
    return by_width[max(by_width, key=lambda w: len(by_width[w]))] if by_width else rows


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
    ap.add_argument("--game", default=GAME_DEFAULT)
    ap.add_argument("--stratagem", default="", help="wiki key, e.g. 'Orbital Precision Strike'")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--sdk", default="refs/hd2runtime/HD2Runtime-0.28.1-sdk.zip")
    ap.add_argument("--wiki", default="refs/wiki/stratagemdata.json")
    ap.add_argument("--proj-dump", default="refs/helldiversdata/generated_projectile_settings.json")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import typelib                                              # noqa: E402

    types = typelib.TypeLib(unseal((game / "dl_library.dl_typelib").read_bytes(), box))

    def stride_of(tid: int) -> int | None:
        try:
            members = types.members(tid)
        except Exception:                                        # noqa: BLE001
            return None
        try:
            if len(members) == 1 and (members[0]["size64"] or 0) > 8:
                return types.free_runs(members[0]["type_id"], 1)[0]
            return types.free_runs(tid, 1)[0]
        except Exception:                                        # noqa: BLE001
            return None

    def rows_of(table: str, stride: int | None = None) -> list[bytes]:
        plain = unseal((game / f"generated_{table}.dl_bin").read_bytes(), box)
        out = []
        for group in groups(plain):
            use = stride or stride_of(group["type_id"])
            if not use:
                continue
            p0 = group["payload_at"]
            marker, count = struct.unpack_from("<QQ", plain, p0)
            if marker != DESCRIPTOR or count <= 0 or count * use > group["payload"]:
                continue
            base = p0 + DESCRIPTOR
            out.extend(plain[base + i * use: base + (i + 1) * use] for i in range(count))
        return dominant(out)

    # ---- local data -----------------------------------------------------------------------------
    strat_rows = []
    plain = unseal((game / "generated_stratagem_settings.dl_bin").read_bytes(), box)
    for group in groups(plain):
        marker, count = struct.unpack_from("<QQ", plain, group["payload_at"])
        if marker != DESCRIPTOR or count * STRATAGEM_STRIDE > group["payload"]:
            continue
        base, pool = group["payload_at"] + DESCRIPTOR, plain[group["payload_at"]:]
        for i in range(count):
            row = base + i * STRATAGEM_STRIDE
            strat_rows.append({
                "display": read_cstr(pool, struct.unpack_from("<Q", plain, row + 16)[0]),
                "type_value": struct.unpack_from("<I", plain, row)[0],
                "cooldown": struct.unpack_from("<f", plain, row + 104)[0],
                "cell": struct.unpack_from("<I", plain, row + 392)[0],
            })

    proj_rows = rows_of("projectile_settings")
    exp_rows = rows_of("explosion_settings")
    exp_by_id = {struct.unpack_from("<I", r, 0)[0]: r for r in exp_rows}

    dump = json.loads(pathlib.Path(a.proj_dump).read_text(encoding="utf-8"))
    proj_items = (dump[0] if isinstance(dump, list) else dump)["ProjectileSettings"]["items"]
    proj_by_upper: dict[int, dict] = {}
    for item in proj_items:
        proj_by_upper.setdefault(item["name_upper"], item)
    proj_row_by_upper = {struct.unpack_from("<I", r, 4)[0]: r for r in proj_rows}

    wiki = json.loads(pathlib.Path(a.wiki).read_text(encoding="utf-8"))["weapon"]
    cat = {}
    with zipfile.ZipFile(a.sdk) as fh:
        for s in json.loads(fh.read("StratagemAuthoringCapabilities.json"))["stratagems"]:
            icon = s.get("uiIcon") or {}
            cat[norm(s["name"])] = {"native": icon.get("nativeType"),
                                    "value": icon.get("nativeTypeValue"),
                                    "name": s["name"]}

    def show(wiki_name: str) -> None:
        entry = wiki[wiki_name]
        print(f"\n=== {wiki_name} ===")
        mine = [r for r in strat_rows if norm(r["display"].replace(".", " ")) == norm(wiki_name)]
        if mine:
            r = mine[0]
            print(f"  [our row ] display={r['display']!r}  +0(type)={r['type_value']}  "
                  f"cooldown={r['cooldown']:g}  +392(cell)={r['cell']}")
        else:
            print("  [our row ] no row matched this display name")
        native = (cat.get(norm(wiki_name)) or {}).get("native")
        print(f"  [type    ] wiki ref={entry.get('ref')!r}   HD2Runtime nativeType={native!r}   "
              f"{'MATCH' if native == entry.get('ref') else 'naming variant / not found'}")
        ptype = entry.get("projectile_type")
        if not ptype:
            print(f"  [projectile] wiki has none; attacks={[a.get('name') for a in entry.get('attacks', [])]}")
            return
        item = proj_by_upper.get(next((i["name_upper"] for i in proj_items
                                       if i["type"] == "ProjectileType_" + ptype), -1))
        print(f"  [projectile] wiki projectile_type={ptype!r} -> ProjectileType_{ptype}")
        if not item:
            print("               (not in the filediver dump)")
            return
        row = proj_row_by_upper.get(item["name_upper"])
        if not row:
            print(f"               name_upper={item['name_upper']} not found in our table")
            return
        print(f"               our row: +0(type id)={struct.unpack_from('<I', row, 0)[0]}  "
              f"calibre={struct.unpack_from('<f', row, 24)[0]:g}  "
              f"speed={struct.unpack_from('<f', row, 32)[0]:g}  "
              f"mass={struct.unpack_from('<f', row, 36)[0]:g}")
        for label, slot in (("impact", 144), ("expire", 156)):
            eid = struct.unpack_from("<I", row, slot)[0]
            if eid == 0:
                print(f"               {label} explosion id 0 -> ExplosionType_None")
                continue
            exp = exp_by_id.get(eid)
            if exp is None:
                print(f"               {label} explosion id {eid} -> not present")
                continue
            print(f"               {label} explosion id {eid} -> our explosion row: "
                  f"inner={struct.unpack_from('<f', exp, 16)[0]:g} "
                  f"outer={struct.unpack_from('<f', exp, 20)[0]:g} "
                  f"stagger={struct.unpack_from('<f', exp, 24)[0]:g} "
                  f"cone={struct.unpack_from('<f', exp, 28)[0]:g} "
                  f"nshrap={struct.unpack_from('<I', exp, 80)[0]}")
        names = [a.get("name") for a in entry.get("attacks", [])]
        print(f"  [attacks  ] {names}")

    if a.stratagem:
        show(a.stratagem)
    elif a.all:
        for key in wiki:
            if wiki[key].get("projectile_type"):
                show(key)
    else:
        print("give --stratagem NAME or --all")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
