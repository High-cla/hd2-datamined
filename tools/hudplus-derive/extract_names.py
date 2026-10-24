#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract HUD+ 0.5.3's authored hash->name maps out of its Lua payload.

The payload embeds a generated table (``GeneratedCommon``) whose rows pair a
numeric field/type hash with the *name string the engine wants*:

    ["bind_field"]={["hash"]="0xc3a3f66c",["call"]="dvpupm"}

That ``call`` string -- not the hex hash -- is what HUD+ passes as the third
argument to ``GameSession.game_object_field(session, goid, call)``.  This tool
pulls every such pair out so we get the hash<->name dictionary for free.

Outputs (both under --out, default D:\\mod\\recon-hudplus\\derived):
  field-names.json   {"fields": {"0xc3a3f66c": {"name": "dvpupm", ...}}, ...}
  type-names.json    {"types": {"0x803159b3": "un6y1d", ...}, ...}
  REPORT.md          human-readable tables + provenance
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "lua", "lua_F476DF93691895FA.payloads", "script.lua")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "derived")

# {["hash"]="0x....",["call"]="name"} -- key order is NOT stable, and some rows
# carry a third key in between (["hash"]=..,["value"]=30,["call"]=..), so scan
# innermost brace blocks and pair the two keys per block instead of by adjacency.
BLOCK = re.compile(r"\{[^{}]*\}")
K_HASH = re.compile(r'\[\s*"hash"\s*\]\s*=\s*"(0x[0-9a-fA-F]+)"')
K_CALL = re.compile(r'\[\s*"call"\s*\]\s*=\s*"([^"]*)"')
# ["<hex>"]={["call"]="un6y1d",   -- a type row keyed by its type hash
TYPE_ROW = re.compile(r'\[\s*"(0x[0-9a-fA-F]{8})"\s*\]\s*=\s*\{\s*'
                      r'\[\s*"call"\s*\]\s*=\s*"([^"]*)"')


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    if not os.path.exists(SCRIPT):
        print(f"payload not found: {SCRIPT}")
        return 1
    with open(SCRIPT, "r", encoding="utf-8", errors="replace") as fh:
        body = fh.read()

    pairs = collections.Counter()
    for block in BLOCK.finditer(body):
        seg = block.group(0)
        h = K_HASH.search(seg)
        if h is None:
            continue
        c = K_CALL.search(seg)
        if c is None:
            continue
        pairs[(h.group(1).lower(), c.group(1))] += 1

    types = collections.Counter()
    for m in TYPE_ROW.finditer(body):
        types[(m.group(1).lower(), m.group(2))] += 1

    # ---- consistency: one name per hash? one hash per name? -------------
    by_hash = collections.defaultdict(set)
    by_name = collections.defaultdict(set)
    for (h, n), _c in pairs.items():
        by_hash[h].add(n)
        by_name[n].add(h)

    field_obj = {}
    for h, names in sorted(by_hash.items()):
        field_obj[h] = {"name": sorted(names)[0]}
        if len(names) > 1:
            field_obj[h]["also"] = sorted(names)[1:]

    type_obj = {}
    type_by_hash = collections.defaultdict(set)
    for (h, n), _c in types.items():
        type_by_hash[h].add(n)
    for h, names in sorted(type_by_hash.items()):
        type_obj[h] = sorted(names)[0]

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "field-names.json"), "w", encoding="utf-8") as fh:
        json.dump({"_source": "HUD+ 0.5.3 lua payload generated tables",
                   "field_count": len(field_obj),
                   "fields": field_obj}, fh, indent=1, ensure_ascii=False)
    with open(os.path.join(OUT, "type-names.json"), "w", encoding="utf-8") as fh:
        json.dump({"_source": "HUD+ 0.5.3 lua payload generated tables",
                   "type_count": len(type_obj),
                   "types": type_obj}, fh, indent=1, ensure_ascii=False)

    collisions = {n: sorted(h) for n, h in by_name.items() if len(h) > 1}
    lines = ["# HUD+ 0.5.3 内嵌 hash → 名字 字典（提取物）", "",
             f"来源载荷：`{os.path.basename(SCRIPT)}`（{len(body):,} 字符）", "",
             "## 1 统计", "",
             "| 项 | 值 |", "|---|---|",
             f"| 字段 hash 数 | **{len(field_obj)}** |",
             f"| 类型 hash 数 | **{len(type_obj)}** |",
             f"| 反向重名（一个名字对应多个 hash） | {len(collisions)} |", ""]
    if collisions:
        lines += ["重名的名字（说明该名字在不同类型下出现过，可能是同义字段）：", ""]
        for n in sorted(collisions):
            lines.append(f"- `{n}` ← {', '.join('`'+x+'`' for x in collisions[n])}")
        lines.append("")
    lines += ["## 2 类型 hash → 类型名", "", "| 类型 hash | call 名 |", "|---|---|"]
    for h, n in sorted(type_obj.items()):
        lines.append(f"| `{h}` | `{n}` |")
    lines += ["", "## 3 字段 hash → 名字", "", "| 字段 hash | 名字 |", "|---|---|"]
    for h, o in sorted(field_obj.items()):
        extra = (" / " + ", ".join(o["also"])) if o.get("also") else ""
        lines.append(f"| `{h}` | `{o['name']}`{extra} |")
    with open(os.path.join(OUT, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"字段 hash : {len(field_obj)}")
    print(f"类型 hash : {len(type_obj)}")
    print(f"重名      : {len(collisions)}")
    print(f"输出      : {OUT}")
    show = ["c3a3f66c", "788b9753", "0f27c68e", "f27c68e", "4441caf8",
            "3b12bd49", "cd889dbc", "a3df1643", "cb0453ea", "8bbeb160"]
    print("\n抽样（我们关心的 hash）:")
    for h in show:
        k = "0x" + h
        print(f"  {k:14s} -> {field_obj.get(k, {}).get('name', '(未收录)')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
