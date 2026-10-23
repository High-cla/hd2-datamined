#!/usr/bin/env python3
"""在常驻包里按**内容**给粒子分类（名字不可用时的唯一办法）。

为什么不用名字
    粒子的 `file_id` 是独立数字 id，不是名字哈希（实测：尾部的 camera_shake 引用
    直接等于 file_id）。srkit-names 只有 16% 的条目能解析出名字，particles 一类
    基本解析不出来。所以只能读资源**内部的可读字符串**来判类别。

输出
    每个粒子里能找到的 ASCII 串，按关键词（fire/flame/burn/napalm/smoke/...）打分。
"""
from __future__ import annotations

import json
import re
import sys

SDK = os.environ.get("HD2SDK", r"C:\Users\Admin\HD2SDK-CommunityEdition")
GAME_DATA = os.environ.get("HD2_GAME_DATA", r"D:\SteamLibrary\steamapps\common\Helldivers 2\data")
NAME_INDEX = os.environ.get("HD2_NAME_INDEX", r"D:\mod\refs\srkit-names.json")
MISSION_PKG = "7ed1f941859987b4"      # 爆炸 158 的粒子所在包 = 任务效果包

sys.path.insert(0, SDK)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                            # noqa: BLE001
        pass

from srkit.container.bundle import BundleSet                     # noqa: E402
from srkit.container.package import Package                      # noqa: E402

STR_RE = re.compile(rb"[\x20-\x7e]{4,}")
WORDS = ["fire", "flame", "burn", "napalm", "incend", "ember", "blaze",
         "smoke", "explo", "spark", "heat", "thermal", "muzzle", "trail", "dust"]


def main() -> int:
    ptype = None
    for en in json.load(open(NAME_INDEX, encoding="utf-8")):
        if en.get("type") == "particles":
            ptype = int(en["type_id"])
            break
    print(f"particles type_id = {ptype}", flush=True)

    bundles = BundleSet(GAME_DATA)
    bundles.load_index()
    print("索引已加载", flush=True)
    def part(suffix: str) -> bytes:
        try:
            return bundles.extract_package(MISSION_PKG + suffix)
        except Exception as exc:                                 # noqa: BLE001
            print(f"  {suffix or '(toc)'} 取不到：{exc}", flush=True)
            return b""

    toc = part("")
    gpu = part(".gpu_resources")
    stream = part(".stream")
    print(f"包字节 toc={len(toc):,} gpu={len(gpu):,} stream={len(stream):,}", flush=True)
    pkg = Package.parse(toc, gpu or None, stream or None, name=MISSION_PKG, load_blobs=True)
    parts = [e for e in pkg.entries if e.type_id == ptype]
    print(f"条目 {len(pkg.entries):,} 粒子 {len(parts):,}", flush=True)

    scored = []
    for e in parts:
        blob = bytes(e.toc_data or b"")
        strs = [s.decode("ascii") for s in STR_RE.findall(blob)]
        low = " ".join(strs).lower()
        hits = {w: low.count(w) for w in WORDS if w in low}
        score = sum(hits.values())
        scored.append((score, e.file_id, len(blob), hits, strs[:14]))
    scored.sort(key=lambda x: -x[0])

    print("\n=== 有内容关键词的粒子（按命中数）===", flush=True)
    shown = 0
    for score, fid, n, hits, sample in scored:
        if score == 0:
            break
        print(f"  {fid:#018x}  {n:>7,}B  {hits}", flush=True)
        print(f"      {sample}", flush=True)
        shown += 1
        if shown >= 40:
            break
    if shown == 0:
        print("  （一个都没有：粒子内部不含可读串，需要换判据）")

    print("\n=== 无关键词粒子的样例（看有没有串可读）===", flush=True)
    k = 0
    for score, fid, n, hits, sample in scored:
        if score:
            continue
        print(f"  {fid:#018x}  {n:>7,}B  {sample[:6]}", flush=True)
        k += 1
        if k >= 15:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
