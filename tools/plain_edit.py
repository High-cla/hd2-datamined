#!/usr/bin/env python3
"""plain_edit.py -- 对任意 LDLD 容器明文做**任意字节写入**，自动用 tail 宿主保住内容哈希。

用途
    改字段（u32 / f32 / 原始字节）而不必为每张表写一个专用工具。
    这是「改文件路线」最底层的那个原语：给偏移和新值，出合法明文。

为什么校正字放 tail
    实机教训（docs/FILE-ROUTE-BOUNDARIES.md §8.7）：把校正字塞进「看起来没用的行」会崩 ——
    `(NOT USED)` 战备行的开头 8 字节正是它的 `+0` 条目 ID，写进去就是撞主键。
    而「最后一组 payload 末尾追加 8 字节零区」这条路被两次实机验证过（pad8 / cd60_tail）。

容器假设
    文件 = `u32 block_count` + 连续 N 个 `"LDLD" | version | type_id | payload_size | wide | extra | payload`
    （24 字节块头）。不是这种形状的表（例如 generated_zone_data）会明确拒绝，不猜。

门禁
    G1 长度 = 原长 + 8；G2 差异 ⊆ 声明的偏移 ∪ 最后一组尺寸字段 ∪ 尾部 8 字节
    G3 重算 MurmurHash64A == 原值；G4 每个声明的值读回等于目标
    G5 其余字节一字节未动；G6 容器重新解析自洽、无尾部残留

用法
    python tools/plain_edit.py --plain <in.dl_bin> --out <out.dl_bin> \\
        --set 42188=u32:1808877270 --set 42192=f32:12.5
    偏移是**文件绝对偏移**（十进制或 0x 开头都行）。
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from murmur64 import murmur64, padding_word_for_hash            # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

TAIL = 8


def parse_blocks(data: bytes) -> list[dict]:
    if len(data) < 4:
        raise ValueError("文件太短")
    count = struct.unpack_from("<I", data, 0)[0]
    pos, blocks = 4, []
    for i in range(count):
        if data[pos:pos + 4] != b"LDLD":
            raise ValueError(f"第 {i} 块头不是 LDLD（@{pos:#x}）——这张表不是这种容器")
        version, type_id, payload, wide, extra = struct.unpack_from("<IIIII", data, pos + 4)
        if version not in (1, 2) or payload <= 0 or pos + 24 + payload > len(data):
            raise ValueError(f"第 {i} 块头非法 version={version} payload={payload}")
        blocks.append({"at": pos, "version": version, "type_id": type_id,
                       "wide": wide, "extra": extra, "size": payload})
        pos += 24 + payload
    if pos != len(data):
        raise ValueError(f"尾部残留 {len(data) - pos} B")
    return blocks


def rebuild(data: bytes, blocks: list[dict], tail: int) -> bytes:
    out = [struct.pack("<I", len(blocks))]
    last = len(blocks) - 1
    for i, b in enumerate(blocks):
        size = b["size"] + (tail if i == last else 0)
        start = b["at"] + 24
        out.append(b"LDLD")
        out.append(struct.pack("<IIIII", b["version"], b["type_id"], size, b["wide"], b["extra"]))
        out.append(data[start:start + b["size"]])
        if i == last and tail:
            out.append(bytes(tail))
    return b"".join(out)


def parse_value(spec: str) -> tuple[int, bytes, object]:
    """'u32:123' / 'f32:1.5' / 'hex:deadbeef' / '4:0x11223344'（首段是字节宽度）。

    必须带冒号：不带冒号的裸整数（如 `--set 0x979c=158`）会被误读成「宽度 158 字节」
    并写入 158 个零字节，把整行抹掉。实机教训：G4 门禁用同一套逻辑回读，会自己骗自己。
    """
    if ":" not in spec:
        raise ValueError(f"--set 值必须写成 类型:值（如 u32:158），收到裸值 {spec!r}；"
                         f"裸整数会被误当作字节宽度并写入零字节")
    kind, _, raw = spec.partition(":")
    kind = kind.strip().lower()
    if kind == "u32":
        v = int(raw, 0) & 0xFFFFFFFF
        return 4, struct.pack("<I", v), v
    if kind == "f32":
        v = float(raw)
        return 4, struct.pack("<f", v), v
    if kind == "u64":
        v = int(raw, 0) & 0xFFFFFFFFFFFFFFFF
        return 8, struct.pack("<Q", v), v
    if kind == "hex":
        b = bytes.fromhex(raw.strip())
        return len(b), b, b.hex()
    if kind.isdigit():
        width = int(kind)
        if raw.lower().startswith("0x") or all(c in "0123456789abcdefABCDEF" for c in raw.strip()):
            b = bytes.fromhex(raw.strip().zfill(width * 2))
        else:
            b = int(raw, 0).to_bytes(width, "little")
        if len(b) != width:
            raise ValueError(f"宽度不符：{spec}")
        return width, b, b.hex()
    raise ValueError(f"无法解析 {spec!r}，支持 u32: / f32: / u64: / hex: / <宽度>:值")


def main() -> int:
    ap = argparse.ArgumentParser(description="LDLD 明文任意字节写入（tail 宿主保哈希）")
    ap.add_argument("--plain", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", default=[], help="偏移=值，可重复")
    ap.add_argument("--allow-wide", action="store_true",
                    help="允许一次写入超过 16 字节（默认拒绝，防止误把数值当成字节宽度）")
    a = ap.parse_args()

    if not a.set:
        raise SystemExit("✗ 没有 --set，无事可做")

    original = pathlib.Path(a.plain).read_bytes()
    blocks = parse_blocks(original)
    print(f"明文 {len(original):,} B  块 {len(blocks)}  "
          f"最后一组 @ {blocks[-1]['at']:#x} payload={blocks[-1]['size']:,}")

    pad8 = (8 - len(original) % 8) % 8      # 先补齐到 8 对齐，再追加 8 B 当宿主
    tail_len = pad8 + TAIL
    edited = bytearray(rebuild(original, blocks, tail_len))
    print(f"重建 {len(edited):,} B（对齐 {pad8} + 宿主 {TAIL}）")

    declared = {}
    for spec in a.set:
        if "=" not in spec:
            raise SystemExit(f"✗ --set 需要 偏移=值，收到 {spec!r}")
        off_s, val_s = spec.split("=", 1)
        off = int(off_s, 0)
        width, blob, shown = parse_value(val_s)
        if off + width > len(original):
            raise SystemExit(f"✗ 偏移 {off:#x} + {width} 越界")
        if width > 16 and not a.allow_wide:
            raise SystemExit(f"✗ {off:#x} 要写 {width} 字节，超过 16 B 上限；"
                             f"确实要整段写请加 --allow-wide")
        old = original[off:off + width].hex()
        edited[off:off + width] = blob
        declared[off] = width
        print(f"  {off:#08x} ({width} B): {old} -> {blob.hex()}   [{val_s}]")

    word_at = len(original) + pad8
    if word_at % 8:
        raise SystemExit(f"✗ 校正字位置 {word_at} 不是 8 对齐")
    h0 = murmur64(original)
    edited[word_at:word_at + TAIL] = padding_word_for_hash(bytes(edited), word_at, h0)
    print(f"原始哈希 0x{h0:016X}   校正字 @ {word_at}")

    checks = []

    def check(tag, cond, detail=""):
        checks.append((tag, bool(cond)))
        print(f"  {'PASS' if cond else 'FAIL'}  {tag}{('  ' + detail) if detail else ''}")

    allowed = set()
    for off, w in declared.items():
        allowed |= set(range(off, off + w))
    last_at = blocks[-1]["at"]
    allowed |= set(range(last_at + 12, last_at + 16))       # 最后一组的 payload 尺寸字段
    allowed |= set(range(word_at, word_at + TAIL))          # 校正字

    diff = {i for i in range(min(len(original), len(edited))) if original[i] != edited[i]}
    check("G1 长度 = 原长 + 对齐 + 8", len(edited) == len(original) + tail_len,
          f"{len(original):,} -> {len(edited):,}")
    check("G2 差异 ⊆ 声明字段 ∪ 尺寸字段 ∪ 校正字", diff <= allowed,
          f"diff={len(diff)}，越界 {[hex(i) for i in sorted(diff - allowed)[:6]]}")
    got = murmur64(bytes(edited))
    check("G3 重算哈希 == 原始哈希", got == h0, f"0x{got:016X}")
    ok_read = True
    for spec in a.set:
        off_s, val_s = spec.split("=", 1)
        off = int(off_s, 0)
        width, blob, _ = parse_value(val_s)
        if bytes(edited[off:off + width]) != blob:
            ok_read = False
    check("G4 声明字段读回一致", ok_read, f"{len(a.set)} 处")
    check("G5 其余字节未动", diff <= allowed, "")
    try:
        parse_blocks(bytes(edited))
        ok_parse = True
    except Exception as exc:                                 # noqa: BLE001
        ok_parse = False
        print(f"      解析失败：{exc}")
    check("G6 容器自洽、无尾部残留", ok_parse)

    if not all(c[1] for c in checks):
        print("\n✗ 门禁未全过，不写输出")
        return 1

    dest = pathlib.Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(edited))
    print(f"\n✓ 全部门禁通过，明文写入 {dest}（{len(edited):,} B）")
    print("下一步：tools/dlbin_seal.py seal-key 封装 → tools/dlbin_deploy.py install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
