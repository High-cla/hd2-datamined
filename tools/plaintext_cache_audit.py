#!/usr/bin/env python3
"""plaintext_cache_audit.py -- 检查明文缓存里有没有"被我们自己的实验污染"的条目。

为什么需要
    `refs/dlbin/plaintext-all/` 是"某个 build 的原版明文"的缓存，我们用它对表做 diff。
    但只要有一次 dump 是在**我们的 mod 已经写进 data/game 之后**做的，那份缓存里就会混进
    改过的表 —— 之后所有"这张表变了没"的判断全错。

    这轮就踩了：2026-10-22 09:52 的 dump 抓到了我们自己的"护甲多被动(Med-Kit)"实验负载
    （`customization_passive_bonuses` 4992 B），而原版是 4016 B。于是 7.2.1 更新后我把它
    误报成"唯一有内容变化的表"。

判据（两条独立证据，都不依赖当前 build）
    1. 与 `refs/dlbin/demo/vanilla_*.dl_bin`（部署前备份的原版封包）比：解密后应当逐字节相同；
    2. 与当前 build 的明文比：我们的游戏是正版更新的，除非本次更新改过这张表，否则也该相同。
    两条都对不上 ⇒ 缓存条目可疑，必须重 dump。

用法
    python tools/plaintext_cache_audit.py --sk refs/dlbin/keys/recipient.sk
    python tools/plaintext_cache_audit.py --sk <sk> --fix     # 用当前 build 的原版覆盖可疑条目
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HEADER = 48


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--cache", default="refs/dlbin/plaintext-all")
    ap.add_argument("--demo", default="refs/dlbin/demo")
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--current", default="", help="当前 build 的明文缓存目录（可选，缺省用 --game 现解）")
    ap.add_argument("--fix", action="store_true", help="用当前 build 的原版覆盖可疑的缓存条目")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))
    cache, demo = pathlib.Path(a.cache), pathlib.Path(a.demo)
    curdir = pathlib.Path(a.current) if a.current else (pathlib.Path(a.game) / "data" / "game")

    # 当前 build 的明文（现解，或读已缓存的目录）
    current: dict[str, bytes] = {}
    for path in sorted(curdir.glob("generated_*.dl_bin")):
        raw = path.read_bytes()
        try:
            current[path.name] = box.decrypt(raw) if len(raw) > HEADER else raw
        except Exception:                                      # noqa: BLE001
            continue

    rows, suspicious, fixed = [], [], []
    for path in sorted(cache.glob("generated_*.dl_bin")):
        cached = path.read_bytes()
        entry = {"file": path.name, "cache_plain": len(cached), "cache_sha": sha(cached)[:16]}
        # 证据 1：demo 里的原版备份（文件名形如 vanilla_generated_xxx.dl_bin）
        backup = demo / f"vanilla_{path.name}"
        if backup.is_file():
            raw = backup.read_bytes()
            try:
                plain = box.decrypt(raw) if len(raw) > HEADER else raw
            except Exception:                                  # noqa: BLE001
                plain = None
            if plain is not None:
                entry["demo_backup"] = len(plain)
                entry["demo_same"] = sha(plain) == sha(cached)
        # 证据 2：当前 build
        if path.name in current:
            entry["current"] = len(current[path.name])
            entry["current_same"] = sha(current[path.name]) == sha(cached)

        verdict = "ok"
        if entry.get("demo_same") is False:
            verdict = "contradicts-demo-backup"
        if entry.get("current_same") is False:
            verdict = "differs-from-current-build" + (
                "-and-demo" if entry.get("demo_same") is False else "")
        entry["verdict"] = verdict
        if verdict != "ok":
            suspicious.append(entry)
            if a.fix and path.name in current:
                path.write_bytes(current[path.name])
                fixed.append(path.name)
                entry["fixed"] = True
        rows.append(entry)

    print(f"缓存条目 {len(rows)} 个，可疑 {len(suspicious)} 个"
          + (f"，已修复 {len(fixed)} 个" if fixed else ""))
    for e in suspicious:
        print(f"  ！{e['file']}: cache={e['cache_plain']} B "
              f"demo={e.get('demo_backup')} B current={e.get('current')} B -> {e['verdict']}")
    for name in fixed:
        print(f"  ✓ 已用当前 build 原版覆盖 {name}")
    if a.out:
        dest = pathlib.Path(a.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps({"rows": rows, "fixed": fixed},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n写入 {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
