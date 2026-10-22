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
    "magazine": (0x000822B0, 8832, 160),  # WeaponMagazineComponentData（552 槽，行 160 B）
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
def drop_component_row(data: bytearray, weapon: str, table_name: str, records):
    """从某张组件表里删掉一个武器的条目（开放寻址表：整表重排，保证探测链仍然有效）。

    行数组不动（留成孤儿行），只重写 hashmap 区域 —— 这是「换模型」时用得上的操作。
    """
    key = WEAPON_KEYS[weapon]
    head, slots_bytes, stride = TABLES[table_name]
    body = head + 28
    n_slots = slots_bytes // 16
    pairs = []
    found = False
    for i in range(n_slots):
        k, v = struct.unpack_from("<QI", data, body + 16 * i)
        if not k:
            continue
        if k == key:
            found = True
            continue
        pairs.append((k, v))
    if not found:
        raise SystemExit(f"✗ {weapon} 在 {table_name} 表里没有条目，无从删除")
    # 重新插入（自然槽 + 线性探测），确定性顺序
    new = bytearray(slots_bytes)
    for k, v in sorted(pairs):
        j = k % n_slots
        for _ in range(n_slots):
            if struct.unpack_from("<Q", new, 16 * j)[0] == 0:
                struct.pack_into("<QII", new, 16 * j, k, v, 0)
                break
            j = (j + 1) % n_slots
        else:
            raise SystemExit(f"✗ {table_name} 重排时表满")
    old = bytes(data[body:body + slots_bytes])
    if bytes(new) == old:
        raise SystemExit("✗ 重排后与原来完全一致，删除没生效")
    data[body:body + slots_bytes] = new
    records.append({"label": f"{weapon}.{table_name} 条目删除（整表重排）", "offset": body,
                    "width": slots_bytes, "old": f"{len(pairs)+1} 键", "new": f"{len(pairs)} 键"})
    print(f"  {table_name}: 删除 {weapon}，重排后 {len(pairs)} 键")


def add_rounds_row(data: bytearray, weapon: str, a: int, b: int, mag: int, reserve: int,
                   template_weapon: str, records, starting: int | None = None):
    """给没有 WeaponRounds 行的武器新增一行（空行 + 空 hashmap 槽），文件长度不变。

    行结构（136 B）：+0 64B=16×float(1.0) · +64 弹丸A/B · +72 弹匣A/B(float)
    · +80 备弹A/B · +88/+92 未知常量 · +96 两个 float · +104 第二池开关(1=有)
    · +108 24B 六个 hash(弹种显示名) · +132 u8
    """
    key = WEAPON_KEYS[weapon]
    head, slots_bytes, stride = TABLES["rounds"]
    _body, rows_base, rows, mapping = table(data, "rounds")
    if key in mapping:
        raise SystemExit(f"✗ {weapon} 已经有 WeaponRounds 行（row {mapping[key]}），不需要新增")
    # hashmap 是「key % slots + 线性探测」的开放寻址表（本文件已验证 0 失败）
    # ⇒ 新键必须落在它的自然槽上，不能随便找个空槽
    body = head + 28
    n_slots = slots_bytes // 16
    natural = key % n_slots
    free_slot = None
    for step in range(n_slots):
        i = (natural + step) % n_slots
        if struct.unpack_from("<Q", data, body + 16 * i)[0] == 0:
            free_slot = i
            break
    if free_slot is None:
        raise SystemExit("✗ WeaponRounds hashmap 满（无空槽）")
    print(f"  hashmap 自然槽 = key%{n_slots} = {natural} -> 取槽 {free_slot}")
    used = set(mapping.values())
    free_row = next((i for i in range(rows) if i not in used), None)
    if free_row is None:
        raise SystemExit("✗ WeaponRounds 没有空行")
    tkey = WEAPON_KEYS[template_weapon]
    if tkey not in mapping:
        raise SystemExit(f"✗ 模板武器 {template_weapon} 没有 WeaponRounds 行")
    src = rows_base + mapping[tkey] * stride
    row = bytearray(data[src:src + stride])
    struct.pack_into("<II", row, 64, a, b)
    struct.pack_into("<ff", row, 72, float(mag), float(mag))
    struct.pack_into("<II", row, 80, reserve, reserve)
    if starting is not None:
        struct.pack_into("<I", row, 88, starting)   # +88 = 初始量（Halt: 32 发 / AR-23: 6 匣）
    struct.pack_into("<I", row, 104, 1)          # 第二池开关
    # +108 的 6 个 hash 是「弹种定义/显示名」：双弹种武器共用同一组值，
    # 单弹种武器是 0。清零会让「切弹页面」抛 INVALID_PARAMETER 崩溃（2026-10-22 实测 ✗）
    # ⇒ 一律沿用模板行原值，不动。
    dst_row = rows_base + free_row * stride
    old_row = bytes(data[dst_row:dst_row + stride])
    data[dst_row:dst_row + stride] = row
    records.append({"label": f"{weapon}.rounds_row(row {free_row})", "offset": dst_row,
                    "width": stride, "old": "空行", "new": f"A={a} B={b} 弹匣{mag} 备弹{reserve}"})
    dst_slot = body + 16 * free_slot
    old_slot = bytes(data[dst_slot:dst_slot + 16])
    struct.pack_into("<QII", data, dst_slot, key, free_row, 0)
    records.append({"label": f"{weapon}.rounds_hashmap(slot {free_slot})", "offset": dst_slot,
                    "width": 16, "old": "空槽", "new": f"key=0x{key:016X} -> row {free_row}"})
    return free_slot, free_row


