#!/usr/bin/env python3
"""table_locid_names.py -- 把表行里存的本地化 ID 解成游戏内文本（显示名 / 大写名 / 短名）。

背景
    `.strings` 资源给每个本地化条目一个 32 位 ID。stratagem_settings 的做法是：
        +40 -> 大写名 ID, +44 -> 显示名 ID, +48 -> 描述 ID
    同样的手法可以套到别的表 —— 只要那张表里有槽位存的是这些 ID。判据不是"猜"，是统计：
    随机 32 位整数落进 ID 集合的概率约 len(ids)/2^32 (24,834 个 ID 时是 5.8e-6)，
    所以"整列几十上百行命中"不可能是巧合。tools/table_locid_scan.py 负责找槽位，
    本工具负责按槽位表把名字倒出来。

槽位表（SLOTS）的来源
    每一项都由 table_locid_scan.py 扫出来，并在下面的注释里写明命中数/去重数，作为证据。

用法
    python tools/table_locid_names.py --table projectile_settings \
        --strings refs/strings-probe/all --strings refs/strings-probe/bundles \
        --out refs/projectile-names.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from table_locid_scan import DESCRIPTOR, groups, load_strings, read_cstr  # noqa: E402

# 表名 -> {字段名: 偏移}。偏移全部经过 table_locid_scan.py 的命中率检验。
SLOTS = {
    # 355 行 × 272 B。命中数/去重数（bundle.00 的 24,834 个 ID）：
    #   +4  225/355 命中 151 去重  '100KG CLUSTER BOMB' / 'CLUSTER BOMB' / '100KG BOMB'
    #   +8  224/355 命中 151 去重  '100kg Cluster Bomb' / 'Cluster Bomb' / '100kg Bomb'
    #   +12  36/355 命中  30 去重  'APHET' / 'FLAK' / 'HE'      <- 弹药/弹头短名
    # filediver 的历史字段名把这三个槽叫 name_upper / name_cased / short_name，语义吻合。
    "projectile_settings": {"name_upper": 4, "name_cased": 8, "short_name": 12},
    # 97+3+4+57+36+21+12 = 230 行 × 88 B，7 个 group（按槽位分：弹药/枪口/内部件/弹匣/瞄具/涂装/扳机/下挂）。
    #   +12 大写名 217/230        +16 显示名 200/230        +20 描述 217/230
    # group6（12 个涂装）的 +16 是 0/12 命中 —— 该组的池里插了颜色块，正是 POINTERS 注释里说的那组。
    # +24 在 filediver 的字段表里叫 Fluff，但这里 0 命中，不是本地化 ID。
    "weapon_customization_settings": {"name_upper": 12, "name_cased": 16,
                                      "description": 20},
    # 424 行 × 152 B。唯一命中 locid 的槽是 +8，但只有 3 行：'Environment'(行 376/377)、
    # 'Unknowable Forces'(行 394)。样本太少，先记录不当作名字字段用。
    "explosion_settings": {},
    # 422 个组 × 64 B，每组一条记录（组头没有 0x10 描述符，payload 就是记录）。
    #   +12 大写名 389/422    +16 显示名 356/422    +20 描述 389/422
    # 解出来就是护甲名：'FS-37 RAVAGER' / 'FS-55 DEVASTATOR'。
    "customization_armor_sets": {"name_upper": 12, "name_cased": 16, "description": 20},
    # 33 个组 × 56 B，单记录。+4 命中 33/33 —— 全表每个被动都解得出名字。
    "customization_passive_bonuses": {"name": 4},
    # 12 个组 × 80 B，单记录。+12 大写 11/12，+16 显示 9/12。
    "unit_customization_settings": {"name_upper": 12, "name_cased": 16},
    # 438 个组 × 624 B，单记录（一个 LDLD 一个星球）。+8 命中 399/438、395 个去重 = 行星名；
    # +16 命中 371/438 但只有 20 个去重 —— 是同一地形共享的描述。
    "planet_data": {"name_upper": 8, "description": 16},
}
# 这些表另有字符串池（行后面还有一段字节），行里存的池内 u64 指针；本工具也能读。
POOL_POINTERS = {
    "weapon_customization_settings": {"debug_name": 0},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", action="append",
                    help="表名（可重复）；不给就扫 SLOTS 里的全部表")
    ap.add_argument("--find", default="",
                    help="按名字子串反查：给出名字 -> 表名 + 行号（做数值修改时的入口）")
    ap.add_argument("--plaintext", default="refs/dlbin/plaintext-all")
    ap.add_argument("--typelib", default="refs/dlbin/plaintext-all/dl_library.dl_typelib")
    ap.add_argument("--strings", action="append", default=None)
    ap.add_argument("--language", default="us")
    ap.add_argument("--out", default=None)
    ap.add_argument("--samples", type=int, default=12)
    a = ap.parse_args()
    if not a.table:
        a.table = list(SLOTS)

    roots = [pathlib.Path(p) for p in (a.strings or ["refs/strings-probe/all"])]
    ids, stats = load_strings(roots, a.language)
    print(f"strings: {stats['blobs_used']}/{stats['blobs_scanned']} 个 {a.language!r} blob, "
          f"{stats['ids']} 个 ID")

    from table_dictionary import Dictionary
    dic = Dictionary(pathlib.Path(a.typelib).read_bytes(), {})

    base = pathlib.Path(a.plaintext)
    out = {"strings": stats, "tables": {}}
    matches: list[tuple[str, dict]] = []
    for name in a.table:
        path = base / f"generated_{name}.dl_bin"
        if not path.is_file():
            print(f"跳过 {name}: 没有 {path}", file=sys.stderr)
            continue
        slots = SLOTS.get(name)
        if slots is None:
            print(f"跳过 {name}: 没有经检验的槽位表（先跑 table_locid_scan.py）", file=sys.stderr)
            continue
        plain = path.read_bytes()
        # 先拿 stride
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
            except Exception:                                  # noqa: BLE001
                continue
            if stride:
                strides[tid] = stride

        rows_out = []
        covered = {field: 0 for field in slots}
        for gi, g in enumerate(groups(plain, strides)):
            p0 = g["payload_at"]
            base_at = g["record_at"]        # 数组型 payload+16，单记录型就是 payload 本身
            for r in range(g["count"]):
                at = base_at + r * g["stride"]
                row = {"index": len(rows_out), "group": gi, "row": r}
                for field, off in slots.items():
                    ident = struct.unpack_from("<I", plain, at + off)[0]
                    text = ids.get(ident, "")
                    row[field] = text
                    row[f"{field}_id"] = ident
                    if text:
                        covered[field] += 1
                for field, off in POOL_POINTERS.get(name, {}).items():
                    target = struct.unpack_from("<Q", plain, at + off)[0]
                    text = read_cstr(plain, p0 + target) if 0 < target < g["payload"] else ""
                    row[field] = text
                    if text:
                        covered[field] = covered.get(field, 0) + 1
                rows_out.append(row)

        # 统一出一个 `name`：显示名优先，缺失时退回大写名，都没有就留空。
        # 退回不是猜测 —— 游戏对没有小写副本的条目本来就显示大写（任务物件在 HUD 上就是大写）。
        # 注意：先算到局部变量再写回 `row["name"]`，否则当主字段本身就叫 name 时会被清空
        # （踩过：passive_bonuses 的 +4 就叫 name，先清零再读自己 → 33 行全部变成 0）。
        primary = [f for f in ("name_cased", "name_upper", "name") if f in slots]
        reverse: dict[str, list[tuple[int, str]]] = {}
        for ident, text in ids.items():
            reverse.setdefault(text.strip().lower(), []).append((ident, text))
        if primary:
            for row in rows_out:
                resolved, source = "", ""
                for field in primary:
                    if row.get(field):
                        resolved, source = row[field], field
                        break
                if not resolved and row.get("name_upper"):
                    variants = [(i, t) for i, t in
                                reverse.get(row["name_upper"].strip().lower(), [])
                                if t != row["name_upper"]]
                    if len(variants) == 1:
                        resolved, source = variants[0][1], "case_variant"
                        row["name_id_used"] = variants[0][0]
                row["name"], row["name_source"] = resolved, source
            covered["name"] = sum(1 for r in rows_out if r["name"])

        total = len(rows_out)
        out["tables"][name] = {"rows": total, "slots": slots, "covered": covered,
                               "data": rows_out}
        if a.find:
            needle = a.find.strip().lower()
            hits = [r for r in rows_out if needle in (r.get("name") or "").lower()]
            matches.extend((name, r) for r in hits)
            continue
        print(f"\n=== {name}: {total} 行 ===")
        for field, off in slots.items():
            n = covered[field]
            pct = f"{100.0 * n / total:.1f}%" if total else "n/a"
            print(f"  +{off:<3d} {field:12s} {n}/{total} ({pct})")
        if "name" in covered:
            sources = {}
            for r in rows_out:
                sources[r["name_source"]] = sources.get(r["name_source"], 0) + 1
            print(f"       {'name':12s} {covered['name']}/{total} 来源 " +
                  "  ".join(f"{k or '(空)'}={v}" for k, v in
                            sorted(sources.items(), key=lambda kv: -kv[1])))
        shown = [r for r in rows_out if r.get(next(iter(slots), ""), "")]
        for row in shown[:a.samples]:
            text = " | ".join(str(row.get(f, ""))[:60] for f in slots)
            print(f"  #{row['index']:4d}  {text}")
    if a.find:
        print(f"\n反查 {a.find!r}：{len(matches)} 条命中")
        for name, row in matches:
            extra = "  ".join(f"{k}={row[k]}" for k in ("name_upper", "short_name", "description")
                              if row.get(k) and k != "name")
            print(f"  {name:32s} #{row['index']:4d}  {row['name']!r}"
                  f"  (group {row['group']}, row {row['row']})"
                  + (f"\n      {extra[:150]}" if extra else ""))
    if a.out:
        dest = pathlib.Path(a.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n写入 {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
