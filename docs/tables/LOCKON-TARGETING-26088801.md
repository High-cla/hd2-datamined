# 锁定 / 制导（lock-on / seek）组件 —— 武器线遗漏项（build 26088801）

> **状态：路线已定位，尚未实机。** 本篇把「memmod 时期 c9-seek 那条线」和「当前 build 的明文表」对上，
> 给出可编辑的落点与下一步。
> 相关：`D:\mod\c9-recon\web-intel-hd2-lockon.md`（公开情报，158 行）· `D:\mod\c9-seek-write\`（当年的写载物）。

---

## 0 一句话

锁定不是一个字段，而是 **`TargetingComponentData` 这一整块组件数据**（当前 build **28,512 B @ 明文 `0x1932294`**），
里面装 **297 行 × 64 B 的 `TargetingComponent`**；外加武器侧的 **`WeaponDataComponentData +400 crosshair_type`**
（值 `16` = Javelin 锁定准星）才是「看起来像锁定武器」的那一半。

---

## 1 当年（c9-seek / memmod）留下的路标

| 项 | 值 | 来源 |
|---|---|---|
| `TargetingComponentData` | `0x2C0968D2`（djb2） | web-intel §1 |
| `TargetingComponent` | `0x5E30EC98` | 同上 |
| `SeekingMissileTargetingMode` | `0xFD5CCE86`（枚举） | 同上 |
| `SeekingMissileTargetingMode_TargetLock` | `0xE1C946F5`（枚举成员） | 同上 |
| `Tag_CanBeLockedOn` | `0x07F0ADE3`（标签） | 同上 |
| 锁定准星 | `WeaponDataComponentData **+400 (0x190)** crosshair_type`，值 **16 = Javelin** | web-intel §2 |
| 用 16 的武器 | **FAF-14 Spear(335) · P-33 Missile Pistol(189) · P-92 Warrant(188) · StA-X3 W.A.S.P.(336)** | 同上 |
| ⚠ 未证 | 16 是否连「锁定中/已锁定」的动态帧一起给；当年的写载物在 `c9-seek-write/`（patch_3） | 同上 |

> 那批武器同时被公开文档标为「发射 **spawned entity**」而不是普通弹丸
> （对应 `ProjectileWeaponComponentData +40 = ProjectileEntity`）—— 与「锁定/制导」是同一族。

---

## 2 当前 build 的离线实测（本篇新增）

用 `generated_entities.dl_bin` 明文（47,259,396 B）扫 275 个 `LDLD` 块：

| 块 | type | 位置 | payload |
|---|---|---|---|
| **TargetingComponentData** | `0x2C0968D2` | **`0x1932294`** | **28,512 B** |
| WeaponDataComponentData | `0x88E4DBB1` | `0x193CCEC` | 475,696 B |

`typelib` 解出的结构（**本 build 的 typelib 里成员名已被剥掉**，只有偏移/尺寸）：

```
TargetingComponentData  0x2C0968D2  size = 28,512 B
  +0     9,504 B = 594 × 16 B   子数组 0xFCDFC705（{u64, u32}）
  +9504 19,008 B = 297 × 64 B   子数组 0x5E30EC98 = **TargetingComponent**

TargetingComponent  0x5E30EC98  size = 64 B，19 个成员
  +0  u32   +4  u32   +8  u32   +12 u32   +16 u32   +20 u32
  +24 u8    +25 u8    +26 u8
  +28 u32
  +32 u8
  +36 u32   +40 u32   +44 u32
  +48 **12 B 向量**（0x85B82A43 = 三浮点，极可能是方向/偏移）
  +60 u8    +61 u8    +62 u8    +63 u8
```

⇒ **297 个 targeting 组件**，每个 64 B；可改的旋钮就是上面那 6 个 u32、3+4 个 u8、以及 +36/+40/+44 三个数值
（后三个大概率是 f32：锁定距离 / 跟踪强度 / 锁定时间之类）。

---

## 3 两个杠杆（要「锁定类武器」必须同时动）

| 杠杆 | 位置 | 作用 |
|---|---|---|
| **武器侧准星** | `WeaponDataComponentData +400 (0x190)`，值 16 | 决定 UI 上是不是锁定准星（Javelin 框） |
| **制导组件** | `TargetingComponentData` 里那 297 行之一 | 决定能不能锁、锁多远、锁多快、跟踪多紧 |

---

## 4 下一步（建议顺序）

| # | 做什么 | 为什么 |
|---|---|---|
| 1 | **拿成员名**：用社区 JSON（`shalzuth/HelldiversData` 的 `components/TargetingComponentData.json`）或 `MrChengl11/hd2-lua-mod-skill` 的 typelib dump，把 19 个成员的**名字与类型**对上 | 本 build 的 typelib 名字被剥了；没有名字只能靠猜偏移 |
| 2 | **求出 297 行与实体的映射**：`0xFCDFC705` 那 594 条 `{u64, u32}` 大概率是 `{标识, 行号}` 索引，用它把「武器实体 → TargetingComponent 行」对上 | 才能精确改「某一把武器」而不是全表 |
| 3 | **先改准星**（最安全、纯 UI）：把某把非锁定武器的 `crosshair_type` 改成 16 | 已被 APW-1 的 3→4 先例证明「准星枚举可写、可见」 |
| 4 | **再改制导参数**（要实机）：挑一把已有锁定武器（如 FAF-14 / P-92），把「锁定距离」类字段翻倍 | 用「能不能锁更远」当判据；一次一个字段 |
| 5 | ⚠ **不要先动 `Tag_CanBeLockedOn`** | 它是实体标签，改错可能让敌人/队友的锁定语义一起乱 |

**编辑手段**沿用现有链路：解封 → `plain_edit.py`（可寻址）改字节 → 保哈希 → `seal-material`／`seal-key` → 装机。
`generated_entities.dl_bin` 的哈希闸门与宿主策略已在
[ENTITY-TABLE-25988413](../tables/ENTITY-TABLE-25988413.md) §2 与
[MEMORY-ACCESS](../boundaries/MEMORY-ACCESS-25988413.md) 里记录（本 build 需先 `build_cache.py` 复算锚点）。

---

## 5 三态

| 主张 | 判定 |
|---|---|
| 当前 build 存在 `TargetingComponentData` 块 | ✓ 离线（`0x1932294`，28,512 B） |
| 里面有 297 × 64 B 的 `TargetingComponent` | ✓ 离线（typelib 尺寸算术自洽：9504 = 594×16，19008 = 297×64） |
| 19 个成员的语义 | ⚠ **未知**（本 build typelib 名字被剥） |
| `crosshair_type +400 = 16` 是锁定准星 | ✓ 公开文档 + 社区数据；**本机未复核** |
| 锁定行为由这 64 B 行控制 | ⚠ 强推断（组件名 + 当年 c9-seek 路标），未实机 |
| memmod 时期 c9-seek 是否跑通过 | ⚠ 待查 `c9-recon/c9seek-2.9.x-final.txt`（本篇未逐行核对） |
