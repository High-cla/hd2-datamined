#!/usr/bin/env python3
"""strings_inventory.py -- 清点解出来的 `.strings` blob：哪些语言、各多少条、ID 空间多大。

为什么需要
    `.strings` 的 ID 空间是**全局**的：同一个 ID 在每种语言里都指向同一条文本的不同译文。
    要判断"某张表里那些查不到的 ID 是不是真的没发布"，必须先证明语料的边界 ——
    也就是"每个 bundle 带的英文副本是不是同一批"。

做法
    只读每个文件的 16 字节头（magic/version/count/language），只有语言命中时才读全文件。
    这样扫 1 GB 级别目录也只是秒级 IO —— 之前先 read_bytes() 再判断语言，5 个 bundle
    就扫了 2 分钟还没完。

用法
    python tools/strings_inventory.py refs/strings-probe/all refs/strings-probe/bundles \\
        --language us
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import string
import struct
import sys
from collections import Counter, defaultdict

MAGIC = b"\xae\xf3\x85>"


def thin_seed0(text: str) -> int:
    """MurmurHash64A(text, seed 0) 的高 32 位 —— .strings 的 language 字段就是这个。"""
    key = text.encode()
    mix = 0xC6A4A7935BD1E995
    mask = (1 << 64) - 1
    h = (len(key) * mix) & mask
    i = 0
    while i + 8 <= len(key):
        k = struct.unpack_from("<Q", key, i)[0]
        i += 8
        k = (k * mix) & mask
        k ^= k >> 47
        k = (k * mix) & mask
        h ^= k
        h = (h * mix) & mask
    tail = key[i:]
    if tail:
        h ^= int.from_bytes(tail, "little")
        h = (h * mix) & mask
    h ^= h >> 47
    h = (h * mix) & mask
    h ^= h >> 47
    return (h >> 32) & 0xFFFFFFFF


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--language", default="us")
    ap.add_argument("--show-languages", action="store_true",
                    help="顺便把 language 字段反查成语言代码")
    a = ap.parse_args()

    want = thin_seed0(a.language)
    lang_counts: Counter = Counter()
    us_by_root: dict[str, set[str]] = defaultdict(set)
    us_missing: Counter = Counter()          # 头里 count 与实际不符
    ids: set[int] = set()
    total = 0

    for root in a.roots:
        base = pathlib.Path(root)
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                with open(path, "rb") as handle:
                    head = handle.read(16)
                    if len(head) < 16 or head[:4] != MAGIC:
                        continue
                    _, _version, count, lang = struct.unpack_from("<4sIII", head, 0)
                    lang_counts[lang] += 1
                    if lang != want:
                        continue
                    data = handle.read()
            except OSError:
                continue
            total += 1
            rel = path.relative_to(base)
            # 一颗目录树里可能装着多个 bundle（bundles/01、bundles/02…），按第一层分开数，
            # 否则"每个 bundle 是不是同一批英文副本"这个问题就没法回答。
            key = f"{base.name}/{rel.parts[0]}" if len(rel.parts) > 1 else base.name
            us_by_root[key].add(hashlib.sha1(head + data).hexdigest()[:12])
            if count <= 0 or len(head) + len(data) < 16 + 8 * count:
                us_missing[str(path)] += 1
                continue
            blob = head + data
            for index in range(count):
                ids.add(struct.unpack_from("<I", blob, 16 + 4 * index)[0])

    print(f"language 字段分布（{len(lang_counts)} 种）:")
    known = {}
    if a.show_languages:
        # 语言字段就是 ThinHash(两字母代码)。直接枚举全部 676 个组合 —— 比维护一张猜测表可靠：
        # 实测这个 build 的 15 种语言全部能被对上（bp cn fr jp es ms us de it pl tc ko pt ru gb）。
        known = {thin_seed0(f"{x}{y}"): f"{x}{y}"
                 for x in string.ascii_lowercase for y in string.ascii_lowercase}
    for lang, n in lang_counts.most_common():
        tag = ""
        if a.show_languages:
            tag = known.get(lang, "")
            tag = f"  ({tag})" if tag else "  (未对上两字母代码)"
        print(f"  {lang:#010x}  {n:5d} blob{tag}")
    for root, hashes in sorted(us_by_root.items()):
        print(f"  {root}: {len(hashes)} 个 distinct {a.language!r} blob")
    union = set().union(*us_by_root.values()) if us_by_root else set()
    print(f"  并集: {len(union)} 个 distinct {a.language!r} blob")
    print(f"  ID 并集: {len(ids)} 个")
    if us_missing:
        print(f"  ⚠ 头部 count 与实际大小不符: {len(us_missing)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
