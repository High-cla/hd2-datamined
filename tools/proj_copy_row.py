"""把一条射弹行的**整个弹头**（272 B）拷到另一条射弹行上，并保内容哈希。

这是 b21/b9 那条老配方的离线版：`copied 272 B from R-36 Eruptor onto JAR-5 Dominator
(68/68 dwords match, target type kept=true)`。

文件：`data/game/generated_projectile_settings.dl_bin`
  明文 96,604 B = u32 组数(1) + LDLD 头(24) + 数组描述符(16) + 355 行 × 272 B
  内容哈希闸门：Murmur64A(明文) == 946A4FE5FAAAE076（game.dll 烘焙）

校正字：射弹表行间没有 padding，文件尾也没有余量 ⇒
  和伤害表一样，用**一条无主射弹行**里的一个「8 字节对齐的全零字」承载。
  注意：行基址 ≡ 4 (mod 8) ⇒ 行内 8 对齐偏移只能是 4、12、20、…

用法：
  python proj_copy_row.py --plain <vanilla_projectile_plain> \
      --source-type 41 --target-type 180 \
      --host-type 291 --host-offset 0x44 --out <out_plain>

门禁：G1 长度不变 · G2 差异 ⊆ 目标行 ∪ 校正字 · G3 哈希回到原值
      G4 目标行 == 源行（除 +0 的 type id）· G5 宿主行除校正字外未变
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

for _stream in (sys.stdout, sys.stderr):          # Windows 控制台默认 GBK，不含 ✗/⚠
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass

from murmur64 import murmur64, padding_word_for_hash  # noqa: E402

EXPECTED_HASH = 0x946A4FE5FAAAE076   # game.dll 里 projectile 明文的内容哈希
STRIDE = 272
ARRAY_BASE = 44                      # 4 + 24 + 16


def rows_of(data: bytes):
    count = struct.unpack_from("<I", data, 0)[0]
    if count != 1:
        raise SystemExit(f"✗ 期望 1 个组，实际 {count}")
    if data[4:8] != b"LDLD":
        raise SystemExit("✗ 组头 magic 不对")
    array_off, rows, pad = struct.unpack_from("<QII", data, 28)
    if pad != 0:
        raise SystemExit(f"✗ 数组描述符 padding 非 0（{pad}）")
    base = 28 + array_off
    if base + rows * STRIDE != len(data):
        raise SystemExit(f"✗ 行数组不自洽：{base}+{rows}×{STRIDE} ≠ {len(data)}")
    return base, rows


def index_by_type(data: bytes, base: int, rows: int):
    table = {}
    for i in range(rows):
        t = struct.unpack_from("<I", data, base + i * STRIDE)[0]
        table[t] = i
    return table


def main() -> int:
    ap = argparse.ArgumentParser(description="整行弹头拷贝（保内容哈希）")
    ap.add_argument("--plain", required=True)
    ap.add_argument("--source-type", type=int, required=True)
    ap.add_argument("--target-type", type=int, required=True)
    ap.add_argument("--host-type", type=int, required=True, help="付校正字的无主射弹 type")
    ap.add_argument("--host-offset", required=True, help="宿主行内的 8 对齐偏移，如 0x44")
    ap.add_argument("--set", action="append", metavar="OFF:VALUE",
                    help="拷贝后在**目标行**里再写一个 u32，如 0x90:178（+144 命中爆炸）")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = open(args.plain, "rb").read()
    base, rows = rows_of(data)
    table = index_by_type(data, base, rows)
    for t in (args.source_type, args.target_type, args.host_type):
        if t not in table:
            raise SystemExit(f"✗ 射弹 type {t} 不存在")
    if len({args.source_type, args.target_type, args.host_type}) != 3:
        raise SystemExit("✗ 源/目标/宿主必须是三行不同的射弹")

    h0 = murmur64(data)
    print(f"明文 {len(data):,} B  hash=0x{h0:016X}" +
          ("  ✓ 与 game.dll 期望一致" if h0 == EXPECTED_HASH else "  ⚠ 与期望不一致（继续，但校正目标是这个值）"))

    src = base + table[args.source_type] * STRIDE
    dst = base + table[args.target_type] * STRIDE
    payload = bytearray(data[src:src + STRIDE])
    struct.pack_into("<I", payload, 0, args.target_type)   # 保留目标自己的 type id
    edited = bytearray(data)
    edited[dst:dst + STRIDE] = payload
    for spec in (args.set or []):
        try:
            off_s, val_s = spec.split(":")
            off, val = int(off_s, 0), int(val_s, 0)
        except ValueError:
            raise SystemExit(f"✗ --set 格式应为 OFFSET:VALUE，收到 {spec!r}")
        if not (0 <= off <= STRIDE - 4) or off % 4:
            raise SystemExit(f"✗ --set 偏移 {off:#x} 必须 4 对齐且在行内")
        if off < 4:
            raise SystemExit("✗ 不能改 +0（那是 type id）")
        old = struct.unpack_from("<I", edited, dst + off)[0]
        struct.pack_into("<I", edited, dst + off, val)
        print(f"  目标行 +{off:#x}: {old} -> {val}")
    print(f"源   row {table[args.source_type]:3d} (type {args.source_type}) @0x{src:X}")
    print(f"目标 row {table[args.target_type]:3d} (type {args.target_type}) @0x{dst:X}")

    host_off = int(args.host_offset, 0)
    if host_off % 8 != 4:
        raise SystemExit(f"✗ 宿主行内偏移必须 ≡ 4 (mod 8)（该表行基址 ≡ 4），收到 {host_off:#x}")
    host = base + table[args.host_type] * STRIDE + host_off
    cur = struct.unpack_from("<Q", edited, host)[0]
    if cur:
        # 上一次校正写进去的值也是语义惰性的（无主行），允许覆盖
        print(f"  提示：宿主 {host:#x} 原本非零（0x{cur:016X}，可能是上一轮校正字）→ 覆盖")
    word = padding_word_for_hash(bytes(edited), host, h0)
    edited[host:host + 8] = word
    print(f"校正字：宿主 type {args.host_type} 行内 +{host_off:#x} → 全部写入 0x{host:08X}")

    edited = bytes(edited)
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
        ok = ok and cond

    check("G1 长度不变", len(edited) == len(data), f"{len(data):,}")
    expected = set(range(dst, dst + STRIDE)) | set(range(host, host + 8))
    diff = {i for i in range(len(data)) if data[i] != edited[i]}
    check("G2 差异 ⊆ 目标行 ∪ 校正字", diff <= expected,
          f"diff={len(diff)} 域外={sorted(diff - expected)[:8]}")
    got = murmur64(edited)
    check("G3 重算哈希 == 原始哈希", got == h0, f"0x{got:016X} vs 0x{h0:016X}")
    set_offs = set()
    for spec in (args.set or []):
        set_offs.add(int(spec.split(":")[0], 0))
    mismatch = [o for o in range(4, STRIDE, 4)
                if o not in set_offs
                and edited[dst + o:dst + o + 4] != data[src + o:src + o + 4]]
    check("G4 目标行 == 源行（+0 与 --set 偏移除外）",
          not mismatch and struct.unpack_from("<I", edited, dst)[0] == args.target_type,
          f"意外差异 {mismatch[:6]}")
    check("G5 宿主行除校正字外未变",
          edited[host - host_off:host] == data[host - host_off:host]
          and edited[host + 8:host - host_off + STRIDE] == data[host + 8:host - host_off + STRIDE])

    if not ok:
        print("✗ 门禁未过，不写文件")
        return 1
    open(args.out, "wb").write(edited)
    print(f"✓ 已写 {args.out}（{len(edited):,} B, hash=0x{murmur64(edited):016X}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
