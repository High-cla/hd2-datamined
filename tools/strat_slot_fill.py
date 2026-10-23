#!/usr/bin/env python3
"""strat_slot_fill.py -- 把「包」填进战备行的**空声明槽**，保住内容哈希。

背景
    `StratagemSettings` 每行两个装包口：`+0xA8`（u64，任意 toc 包 id）与 `+0xF8`
    （u32，一个有 `LoadoutEntry` 条目的物品 id ⇒ 间接装它的包）。
    原版 153 行里 **133 行没填满**（存量 155 个空槽）：两槽全空 22 行、仅 `+0xA8` 空 17 行、
    仅 `+0xF8` 空 94 行。这张表由 `tools/strat_slot_census.py` 现算，不在这里硬编码。

这个工具做的事
    名字（或 idx） → 在普查里找到那一行 → 确认目标槽**原本是空的** → 把值算成文件绝对偏移，
    **一次** `plain_edit.py` 写完全部行（只追加一个 tail 宿主 + 一个校正字）→ 读回验证 → 可选封装。

为什么默认拒绝覆盖已占用的槽
    已占用的槽是那发战备自己的载荷声明；覆盖它等于换掉它的资产包（紫问号风险）。
    真要做就显式 `--force`，并且先想清楚为什么要顶掉原版。

同名多行会一起写
    本 build 的战备表是 12 个块（12 个战备池），同一发战备可能出现在多个块里
    （`Reinforce` 在 `0x6fdc`/`0x1247c`、`Resupply` 在 `0x1c50`/`0xb6ec`…）。
    只改其中一行很可能改到不被使用的那个池 —— 所以默认**同名全改**，`--only-idx` 才单改。

用法
    python tools/strat_slot_fill.py --list
    python tools/strat_slot_fill.py --name "SOS Beacon" --a8 0x68F670405A504F68 \\
        --out out/stratagem.plain
    python tools/strat_slot_fill.py --idx 59 --a8 0x68F670405A504F68 --out out/s.plain --seal

门禁
    G1 目标槽原本为空（除非 --force）      G2 只改声明的偏移
    G3 每个值读回 == 目标                G4 重算 Murmur 由 plain_edit 保证（它自己带 G1–G6）
    G5 行身份字段（+0 id）未变
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pod_loadout import Data, STRAT_PLAIN, OFF_A8, OFF_F8          # noqa: E402
from strat_slot_census import census, slot_class, CLASS_CN        # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                             # noqa: BLE001
        pass


def _labels(r: dict) -> list[str]:
    """可用来选行的名字：行内自带的内部名（可靠）+ 外部名单的显示名（个别行贴错，只当别名）。"""
    return [x for x in (r.get("name"), r.get("display")) if x]


def pick(rows: list[dict], name: str, idx: int | None) -> list[dict]:
    if idx is not None:
        if not 0 <= idx < len(rows):
            raise SystemExit(f"✗ idx 必须在 0..{len(rows) - 1}")
        return [rows[idx]]
    if not name:
        raise SystemExit("✗ 需要 --name 或 --idx")
    needle = name.strip().lower()
    # 先按**全名精确**匹配；没有再退回子串。否则 "Machine Gun" 会连
    # "Heavy Machine Gun" / "Machine Gun Sentry" 一起改掉（那是别的战备自己的声明）
    exact = [r for r in rows if any(l.strip().lower() == needle for l in _labels(r))]
    if exact:
        return exact
    hits = [r for r in rows if any(needle in l.lower() for l in _labels(r))]
    if not hits:
        hits = [r for r in rows if needle in str(r["idx"])]
    if not hits:
        raise SystemExit(f"✗ 没有名字含 {name!r} 的行；用 --list 看全表")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="把包填进战备行的空声明槽（保内容哈希）")
    ap.add_argument("--list", action="store_true", help="列出所有有空槽的行后退出")
    ap.add_argument("--free", action="store_true", help="配合 --list：只列有空槽的行（默认就是）")
    ap.add_argument("--name", default="", help="战备显示名子串（同名行全部一起改）")
    ap.add_argument("--idx", type=int, default=None, help="按普查 idx 精确指定单行")
    ap.add_argument("--a8", default=None, help="填进 +0xA8 的 toc 包 id（u64，可写 0x 或十进制）")
    ap.add_argument("--f8", default=None, help="填进 +0xF8 的 LoadoutEntry 条目 id（u32）")
    ap.add_argument("--fill", action="append", default=[],
                    help="多目标写法，可重复：'名字子串::a8=0x..' 或 '名字子串::f8=0x..'\n"
                         "（两个槽要一起写就用逗号：'名字::a8=0x...,f8=0x...'）。给了 --fill 就忽略 --name/--idx")
    ap.add_argument("--force", action="store_true", help="允许覆盖已占用的槽（危险）")
    ap.add_argument("--plain", default=str(STRAT_PLAIN), help="输入明文（默认本 build 的缓存）")
    ap.add_argument("--out", default="out/stratagem.plain", help="输出明文路径")
    ap.add_argument("--seal", action="store_true", help="顺带封装成 generated_stratagem_settings.dl_bin")
    ap.add_argument("--pk", default=r"D:\mod\refs\dlbin\keys\recipient.pk", help="封装公钥")
    a = ap.parse_args()

    d = Data()
    rows = census(d)

    if a.list or (a.a8 is None and a.f8 is None and not a.fill):
        print(f"{'idx':>3} {'行基址':>8} {'+0xA8':>20} {'+0xF8':>12} {'类别':<12} 名字")
        for r in rows:
            if slot_class(r) == "full":
                continue
            print(f"{r['idx']:>3} {r['row_base']:#8x} "
                  f"{('0x%016X' % r['a8']) if r['a8'] else '0':>20} "
                  f"{('0x%08X' % r['f8']) if r['f8'] else '0':>12} "
                  f"{CLASS_CN[slot_class(r)]:<12} {r['name'] or '未知'}")
        return 0

    # 归一成 [(row, 'a8'|'f8', value)] 再统一过门禁
    jobs: list[tuple[dict, str, int]] = []
    specs = [(a.name, a.a8, a.f8)] if a.fill == [] else []
    for spec in a.fill:
        if "::" not in spec:
            raise SystemExit(f"✗ --fill 要写成 '名字::字段=值'，收到 {spec!r}")
        nm, rest = spec.split("::", 1)
        got = {"a8": None, "f8": None}
        for part in rest.split(","):
            if "=" not in part:
                raise SystemExit(f"✗ --fill 的字段段要写成 字段=值，收到 {part!r}")
            k, v = part.split("=", 1)
            k = k.strip().lower().removeprefix("+0x").removeprefix("0x")
            if k not in got:
                raise SystemExit(f"✗ --fill 只认 a8 / f8，收到 {k!r}")
            got[k] = v
        specs.append((nm, got["a8"], got["f8"]))

    for nm, a8v, f8v in specs:
        if a8v is None and f8v is None:
            continue
        for r in pick(rows, nm or "", a.idx if len(specs) == 1 else None):
            if a8v is not None:
                jobs.append((r, "a8", int(a8v, 0)))
            if f8v is not None:
                jobs.append((r, "f8", int(f8v, 0) & 0xFFFFFFFF))

    sets, notes, plan = [], [], []
    for r, field, val in jobs:
        cur = r[field]
        if cur and not a.force:
            raise SystemExit(f"✗ idx {r['idx']} 的 +0x{field.upper()} 已占用（0x{cur:0{16 if field == 'a8' else 8}X}）；"
                             f"覆盖会顶掉它自己的申报，确要盖请加 --force")
        if val == cur:
            print(f"  (跳过 idx {r['idx']} +0x{field.upper()}：值与原值相同)")
            continue
        off = r["row_base"] + (OFF_A8 if field == "a8" else OFF_F8)
        width = 8 if field == "a8" else 4
        sets.append((off, width, val))
        plan.append((r["idx"], field, val))
        notes.append(f"idx {r['idx']} +0x{field.upper()} @{off:#x}: "
                     f"0x{cur:0{width * 2}X} -> 0x{val:0{width * 2}X}")

    if not sets:
        raise SystemExit("✗ 没有实际改动（值与原值相同？）")

    print(f"目标 {len(plan)} 处 / {len({p[0] for p in plan})} 行")
    for n in notes:
        print("  " + n)

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(HERE / "plain_edit.py"), "--plain", a.plain, "--out", str(out)]
    for off, width, val in sets:
        kind = "u64" if width == 8 else "u32"
        cmd += ["--set", f"{off}={kind}:{val}"]
    print("\n写入：", " ".join(cmd[2:]))
    sys.stdout.flush()
    if subprocess.run(cmd).returncode:
        raise SystemExit("✗ plain_edit 门禁未过")

    # 读回验证：用同一个解析器重新普查输出文件
    d2 = Data()
    d2.strat = out.read_bytes()
    rows2 = census(d2)
    for idx, field, val in plan:
        got = rows2[idx][field]
        if got != val:
            raise SystemExit(f"✗ 读回不一致 idx {idx} {field}: 期望 {val:#x} 实得 {got:#x}")
        print(f"  PASS  读回 idx {idx} {field} = {val:#x}")
    ids_ok = all(x["strat_id"] == y["strat_id"] for x, y in zip(rows, rows2))
    print(f"  {'PASS' if ids_ok else 'FAIL'}  153 行 +0 id 未变")
    if not ids_ok:
        raise SystemExit("✗ 行身份被破坏")

    sealed = None
    if a.seal:
        pk = pathlib.Path(a.pk)
        if not pk.is_file():
            raise SystemExit(f"✗ 找不到封装公钥 {pk}")
        sealed = out.with_name("generated_stratagem_settings.dl_bin")
        rc = subprocess.run([sys.executable, str(HERE / "dlbin_seal.py"), "seal-key",
                             str(out), "--key", str(pk), "--out", str(sealed)]).returncode
        if rc:
            raise SystemExit("✗ 封装失败")
        print(f"✓ 封装 {sealed}")

    print(f"\n✓ 明文 {out}")
    if sealed:
        print("部署（确认游戏已关闭）：")
        print(f"  python tools/dlbin_deploy.py install --file generated_stratagem_settings.dl_bin "
              f"--sealed {sealed}")
        print("回滚：python tools/dlbin_deploy.py restore --file generated_stratagem_settings.dl_bin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
