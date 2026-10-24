#!/usr/bin/env python3
"""armor_kit_weight.py -- 改单件护甲的「部件档位」（rating / speed / stamina 的唯一文件侧入口）。

为什么是这张表
    `ArmorStatsCapabilities.json`（HD2Runtime 0.30.3）的 `executableData` 说得死：三档基准
    （light 0/1.1/0.75 · medium 1/1/1 · heavy 2/0.9/1.5）和伤害曲线都在 **game.dll 的可执行数据页**里，
    不是 .dl_bin 表。文件侧能动的只有**每一件甲 9 个部件各属哪一档**：

        rating  = 评分槽（torso + 双腿 + 双臂 + 双肩，7 个）的 A 求均值，再叠被动 armor 行
        speed   = 全部 9 件的 S 求均值
        stamina = 全部 9 件的 F 求均值
        显示     RATING = 50 + 50A · SPEED = 500S · STAMINA = 100(2 - F)

    所以「把一件轻甲改成重甲」= 把它的**所有部件**的档位写成 2，期望值可以精确预测：
    50/550/125 → 150/450/50。

数据结构（`generated_customization_armor_sets.dl_bin`，本 build 422 个 LDLD 块 = 422 条记录）
    payload：
        +0   64 B  记录（`HelldiverCustomizationKit`）
              +0  id(u32，护甲 kit id)         +24 u32                  +28 passive(u32)
              +32 8 B                          +40 KitType(u32)         +44 f32
              +48 u32 部件组数组偏移(相对 payload)      +56 u32 部件组个数
        +off 24 B × 组数  组 = {+0 u32 组类型, +8 u32 部件数组偏移, +16 u32 部件个数}
        再往后 112 B × 部件  部件 = {+0 8 B 哈希, +8 u32 槽位 1..9, +12 u32 变体 0/1/2,
                                     +16 u32 档位 0=light 1=medium 2=heavy, ...}

    ★ 2026-10-24 判定依据（离线，135/135）：SDK 的 135 件甲的逐槽 weights 与本表 `+16` 逐件对上 ——
      斗篷槽（槽位 1，全表恰好 135 个）135/135 精确；每件甲至少有 1 个「身体组」的档位集合与 SDK 完全一致；
      剩下 29 件甲只在一个身体组里一致，正对应 SDK 说的 `slim_stats only when the slim body differs`。

用法
    python tools/armor_kit_weight.py --show                       # 列 135 件甲（id/编号/名字/档位）
    python tools/armor_kit_weight.py --show --name "B-01"         # 按名字过滤
    python tools/armor_kit_weight.py --dry-run --kit 0x250FD6C1 --weight heavy
    python tools/armor_kit_weight.py --kit 0x250FD6C1 --weight heavy --out out/x.plain

    --kit 接受 id（0x 可选）/编号 /名字；--name 名字与 --perk 被动号可批量选。
    --weight 接受 light/medium/heavy 或 0/1/2。
    --slots 只改指定槽位（默认全部）；--body-types 只改指定身体组（默认全部）。

门禁
    G0 容器几何自洽（422 块、每块 payload 恰好被记录/组/部件铺满，不重不漏）
    G1 长度 = 原长 + 对齐 + 8
    G2 差异 ⊆ 目标部件的 +16 ∪ 最后一组尺寸字段 ∪ 校正字
    G3 重算 MurmurHash64A == 原版
    G4 目标部件读回 == 目标档位
    G5 目标**之外**的部件一个没动
    G6 容器重解析自洽、无尾部残留
    G7 改完重解码，逐件甲的档位集合 == 预期
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from plain_edit import parse_blocks, rebuild, TAIL                        # noqa: E402
from murmur64 import murmur64, padding_word_for_hash                     # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                    # noqa: BLE001
        pass

DEFAULT = r"D:\mod\refs\dlbin\plaintext-26088801\generated_customization_armor_sets.dl_bin"
SDK = r"D:\mod\c11-recon\sdk-0.30.3\ArmorStatsCapabilities.json"

REC = 64          # HelldiverCustomizationKit (size64)
BODY = 24         # BodyTypePieces
PIECE = 112       # 部件
OFF_PIECE_BASE = 48      # 记录里「部件组数组偏移」
OFF_PIECE_COUNT = 56     # 记录里「部件组个数」
OFF_SLOT = 8             # 部件里槽位
OFF_VARIANT = 12         # 部件里变体
OFF_WEIGHT = 16          # 部件里档位  <-- 本工具写这个

SLOTS = ["cape", "torso", "hips", "left_leg", "right_leg",
         "left_arm", "right_arm", "left_shoulder", "right_shoulder"]
WEIGHT_NAME = {0: "light", 1: "medium", 2: "heavy"}
WEIGHT_VAL = {"light": 0, "medium": 1, "heavy": 2, "0": 0, "1": 1, "2": 2}

# SDK 的显示公式（用来给「预测」那一列算数）
CLASS_A = {0: 0.0, 1: 1.0, 2: 2.0}
CLASS_S = {0: 1.1, 1: 1.0, 2: 0.9}
CLASS_F = {0: 0.75, 1: 1.0, 2: 1.5}
RATING_SLOTS = {2, 4, 5, 6, 7, 8, 9}      # 不含 cape(1) 与 hips(3)


# --------------------------------------------------------------------- 解析
def decode_record(pay: bytes) -> dict:
    """payload -> {id, passive, bodies:[{type, off, count, pieces:[{at,slot,variant,weight}]}]}"""
    kit_id, = struct.unpack_from("<I", pay, 0)
    passive, = struct.unpack_from("<I", pay, 28)
    body_off, = struct.unpack_from("<I", pay, OFF_PIECE_BASE)
    body_cnt, = struct.unpack_from("<I", pay, OFF_PIECE_COUNT)
    bodies = []
    for b in range(body_cnt):
        at = body_off + BODY * b
        btype, _p, poff, _q, pcount, _r = struct.unpack_from("<6I", pay, at)
        pieces = []
        for i in range(pcount):
            pa = poff + PIECE * i
            slot, variant, weight = struct.unpack_from("<3I", pay, pa + OFF_SLOT)
            pieces.append({"at": pa, "slot": slot, "variant": variant, "weight": weight})
        bodies.append({"at": at, "type": btype, "off": poff, "count": pcount, "pieces": pieces})
    return {"id": kit_id, "passive": passive, "bodies": bodies}


def parse_table(plain: bytes) -> tuple[list[dict], list[dict]]:
    blocks = parse_blocks(plain)
    kits = []
    for gi, b in enumerate(blocks):
        p0 = b["at"] + 24
        pay = plain[p0:p0 + b["size"]]
        rec = decode_record(pay)
        rec["group"] = gi
        rec["payload_at"] = p0
        rec["payload_size"] = b["size"]
        kits.append(rec)
    return blocks, kits


def geometry_checks(plain: bytes, blocks: list[dict], kits: list[dict]) -> list[str]:
    """G0：记录 64 B + 组 + 部件必须**互不重叠**且都在 payload 内。

    422 块里 413 块被「记录 + 组 + 部件」精确铺满；另外 9 块尾部还跟着一段
    其它数组（`{u32 3}{u32 0}{u64 哈希}` 那种），那是非护甲的 cosmetic 记录，
    我们不碰它，所以这里只要求「不重叠 + 不越界」，把余量作为统计报出来。
    """
    problems = []
    if len(blocks) != 422:
        problems.append(f"块数 {len(blocks)} != 422")
    exact = 0
    for k in kits:
        pay = plain[k["payload_at"]:k["payload_at"] + k["payload_size"]]
        used = bytearray(len(pay))
        used[0:REC] = b"\x01" * REC
        for b in k["bodies"]:
            if b["at"] + BODY > len(pay):
                problems.append(f"块{k['group']} 组越界 @{b['at']}")
                continue
            if any(used[b["at"]:b["at"] + BODY]):
                problems.append(f"块{k['group']} 组重叠 @{b['at']}")
            used[b["at"]:b["at"] + BODY] = b"\x01" * BODY
            for p in b["pieces"]:
                if p["at"] + PIECE > len(pay):
                    problems.append(f"块{k['group']} 部件越界 @{p['at']}")
                    continue
                if any(used[p["at"]:p["at"] + PIECE]):
                    problems.append(f"块{k['group']} 部件重叠 @{p['at']}")
                used[p["at"]:p["at"] + PIECE] = b"\x01" * PIECE
        if all(used):
            exact += 1
    k_ = {"exact": exact, "total": len(kits)}
    geometry_checks.stats = k_
    if exact < len(kits) * 0.95:
        problems.append(f"只有 {exact}/{len(kits)} 块几何精确铺满，低于 95%")
    return problems


# --------------------------------------------------------------------- 选择
def sdk_kits() -> dict[int, dict]:
    if not pathlib.Path(SDK).is_file():
        return {}
    data = json.load(open(SDK, encoding="utf-8"))
    return {int(k["id"], 16): k for k in data["kits"]}


def sdk_passive_armor() -> dict[int, float]:
    """被动号 -> 加到 A 上的数值（Add 行求和；Set/Multiply 这几件甲都没有）。"""
    if not pathlib.Path(SDK).is_file():
        return {}
    data = json.load(open(SDK, encoding="utf-8"))
    out = {}
    for row in data.get("passiveArmorBonuses", []):
        add = sum(r["value"] for r in row.get("rows", []) if r.get("type") == "Add")
        mult = 1.0
        for r in row.get("rows", []):
            if r.get("type") == "Multiply":
                mult *= r["value"]
        out[row["passive"]] = add * mult
    return out


def matches(kit: dict, sdk: dict[int, dict], a) -> bool:
    if a.kit:
        for want in a.kit:
            w = want.strip()
            if w.lower().startswith("0x"):
                if kit["id"] == int(w, 16):
                    return True
            elif w.isdigit():
                sk = sdk.get(kit["id"])
                if sk and sk["index"] == int(w):
                    return True
            else:
                sk = sdk.get(kit["id"])
                if sk and sk["name"] and w.lower() in sk["name"].lower():
                    return True
        return False
    if a.name:
        sk = sdk.get(kit["id"])
        if not sk or not sk["name"]:
            return False
        return a.name.lower() in sk["name"].lower()
    if a.perk:
        sk = sdk.get(kit["id"])
        return bool(sk) and sk["passive"]["id"] in a.perk
    return False


def predict(kits: list[dict], sdk: dict[int, dict], target: int, slots: set[str],
            bodies: set[int]) -> dict[int, dict]:
    """按 SDK 公式重算改后的 rating/speed/stamina（只看能改到的那一档）。"""
    slot_index = {name: i + 1 for i, name in enumerate(SLOTS)}
    want_slots = {slot_index[s] for s in slots} if slots else set(range(1, 10))
    out = {}
    for k in kits:
        sk = sdk.get(k["id"])
        if not sk:
            continue
        # 每组各算一遍，取最接近 SDK 原值的那组当「游戏读的那组」
        per_body = []
        for b in k["bodies"]:
            if bodies and b["type"] not in bodies:
                continue
            w = {}
            for p in b["pieces"]:
                # 同一槽位若有多件（变体），取第一件
                w.setdefault(p["slot"], p["weight"])
            per_body.append(w)
        if not per_body:
            continue
        base = sk["vanilla"]
        best = None
        for w in per_body:
            a_slots = [w[s] for s in w if s in RATING_SLOTS]
            if not a_slots:
                continue
            A = sum(CLASS_A[x] for x in a_slots) / len(a_slots)
            S = sum(CLASS_S[x] for x in w.values()) / len(w)
            F = sum(CLASS_F[x] for x in w.values()) / len(w)
            err = abs((50 + 50 * A) - base["rating"]) + abs(500 * S - base["speed"])
            if best is None or err < best[0]:
                best = (err, A, S, F)
        if best is None:
            continue
        _err, A, S, F = best
        out[k["id"]] = {"A": A, "S": S, "F": F, "passive": k["passive"],
                        "rating": 50 + 50 * A, "speed": 500 * S, "stamina": 100 * (2 - F)}
    return out


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="改单件护甲的部件档位（rating/speed/stamina 的唯一文件侧入口）")
    ap.add_argument("--plain", default=DEFAULT)
    ap.add_argument("--out", default=None)
    ap.add_argument("--show", action="store_true", help="只列表，不改")
    ap.add_argument("--kit", action="append", default=[], help="id / 编号 / 名字，可重复")
    ap.add_argument("--name", default="", help="名字子串（批量）")
    ap.add_argument("--perk", action="append", type=int, default=[], help="被动号（批量）")
    ap.add_argument("--weight", default="", help="light/medium/heavy 或 0/1/2")
    ap.add_argument("--slots", default="", help="只改这些槽位（逗号分隔，默认全部）")
    ap.add_argument("--body-types", default="", help="只改这些组类型（逗号分隔，默认全部）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    plain = pathlib.Path(a.plain).read_bytes()
    blocks, kits = parse_table(plain)
    sdk = sdk_kits()
    passive_armor = sdk_passive_armor()

    problems = geometry_checks(plain, blocks, kits)
    if problems:
        print("✗ G0 几何不自洽：")
        for p in problems[:10]:
            print("   ", p)
        return 1
    st = getattr(geometry_checks, "stats", {"exact": 0, "total": len(kits)})
    print(f"G0 通过：{len(blocks)} 块；几何精确铺满 {st['exact']}/{st['total']} 块"
          f"（其余是非护甲 cosmetic 记录，尾部另有数组，我们不碰）；"
          f"SDK 认得 {sum(1 for k in kits if k['id'] in sdk)} 件")

    if a.show:
        slots_filter = [s for s in a.slots.split(",") if s] if a.slots else []
        print(f"\n{'idx':>4} {'id':<11} {'class':<7} {'档位(cape..shoulder)':<20} "
              f"{'perk':>4} {'passive':<18} {'rating':>6} {'speed':>5} {'stam':>5} {'parts':>5}  name")
        for k in kits:
            sk = sdk.get(k["id"])
            if (a.name or a.perk or a.kit) and not matches(k, sdk, a):
                continue
            w = [p["weight"] for b in k["bodies"] for p in b["pieces"]]
            capes = [p for b in k["bodies"] for p in b["pieces"] if p["slot"] == 1]
            cls = WEIGHT_NAME[capes[0]["weight"]] if capes else "?"
            ws = "".join(str(x) for x in w[:9])
            if sk:
                v = sk["vanilla"]
                print(f"{sk['index']:>4} 0x{k['id']:08X}  {sk['class']:<7} {ws:<20} "
                      f"{sk['passive']['id']:>4} {(sk['passive']['name'] or '')[:18]:<18} "
                      f"{v['rating']:>6.0f} {v['speed']:>5.0f} {v['stamina']:>5.0f} "
                      f"{len(w):>5}  {sk['name']}")
            else:
                print(f"{'--':>4} 0x{k['id']:08X}  {'?':<7} {ws:<20} "
                      f"{'--':>4} {'(不在 SDK 的 135 件里)':<18} {'--':>6} {'--':>5} {'--':>5} "
                      f"{len(w):>5}")
        return 0

    if not a.weight:
        raise SystemExit("✗ 要给 --weight（light/medium/heavy 或 0/1/2），或者用 --show")
    if a.weight.lower() not in WEIGHT_VAL:
        raise SystemExit(f"✗ 档位 {a.weight!r} 不认识")
    target = WEIGHT_VAL[a.weight.lower()]
    slots = {s.strip() for s in a.slots.split(",") if s.strip()}
    bad_slots = slots - set(SLOTS)
    if bad_slots:
        raise SystemExit(f"✗ 槽位不认识：{sorted(bad_slots)}（可用 {SLOTS}）")
    body_types = {int(x, 0) for x in a.body_types.split(",") if x.strip()}
    if not (a.kit or a.name or a.perk):
        raise SystemExit("✗ 要给 --kit / --name / --perk 之一来指定目标")

    picked = [k for k in kits if matches(k, sdk, a)]
    if not picked:
        raise SystemExit("✗ 没有匹配的记录")
    print(f"\n选中 {len(picked)} 条记录：" + " ".join(f"0x{k['id']:08X}" for k in picked))

    slot_index = {name: i + 1 for i, name in enumerate(SLOTS)}
    want_slots = {slot_index[s] for s in slots} if slots else set(range(1, 10))

    edits, skipped = [], 0
    for k in picked:
        for b in k["bodies"]:
            if body_types and b["type"] not in body_types:
                continue
            for p in b["pieces"]:
                if p["slot"] not in want_slots:
                    continue
                if p["weight"] == target:
                    skipped += 1
                    continue
                abs_off = k["payload_at"] + p["at"] + OFF_WEIGHT
                edits.append({"abs": abs_off, "old": p["weight"], "new": target,
                              "kit": k["id"], "group": k["group"], "slot": p["slot"],
                              "body": b["type"]})
    print(f"要改 {len(edits)} 个部件档位（已经是目标值的 {skipped} 个跳过）")
    if not edits:
        raise SystemExit("✗ 没有要改的（已经是该档位？）")

    # 预测（用改后的档位重算 SDK 的显示公式；取「和原值最接近的那个身体组」当游戏读的那组）
    for k in picked:
        sk = sdk.get(k["id"])
        if not sk:
            continue
        before = sk["vanilla"]
        new_w = {}
        for b in k["bodies"]:
            for p in b["pieces"]:
                new_w.setdefault((b["type"], p["slot"]), p["weight"])
        for b in k["bodies"]:
            for p in b["pieces"]:
                if not body_types or b["type"] in body_types:
                    if p["slot"] in want_slots:
                        new_w[(b["type"], p["slot"])] = target
        # 每个身体组算一套
        best = None
        for b in k["bodies"]:
            w = {s: v for (bt, s), v in new_w.items() if bt == b["type"]}
            if not w:
                continue
            a_slots = [v for s, v in w.items() if s in RATING_SLOTS]
            if not a_slots:
                continue
            A = sum(CLASS_A[x] for x in a_slots) / len(a_slots)
            S = sum(CLASS_S[x] for x in w.values()) / len(w)
            F = sum(CLASS_F[x] for x in w.values()) / len(w)
            old_w = {p["slot"]: p["weight"] for p in b["pieces"]}
            old_a = [v for s, v in old_w.items() if s in RATING_SLOTS]
            old_err = abs((50 + 50 * (sum(CLASS_A[x] for x in old_a) / len(old_a)))
                          - before["rating"])
            if best is None or old_err < best[0]:
                best = (old_err, b["type"], A, S, F)
        if not best:
            continue
        _e, btype, A, S, F = best
        pbonus = passive_armor.get(sk["passive"]["id"], 0.0)
        print(f"  0x{k['id']:08X} {sk['name'] or '<unnamed>':<26} "
              f"{before['rating']:>5.0f}/{before['speed']:>4.0f}/{before['stamina']:>4.0f} -> "
              f"{50 + 50 * (A + pbonus):>5.0f}/{500 * S:>4.0f}/{100 * (2 - F):>4.0f}"
              f"   (A={A:.2f}+被动{pbonus:+.1f} S={S:.3f} F={F:.2f}，组{btype})")

    # 写
    pad8 = (8 - len(plain) % 8) % 8
    tail_len = pad8 + TAIL
    edited = bytearray(rebuild(plain, blocks, tail_len))
    declared = {}
    for e in edits:
        edited[e["abs"]:e["abs"] + 4] = struct.pack("<I", e["new"])
        declared[e["abs"]] = 4
    word_at = len(plain) + pad8
    h0 = murmur64(plain)
    edited[word_at:word_at + TAIL] = padding_word_for_hash(bytes(edited), word_at, h0)
    print(f"原始哈希 0x{h0:016X}  校正字 @ {word_at}")

    allowed = set()
    for off in declared:
        allowed |= set(range(off, off + 4))
    last_at = blocks[-1]["at"]
    allowed |= set(range(last_at + 12, last_at + 16))
    allowed |= set(range(word_at, word_at + TAIL))
    diff = {i for i in range(min(len(plain), len(edited))) if plain[i] != edited[i]}

    checks = []

    def check(tag, cond, detail=""):
        checks.append((tag, bool(cond)))
        print(f"  {'PASS' if cond else 'FAIL'}  {tag}{('  ' + detail) if detail else ''}")

    check("G1 长度 = 原长 + 对齐 + 8", len(edited) == len(plain) + tail_len,
          f"{len(plain):,} -> {len(edited):,}")
    check("G2 差异 ⊆ 目标部件 ∪ 尺寸字段 ∪ 校正字", diff <= allowed,
          f"diff={len(diff)} 处，越界 {[hex(i) for i in sorted(diff - allowed)[:6]]}")
    got = murmur64(bytes(edited))
    check("G3 重算哈希 == 原版", got == h0, f"0x{got:016X}")
    check("G4 目标部件读回 == 目标档位",
          all(struct.unpack_from("<I", edited, e["abs"])[0] == target for e in edits),
          f"{len(edits)} 处")
    # G5：目标之外的部件一个没动
    target_set = {e["abs"] for e in edits}
    changed_pieces = 0
    for k in kits:
        for b in k["bodies"]:
            for p in b["pieces"]:
                off = k["payload_at"] + p["at"] + OFF_WEIGHT
                if off in target_set:
                    continue
                if bytes(edited[off:off + 4]) != plain[off:off + 4]:
                    changed_pieces += 1
    check("G5 目标之外的部件未动", changed_pieces == 0, f"意外改动 {changed_pieces}")
    try:
        parse_blocks(bytes(edited))
        ok_parse = True
    except Exception as exc:                                             # noqa: BLE001
        ok_parse = False
        print(f"      解析失败：{exc}")
    check("G6 容器自洽、无尾部残留", ok_parse)
    # G7：重解码后目标甲的档位集合
    _b2, kits2 = parse_table(bytes(edited))
    by_id = {k["id"]: k for k in kits2}
    g7 = True
    for k in picked:
        if body_types:
            continue
        for b in by_id[k["id"]]["bodies"]:
            for p in b["pieces"]:
                if p["slot"] in want_slots and p["weight"] != target:
                    g7 = False
    check("G7 重解码：目标甲的每个部件都是目标档位", g7)

    if not all(c[1] for c in checks):
        print("\n✗ 门禁未全过，不写输出")
        return 1

    if a.dry_run:
        print("\n✓ 门禁全过（--dry-run，不写文件）")
        return 0

    dest = pathlib.Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(edited))
    print(f"\n✓ 门禁全过，明文写入 {dest}（{len(edited):,} B）")
    print("下一步：tools/dlbin_seal.py seal-key --key D:/mod/refs/dlbin/keys/recipient.pk "
          "→ tools/dlbin_deploy.py install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
