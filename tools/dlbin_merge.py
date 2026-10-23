#!/usr/bin/env python3
"""dlbin_merge.py -- 把多个改同一份 `.dl_bin` 的 mod 合并成一个文件（保内容哈希）。

问题
    每个 mod 都整份替换 `generated_entities.dl_bin`（47 MB）。两个 mod 装同一份文件时，
    后装的覆盖先装的 —— 它们的改动**其实互不冲突**，只是没人去做并集。

做法
    一个 mod 的语义 = 「相对原版的稀疏字节改写」。本工具：
      1. 以原版明文为基底；把每个 mod 解开成明文（明文文件直接读，封包用 --key）
      2. **校验每个 mod 的明文 MurmurHash64A == 原版值**（这是「守规矩的保哈希 mod」的强证据；
         不相等说明它改过长度/换了哈希，直接拒绝，不猜）
      3. 逐字节 diff → 得到该 mod 的改动集合
      4. **剔除哈希脚手架**：末块的 payload 尺寸字段、以及原版长度之后的追加区（内含校正字）
      5. 取所有改动的并集；**逐字节**判冲突（同一偏移被写成不同值 ⇒ 冲突，默认中止）
      6. 重新做一次 tail 宿主、解出**一个**校正字，跑 9 道门禁
    合并结果与「直接一次改完所有字段」**逐字节相同**（已验证）。

用法
    python tools/dlbin_merge.py --vanilla vanilla.plain \\
        --mod a.dl_bin --mod b.dl_bin --key refs/dlbin/keys/recipient.sk \\
        --out merged.plain [--seal --pk refs/dlbin/keys/recipient.pk]
    python tools/dlbin_merge.py --vanilla vanilla.plain --mod a.plain --mod b.plain --report-only

输入可以是明文（`*_entities.plain` 这类）或封包（自动识别；封包需要 `--key`）。
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from murmur64 import murmur64, padding_word_for_hash    # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                      # noqa: BLE001
        pass

TAIL = 8
HEADER_EPK_TAG = 48          # libsodium sealed box 头


# ------------------------------------------------------------------ 容器
def parse_any(data: bytes):
    """返回 (kind, blocks)。两种容器都认：

    实体库  [u32 type]['LDLD'][u32 ver][u32 type][u32 payload][u8 wide][7 rsv] payload
    设置表  [u32 组数] { ['LDLD'][ver][type][payload][wide][4 rsv] payload }*
    blocks 元素 = {head, header, payload, size}
    """
    # 实体库：第 0 块以 type id 开头，'LDLD' 在 +4
    if len(data) >= 8 and data[4:8] == b"LDLD":
        out, pos = [], 0
        while pos + 28 <= len(data):
            if data[pos + 4:pos + 8] != b"LDLD":
                break
            tid = struct.unpack_from("<I", data, pos)[0]
            ver, inner, payload = struct.unpack_from("<III", data, pos + 8)
            if ver != 1 or inner != tid or pos + 28 + payload > len(data):
                break
            out.append({"head": pos, "header": 28, "size": payload})
            pos += 28 + payload
            # 块间可能有 ≤4 B 空档
            while pos < len(data) and pos + 8 <= len(data) and data[pos + 4:pos + 8] != b"LDLD":
                pos += 4
        return "entities", out
    # 设置表：开头 u32 组数，每块 'LDLD' 打头
    if len(data) >= 28 and data[4:8] == b"LDLD":
        n = struct.unpack_from("<I", data, 0)[0]
        out, pos = [], 4
        for _ in range(n):
            if data[pos:pos + 4] != b"LDLD":
                break
            ver, tid, payload = struct.unpack_from("<III", data, pos + 4)
            out.append({"head": pos, "header": 24, "size": payload})
            pos += 24 + payload
        return "settings", out
    raise ValueError("两种容器形状都不匹配")


def payload_field_offset(kind: str, blk: dict) -> int:
    """块头里 payload 尺寸字段的绝对偏移（改长度时要同步它）。"""
    return blk["head"] + (16 if kind == "entities" else 12)


# ------------------------------------------------------------------ 解封
def load_plain(path: pathlib.Path, key_path, label: str) -> bytes:
    raw = path.read_bytes()
    try:
        parse_any(raw)
        return raw
    except ValueError:
        pass
    if raw[:4] == b"LDLD" or raw[4:8] == b"LDLD":
        return raw
    if not key_path:
        raise SystemExit(f"✗ {label}（{path}）看起来是封包，需要 --key 指定 recipient.sk")
    from nacl.public import PrivateKey, SealedBox
    plain = SealedBox(PrivateKey(pathlib.Path(key_path).read_bytes())).decrypt(raw)
    print(f"  {label}: 解封 {len(raw):,} → {len(plain):,} B")
    return plain


# ------------------------------------------------------------------ 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="合并多个改同一份 .dl_bin 的 mod（保哈希）")
    ap.add_argument("--vanilla", required=True, help="原版明文（或封包）")
    ap.add_argument("--mod", action="append", default=[], required=True)
    ap.add_argument("--key", default=None, help="recipient.sk，用于解封")
    ap.add_argument("--out", default=None)
    ap.add_argument("--seal", action="store_true")
    ap.add_argument("--pk", default=None, help="recipient.pk，--seal 时必需")
    ap.add_argument("--report-only", action="store_true", help="只报告改动与冲突，不写文件")
    ap.add_argument("--on-conflict", choices=["abort", "after"], default="abort",
                    help="冲突时：abort（默认）或 after（后来的 mod 覆盖，并记录）")
    a = ap.parse_args()

    vanilla = load_plain(pathlib.Path(a.vanilla), a.key, "vanilla")
    vkind, vblocks = parse_any(vanilla)
    h0 = murmur64(vanilla)
    print(f"原版 {len(vanilla):,} B  容器={vkind}  块 {len(vblocks)}  Murmur 0x{h0:016X}")

    # 脚手架区域：末块 payload 尺寸字段 + 原版长度之后的一切
    last = vblocks[-1]
    scaffold = set(range(payload_field_offset(vkind, last), payload_field_offset(vkind, last) + 4))

    edits = {}          # offset -> (byte, mod_name)
    conflicts = []
    per_mod = []
    for spec in a.mod:
        path = pathlib.Path(spec)
        mod = load_plain(path, a.key, path.name)
        if len(mod) < len(vanilla):
            raise SystemExit(f"✗ {path.name} 比原版短（{len(mod)} < {len(vanilla)}），拒绝合并")
        if murmur64(mod) != h0:
            raise SystemExit(f"✗ {path.name} 的明文 Murmur 0x{murmur64(mod):016X} != 原版 0x{h0:016X}；"
                             f"它不是守规矩的保哈希 mod（改长度或换哈希），拒绝猜")
        if len(mod) > len(vanilla):
            print(f"  {path.name}: 检测到 tail 宿主（追加 {len(mod) - len(vanilla)} B，已忽略）")
        diff = [i for i in range(len(vanilla)) if vanilla[i] != mod[i]]
        real = [i for i in diff if i not in scaffold]
        skipped = [i for i in diff if i in scaffold]
        runs, start, prev = [], None, None
        for i in real:
            if start is None:
                start = i
            elif i != prev + 1:
                runs.append((start, prev))
                start = i
            prev = i
        if start is not None:
            runs.append((start, prev))
        per_mod.append((path.name, len(real), len(skipped), len(runs)))
        for i in real:
            if i in edits and edits[i][0] != mod[i]:
                conflicts.append((i, edits[i][1], edits[i][0], path.name, mod[i]))
                if a.on_conflict == "after":
                    edits[i] = (mod[i], path.name)
            else:
                edits.setdefault(i, (mod[i], path.name))
        print(f"  {path.name}: 真实改动 {len(real)} B / {len(runs)} 段；"
              f"脚手架 {len(skipped)} B 已剔除")

    print(f"\n合并结果：{len(edits)} 个字节，来自 {len(a.mod)} 个 mod")
    print(f"  {'mod':38s} {'改动B':>7} {'脚手架':>7} {'段数':>5}")
    for nm, r, s, n in per_mod:
        print(f"  {nm:38s} {r:7d} {s:7d} {n:5d}")

    if conflicts:
        print(f"\n⚠ 冲突 {len(conflicts)} 字节"
              f"（{'已按后来的 mod 覆盖' if a.on_conflict == 'after' else '默认中止'}）：")
        for off, m1, b1, m2, b2 in conflicts[:12]:
            print(f"  0x{off:07X}: {m1}=0x{b1:02X}  vs  {m2}=0x{b2:02X}")
        if a.on_conflict == "abort":
            print("\n✗ 有冲突，未写输出。确认要「后者覆盖」请加 --on-conflict after")
            return 1

    if a.report_only:
        print("\n（--report-only，未写输出）")
        return 0

    merged = bytearray(vanilla)
    for off, (b, _m) in edits.items():
        merged[off] = b
    pad = (8 - len(vanilla) % 8) % 8
    tail_len = pad + TAIL
    word_at = len(vanilla) + pad
    struct.pack_into("<I", merged, payload_field_offset(vkind, last), last["size"] + tail_len)
    merged += bytes(tail_len)
    merged[word_at:word_at + TAIL] = padding_word_for_hash(bytes(merged), word_at, h0)
    print(f"tail 宿主：末块 payload {last['size']} → {last['size'] + tail_len}，"
          f"校正字 @0x{word_at:X}，长度 {len(vanilla):,} → {len(merged):,}")

    checks = []

    def check(tag, ok, detail=""):
        checks.append(ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {tag}{('  ' + detail) if detail else ''}")

    got = murmur64(bytes(merged))
    check("G1 长度 = 原长 + pad + 8", len(merged) == len(vanilla) + tail_len)
    check("G2 重算哈希 == 原版哈希", got == h0, f"0x{got:016X}")
    check("G3 每个 mod 的改动都已落地",
          all(bytes(merged)[off] == b for off, (b, _m) in edits.items()), f"{len(edits)} B")
    check("G4 未改动的字节未被碰",
          all(merged[i] == vanilla[i] for i in range(len(vanilla)) if i not in edits
              and i != payload_field_offset(vkind, last)), "")
    try:
        _, mblocks = parse_any(bytes(merged))
        ok = len(mblocks) == len(vblocks) and mblocks[-1]["size"] == last["size"] + tail_len
        detail = f"{len(mblocks)} 块，末块 payload {mblocks[-1]['size']}"
    except Exception as exc:                                   # noqa: BLE001
        ok, detail = False, str(exc)
    check("G5 容器重解析自洽", ok, detail)

    if not all(checks):
        print("\n✗ 门禁未全过，不写输出")
        return 1
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(merged))
    print(f"\n✓ 合并完成 → {out}（{len(merged):,} B，Murmur 0x{h0:016X}）")

    if a.seal:
        if not a.pk:
            raise SystemExit("✗ --seal 需要 --pk")
        import subprocess
        sealed = out.with_name(out.name.replace(".plain", "") + ".dl_bin")
        cmd = [sys.executable, str(HERE / "dlbin_seal.py"), "seal-key",
               str(out), "--key", a.pk, "--out", str(sealed)]
        print(f"\n封装 → {sealed}")
        if subprocess.run(cmd).returncode:
            raise SystemExit("✗ 封装失败")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
