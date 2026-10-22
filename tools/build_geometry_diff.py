#!/usr/bin/env python3
"""build_geometry_diff.py -- 用旧 build 的表几何（refs/table-geometry.json）对照新 build 的每一张表。

为什么不是直接比明文哈希
    明文哈希需要旧 build 的明文，我们只缓存了 23 个文件（21 张表）。其余 34 张没有旧明文，
    但 `table-geometry.json` 记着旧 build 每张表的：明文字节数 / 组数 / 行数 / 步长。
    这三样任何一样变了，都说明表被动过；全一样就说明结构没变（值可能变，但结构没变）。

判据
    * plain 字节数变化        -> 表被动过（最硬的信号）
    * 明文哈希变化（有缓存时）  -> 表被动过
    * 组数变化                -> 容器结构变了
    * 行数/步长变化            -> 元素类型或数组长度变了

用法
    python tools/build_geometry_diff.py --sk refs/dlbin/keys/recipient.sk \\
        --geometry work/repo-25988413/refs/table-geometry.json --out refs/build-geometry-diff.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys

HEADER = 48


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
        if version in (1, 2) and payload > 0 and at + 24 + payload <= len(plain):
            marker, count = struct.unpack_from("<QQ", plain, at + 24)
            out.append({"type_id": type_id, "payload": payload,
                        "marker": marker, "count": count})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--geometry", default="work/repo-25988413/refs/table-geometry.json")
    ap.add_argument("--old", default="refs/dlbin/plaintext-all",
                    help="旧明文缓存（有几张算几张，用来做哈希对照）")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))
    geo = {t["table"]: t for t in json.loads(pathlib.Path(a.geometry)
                                            .read_text(encoding="utf-8"))["tables"]}
    gamedir = pathlib.Path(a.game) / "data" / "game"
    olddir = pathlib.Path(a.old)

    rows, changed = [], []
    for path in sorted(gamedir.glob("generated_*.dl_bin")):
        raw = path.read_bytes()
        plain = box.decrypt(raw) if len(raw) > HEADER else raw
        gs = groups(plain)
        entry = {"table": path.name, "plain": len(plain), "groups": len(gs),
                 "plaintext_sha256": hashlib.sha256(plain).hexdigest()}
        old_geo = geo.get(path.name)
        if not old_geo:
            entry["status"] = "not-in-geometry"
        else:
            same_size = old_geo["plain"] == entry["plain"]
            same_groups = old_geo["groups"] == entry["groups"]
            old_copy = olddir / path.name
            same_hash = None
            if old_copy.is_file():
                same_hash = (hashlib.sha256(old_copy.read_bytes()).hexdigest()
                             == entry["plaintext_sha256"])
            entry["old_plain"] = old_geo["plain"]
            entry["old_groups"] = old_geo["groups"]
            entry["same_size"] = same_size
            entry["same_groups"] = same_groups
            entry["same_plaintext"] = same_hash
            # 判据顺序很重要：几何（大小 + 组数）是**旧 build 的字典**给的，缓存明文只是
            # 我们自己留的一份副本，副本可能来自别的来源（这轮就踩到：缓存里的
            # passive_bonuses 是 4992，而旧 build 的字典和当前文件都是 4016）。
            # 所以先按几何判，几何说没变就是没变；缓存哈希只作为一个附加标记报出来。
            if same_size and same_groups:
                if same_hash is True:
                    entry["status"] = "identical"        # 明文逐字节相同（有旧明文才算得出）
                elif same_hash is False:
                    entry["status"] = "structure-same-cache-differs"
                else:
                    entry["status"] = "structure-same"   # 没有旧明文，只能证明结构没变
            else:
                entry["status"] = "changed"
        if entry["status"] == "changed":
            changed.append(entry)
        rows.append(entry)

    print(f"表 {len(rows)} 张：" +
          "  ".join(f"{k}={sum(1 for r in rows if r['status'] == k)}"
                    for k in ("identical", "structure-same",
                              "structure-same-cache-differs", "changed", "not-in-geometry")))
    for e in changed:
        print(f"  ！{e['table']}: plain {e['old_plain']} -> {e['plain']}，"
              f"组 {e['old_groups']} -> {e['groups']}")
    if a.out:
        dest = pathlib.Path(a.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps({"tables": rows}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        print(f"\n写入 {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
