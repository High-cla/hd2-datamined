# 护甲三数字的文件侧入口：`generated_customization_armor_sets.dl_bin` 的「部件档位」

> build `26088801` · 2026-10-24 · 状态：**✓ 离线**（数据层逐件对上 SDK）· **⚠ 未上机**（本次实验待读）

## 0. 一句话

护甲卡片上的 **RATING / SPEED / STAMINA REGEN 不在这张表的任何一条数值字段里**，
它们是「**game.dll 里的 3 行 class_table** × **这件甲 9 个部件各属哪一档**」算出来的。
文件侧唯一能动的就是**后半截**：把某件甲的部件档位从 light 改成 heavy，它的三个数字就会一起变。
每个部件的档位就住在 `generated_customization_armor_sets.dl_bin` 的部件记录 `+16`（u32）。

## 1. 两层模型（权威来源：`ArmorStatsCapabilities.json`，HD2Runtime 0.30.3）

| 层 | 在哪 | 我们能不能改 |
|---|---|---|
| **第一层：3 行基准** `<br>light 0 / 1.1 / 0.75`<br>`medium 1 / 1 / 1`<br>`heavy 2 / 0.9 / 1.5` | **game.dll 可执行数据页**（`armor 0x21CB160` · `speed 0x2160678` · `stamina 0x21C6F78`） | ✗ 不在 `.dl_bin`，属另一条路线 |
| **第二层：每件甲 9 个部件的档位** | **本表（`.dl_bin`）** | ✓ 本文件 |

聚合公式（SDK `formulas`）：

| 数字 | 怎么算 | 显示 |
|---|---|---|
| RATING | 评分槽（`torso` + 双腿 + 双臂 + 双肩，**不含 cape / hips**）的 A 求均值，再叠被动的 `armor_rating` 行（`(Set else 均值) + ΣAdd`，再 `× ΠMultiply`）；**每次命中都读** | `50 + 50·A` |
| SPEED | **全部 9 件**（含 cape / hips）的 S 求均值；在「施加护甲」时写入（出生/换甲） | `500·S` |
| STAMINA | **全部 9 件**的 F 求均值 | `100·(2 − F)` |
| 卡片上的 Light/Medium/Heavy 标签 | **torso 的档位** | — |

伤害曲线也在同一页：`A = −1/0/1/2/3 → ×1.66 / ×1.25 / ×1.00 / ×0.75 / ×0.65`（线性插值）。

## 2. 记录布局（本 build 实测：422 块 = 422 条记录）

```
payload（没描述符，payload 开头就是记录）
  +0    64 B  记录 HelldiverCustomizationKit
        +0  u32   kit id          ← 与 SDK kits[].id 逐一对上（135/135）
        +12 u32   name_upper(locid)      +16 name_cased      +20 description
        +24 u32   Rarity                 +28 u32 PassiveBonus(被动号)
        +32 8 B                          +40 KitType          +44 f32
        +48 u32   部件组数组偏移（相对 payload）
        +56 u32   部件组个数
  → 24 B × 组数   组 = { +0 u32 组类型(=3/0/1), +8 u32 部件数组偏移, +16 u32 部件个数 }
  → 112 B × 部件  部件 = { +0 8 B 哈希, +8 u32 槽位 1..9, +12 u32 变体 0/1/2,
                          +16 u32 档位 0=light 1=medium 2=heavy, ... }
```

- 槽位号：`1 cape · 2 torso · 3 hips · 4 left_leg · 5 right_leg · 6 left_arm · 7 right_arm · 8 left_shoulder · 9 right_shoulder`
- 一件甲 = **3 个「部件组」×（7~9 个部件）= 23~25 个部件**。三组分别覆盖不同槽位子集
  （例如组 3 只放 cape/腿/臂，组 0 与组 1 才放 torso/hips/肩）——**这就是「stocky / slim / any-body」那三套**。
- 422 块里 413 块被「记录 + 组 + 部件」**精确铺满**；另 9 块尾部还有一段别的数组（`{u32 3}{u32 0}{u64 哈希}…`），
  那是**非护甲 cosmetic 记录**（id 不在 SDK 的 135 件里，槽位字段是 0 或 1），本工具不碰。
- 422 块 = **135 件护甲**（偶数编号）+ 287 条 cosmetic 记录（多数只有 1 个部件）。

## 3. `+16` 就是档位：135/135 的离线判据

