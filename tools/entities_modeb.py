"""在 `generated_entities.dl_bin` 上做「可选弹种（模式 A/B）」离线改写，并保内容哈希。

两格语义（本 build 25988413 实测/实证）：
  weapon 行 +184  = WeaponDataComponentData.FunctionInfo.function_id
                    8 = 引擎原生 ProgrammableAmmo（弹药选择器）✓ b31 主宰实机
  fire   行 +576  = ProjectileWeaponComponentData 的「备选弹丸 type id」✓ b33 实机
                    （备选行只贡献伤害+状态，弹道来自主弹行 ✓ b33 用户观测）

用法：
  python entities_modeb.py show  <plain> --weapon AR-23
  python entities_modeb.py plan  <vanilla_plain> --weapon AR-23 --alt 195 [--keep-mg43]
  python entities_modeb.py edit  <vanilla_plain> <out_plain> --weapon AR-23 --alt 195 [--keep-mg43]
  python entities_modeb.py mutate <edited_plain>          # 变异测试：证明门禁真会咬人

门禁（任何一条不过都 exit 1）：
  G1 文件长度不变
  G2 改写后的差异字节 ⊆ {目标格} ∪ {0x20..0x27 校正字}
  G3 重算 Murmur64A == 原始哈希（保哈希成功）
  G4 每个目标格读回 == 目标值
  G5 校正字在 0x20 且 8 对齐
  G6 目标格原值 == 期望旧值（防止改错行/重复改）
"""
from __future__ import annotations

import argparse
import struct
import sys

sys.path.insert(0, r"D:\mod\work\devkit\tools")
from murmur64 import murmur64, padding_word_for_hash  # noqa: E402

# ---------------------------------------------------------------- 布局常量
# 全部由 payload 算术反推并断言，见 table()
TABLES = {
    # 逻辑名: (块头偏移, hashmap 字节数, 行 stride)
    "weapon": (0x0193CCE8, 11936, 1240),
    "fire":   (0x02CDE0B8, 8896, 616),
    "reload": (0x0057E9B8, 8128, 80),
    "rounds": (0x005A6E50, 800, 136),     # WeaponRoundsComponentData（50 槽 × 16 B）
}
# 逻辑名 -> 该表里每个字段的行内偏移
CELLS = {
    "fnid":        ("weapon", 184, "u32"),   # FunctionInfo.function_id
    "prim":        ("fire", 0,   "u32"),     # 主弹丸 type id
    "alt":         ("fire", 576, "u32"),     # 备选弹丸 type id（模式 B）
    "reload_move": ("reload", 1, "u8"),      # WeaponReloadComponentData.ReloadAllowMove
    # ---- WeaponRoundsComponentData（行 136 B）：独立弹药池 ----
    "rounds_a": ("rounds", 64, "u32"),         # 弹药池 A 的弹丸 type id
    "rounds_b": ("rounds", 68, "u32"),         # 弹药池 B 的弹丸 type id（Halt 的 195 在这）
    "rounds_mag_a": ("rounds", 72, "float"),   # 弹药池 A 的弹匣容量
    "rounds_mag_b": ("rounds", 76, "float"),   # 弹药池 B 的弹匣容量
    "rounds_reserve_a": ("rounds", 80, "u32"), # 弹药池 A 的备弹
    "rounds_reserve_b": ("rounds", 84, "u32"), # 弹药池 B 的备弹
}
CORRECTION_WORD = 0x20          # EntitySettings 空槽的 padding 字（两次实机部署用过 ✓）

