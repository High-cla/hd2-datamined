# `weapon_customization_settings` 解码（build 25988413）

> 这张表是**武器配件总表**：252 行 = 弹种 82 + 弹匣 57 + 枪口 37 + 瞄具 22 + 下挂 20 +
> 备选弹种 15 + 涂装 12 + 内部件 4 + 扳机 3。
> 整表可读导出：`refs/exports/weapon_customization_settings.csv`（252 行 × 13 字段，含行名）。

## 1. 行结构（88 B，逐字段已对上）

字段名与偏移来自 **xypwn/filediver** 的 `datalibrary/weapon_customization.go`
（`rawWeaponCustomizableItem`），我们把它的 88 字节结构与本机数据逐项对齐过：

| 偏移 | 字段 | 类型 | 本机观测 |
|---:|---|---|---|
| **`+0`** | **`DebugNameOffset`** | **u64 指针** | **就是每行自带的名字指针**：252/252 行解析出显示名，248 个不同值。早先以为它"只是碰巧"，已否证 |
| `+8` | `ID` | ThinHash (u32) | **252 个不同值** ⇒ 每件配件的唯一 id |
| `+12` | `NameUpper` | u32 | 158 个不同值（大写名哈希）|
| `+16` | `NameCased` | u32 | 158 个不同值（原样名哈希）|
| `+20` | `Description` | u32 | 158 个不同值（描述哈希）|
| `+24` | `Fluff` | u32 | **恒为 0**（本表没填）|
| `+28` | *(padding)* | 4 B | |
| `+32` | `AddPath` | Hash (u64) | 249 个不同值（模型/挂点资源）|
| `+40` | `Icon` | Hash (u64) | 252 行**全 0**（图标另有来源）|
| `+48` | `SlotsOffset` | u64 | → 槽位枚举数组 |
| `+56` | `SlotsCount` | u64 | 每件 1 个槽位（个别多项）|
| `+64` | `UIWidgetColorsOffset` | u64 | → `CApiVector3` 数组 |
| `+72` | `UIWidgetColorsCount` | u64 | |
| `+80` | `SortGroups` | u32 | **4 个不同值**，见下 |
| `+84` | *(padding)* | 4 B | |

## 2. 那两个枚举

`WeaponCustomizationSlot`（`+48/+56` 指向的数组，元素为 u32）：

| 值 | 名称 | 本表件数 |
|---:|---|---:|
| 0 | None | 0 |
| 1 | **Underbarrel** | 20 |
| 2 | **Optics** | 22 |
| 3 | **PaintScheme** | 12 |
| 4 | **Muzzle** | 37 |
| 5 | **Magazine** | 57 |
| 6 | **AmmoType** | 82 |
| 7 | **AmmoTypeAlt** | 15 |
| 8 | **Internals** | 4 |
| 9 | **Triggers** | 3 |

`WeaponCustomizationSortGroups`（`+80`）：

| 值 | 名称 | 本表件数 |
|---:|---|---:|
| 0 | None | 240 |
| 1 | Paint_Default | 1 |
| 2 | Paint_Solid | 7 |
| 3 | Paint_Camo | 4 |

## 3. 上一版猜错了什么

之前推测 `+8/+12/+16/+20` 是"按弹种分组的一组 4 个 id"。**不对**——它们是
`ID`、`NameUpper`、`NameCased`、`Description`：一个唯一 id 加三个**名字/描述的 32 位哈希**。
真正的分组列是 `+48/+56`（槽位枚举）和 `+80`（排序组）。这也是"158 个不同值"的来源：
252 件配件里有 158 个不同的（名字, 描述）组合。

## 4. 交叉验证（不是推论，是计数）

1. **弹种行全部落在 AmmoType**：82 条 `AmmoType` 里包含全部 `PISTOL-SMG` / `RIFLE` / `SHOTGUN`
   弹药名；反查"名字像弹药但槽位不是 AmmoType"的行 = **0 条**。
2. **涂装行全部落在 Paint_* 排序组**：`Forest Solid` / `Arctic Camo` / `Desert Solid` 等 12 条
   `PaintScheme` 行的 `SortGroups` 只在 1/2/3。
3. **`Fluff` 恒 0、`Icon` 恒 0** 与 filediver 结构里这两个字段"本表没填"的预期一致。

## 5. 复现

```bash
# 整表导出（需要你自己的 recipient.sk，仓库不含密钥）
python tools/table_export.py --table weapon_customization_settings \
    --sk <你的>/recipient.sk --out out/wc
# 产 out/wc.csv（含 slots / sort_group 两列）与 out/wc.md（字段图例 + 前 15 行）
```

`tools/table_export.py` 里的 `LAYOUTS` 就是这张表的注解：字段名、两个枚举、槽位数组位置。
换别的表时把注解补进 `LAYOUTS` 即可复用同一套导出。

## 6. 出处

* 结构与字段名：**xypwn/filediver**，`datalibrary/weapon_customization.go`、
  `datalibrary/enum/weaponcustomizationslot.go`、`.../weaponcustomizationsortgroups.go`（MIT）。
* 本表数据、偏移核对、槽位解码：本项目（`tools/table_export.py` + 密钥解封）。
* 行名来自**每行自带的 `+0` 指针**（`DebugNameOffset`），不是尾部的平行数组：指针名与位置名
  在 8 个组上 240/240 一致，而位置法在第 9 组（12 个染料，块里混着颜色二进制）会吐出碎片。
  抽取方式见 `tools/table_row_names.py`、`tools/probe_row_name_offsets.py` 与字典文档 §0.5。
