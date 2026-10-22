#!/usr/bin/env python3
"""wiki_match_tables.py -- 把表里解出来的名字和本地 wiki 页面标题对上，量化覆盖率。

为什么先做匹配而不是直接写文档
    "本地 wiki 页面完成"这件事有两种可能：页面没抓到，或者页面抓到了但名字写法不一样
    （厂商前缀、斜杠、罗马数字 vs 阿拉伯数字）。只有先把匹配跑一遍，才知道缺的是哪一边。

匹配规则（与 tools/stratagem_display_names.py 一致，便于横向比较）
    1. 扁平化：小写 + 只留 a-z0-9，去掉空格/连字符/撇号/点；
    2. 先精确匹配（扁平后相等）；
    3. 再后缀匹配：wiki 标题扁平后以表里的名字结尾（例如 "SH-20 Ballistic Shield Backpack"
       以 "ballisticshieldbackpack" 结尾），要求唯一且名字长度 ≥ 6。

用法
    python tools/wiki_match_tables.py --names refs/locid-names.json \\
        --db refs/wiki/wiki.sqlite --out refs/wiki/name-matches.json
"""
from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import sqlite3
import sys


def flat(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# 表 -> 可以匹配的 wiki 页面种类（种类来自 wiki_build_db.py 对信息框模板的分类）
# 护甲表里混着披风，wiki 也把 cape 归在 Category:Armor，所以这一类允许多种 kind；
# 只认 armor 会把 91 个本该匹配上的名字记成"没页面"。
KIND_OF = {
    "customization_armor_sets": ("armor", "cape", "cosmetic"),
    "customization_passive_bonuses": ("armor-passive",),
    "planet_data": ("planet",),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="refs/locid-names.json")
    ap.add_argument("--db", default="refs/wiki/wiki.sqlite")
    ap.add_argument("--out", default="refs/wiki/name-matches.json")
    a = ap.parse_args()

    names = json.loads(pathlib.Path(a.names).read_text(encoding="utf-8"))
    conn = sqlite3.connect(a.db)
    by_kind: dict[str, list[str]] = {}
    for title, kind in conn.execute("SELECT title, kind FROM page"):
        by_kind.setdefault(kind, []).append(title)

    report = {}
    for table, data in names["tables"].items():
        kinds = KIND_OF.get(table)
        if not kinds:
            continue
        pages = [p for k in kinds for p in by_kind.get(k, [])]
        by_flat = {flat(p): p for p in pages}
        rows = data["data"]
        # 表里可能有同名行（同一套护甲的多条记录），匹配按名字去重统计
        unique_names = list(dict.fromkeys(r["name"] for r in rows if r.get("name")))
        exact, suffix, unmatched = [], [], []
        contains, fuzzy = [], []
        flats = [(flat(p), p) for p in pages]
        for name in unique_names:
            key = flat(name)
            if key in by_flat:
                exact.append({"name": name, "title": by_flat[key]})
                continue
            # 规则 3：wiki 标题以我们的名字结尾（"SH-20 Ballistic Shield Backpack" 对我们
            # 的 "Ballistic Shield Backpack"）
            cands = [p for fp, p in flats if fp.endswith(key) and len(key) >= 6]
            if len(cands) == 1:
                suffix.append({"name": name, "title": cands[0], "by": "title-ends-with-name"})
                continue
            # 规则 4：反方向 —— 我们的名字以 wiki 标题结尾（游戏里叫 "Greatcloak of Rebar
            # Resolve"，wiki 页面叫 "Rebar Resolve"）。唯一 + 标题够长才认。
            cands = [p for fp, p in flats if key.endswith(fp) and len(fp) >= 6]
            if len(cands) == 1:
                contains.append({"name": name, "title": cands[0], "by": "name-ends-with-title"})
                continue
            # 规则 5：拼写差一个字母（游戏表里 "Rememberance"，wiki 写 "Remembrance"）
            near = difflib.get_close_matches(name, pages, n=1, cutoff=0.92)
            if near:
                fuzzy.append({"name": name, "title": near[0], "by": "fuzzy-spelling"})
            else:
                unmatched.append(name)
        report[table] = {
            "kinds": list(kinds),
            "rows": data["rows"],
            "named_rows": len(rows),
            "unique_names": len(unique_names),
            "wiki_pages_of_kind": len(pages),
            "exact": len(exact),
            "suffix": len(suffix),
            "contains": len(contains),
            "fuzzy": len(fuzzy),
            "matched": len(exact) + len(suffix) + len(contains) + len(fuzzy),
            "unmatched": unmatched,
            "matches": exact + suffix + contains + fuzzy,
        }
        print(f"{table:32s} 行 {data['rows']:4d} 有名 {len(rows):4d} 唯一名 {len(unique_names):4d} "
              f"wiki({'/'.join(kinds)}) {len(pages):4d}  精确 {len(exact):4d} 后缀 {len(suffix):4d} "
              f"含 {len(contains):d} 模糊 {len(fuzzy):d}  未匹配 {len(unmatched):4d}")

    dest = pathlib.Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n写入 {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