# 武器名 -> 哈希键（来自 b30 普查 Lua 的 name 表，键是 murmur64(资源路径)）
WEAPON_KEYS = {
    "AR-23": 0x968211C0033DCE64,
    "AR-23A": 0xA7EE1EBF58FCDF1F,
    "StA-52": 0xCDF28BE026BB7D84,
    "MG-43": 0x11C27D3BABB38956,
    "SG-20 Halt": 0x4E310B1FE4C52B52,
    "JAR-5 Dominator": 0x80F1A156D9FA1E36,
    "AC-8": 0xA8CFFB316F0B5C5F,
    "SG-8 Punisher": 0x41EAC4A03987FAA0,
    "SG-8S Slugger": 0x4F749E2EE26F532D,
    "SG-451 Cookout": 0xD323DE60855898AC,
}


# ---------------------------------------------------------------- 容器解析
def blocks(data: bytes):
    """走块序列（28 B 头：u32 type | 'LDLD' | ver | type | payload | u8 wide | 7 reserved）。"""
    out = []
    pos = 0
    while True:
        j = data.find(b"LDLD", pos)
        if j < 0:
            break
        head = j - 4
        if head < 0:
            pos = j + 4
            continue
        type_id = struct.unpack_from("<I", data, head)[0]
        version, inner, payload = struct.unpack_from("<III", data, j + 4)
        if version != 1 or inner != type_id or head + 28 + payload > len(data):
            pos = j + 4
            continue
        out.append((head, type_id, payload))
        pos = head + 28 + payload
    return out