| 判据 | 结果 |
|---|---|
| 记录 `+0` 的 id 与 SDK `kits[].id` 命中 | **135/135** |
| 每件甲的 **cape 槽（槽位 1）**档位 == SDK 的 `weights.cape`（全表恰好 135 个槽位 1 的部件） | **135/135 精确** |
| 每件甲**至少有一个部件组**的档位集合 == SDK 的 `weights` 集合 | **135/135** |
| 105 件甲三组全一致、**29 件甲只有一组一致** | 与 SDK 原文 *"`slim_stats` only when the slim body differs"* 对得上 |
| 把 `+16` 换到别的偏移再扫一遍（112 B 全扫） | 只有 `+16` 超过 14/135，其余全是 0 值常量字段 |

> 也就是说：**「同一件甲的不同体型可以有不同档位」是真的**，SDK 的 `weights` 只记了其中一个体型。
> 想改得干净，就**三组一起改**（本工具默认如此）。

## 4. 工具

`tools/armor_kit_weight.py`

```bash
python tools/armor_kit_weight.py --show                      # 列 135 件甲（id/编号/名字/档位/预测列）
python tools/armor_kit_weight.py --show --name "B-01"
python tools/armor_kit_weight.py --kit 0x250FD6C1 --weight heavy --dry-run
python tools/armor_kit_weight.py --kit "B-01 Tactical" --weight heavy --out out/x.plain.dl_bin
```

- `--kit` 接受 id / SDK 编号 / 名字子串；`--name` `--perk` 可批量。
- `--weight` = `light|medium|heavy|0|1|2`；`--slots` / `--body-types` 可只改一部分。
- 只改**已有 4 字节**，靠「文件尾追加 8 B 零区当宿主 + 解一个校正字」保住 MurmurHash64A。
- 门禁 G0（几何不重叠/不越界，413/422 精确铺满）· G1 长度 · G2 差异范围 · G3 重算哈希 == 原版 ·
  G4 目标读回 · G5 目标之外的部件一个没动 · G6 容器自洽 · G7 重解码后档位 == 目标。

## 5. 本次实验件（已装）

| 项 | 值 |
|---|---|
| 产物 | `D:\mod\out\armor-w1\generated_customization_armor_sets.dl_bin`（453,264 B，sha256 `98933f030c754dd1`） |
| 明文 | `…\generated_customization_armor_sets.plain.dl_bin`（453,216 B，sha256 `cd7164b29669bf50`） |
| 改动 | **B-01 Tactical 的 9 条记录**（`0x250FD6C1` `0x1D0E3431` `0x708451E9` `0x61B31723` `0x4F7FB2BD` `0x6351A9AA` `0x6D30F386` `0xD59566D5` `0x1369B95B`）**全部 207 个部件档位 → 2(heavy)** |
| 差异 | 只 208 处（207 个部件 + 1 个尺寸字段字节），全部在声明范围内 |
| 基线 | 盘上原文件解封后与明文缓存 `9dab2ea0…` **逐字节相同** ⇒ 缓存没被我们污染 |

**预测**（`50+50A` / `500S` / `100(2−F)`，被动 armor 行另算）：

| 被动 | 现在 | 改后 |
|---|---|---|
| STANDARD ISSUE（5 条） | 100 / 500 / 100 | **150 / 450 / 50** |
| EXTRA PADDING（4 条，被动 +1.0 A） | 150 / 500 / 100 | **200 / 450 / 50** |

⇒ 两组的**变化量完全一样**：rating **+50**、speed **−50**、stamina **−50**。B-01 Tactical 是起手甲，人人都有。

## 6. 读法（一次只读一个变量）

| 看什么 | 期望 |
|---|---|
| 军械库卡片 | 上面那张表；卡片标签 Light/Medium/Heavy **跟着 torso 走**（B-01 本来就 medium → 还是 Heavy 标签） |
| 出生后冲刺 | 明显变慢（500 → 450，−10%） |
| 耐力 | 条变短、消耗更快（100 → 50） |
| 挨打 | 掉血少一档（A 1 → 2，伤害 ×1.00 → ×0.75） |

回滚：`python tools/dlbin_deploy.py restore --file generated_customization_armor_sets.dl_bin`

## 7. 未解

1. 三个「部件组」到底哪一个是 stocky/slim/any —— 只知道组类型字段是 `3 / 0 / 1`，同一件甲三组覆盖的槽位子集不同。
   要钉死：只改一组，看 `describe()`/卡片是否只在一个体型下变。
2. 部件 `+12`（变体 0/1/2）是什么 —— 同一槽位常有两三个部件，变体字段是它们的区分位。
3. `+44`（f32，多数记录是 −1.0）与 `+40`（KitType）未解。
4. **class_table 与伤害曲线的实际字节布局** —— 旧 build 转储扫描进行中（`docs/recon/CLASS-TABLE-DUMP.md`）。
