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
| **第一层：3 行基准** | **game.dll 只读数据段的三张 12 B 表**（见 §1.1，位置已实测钉死） | ✗ 不在 `.dl_bin`，属另一条路线 |
| **第二层：每件甲 9 个部件的档位** | **本表（`.dl_bin`）** | ✓ 本文件 |

### 1.1 第一层三张表：旧 build 转储里逐字节实测（✓ 离线，三份转储一致）

| 表 | RVA | 段 | 原始 12 B | f32 | 顺序 |
|---|---|---|---:|---|---|
| armor `A` | **`0x21CB160`** | S1 `r--` | `00 00 00 00 00 00 80 3F 00 00 00 40` | **0.0 · 1.0 · 2.0** | light→heavy 升序 |
| speed `S` | **`0x2160678`** | S1 `r--` | `CD CC 8C 3F 00 00 80 3F 66 66 66 3F` | **1.1 · 1.0 · 0.9** | light→heavy |
| stamina `F` | **`0x21C6F78`** | S1 `r--` | `00 00 40 3F 00 00 80 3F 00 00 C0 3F` | **0.75 · 1.0 · 1.5** | light→heavy |
| 伤害曲线 | `0x21ceff0` | S1 `r--` | 40 B，5 × `{f32 A; f32 mult}` | (3,0.65) (2,0.75) (1,1.00) (0,1.25) (−1,1.66) | A 降序 |

- 来源：`docs/recon/CLASS-TABLE-DUMP.md` §5.1 / §0.1；SDK 文档给的就是这三个 RVA，**在我们的旧 build 上逐字节有效**。
- 三张表在镜像里**相距很远**（`0x2160678` → `0x21C6F78` → `0x21CB160`，跨约 2.1 MB），所以任何"三行相邻"的搜索都会漏 —— 这是上一轮否证的真正原因。
- SDK 原文：这三张表在**运行时被 loader 放成 PAGE_EXECUTE_READWRITE**（`game.dll+0x2112000`，0x528000 B），
  HD2Runtime 把写入它们算作「reviewed executable data」。⇒ 对我们是**没有内存写路线就碰不到**，但将来若通，就是 3 处 4 字节的现成靶子。

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

## 2.1 ★ 完整数值模型：从字节算出三个数字，**135/135 精确复现**

这条比下面的"集合对得上"强得多 —— 它把 SDK 记的 **411/135 件甲的三个人工数字**当靶子，逐件精确复现：

| 步骤 | 规则 |
|---|---|
| ① 取档位向量 | 每个槽位 1..9 取 **`variant`（`+12`）最小的那件**（=0）的档位 |
| ② RATING | `50 + 50 × ( mean(A[槽位 2,4,5,6,7,8,9]) + 被动 armor 行 )` |
| ③ SPEED / STAMINA（卡片口径） | `500 × mean(S[去掉 cape(1)/hips(3)])` · `100×(2 − mean(F[同上]))` |
| ④ SPEED / STAMINA（实战口径，SDK 说含 cape/hips） | 均值取**全部 9 槽** |

| 变体规则 → 复现出的件数 | 结果 |
|---|---|
| **每个槽位取 variant 最小的一件** | **135/135 精确相等** ✓ |
| 取 variant 最大的一件 | 113/135 |
| 优先取共享组（组类型 3）的那件 | 126/135 |

⇒ 三件事同时被钉死：**(a) `+16` 是档位；(b) `+12` 是变体、且只有 variant 0 参与数值；(c) 三个数字的聚合公式。**
复现命令：`python tools/armor_kit_weight.py --verify-model`。

> `+12` 变体的真实语义还没全解：同一个槽位常有两三件（variant 0/1/2），**只有 variant 0 参与 class 计算**。
> 某个 kit 的 variant 1 手臂件档位与 variant 0 不同（例：CW-22 Kodiak 的手臂 v0=heavy、v1=medium），
> 这就是上一版"按集合对"时 11 件甲对不上的来源 —— 那些**是多出来的变体件，不是错**。

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
- 三个自检模式：
  | 旗标 | 干什么 | 当前结果 |
  |---|---|---|
  | `--verify-model` | 用模型重算 135 件甲的三个数字，与 SDK vanilla 逐件比 | **135/135 精确相等** |
  | `--selftest` | 改出去（全 heavy）再改回来（原档位），检查除尾宿主外**逐字节回原样** | **6/6 全过** |
  | `--show [--name/--perk]` | 列表 + 每件甲的档位向量 | — |

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

### 5.1 下一发已经预生成：只改 torso（等 w1 读完再上）

| 项 | 值 |
|---|---|
| 产物 | `D:\mod\out\armor-w2\generated_customization_armor_sets.dl_bin`（453,264 B，sha256 `00fac3b0cff465e6`） |
| 改动 | B-01 的 9 条记录里**只有横跨三组的 36 个 torso 部件**（槽位 2）→ heavy，其余 171 个部件不动 |
| **预测（卡片）** | **107 / 493 / 93**（`A = 8/7 = 1.143`） |
| **预测（实战）** | **107 / 494 / 94**（S/F 含 cape/hips，9 件均值） |
| 这一发能额外证明什么 | ①「按槽位粒度」成立；② 卡片到底用哪套均值（493/93 vs 494/94 一眼可分）；③ 卡片标签应翻成 **Heavy**（标签跟 torso 走） |

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
2. 部件 `+12`（变体 0/1/2）的**语义** —— 已证「只有 variant 0 参与数值计算」（§2.1），
   但 variant 1/2 是什么还没解（猜测：不同体型专用的替换件，或 LOD/时装变体）。
3. `+44`（f32，多数记录是 −1.0）与 `+40`（KitType）未解。
4. ~~class_table 与伤害曲线的实际字节布局~~ → **已定**：见 §1.1（三份转储逐字节一致）。
5. **当前 build（`26088801`）里这三张表的 RVA 是否仍是那三个** —— ⚠ 未证。当前 build 的 `game.dll` 在盘上是加壳的（15.5 MB vs 内存 74.7 MB），
   而 EAC 挡住了一切 dump 路线，所以只能沿用旧 build 的 RVA + 假定布局稳定（同一 `game.dll` 版本号族内通常成立）。