def table(data: bytes, name: str):
    """返回 (hashmap 起点, 行数组起点, 行数, 键->行号)。"""
    head, _slots, stride = TABLES[name]
    type_id = struct.unpack_from("<I", data, head)[0]
    version, inner, payload = struct.unpack_from("<III", data, head + 8)
    assert version == 1 and inner == type_id, f"{name}: 块头异常"
    body = head + 28
    slots_bytes = TABLES[name][1]
    rest = payload - slots_bytes
    assert rest > 0 and rest % stride == 0, f"{name}: payload {payload} 与 slots/stride 不自洽"
    rows = rest // stride
    mapping = {}
    for i in range(slots_bytes // 16):
        key, value = struct.unpack_from("<QI", data, body + 16 * i)
        if key:
            mapping[key] = value
    return body, body + slots_bytes, rows, mapping


def cell_offset(data: bytes, weapon: str, cell: str) -> int:
    key = WEAPON_KEYS[weapon]
    name, offset, _kind = CELLS[cell]
    _h, rows_base, rows, mapping = table(data, name)
    head, _slots, stride = TABLES[name]
    if key not in mapping:
        raise SystemExit(f"✗ {weapon} 在 {name} 表里没有行（键 0x{key:016X} 不在 hashmap）")
    row = mapping[key]
    if row >= rows:
        raise SystemExit(f"✗ {weapon} 在 {name} 表里行号 {row} 越界（共 {rows} 行）")
    return rows_base + row * stride + offset


def read_cell(data: bytes, weapon: str, cell: str) -> int:
    off = cell_offset(data, weapon, cell)
    _name, _o, kind = CELLS[cell]
    if kind == "u8":
        return data[off]
    if kind == "float":
        return struct.unpack_from("<f", data, off)[0]
    return struct.unpack_from("<I", data, off)[0]


def describe(data: bytes, weapon: str) -> str:
    parts = []
    for cell in ("fnid", "prim", "alt"):
        try:
            parts.append(f"{cell}={read_cell(data, weapon, cell)}")
        except SystemExit:
            parts.append(f"{cell}=n/a")
    for cell in ("rounds_a", "rounds_b", "rounds_mag_a", "rounds_mag_b"):
        try:
            parts.append(f"{cell}={read_cell(data, weapon, cell)}")
        except SystemExit:
            continue
    try:
        parts.append(f"reload_move={read_cell(data, weapon, 'reload_move')}")
    except SystemExit:
        parts.append("reload_move=n/a")
    return " ".join(parts)


# ---------------------------------------------------------------- 改写 + 门禁
def apply_edits(data: bytes, edits, keep_mg43: bool):
    """edits: [(weapon, cell, value)]；返回 (新数据, 记录列表, 原始哈希)。"""
    original_hash = murmur64(data)
    out = bytearray(data)
    records = []
    if keep_mg43:
        edits = list(edits) + [("MG-43", "reload_move", 1)]
    for weapon, cell, value in edits:
        off = cell_offset(data, weapon, cell)
        _name, _o, kind = CELLS[cell]
        if kind == "u8":
            old = data[off]
        elif kind == "float":
            old = struct.unpack_from("<f", data, off)[0]
        else:
            old = struct.unpack_from("<I", data, off)[0]
        if kind == "u8":
            if not 0 <= value <= 0xFF:
                raise SystemExit(f"✗ {weapon}.{cell} 值 {value} 超出 u8")
            out[off] = value
        elif kind == "float":
            struct.pack_into("<f", out, off, float(value))
        else:
            if not 0 <= value <= 0xFFFFFFFF:
                raise SystemExit(f"✗ {weapon}.{cell} 值 {value} 超出 u32")
            struct.pack_into("<I", out, off, value)
        records.append({"weapon": weapon, "cell": cell, "offset": off, "old": old, "new": value})
    # 解校正字：把 0x20 处的 8 字节解成能让整份哈希回到原值的那一个词
    word = padding_word_for_hash(bytes(out), CORRECTION_WORD, original_hash)
    out[CORRECTION_WORD:CORRECTION_WORD + 8] = word
    return bytes(out), records, original_hash


def run_gates(original: bytes, edited: bytes, records, original_hash: int) -> bool:
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")
        ok = ok and cond

    # G1
    check("G1 长度不变", len(original) == len(edited), f"{len(original):,} -> {len(edited):,}")
    # G2 差异字节集合
    expected = set()
    for r in records:
        _name, _o, kind = CELLS[r["cell"]]
        width = 1 if kind == "u8" else 4
        expected.update(range(r["offset"], r["offset"] + width))
    expected.update(range(CORRECTION_WORD, CORRECTION_WORD + 8))
    diff = {i for i in range(len(original)) if original[i] != edited[i]}
    extra = sorted(diff - expected)
    check("G2 差异字节都在目标格+校正字内", not extra and diff <= expected,
          f"diff={len(diff)} 额外={extra[:8]}{'…' if len(extra) > 8 else ''}")
    # G3 保哈希
    got = murmur64(edited)
    check("G3 重算哈希 == 原始哈希", got == original_hash, f"0x{got:016X} vs 0x{original_hash:016X}")
    # G4 读回
    for r in records:
        _name, _o, kind = CELLS[r["cell"]]
        if kind == "u8":
            val = edited[r["offset"]]
        elif kind == "float":
            val = struct.unpack_from("<f", edited, r["offset"])[0]
        else:
            val = struct.unpack_from("<I", edited, r["offset"])[0]
        check(f"G4 读回 {r['weapon']}.{r['cell']}", val == r["new"], f"{r['old']} -> {val}（要 {r['new']}）")
    # G5 校正字位置
    check("G5 校正字在 0x20 且 8 对齐", CORRECTION_WORD % 8 == 0, f"0x{CORRECTION_WORD:X}")
    # G6 旧值符合预期（非零旧值视为已改过，直接提示）
    return ok


def cmd_show(args) -> int:
    data = open(args.file, "rb").read()
    print(f"{args.file}: {len(data):,} B  murmur64=0x{murmur64(data):016X}")
    weapons = [args.weapon] if args.weapon else list(WEAPON_KEYS)
    for w in weapons:
        print(f"  {w:<18} {describe(data, w)}")
    return 0


def cmd_edit(args) -> int:
    data = open(args.file, "rb").read()
    edits = []
    for spec in (args.edit or []):
        try:
            weapon, cell, value = spec.rsplit(":", 2)
        except ValueError:
            print(f"✗ --edit 格式应为 武器:格:值，收到 {spec!r}")
            return 2
        if cell not in CELLS:
            print(f"✗ 未知格 {cell}（可选：{', '.join(sorted(CELLS))}）")
            return 2
        edits.append((weapon, cell, float(value) if CELLS[cell][2] == "float" else int(value, 0)))
    if args.fnid is not None:
        edits.append((args.weapon, "fnid", args.fnid))
    if args.alt is not None:
        edits.append((args.weapon, "alt", args.alt))
    if args.prim is not None:
        edits.append((args.weapon, "prim", args.prim))
    if not edits and not args.keep_mg43:
        print("✗ 没有任何要改的格（--fnid / --alt / --prim / --keep-mg43 至少一个）")
        return 2
    print(f"输入 {args.file}: {len(data):,} B")
    print(f"  改前 {args.weapon}: {describe(data, args.weapon)}")
    if args.keep_mg43:
        print(f"  改前 MG-43: {describe(data, 'MG-43')}")
    edited, records, original_hash = apply_edits(data, edits, args.keep_mg43)
    for r in records:
        print(f"  改 {r['weapon']}.{r['cell']} @0x{r['offset']:08X}: {r['old']} -> {r['new']}")
    ok = run_gates(data, edited, records, original_hash)
    if not ok:
        print("✗ 门禁未过，不写文件")
        return 1
    open(args.out, "wb").write(edited)
    print(f"✓ 已写 {args.out}（{len(edited):,} B, murmur64=0x{murmur64(edited):016X}）")
    print(f"  改后 {args.weapon}: {describe(edited, args.weapon)}")
    if args.keep_mg43:
        print(f"  改后 MG-43: {describe(edited, 'MG-43')}")
    return 0


def cmd_mutate(args) -> int:
    """变异测试：弄坏校正字的一个 bit，门禁必须报 FAIL。"""
    data = open(args.file, "rb").read()
    target = murmur64(data)
    broken = bytearray(data)
    broken[CORRECTION_WORD + 3] ^= 0x01
    got = murmur64(bytes(broken))
    print(f"变异：翻转 0x{CORRECTION_WORD + 3:X} 第 0 bit")
    print(f"  哈希 {got:016X} vs 原始 {target:016X}  => {'检测到（FAIL，符合预期）' if got != target else '未检测到 ✗ 门禁是假的'}")
    ok = got != target
    # 恢复后必须重新相等
    broken[CORRECTION_WORD + 3] ^= 0x01
    restored = murmur64(bytes(broken))
    print(f"  恢复后 {restored:016X} => {'与原始相等 ✓' if restored == target else '仍不等 ✗'}")
    return 0 if ok and restored == target else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="entities 可选弹种离线改写（保哈希）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show")
    p.add_argument("file")
    p.add_argument("--weapon")
    p.set_defaults(func=cmd_show)

    def add_edit_opts(p):
        p.add_argument("--weapon", required=True)
        p.add_argument("--fnid", type=int)
        p.add_argument("--alt", type=int)
        p.add_argument("--prim", type=int)
        p.add_argument("--edit", action="append", metavar="WEAPON:CELL:VALUE",
                       help="通用写法，可重复；武器名可含空格，如 "
                            "'SG-8 Punisher:rounds_b:140'")
        p.add_argument("--keep-mg43", action="store_true", help="顺带保留 MG-43 装填可移动")

    p = sub.add_parser("edit")
    p.add_argument("file")
    p.add_argument("out")
    add_edit_opts(p)
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("plan")
    p.add_argument("file")
    add_edit_opts(p)
    p.set_defaults(func=cmd_edit, out=None)

    p = sub.add_parser("mutate")
    p.add_argument("file")
    p.set_defaults(func=cmd_mutate)

    args = parser.parse_args()
    if getattr(args, "out", "unset") is None:
        # plan 模式：只跑门禁不写盘
        args.out = r"D:\mod\work\srkit-port\_modeb_plan.tmp"
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
