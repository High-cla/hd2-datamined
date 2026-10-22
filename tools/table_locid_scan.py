#!/usr/bin/env python3
"""table_locid_scan.py -- 在一张 `.dl_bin` 表里找出"本地化 ID 槽"和"字符串池偏移槽"。

为什么可行
    `.strings` 资源给每个本地化条目分配一个 32 位整数 ID，表行如果要显示名字，就存这个 ID。
    随机一个 32 位整数撞进 ID 集合的概率是 len(ids) / 2^32 —— bundle.00 的 24,846 个 ID 对应
    5.8e-6。也就是说：

        单行命中 = 巧合
        一整列（几十上百行）命中 = 不可能是巧合

    二项分布的尾巴有多长可以直接算：355 行 × 5.8e-6 = 0.0021 次期望误报，因此"≥2 行命中"
    已经 p < 2e-6。这条判据不依赖任何外部映射表，是纯统计的。

第二种槽位
    有些表不存本地化 ID，而存**本表字符串池内的 32 位偏移**（stratagem 用的是 u64 指针，
    projectile 疑似用的是 u32 偏移）。这类槽位的判据同样硬：偏移必须落在 payload 内，且
    指到的位置是一段可打印 ASCII 的 NUL 结尾串，并且**每行各不相同**。随机 u32 同时满足
    这三条的概率远低于 1e-3。

输出
    每个候选槽位一行：offset / 命中数 / 去重数 / 样本文本。不要靠"看起来像"来判断，
    只认 hits 与 distinct 的比例。

用法
    python tools/table_locid_scan.py --table projectile_settings \
        --strings refs/strings-probe/all --out refs/locid-scan.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

MAGIC = b"\xae\xf3\x85>"
DESCRIPTOR = 16
POOL_START = 16          # payload = u64 0x10 | u64 count | rows | pool
ROW_BASE = 24            # payload 在 LDLD 头后 24 字节


def murmur64a(key: bytes) -> int:
    """MurmurHash64A，seed 0 —— 用真实 .strings 的 language 字段验证过。"""
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
        h ^= int.from_bytes(tail, "little") & ((1 << (8 * len(tail))) - 1)
        h = (h * mix) & mask
    h ^= h >> 47
    h = (h * mix) & mask
    h ^= h >> 47
    return h


def thin(text: str) -> int:
    return (murmur64a(text.encode()) >> 32) & 0xFFFFFFFF


def load_strings(dirs: list[pathlib.Path], language: str = "us"):
    """id -> 文本。返回 (表, 统计)。"""
    want = thin(language)
    table: dict[int, str] = {}
    blobs = scanned = 0
    for root in dirs:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if len(data) < 16 or data[:4] != MAGIC:
                continue
            scanned += 1
            _magic, _version, count, lang = struct.unpack_from("<4sIII", data, 0)
            if lang != want or count <= 0 or len(data) < 16 + 8 * count:
                continue
            blobs += 1
            for index in range(count):
                ident = struct.unpack_from("<I", data, 16 + 4 * index)[0]
                offset = struct.unpack_from("<I", data, 16 + 4 * count + 4 * index)[0]
                if offset >= len(data):
                    continue
                end = data.find(b"\0", offset)
                if end <= offset:
                    continue
                try:
                    text = data[offset:end].decode("utf-8")
                except UnicodeDecodeError:
                    continue
                table.setdefault(ident, text)
    stats = {"blobs_scanned": scanned, "blobs_used": blobs, "ids": len(table)}
    return table, stats


def groups(plain: bytes, strides: dict[int, int]):
    """(payload_at, stride, count, type_id, record_at)。

    stride 不许从 `payload % count` 猜：有字符串池的表永远除不尽（explosion 424 行后面跟着
    3,664 B 池）。正确来源是 typelib —— 容器类型的唯一成员是行数组，成员的元素类型大小就是
    stride。projectile 272 / explosion 152 / beam 112 / arc 104，与实测几何逐字节吻合。

    **两种组头，必须都认**（这是踩过的坑）：
      * 数组型：payload 开头是 `u64 0x10 | u64 count`，记录从 payload+16 开始。
        stratagem / projectile / explosion / weapon_customization 都是这种。
      * 单记录型：payload **直接就是那条记录**，没有描述符。planet_data(624 B)、
        zone_data(912 B)、customization_armor_sets(64 B)、unit_customization_settings(80 B)、
        customization_passive_bonuses(56 B) 都是这种 —— 一个 LDLD 一条记录，
        payload 里记录后面还跟着一段从属数据。
    只认第一种会把后面这些表整个跳过，然后输出一句"没有候选槽位" —— 那是假阴性。
    """
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
        p0 = at + 24
        stride = strides.get(type_id)
        if not stride:
            continue
        marker, count = struct.unpack_from("<QQ", plain, p0)
        if marker == DESCRIPTOR and count > 0 and DESCRIPTOR + count * stride <= payload:
            out.append({"payload_at": p0, "count": count, "stride": stride,
                        "payload": payload, "type_id": type_id, "record_at": p0 + DESCRIPTOR,
                        "layout": "array",
                        "pool_bytes": payload - DESCRIPTOR - count * stride})
        elif stride + 8 <= payload:
            # 单记录：payload 就是记录本身
            out.append({"payload_at": p0, "count": 1, "stride": stride,
                        "payload": payload, "type_id": type_id, "record_at": p0,
                        "layout": "single",
                        "pool_bytes": payload - stride})


def read_cstr(buf: bytes, at: int, limit: int = 250) -> str:
    if at <= 0 or at >= len(buf):
        return ""
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end <= at:
        return ""
    raw = buf[at:end]
    if any(b < 32 or b > 126 for b in raw):
        return ""
    return raw.decode("ascii")


def scan(plain: bytes, ids: dict[int, str], strides: dict[int, int], min_hits: int = 2):
    """按 (stride, offset) 聚合统计，跨组累计。

    为什么要跨组聚合：单记录型的表（planet_data 438 组、armor_sets 422 组）每组只有 1 行，
    按组统计命中数永远 ≤ 1，会被 min_hits 过滤掉 —— 那正是第一次扫这几张表得出"没有候选"
    的原因。同一个 stride 的所有组显然是同一种记录，理应放在一起数。
    """
    agg: dict[tuple[int, int], dict] = {}
    for g in groups(plain, strides):
        base = g["record_at"]
        stride, count, payload_at = g["stride"], g["count"], g["payload_at"]
        payload = g["payload"]
        for off in range(0, stride - 3, 4):
            slot = agg.setdefault((stride, off), {"rows": 0, "hits": 0, "pool_hits": 0,
                                                  "distinct": set(), "pool_distinct": set(),
                                                  "samples": [], "pool_samples": [],
                                                  "groups": 0, "layouts": set()})
            slot["groups"] += 1
            slot["layouts"].add(g["layout"])
            for r in range(count):
                at = base + r * stride + off
                if at + 4 > len(plain):
                    break
                slot["rows"] += 1
                val = struct.unpack_from("<I", plain, at)[0]
                if val in ids:
                    slot["hits"] += 1
                    slot["distinct"].add(val)
                    if len(slot["samples"]) < 6:
                        slot["samples"].append(ids[val])
                if 0 < val < payload:
                    text = read_cstr(plain, payload_at + val)
                    if text:
                        slot["pool_hits"] += 1
                        slot["pool_distinct"].add(text)
                        if len(slot["pool_samples"]) < 6:
                            slot["pool_samples"].append(text)
    rows_out = []
    for (stride, off), slot in sorted(agg.items(), key=lambda kv: (-kv[1]["hits"], kv[0])):
        common = {"offset": off, "stride": stride, "rows": slot["rows"],
                  "groups": slot["groups"], "layouts": sorted(slot["layouts"])}
        if slot["hits"] >= min_hits:
            rows_out.append({**common, "kind": "locid", "hits": slot["hits"],
                             "distinct": len(slot["distinct"]),
                             "samples": slot["samples"]})
        if slot["pool_hits"] >= min_hits:
            rows_out.append({**common, "kind": "pool_offset", "hits": slot["pool_hits"],
                             "distinct": len(slot["pool_distinct"]),
                             "samples": slot["pool_samples"]})
    return rows_out


def strides_from(dic, type_ids):
    """type_id -> stride：容器类型的唯一成员是行数组，元素类型的 record_size 就是 stride。"""
    out = {}
    for tid in type_ids:
        try:
            _elem, stride = dic.element_of(tid)
        except Exception:                                      # noqa: BLE001
            continue
        if stride:
            out[tid] = stride
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", action="append", required=True,
                    help="表名（可重复），如 projectile_settings")
    ap.add_argument("--plaintext", default="refs/dlbin/plaintext-all")
    ap.add_argument("--typelib", default="refs/dlbin/plaintext-all/dl_library.dl_typelib")
    ap.add_argument("--strings", action="append", default=None,
                    help="解开的 .strings 目录（可重复）；缺省 refs/strings-probe/all")
    ap.add_argument("--language", default="us")
    ap.add_argument("--min-hits", type=int, default=2)
    ap.add_argument("--out", default=None, help="写 JSON 结果")
    a = ap.parse_args()

    roots = [pathlib.Path(p) for p in (a.strings or ["refs/strings-probe/all"])]
    ids, stats = load_strings(roots, a.language)
    print(f"strings: {stats['blobs_used']}/{stats['blobs_scanned']} 个 {a.language!r} blob, "
          f"{stats['ids']} 个 ID")
    if not ids:
        print("没有 ID，先解 strings", file=sys.stderr)
        return 1

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from table_dictionary import Dictionary
    dic = Dictionary(pathlib.Path(a.typelib).read_bytes(), {})

    base = pathlib.Path(a.plaintext)
    report = {"strings": stats, "tables": {}}
    for name in a.table:
        path = base / f"generated_{name}.dl_bin"
        if not path.is_file():
            print(f"跳过 {name}: 没有 {path}", file=sys.stderr)
            continue
        plain = path.read_bytes()
        # 先扫出所有 group 的 type_id，再一次性问 typelib 要 stride
        heads, start = [], 0
        while True:
            at = plain.find(b"LDLD", start)
            if at < 0:
                break
            start = at + 4
            if at + 24 > len(plain):
                continue
            version, type_id, payload, _wide = struct.unpack_from("<IIII", plain, at + 4)
            if version in (1, 2) and payload > 0 and at + 24 + payload <= len(plain):
                heads.append(type_id)
        strides = strides_from(dic, heads)
        found = scan(plain, ids, strides, a.min_hits)
        group_list = groups(plain, strides)
        report["tables"][name] = {"groups": [], "candidates": found}
        print(f"\n=== {name} ({len(plain)} B) ===")
        layouts: dict[str, int] = {}
        stride_of: dict[int, int] = {}
        for g in group_list:
            layouts[g["layout"]] = layouts.get(g["layout"], 0) + 1
            stride_of[g["stride"]] = stride_of.get(g["stride"], 0) + 1
        report["tables"][name]["groups"] = [
            {"stride": s, "groups": n} for s, n in sorted(stride_of.items())]
        print(f"  组: {len(group_list)} 个  形态 {layouts}  "
              f"stride {sorted(stride_of.items())}")
        if not found:
            print("  没有候选槽位")
        for row in found:
            label = ""
            for elem in {g["type_id"] for g in group_list if g["stride"] == row["stride"]}:
                try:
                    child, _ = dic.element_of(elem)
                except Exception:                              # noqa: BLE001
                    continue
                for m in dic.members(child):
                    if m["offset"] <= row["offset"] < m["offset"] + max(m["size"], 4):
                        label = f"  member[{m['offset']}:{m['size']}] {m['type']}"
                        break
                if label:
                    break
            print(f"  [{row['kind']:11s}] stride{row['stride']:<5d} +{row['offset']:<4d} "
                  f"{row['hits']}/{row['rows']} 命中, {row['distinct']} 去重  "
                  f"{row['samples'][:4]}{label}")
    if a.out:
        out = pathlib.Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
