#!/usr/bin/env python3
"""stratagem_tune.py -- 改战备表里的冷却 / 调用时间 / 次数，**保住内容哈希**。

为什么这条线先开
    `generated_stratagem_settings.dl_bin` 的字段是现在最清楚的一张表：
    `+80` max_uses、`+84` call-in 秒、`+104` cooldown 秒、`+392` 面板格 —— 后三个都和
    wiki 数值对过（34/35 一致），Airburst 的 90/100 差异也被 1.007.200 补丁说明解释掉。
    改完的效果在战备面板上**直接能看见数字**，不用进任务就能验。

哈希怎么保住（和爆炸/伤害表同一套做法）
    明文被 `game.dll` 里烘焙的 MurmurHash64A 校验（seed 0xDEADBEEFABAD1DEA）。改字节后
    必须把哈希解回原值：在一个**语义惰性的 8 字节对齐字**里放校正字。
    战备表每行只有 13 段 ≤7 B 的结构空隙，凑不出 8 字节，所以**拿一整行"未使用"的战备当宿主**：
    本 build 里确有两行名字自带 `(NOT USED)`（`EAGLE. (NOT USED) ADDITIONAL STRAFING RUNS`、
    `EAGLE. (NOT USED) AIR-TO-AIR MISSLES`），它们 cell 与真实战备共用 7 号格、显示名 ID 是死引用，
    不会被面板渲染 —— 整行 400 B 都是惰性区。

门禁（任一条不过就拒绝输出）
    G1 长度不变
    G2 差异 ⊆ 目标行 ∪ 校正字那 8 字节
    G3 重算哈希 == 原始哈希
    G4 目标字段读回等于新值
    G5 宿主行除校正字外一字节未变
    G6 目标行除被改字段外一字节未变
    G7 目标行身份字段（+0 type、+40/+44/+48 本地化 ID）未变

用法
    python tools/stratagem_tune.py --plain refs/dlbin/plaintext-26088801/generated_stratagem_settings.dl_bin \
        --name "380mm HE Barrage" --set cooldown=60 --out out/stratagem_380mm_cd60.plain.dl_bin
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from murmur64 import murmur64, padding_word_for_hash            # noqa: E402
from table_dictionary import Dictionary                          # noqa: E402

STRIDE = 400
FIELDS = {"uses": (80, "u32"), "callin": (84, "f32"), "cooldown": (104, "f32")}
IDENTITY = (0, 40, 44, 48, 52, 56)          # type enum + 五个本地化 ID：不许动


def groups(plain: bytes, dic: Dictionary) -> list[dict]:
    """`LDLD` 组：数组型组头 `u64 0x10 | u64 count`，行起点 = payload+16。"""
    out, start = [], 0
    while True:
        at = plain.find(b"LDLD", start)
        if at < 0:
            return out
        start = at + 4
        if at + 24 > len(plain):
            continue
        version, type_id, payload, _wide = struct.unpack_from("<IIII", plain, at + 4)
        if version not in (1, 2) or payload <= 0 or at + 24 + payload > len(plain):
            continue
        marker, count = struct.unpack_from("<QQ", plain, at + 24)
        if marker != 16 or count == 0:
            continue
        try:
            _elem, stride = dic.element_of(type_id)
        except Exception:                                          # noqa: BLE001
            continue
        if stride != STRIDE or 16 + count * STRIDE > payload:
            continue
        out.append({"at": at, "payload_at": at + 24, "count": count,
                    "rows_at": at + 24 + 16, "payload": payload})


def row_name(plain: bytes, group: dict, row_at: int) -> str:
    target = struct.unpack_from("<Q", plain, row_at + 16)[0]
    if not 0 < target < group["payload"]:
        return ""
    at = group["payload_at"] + target
    end = plain.find(b"\0", at, at + 250)
    if end <= at:
        return ""
    try:
        return plain[at:end].decode("ascii")
    except UnicodeDecodeError:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="战备表字段写入（保内容哈希）")
    ap.add_argument("--plain", required=True, help="明文 .dl_bin（缓存或解封后的）")
    ap.add_argument("--name", default="", help="按内部名子串找行，如 '380mm HE Barrage'")
    ap.add_argument("--type", type=lambda v: int(v, 0), default=None, help="按 +0 type 枚举找行")
    ap.add_argument("--set", action="append", default=[],
                    help="字段=值，字段取 uses / callin / cooldown，可重复")
    ap.add_argument("--host-name", default="NOT USED",
                    help="校正字宿主行的内部名子串（默认用 '(NOT USED)' 的行）")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if not a.set:
        raise SystemExit("✗ 没有 --set，无事可做")
    data = pathlib.Path(a.plain).read_bytes()
    # typelib 路径允许跟明文同目录
    typelib = pathlib.Path(a.plain).with_name("dl_library.dl_typelib")
    if not typelib.is_file():
        raise SystemExit(f"✗ 找不到 typelib（{typelib}），它应与明文在同一目录")
    dic = Dictionary(typelib.read_bytes(), {})

    gs = groups(data, dic)
    if not gs:
        raise SystemExit("✗ 一个战备组都没解析出来")
    rows = []
    for gi, g in enumerate(gs):
        for r in range(g["count"]):
            at = g["rows_at"] + r * STRIDE
            rows.append({"group": gi, "row": r, "at": at,
                         "type": struct.unpack_from("<I", data, at)[0],
                         "name": row_name(data, g, at)})
    print(f"明文 {len(data):,} B  组 {len(gs)}  行 {len(rows)}")

    # ---- 找目标行 ----
    if a.type is not None:
        cands = [x for x in rows if x["type"] == a.type]
    else:
        needle = a.name.strip().lower()
        cands = [x for x in rows if needle and needle in x["name"].lower()]
    if len(cands) != 1:
        print(f"✗ 目标不唯一：命中 {len(cands)} 行 -> {[x['name'] for x in cands][:5]}")
        return 2
    target = cands[0]
    print(f"目标：组{target['group']} 行{target['row']} type={target['type']:#x} "
          f"{target['name']!r}")

    # ---- 找宿主行（校正字）----
    hosts = [x for x in rows if a.host_name.lower() in x["name"].lower()
             and x["at"] != target["at"]]
    if not hosts:
        print(f"✗ 找不到宿主行（名字含 {a.host_name!r}）")
        return 2
    host = hosts[-1]
    host_start = host["at"]
    word_at = (host_start + 7) // 8 * 8            # 宿主行内第一个 8 对齐字
    if not (host_start <= word_at <= host_start + STRIDE - 8):
        print("✗ 宿主行内找不到 8 对齐字")
        return 2
    print(f"宿主：组{host['group']} 行{host['row']} {host['name']!r}  校正字 @ {word_at}")

    h0 = murmur64(data)
    print(f"原始哈希 0x{h0:016X}")

    edited = bytearray(data)
    touched = []
    for spec in a.set:
        if "=" not in spec:
            print(f"✗ --set 需要 字段=值，收到 {spec!r}")
            return 2
        field, value = spec.split("=", 1)
        field = field.strip()
        if field not in FIELDS:
            print(f"✗ 未知字段 {field!r}，可选 {list(FIELDS)}")
            return 2
        off, kind = FIELDS[field]
        at = target["at"] + off
        if kind == "u32":
            old = struct.unpack_from("<I", edited, at)[0]
            struct.pack_into("<I", edited, at, int(value, 0))
            new = struct.unpack_from("<I", edited, at)[0]
        else:
            old = struct.unpack_from("<f", edited, at)[0]
            struct.pack_into("<f", edited, at, float(value))
            new = struct.unpack_from("<f", edited, at)[0]
        touched.append((off, field, old, new))
        print(f"  {field} +{off}: {old!r} -> {new!r}")

    word = padding_word_for_hash(bytes(edited), word_at, h0)
    edited[word_at:word_at + 8] = word

    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")

    expected = set(range(target["at"], target["at"] + STRIDE)) | set(range(word_at, word_at + 8))
    diff = {i for i in range(len(data)) if data[i] != edited[i]}
    check("G1 长度不变", len(edited) == len(data), f"{len(data):,}")
    check("G2 差异 ⊆ 目标行 ∪ 校正字", diff <= expected, f"diff={len(diff)}")
    got = murmur64(bytes(edited))
    check("G3 重算哈希 == 原始哈希", got == h0, f"0x{got:016X}")
    check("G4 目标字段读回", all(
        (struct.unpack_from("<I", edited, target["at"] + o)[0] if isinstance(v, int)
         else abs(struct.unpack_from("<f", edited, target["at"] + o)[0] - v) < 1e-6)
        for o, _f, _old, v in touched), str([(f, v) for _o, f, _old, v in touched]))
    hs = host_start
    check("G5 宿主行除校正字外未变",
          edited[hs:word_at] == data[hs:word_at]
          and edited[word_at + 8:hs + STRIDE] == data[word_at + 8:hs + STRIDE])
    touched_offsets = {o for o, _f, _old, _v in touched}
    extra = [o for o in range(0, STRIDE, 4)
             if o not in touched_offsets
             and edited[target["at"] + o:target["at"] + o + 4]
             != data[target["at"] + o:target["at"] + o + 4]]
    check("G6 目标行其余字段未变", not extra, f"越界改动的偏移 {extra[:6]}")
    ident_ok = all(edited[target["at"] + o:target["at"] + o + 4]
                   == data[target["at"] + o:target["at"] + o + 4] for o in IDENTITY)
    check("G7 身份字段未变", ident_ok, f"offsets={IDENTITY}")

    if not all(c[1] for c in checks):
        print("\n✗ 门禁未全过，不写输出")
        return 1
    dest = pathlib.Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(edited))
    print(f"\n✓ 全部门禁通过，明文写入 {dest}（{len(edited):,} B）")
    print("下一步：用 tools/dlbin_seal.py 以 recipient.pk 重新封装，再写入 data/game/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
