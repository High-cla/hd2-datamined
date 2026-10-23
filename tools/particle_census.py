#!/usr/bin/env python3
"""列出常驻包里可借用的粒子资源（爆炸 `+0x38` 的候选池）。

背景
    爆炸行 `+0x38`（u64）= 粒子特效资源的 file_id。能不能画出来，只取决于
    该资源所属的包是否驻留。所以「给某个爆炸加火光」= 把 `+0x38` 指向一个
    已经在内存里的火粒子，**不需要加载任何包**。

本脚本做的事
    1. 列出所有包名（`BundleSet.package_names()`），把 `packages/content/*` 里
       带 effect 的挑出来；
    2. 对指定包解出条目表，筛出 particles 类型；
    3. 用 srkit-names.json 把 file_id 映射回名字，挑出火 / 凝固汽油 / 燃烧类。

用法
    python tools/particle_census.py --package packages/content/effects_mission
    python tools/particle_census.py --list-packages effect
"""
from __future__ import annotations

import argparse
import json
import os
import sys

SDK = os.environ.get("HD2SDK", r"C:\Users\Admin\HD2SDK-CommunityEdition")
GAME_DATA = os.environ.get("HD2_GAME_DATA", r"D:\SteamLibrary\steamapps\common\Helldivers 2\data")
NAME_INDEX = os.environ.get("HD2_NAME_INDEX", r"D:\mod\refs\srkit-names.json")

sys.path.insert(0, SDK)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

from srkit.container.bundle import BundleSet                     # noqa: E402
from srkit.container.package import Package                      # noqa: E402

FIRE_WORDS = ("fire", "flame", "burn", "napalm", "incend", "ember", "blaze", "thermal")


def main() -> int:
    ap = argparse.ArgumentParser(description="常驻包粒子普查")
    ap.add_argument("--package", action="append", default=[], help="包名（可重复）")
    ap.add_argument("--list-packages", default="", help="只列包名，含该子串")
    ap.add_argument("--all", action="store_true", help="列出全部粒子，不只火的")
    a = ap.parse_args()

    bundles = BundleSet(GAME_DATA)
    bundles.load_index()
    names = bundles.package_names()
    print(f"包总数 {len(names):,}")

    if a.list_packages:
        hits = [n for n in names if a.list_packages.lower() in n.lower()]
        print(f"含 {a.list_packages!r} 的包 {len(hits)} 个：")
        for n in hits[:200]:
            print("  ", n)
        return 0

    if not a.package:
        print("\n提示：用 --package 指定包，或 --list-packages <子串> 先找包名")
        return 0

    # file_id -> (type, name)
    byid: dict[int, dict] = {}
    for en in json.load(open(NAME_INDEX, encoding="utf-8")):
        try:
            byid[int(en["file_id"])] = en
        except Exception:                                        # noqa: BLE001
            continue
    print(f"名字索引 {len(byid):,} 条")

    # particles 的 type id：从名字索引里取一个样本
    ptype = None
    for en in byid.values():
        if en.get("type") == "particles":
            ptype = int(en["type_id"])
            break
    print(f"particles type_id = {ptype}")

    for pname in a.package:
        if pname not in names:
            print(f"\n✗ 包 {pname!r} 不在索引里")
            continue
        toc = bundles.extract_package(pname)
        pkg = Package.parse(toc, b"", b"", name=pname, load_blobs=False)
        parts = [e for e in pkg.entries if e.type_id == ptype]
        print(f"\n=== {pname}: 条目 {len(pkg.entries):,}，粒子 {len(parts):,} ===")
        rows = []
        for e in parts:
            en = byid.get(e.file_id, {})
            nm = str(en.get("name", ""))
            rows.append((e.file_id, nm))
        fire = [r for r in rows if any(w in r[1].lower() for w in FIRE_WORDS)]
        print(f"  名字可解析 {sum(1 for _, nm in rows if nm and not nm.lower() == format(_ or 0,'X').lower()):,}")
        print(f"  疑似火粒子 {len(fire):,}")
        for fid, nm in (rows if a.all else fire)[:120]:
            print(f"    {fid:#018x}  {nm[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
