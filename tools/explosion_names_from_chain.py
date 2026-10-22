#!/usr/bin/env python3
"""explosion_names_from_chain.py -- 给爆炸行安名字：靠指向它的投掷物。

问题
    explosion_settings 的 424 行里没有任何名字字段（+0 是类型枚举，+4 是 damage_id，
    +16/+20/+24 是三层半径……）。我们试过
        * u32 本地化 ID 槽：只有 +8 有 3 行命中（'Environment'/'Unknowable Forces'），不是名字
        * u64 池指针：没有一个解出可打印串
    所以"从爆炸行自己读出名字"这条路是死的（✗ 否证，见 docs/LOCID-NAMES-25988413.md）。

    ���指向它的行是有名字的：projectile_settings 的 +144 (explode_on_impact_id) 和
    +156 (explode_id) 存的就是爆炸行的 +0 类型枚举，而投掷物行的 +8 是本地化 ID，
    能解成 '500kg Bomb' / 'Napalm Bomb Mk2' 这样的游戏内名。于是

        爆炸行 = 引用它的投掷物名字的集合

    这就是"引用链命名"：名字不在表里，但在边上。一个爆炸被谁用，就从谁那里得到名字；
    被多个投掷物共用的，会列出全部消费方——这本身也是有价值的结构信息
    （共用 = 同一个爆炸被复用，改半径会同时影响多个武器）。

用法
    python tools/explosion_names_from_chain.py --strings refs/strings-probe/all \\
        --out refs/explosion-names-chain.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from table_locid_scan import DESCRIPTOR, groups, load_strings  # noqa: E402
from table_dictionary import Dictionary                        # noqa: E402

EXPLODE_ON_IMPACT, EXPLODE_ID = 144, 156
NAME_CASED, NAME_UPPER = 8, 4
EXPLOSION_TYPE, DAMAGE_ID = 0, 4


def read_table(plain: bytes, dic, typelib_ok=True):
    """返回 (rows, stride)：rows 是每行的起始绝对偏移。groups() 要求 stride 来自 typelib。"""
    heads, start = [], 0
    while True:
        at = plain.find(b"LDLD", start)
        if at < 0:
            break
        start = at + 4
        if at + 24 > len(plain):
            continue
        version, type_id, payload, _wide = struct.unpack_from("<IIII", plain, at + 4)
        if version in (1, 2) and payload > 0 and at + 24 + payload <= len(plain):
            heads.append(type_id)
    strides = {}
    for tid in heads:
        try:
            _elem, stride = dic.element_of(tid)
        except Exception:                                      # noqa: BLE001
            continue
        if stride:
            strides[tid] = stride
    out = []
    for gi, g in enumerate(groups(plain, strides)):
        base = g["record_at"]          # 数组型 payload+16；单记录型就是 payload 本身
        for r in range(g["count"]):
            out.append((gi, r, base + r * g["stride"], g))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plaintext", default="refs/dlbin/plaintext-all")
    ap.add_argument("--typelib", default="refs/dlbin/plaintext-all/dl_library.dl_typelib")
    ap.add_argument("--strings", action="append", default=None)
    ap.add_argument("--out", default="refs/explosion-names-chain.json")
    a = ap.parse_args()

    ids, stats = load_strings([pathlib.Path(p) for p in
                               (a.strings or ["refs/strings-probe/all"])])
    print(f"strings: {stats['ids']} 个 ID")
    dic = Dictionary(pathlib.Path(a.typelib).read_bytes(), {})
    base = pathlib.Path(a.plaintext)

    proj = (base / "generated_projectile_settings.dl_bin").read_bytes()
    expl = (base / "generated_explosion_settings.dl_bin").read_bytes()

    # 爆炸行：index -> 那一行的信息
    explosion_rows = []
    by_type: dict[int, list[int]] = {}
    for gi, r, at, g in read_table(expl, dic):
        type_id = struct.unpack_from("<I", expl, at + EXPLOSION_TYPE)[0]
        row = {"group": gi, "row": r, "type_id": type_id,
               "damage_id": struct.unpack_from("<I", expl, at + DAMAGE_ID)[0],
               "r1_inner": round(struct.unpack_from("<f", expl, at + 16)[0], 3),
               "r2_outer": round(struct.unpack_from("<f", expl, at + 20)[0], 3),
               "r3_shockwave": round(struct.unpack_from("<f", expl, at + 24)[0], 3),
               "cone_angle": round(struct.unpack_from("<f", expl, at + 28)[0], 3),
               "consumers": []}
        explosion_rows.append(row)
        by_type.setdefault(type_id, []).append(len(explosion_rows) - 1)

    # 投掷物：名字 + 它引用的爆炸
    named_projectiles = 0
    linked = 0
    dangling = []          # 指向了不存在的爆炸类型 —— 记下来，不静默丢弃
    for gi, r, at, g in read_table(proj, dic):
        name = ids.get(struct.unpack_from("<I", proj, at + NAME_CASED)[0], "")
        if not name:
            name = ids.get(struct.unpack_from("<I", proj, at + NAME_UPPER)[0], "")
        if name:
            named_projectiles += 1
        for slot, kind in ((EXPLODE_ON_IMPACT, "on_impact"), (EXPLODE_ID, "explode")):
            target = struct.unpack_from("<I", proj, at + slot)[0]
            if not target:
                continue
            if target in by_type:
                linked += 1
                for index in by_type[target]:
                    explosion_rows[index]["consumers"].append(
                        {"projectile_row": r, "name": name, "via": kind, "slot": slot})
            else:
                dangling.append({"projectile_row": r, "name": name,
                                 "via": kind, "target_type": target})

    rows = explosion_rows
    named = [r for r in rows if any(c["name"] for c in r["consumers"])]
    unique = [r for r in named if len({c["name"] for c in r["consumers"] if c["name"]}) == 1]
    shared = [r for r in named if len({c["name"] for c in r["consumers"] if c["name"]}) > 1]

    for r in rows:
        names = []
        for c in r["consumers"]:
            if c["name"] and c["name"] not in names:
                names.append(c["name"])
        r["names"] = names
        r["name"] = names[0] if len(names) == 1 else ""

    out = {"strings": stats, "explosions": len(rows), "named": len(named),
           "unique_name": len(unique), "shared_name": len(shared),
           "projectiles_named": named_projectiles, "links": linked,
           "dangling_links": dangling, "rows": rows}
    dest = pathlib.Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"爆炸行 {len(rows)}  有消费方 {len([r for r in rows if r['consumers']])}  "
          f"能命名 {len(named)}（唯一 {len(unique)} / 共用 {len(shared)}）")
    print(f"投掷物有名 {named_projectiles}  有效引用边 {linked}  悬空引用 {len(dangling)}")
    print("\n样本（唯一消费方的爆炸）:")
    for r in unique[:12]:
        print(f"  行{r['row']:3d} type={r['type_id']:4d} 半径 {r['r1_inner']:6.2f}/"
              f"{r['r2_outer']:6.2f}/{r['r3_shockwave']:6.2f}  -> {r['name']!r}")
    print("\n样本（多消费方共用）:")
    for r in shared[:6]:
        print(f"  行{r['row']:3d} type={r['type_id']:4d} -> {r['names'][:4]}")
    print(f"\n写入 {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
