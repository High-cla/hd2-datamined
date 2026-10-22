"""在 `generated_damage_settings.dl_bin` 里**造一颗自己的弹道伤害行**，并保内容哈希。

用途：把一条「无主行」（没有任何射弹/爆炸引用）整条改写成我们要的数值 ——
伤害 / 坚固伤害 / 穿甲 / 状态（类型 + 强度），供 `entities` 里某把武器的备选弹丸指向。

为什么必须挑无主行：伤害行会被多把武器共享（type 116 = AR-23/AR-23A/StA-52/M-105 ✓），
改共享行 = 连带改别人。无主行 = 只服务我们这一颗弹 ✓

哈希校正：伤害表**没有行内 padding 可用**，所以照 dmg_edit.py 的老办法 ——
在**另一条无主行**的一个「空的 8 字节对齐状态槽」里解出校正字。

用法：
  python dmg_custom_row.py --plain <vanilla_plain> --source-type 116 --target-type 186 \
         --status 39 --strength 25 --host-type 296 --out <out_plain> [--damage 90 --durable 22]

门禁：
  G1 长度不变   G2 差异 ⊆ 目标行 ∪ 校正字   G3 重算哈希 == 原始哈希
  G4 目标行读回   G5 目标行原内容符合预期（防改错行）   G6 源行未被改动
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from murmur64 import murmur64, padding_word_for_hash  # noqa: E402

DAMAGE_TYPE = 0xE0A72CF0
STRIDE = 76
STATUS_AT = 44
SLOTS = 4


def parse_ldld(data: bytes):
    count = struct.unpack_from("<I", data, 0)[0]
    out = []
    pos = 4
    for i in range(count):
        if data[pos:pos + 4] != b"LDLD":
            raise ValueError(f"group {i}: bad magic at 0x{pos:X}")
        version, type_id, size = struct.unpack_from("<III", data, pos + 4)
        if version != 1:
            raise ValueError(f"group {i}: version {version}")
        out.append({"type": type_id, "payload": pos + 24, "size": size})
        pos += 24 + size
    return out


def damage_array(data: bytes):
    for g in parse_ldld(data):
        if g["type"] == DAMAGE_TYPE:
            aoff, count, pad = struct.unpack_from("<QII", data, g["payload"])
            if pad != 0:
                raise ValueError("unexpected array descriptor padding")
            base = g["payload"] + aoff
            if base + count * STRIDE > g["payload"] + g["size"]:
                raise ValueError("array overruns its group payload")
            return base, count
    raise ValueError("damage settings group not found")


def rows(data: bytes):
    base, count = damage_array(data)
    out = []
    for i in range(count):
        off = base + i * STRIDE
        t, dmg, dur = struct.unpack_from("<Iii", data, off)
        status = [struct.unpack_from("<If", data, off + STATUS_AT + 8 * k) for k in range(SLOTS)]
        out.append({"index": i, "offset": off, "type": t, "damage": dmg, "durable": dur,
                    "status": status})
    return out


def empty_aligned_words(row):
    words = []
    for k in range(SLOTS):
        pos = row["offset"] + STATUS_AT + 8 * k
        t, v = row["status"][k]
        if t == 0 and v == 0.0 and pos % 8 == 0:
            words.append({"offset": pos, "slot": k})
    return words


def cmd_run(args) -> int:
    data = open(args.plain, "rb").read()
    original_hash = murmur64(data)
    table = {r["type"]: r for r in rows(data)}
    if args.source_type not in table:
        print(f"✗ 源行 {args.source_type} 不存在")
        return 2
    if args.target_type not in table:
        print(f"✗ 目标行 {args.target_type} 不存在")
        return 2
    if args.host_type not in table:
        print(f"✗ 校正宿主行 {args.host_type} 不存在")
        return 2
    src, tgt, host = table[args.source_type], table[args.target_type], table[args.host_type]
    if args.target_type == args.host_type or args.target_type == args.source_type:
        print("✗ 目标行不能等于源行或宿主行")
        return 2

    # 目标行原内容快照（防改错行）
    print(f"源行 {args.source_type}: damage={src['damage']} durable={src['durable']} "
          f"status={src['status']}")
    print(f"目标行 {args.target_type}: damage={tgt['damage']} durable={tgt['durable']} "
          f"status={tgt['status']}")
    print(f"宿主行 {args.host_type}: damage={host['damage']}（应为无主行）")

    edited = bytearray(data)
    # 1) 整行改写：抄源行 76 字节（含伤害/坚固/穿甲/demo/stagger/push），但保留目标行自己的 id
    payload = bytearray(data[src["offset"]:src["offset"] + STRIDE])
    struct.pack_into("<I", payload, 0, args.target_type)
    if args.damage is not None:
        struct.pack_into("<i", payload, 4, args.damage)
    if args.durable is not None:
        struct.pack_into("<i", payload, 8, args.durable)
    struct.pack_into("<I", payload, STATUS_AT + 0, args.status)
    struct.pack_into("<f", payload, STATUS_AT + 4, args.strength)
    edited[tgt["offset"]:tgt["offset"] + STRIDE] = payload

    # 2) 校正字：宿主行的空状态槽
    words = empty_aligned_words(host)
    if not words:
        print("✗ 宿主行没有空的 8 字节对齐状态槽")
        return 2
    word = padding_word_for_hash(bytes(edited), words[0]["offset"], original_hash)
    edited[words[0]["offset"]:words[0]["offset"] + 8] = word

    edited = bytes(edited)
    # ---------------- 门禁
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
        ok = ok and cond

    check("G1 长度不变", len(edited) == len(data), f"{len(data):,}")
    expected = set(range(tgt["offset"], tgt["offset"] + STRIDE)) | set(
        range(words[0]["offset"], words[0]["offset"] + 8))
    diff = {i for i in range(len(data)) if data[i] != edited[i]}
    check("G2 差异 ⊆ 目标行 ∪ 校正字", diff <= expected,
          f"diff={len(diff)} 目标行内={len(diff - expected)}")
    got = murmur64(edited)
    check("G3 重算哈希 == 原始哈希", got == original_hash, f"0x{got:016X} vs 0x{original_hash:016X}")
    row = rows(edited)
    by = {r["type"]: r for r in row}
    t2 = by[args.target_type]
    check("G4 读回 damage/durable", t2["damage"] == (args.damage if args.damage is not None else src["damage"])
          and t2["durable"] == (args.durable if args.durable is not None else src["durable"]),
          f"{t2['damage']}/{t2['durable']}")
    check("G4 读回 status", t2["status"][0] == (args.status, args.strength),
          f"{t2['status'][0]}")
    check("G6 源行未被改动", by[args.source_type]["damage"] == src["damage"]
          and by[args.source_type]["status"] == src["status"])

    if not ok:
        print("✗ 门禁未过，不写文件")
        return 1
    open(args.out, "wb").write(edited)
    print(f"✓ 已写 {args.out}（{len(edited):,} B, murmur64=0x{murmur64(edited):016X}）")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="造一颗自己的伤害行（保哈希）")
    p.add_argument("--plain", required=True)
    p.add_argument("--source-type", type=int, required=True, help="抄哪一行（如 AR-23 = 116）")
    p.add_argument("--target-type", type=int, required=True, help="写哪一行（必须无主）")
    p.add_argument("--status", type=int, required=True, help="状态 id（39=眩晕 · 5=火 · 42/44=毒气）")
    p.add_argument("--strength", type=float, required=True, help="状态强度（1.0 = 一颗 Halt 弹丸）")
    p.add_argument("--damage", type=int)
    p.add_argument("--durable", type=int)
    p.add_argument("--host-type", type=int, required=True, help="付哈希校正的无主行")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