def apply_edits(data: bytes, edits, keep_mg43: bool, add_rounds=None, template_weapon="SG-8 Punisher"):
    """edits: [(weapon, cell, value)]；返回 (新数据, 记录列表, 原始哈希)。"""
    original_hash = murmur64(data)
    out = bytearray(data)
    records = []
    if keep_mg43:
        edits = list(edits) + [("MG-43", "reload_move", 1)]
    if getattr(apply_edits, "_drop", None):
        for weapon_name, table_name in apply_edits._drop:
            drop_component_row(out, weapon_name, table_name, records)
    added_rows = None
    if add_rounds:
        weapon, a, b, mag, reserve = add_rounds
        added_rows = add_rounds_row(out, weapon, a, b, mag, reserve, template_weapon, records,
                                    starting=getattr(cmd_edit, "_starting", None))
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
        records.append({"label": f"{weapon}.{cell}", "offset": off,
                        "width": 1 if kind == "u8" else 4, "old": old, "new": value})
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
        expected.update(range(r["offset"], r["offset"] + r["width"]))
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
        if r["width"] > 8:
            check(f"G4 写入 {r['label']}", True, r["new"])
            continue
        kind = CELLS[r["label"].split(".")[-1]][2] if "." in r["label"] else "u32"
        if kind == "u8":
            val = edited[r["offset"]]
        elif kind == "float":
            val = struct.unpack_from("<f", edited, r["offset"])[0]
        else:
            val = struct.unpack_from("<I", edited, r["offset"])[0]
        check(f"G4 读回 {r['label']}", val == r["new"], f"{r['old']} -> {val}（要 {r['new']}）")
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
        edits.append((args.weapon or args.add_rounds.split(":")[0], "fnid", args.fnid))
    if args.alt is not None:
        edits.append((args.weapon or args.add_rounds.split(":")[0], "alt", args.alt))
    if args.prim is not None:
        edits.append((args.weapon or args.add_rounds.split(":")[0], "prim", args.prim))
    if not edits and not args.keep_mg43 and not args.add_rounds and not args.drop:
        print("✗ 没有任何要改的格（--fnid / --alt / --prim / --keep-mg43 至少一个）")
        return 2
    print(f"输入 {args.file}: {len(data):,} B")
    if args.weapon:
        print(f"  改前 {args.weapon}: {describe(data, args.weapon)}")
    if args.keep_mg43:
        print(f"  改前 MG-43: {describe(data, 'MG-43')}")
    add_rounds = None
    if args.add_rounds:
        w, a, b, mag, reserve = args.add_rounds.split(":")
        add_rounds = (w, int(a, 0), int(b, 0), int(mag), int(reserve))
    cmd_edit._starting = args.rounds_starting
    drop = []
    for spec in (args.drop or []):
        w, t = spec.rsplit(":", 1)
        drop.append((w, t))
    apply_edits._drop = drop
    edited, records, original_hash = apply_edits(data, edits, args.keep_mg43, add_rounds,
                                                 args.rounds_template)
    for r in records:
        print(f"  改 {r['label']} @0x{r['offset']:08X}: {r['old']} -> {r['new']}")
    ok = run_gates(data, edited, records, original_hash)
    if not ok:
        print("✗ 门禁未过，不写文件")
        return 1
    open(args.out, "wb").write(edited)
    print(f"✓ 已写 {args.out}（{len(edited):,} B, murmur64=0x{murmur64(edited):016X}）")
    if args.weapon:
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
        p.add_argument("--weapon")
        p.add_argument("--fnid", type=int)
        p.add_argument("--alt", type=int)
        p.add_argument("--prim", type=int)
        p.add_argument("--edit", action="append", metavar="WEAPON:CELL:VALUE",
                       help="通用写法，可重复；武器名可含空格，如 "
                            "'SG-8 Punisher:rounds_b:140'")
        p.add_argument("--add-rounds", metavar="WEAPON:A:B:MAG:RESERVE",
                       help="给没有 WeaponRounds 行的武器新增独立弹药池行，如 "
                            "'AR-23:281:140:30:45'")
        p.add_argument("--drop", action="append", metavar="WEAPON:TABLE",
                       help="删除某武器在某张组件表里的条目（如 'AR-23:magazine'），"
                            "用于在互斥模型间切换")
        p.add_argument("--rounds-starting", type=int, default=None,
                       help="新增行的 +88 初始量（霰弹族=发数，整匣换弹=匣数）")
        p.add_argument("--rounds-template", default="SG-20 Halt",
                       help="新增行时抄哪一行（默认 SG-8 Punisher）")
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
