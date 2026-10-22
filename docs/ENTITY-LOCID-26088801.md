# 实体库的本地化 ID 字段：`实体 → 游戏内名字`（build 26088801）

> 状态：**✓ 实测**（只读静态解析，2026-10-22）。对象是 `data/game/generated_entities.dl_bin`
> 明文 47,259,396 B（Murmur64A `8E49771B181FFAA1`，sha256 `dc6d52a1…f5f98b`；
> 与 build 25988413 的 entities 明文**逐字节相同**，所以本文结论对两个 build 同时成立）。
> 工具：`tools/entity_locid_scan.py`（新增，可复跑）。数据产物：`refs/entity-locid-names.json`。

---

## 1. 结论（先看这段）

1. **实体名只有一处**：`EncyclopediaEntryComponentData`（块 56，675 行 × 56 B）。
   它一行 = 一个实体（行 ↔ 哈希图键），**643 行能解出名字**（359 个不同名字，重复的是同一物品的多个实体变体）。
   字段：`+0` 单数名（`Liberator`）、`+8` 大写名（`LIBERATOR`）、`+4` 复数名（`Liberators`）、
   `+36` 物品代码（`AR-23`）、`+20` 长描述（**本工具不导出**）。
   （另有 4 个小组件带少量**道具/角色/战备标签**名，如剧情海报标题 55 条、角色类别 48 条、货架战备名 19 条，
   它们是 UI 标签不是实体标识，统一归到 §6，不进名字表。）
2. **实体库一共 1,939 个实体**（块 0 的 4,096 槽哈希图，键 = `Murmur64A(资源路径)`）。
   有名字的 643 个（33.2%），其余 1,296 个**没有本地名字段** —— 不是没找到，是扫完了没有（§6/§7）。
3. **武器/护甲的军械库名字确实不在实体库里**（`WeaponDataComponentData` 374 行、`EquipmentComponentData`
   352 行，名字槽 0 命中；WeaponData 只有 3 把枪的 2 个"口径标签"槽有值）。但装备在百科里有条目，
   所以名字走百科拿到了：枪械 **131**（主武器 59 · 支援 45 · 副 27）+ 投掷物 24 + 背包 36 + 载具 15。
4. `LoadoutEntryComponentData` 的 `equipment_tags[5]`（`+12` 起）**存的是标签名的 locid**，不是枚举：
   `ANTI-TANK` / `EXPLOSIVE` / `ROUNDS RELOAD` / `ONE HANDED`… 共 23 种，290 个命中。
5. 其余命中（**15,367 个**，不含两个名字表）是 HUD/交互/目标文本，**不是实体名**：交互提示 8,996、
   小游戏 HUD 5,582、剧情道具 284、目标文本 269、角色标签 85、搬运目标 80……；本工具只给统计，不导出文本。
6. 判据是纯统计的：整表 4 字节对齐窗口 11,814,849 个，落进 24,834 条 ID 语料的有 **17,500 个 / 去重 2,124**，
   随机期望 **68.3** → 富集 **256 倍**。名字槽一列 609/675 命中，随机期望 0.0039，Poisson 尾概率约 **1e-2900**。

---

## 2. 几何：275 个块是怎么拆开的

文件是块序列，块头 28 B：`u32 type | 'LDLD' | u32 ver(=1) | u32 type | u32 payload | u8 wide | 7 reserved`。
共 **275 个块**（块间偶有 4 B 对齐空当），块 0/1 是全局表（`EntitySettingsHashmap` / `EntityNetworkDataArray`），
其余 273 个 = 组件表。**三种块形态**：

| 形态 | payload 结构 | 块数 | 例子 |
|---|---|---:|---|
| 常规 | `[ComponentIndexData 哈希图][行数组][0..7 B 8 对齐尾垫]` | 265 | Encyclopedia 21,600 + 675×56 = 59,400 |
| 原生数组 | 行类型是原生类型（record_size 1），成员 size 就是行数 | 7 | Backpack 40 行、Destructible 299 行 |
| 带尾数组 | `[哈希图][行数组][尾数组]` | 1 | LoadoutEntry 6,368 + 199×32 + 796(+4 垫) = 13,536 |

几何**不靠猜**：容器类型的成员由 `dl_library.dl_typelib` 给出 —— `ComponentIndexData` 的成员大小 = 槽数×16，
另一个结构化成员的类型 record_size = 行大小、成员大小 = 行数×行大小。行数**取成员自己的 size**，
不是 `(payload-哈希图)//stride`：后者会把 LoadoutEntry 后面的 796 B 原生尾数组算成行（199 → 224，踩过）。

**几何自证**（不通过就不参与扫描）：每块哈希图必须满足「键数 ≤ 行数」「所有行号 < 行数」「pad = 0」
「空槽全零」「行数组不越界」。273 个可拆块**全部通过**（块 14 `ResourceDependency` 的哈希图是空的，键 0，允许）。
块尾剩余字节：204 个块恰好为 0，**68 个块有 1~7 B 的 8 字节对齐垫**，`LoadoutEntry` 的 800 B 是 796 B 尾数组 + 4 B 垫。

### 实体索引（块 0）

`4096 槽 × 32 B = 131,072 B` 的哈希图，`{u64 键, u64 组件表偏移, u64 组件数, u32}`，已用 **1,939** 槽。
尾部 54,100 B = **27,050 个 u16**，与「组件数之和 × 2」逐字节吻合（组件类型索引，本工具未解码）。

⚠ 块 0 里还有 **33 个"行数组外"命中**，全部是结构性巧合，已单独计数而不是混进槽统计：
* 32 个 = 尾部 u16 数组里同一对 u16（`0x006F,0x007C`）反复出现 16 次，拼成同一个 u32 `0x007C006F`，
  在 4 对齐和 2 对齐两遍扫描里各被数到 16 次 → 去重后只有 **1 个 ID**；
* 1 个 = 某条目字段 `a`（绝对偏移 149,196）的数值恰好等于某个 locid。

---

## 3. 判据与总账

`.strings` 英文语料：**18 个 blob / 24,834 条 ID**（全局唯一，见 `LOCID-NAMES-25988413.md`）。
随机 u32 命中概率 = 24,834 / 2³² = **5.782e-6**；一列 N 行的随机期望 = N × 5.782e-6。

```
4 字节对齐窗口        11,814,849
命中                    17,500     去重 2,124
随机期望                  68.3     富集 256×
另外 3 种对齐命中            16     （见下）
──────────────────────────────────────────────
行数组内（可归因）      17,483
行数组外（块 0）            33     （见 §2）
```

* 非 4 对齐那 16 个：正好是 §2 里那对 u16 在偏移 2 对齐处重复出现的同一 ID；把 4 种对齐的随机期望
  摊开（各 17.1）后，**没有任何证据支持存在非 4 对齐的 locid 字段**。
* 槽位统计（`(块, 行内偏移)` 聚合）：**227 个槽有命中**，其中 **185 个 ≥2 命中**、
  **42 个只命中 1 次**（每槽随机期望 0.003~0.02，这 42 个就是巧合，不予采信）；
  按覆盖率过滤（≥10%）后剩 **151 个**槽 —— 数据产品 `other_text_fields` 收的是
  「≥2 命中 且 覆盖率 ≥10%」的那 **131 个**（剔除两个名字表之后）。
* 有命中的块 **22 个**，其中 16 个块存在 ≥2 命中的槽；**其余 253 个块一个名字槽都没有**。
* 命中分布高度集中：`InteractableComponentData` 8,996 + `InteractableMinigameComponentData` 5,582
  + `EncyclopediaEntryComponentData` 1,826 + `LoadoutEntryComponentData` 290 = **16,694（95.5%）**。

| 块 | 组件 | 行 × 行大小 | 命中槽 | 命中 | 最高覆盖 | 角色 |
|---:|---|---:|---:|---:|---:|---|
| 203 | `InteractableComponentData` | 562 × 1,104 | 18 | 8,996 | 100% | 交互提示（共享） |
| 79 | `InteractableMinigameComponentData` | 76 × 10,432 | 137 | 5,582 | 100% | 小游戏 HUD（共享） |
| **56** | **`EncyclopediaEntryComponentData`** | **675 × 56** | **8** | **1,826** | **90%** | **实体名 / 代码 / 描述** |
| **23** | **`LoadoutEntryComponentData`** | **199 × 32** | **5** | **290** | **70%** | **装备标签名** |
| 249 | `StoryInteractableComponentData` | 60 × 56 | 9 | 284 | 100% | 海报标题/说明 |
| 71 | `ObjectiveComponentData` | 217 × 2,704 | 9 | 174 | 53% | 目标文本 |
| 214 | `CharacterNameComponentData` | 91 × 16 | 2 | 85 | 53% | 角色类别标签 |
| 157 | `ObjectiveCarryComponentData` | 40 × 128 | 2 | 80 | 100% | 搬运目标文本 |
| 125 | `MinigameExternalSwitchesComponentData` | 21 × 104 | 3 | 46 | 100% | 开关提示 |
| 129 | `InteractableStateSwitchComponentData` | 25 × 264 | 5 | 24 | 24% | 状态提示 |
| 189 | `HealthComponentData` | 507 × 22,096 | 3 | 21 | 1% | 3 条状态文案（子数组） |
| 127 | `HellpodRackComponentData` | 73 × 568 | 1 | 19 | 26% | 战备货架标签 |
| 111 | `ShowOnMapComponentData` | 26 × 48 | 1 | 15 | 58% | 地图标签 |
| 139 | `ObjectiveSecureAreaComponentData` | 5 × 68 | 3 | 15 | 100% | 目标文本 |
| 199 | `WeaponDataComponentData` | 374 × 1,240 | 2 | 6 | 1% | 口径标签（3 把枪） |
| 212 | `UploadDiscoveryComponentData` | 11 × 48 | 4 | 5 | 18% | HUD 提示 |

（另 6 个块只有 1 命中的巧合槽：`ObjectiveShuttleController` / `ObjectivePreventInvasion` / `Thrower` /
`AbilityWeapon` / `HintTrigger` / 未知类型 `0xF57457DA`。）

---

## 4. 名字字段：`EncyclopediaEntryComponentData`（块 56）

几何：块头 `0xC5E60`，payload `0xC5E7C`，哈希图 21,600 B（1,350 槽，已用 675），行数组 675 × 56 = 37,800，
**尾垫 0**，几何自证通过。行 ↔ 实体的对应由该块自己的哈希图给出（675 个键、675 行，一一对应）。

| 行内 | 角色 | 命中/行数 | 覆盖率 | 去重 | 随机期望 | p | 导出 |
|---:|---|---:|---:|---:|---:|---:|---|
| `+0` | 单数名 | **609/675** | 90.2% | 344 | 0.0039 | 1e-2900 | ✓ |
| `+8` | 大写名 | 495/675 | 73.3% | 326 | 0.0039 | 1e-2313 | ✓ |
| `+4` | 复数名 | 179/675 | 26.5% | 91 | 0.0039 | 1e-758 | ✓ |
| `+36` | 物品代码 | 211/675 | 31.3% | 185 | 0.0039 | 1e-909 | ✓ |
| `+20` | 长描述 | 217/675 | 32.1% | 191 | 0.0039 | 1e-937 | ✗（只发名字） |
| `+40` | 实现状态标记 | 80/675 | 11.9% | 30 | 0.0039 | 1e-312 | ✗ |

（`+8` 叫"大写名"是因为 495 条里绝大多数是全大写，但少数条目本身是混合大小写（如 `Eagle Storm`），
原样保留、不做大小写变换。同时有 `+0` 与 `+8` 的 483 条里，**477 条（98.8%）是同一词的大小写变体**；
6 条不同（如 `Fusion Repeater` vs `FACTORY STRIDER`），是条目数据复用的痕迹。）

结果：**643/675 有名字**（609 直接来自 `+0`，34 只有大写名走 `+8` 兜底），359 个不同名字；
32 行连 `+0/+8` 都是 0（行号 0、14、35、36、90、93、94、97、111、158、164、165、168、169、180、213、
223、315、380、403、414、438、479、518~523、559、600、648 —— 这些行在实体表里都存在，只是没有名字）。
10 条是**占位名**（`Sample` ×9、`Sample Container`），JSON 里标了 `"quality": "placeholder"`。

### 4.1 逐字样本（键 ↔ 名字）

| 实体键 | 名字 | 大写 | 代码 | 类别 |
|---|---|---|---|---|
| `0x968211C0033DCE64`（AR-23，WeaponData 行 273） | `Liberator` | `LIBERATOR` | `AR-23` | 主武器 |
| `0x11C27D3BABB38956`（MG-43，行 354） | `Machine Gun` | `MACHINE GUN` | `MG-43` | 支援武器 |
| `0x41EAC4A03987FAA0`（SG-8） | `Punisher` | `PUNISHER` | `SG-8` | 主武器 |
| `0xA8CFFB316F0B5C5F`（AC-8） | `Autocannon` | `AUTOCANNON` | `AC-8` | 支援武器 |
| `0x80F1A156D9FA1E36`（JAR-5） | `Dominator` | `DOMINATOR` | `JAR-5` | 主武器 |
| `0xCDF28BE026BB7D84`（StA-52） | `Assault Rifle` | `ASSAULT RIFLE` | `StA-52` | 主武器 |
| `0x4E310B1FE4C52B52`（SG-20） | `Halt` | `HALT` | `SG-20` | 主武器 |
| `0xB6AFF2195568767F`（R-36） | `Eruptor` | `ERUPTOR` | `R-36` | 主武器 |

敌人的样本：`Charger / Chargers / CHARGER`、`Shrieker / Shriekers`、`Bile Titan`、`Hive Lord`、`Berserker`、
`Gazer Spire`；载具：`GUNNER FRV`（代码 M-102）、`Patriot Exosuit`（EXO-45）、`Bastion Mk XVI`（TD-220）、
`GROUND ALL-TERRAIN EXTRACTION RIG`；投掷物：`Arc`（G-31）、`Giga Grenade`（G-48）、`Smokescreen`（G-89）。

分类（按 `LoadoutEntry.item_type` + 组件隶属关系，见 JSON `kind`）：
主武器 59 · 支援武器 45 · 副武器 27 · 投掷物 24 · 背包 36 · 载具 15 · 敌人 140 · 单位 165 · 可交互物 131 · 其它 1 = **643**。

### 4.2 交叉验证（三条独立证据）

**(a) wiki 页面标题对表**（`refs/wiki/cat_weapons.json` + `cat_stratagems.json`，236 个标题）：
643 条里 **211 条带 `+36` 代码**，其中 **205 条**能用 `代码 + 名字` 精确匹配 wiki 标题：

```
AR-23  Liberator          -> AR-23 Liberator
MG-43  Machine Gun        -> MG-43 Machine Gun
G-31   Arc                -> G-31 Arc
EXO-45 Patriot Exosuit    -> EXO-45 Patriot Exosuit
M-102  GUNNER FRV         -> M-102 Gunner FRV
TD-220 Bastion Mk XVI     -> TD-220 Bastion MK XVI
MS-11  Solo Silo          -> MS-11 Solo Silo
```

6 条带代码但没匹配上，都是 wiki 命名变体或还没建页：`SH-20 MEDIC BACKPACK`、`SG-8F Punisher fire of liberty`、
`G/40-K Melta Mine`、`AR-23L Liberator Legacy`、`LAS-22 Shear`、`P-41 Ombudsman`。另有 6 条无代码的条目
按名字命中（`Resupply`、`HIVE BREAKER DRILL`×2、`TACTICAL VIDEO CAMERA`、`AQUIFER DRILL`、`LAS-13 Trident`）。

**(b) 名字 ↔ 实体资源路径语义自洽**：675 个键里有 56 个能在 srkit 资源清单里解析成 `content/` 路径，
其中 **33 个（58.9%）名字词与路径词有交集** —— 示例：

```
Charger        <- content/fac_bugs/cha_charger/cha_charger
Shrieker       <- content/fac_bugs/cha_shrieker/cha_shrieker
Stalker        <- content/fac_bugs/cha_stalker/cha_stalker
Scout Strider  <- content/fac_cyborgs/vehicles/cyborg_walker_scout/cyborg_walker_scout
GUNNER FRV     <- content/fac_helldivers/vehicles/frv/frv
Shrieker Nest  <- content/env_bugs/assets/gameplay/bug_spawner_shrieker
```

（解析率只有 56/643，是因为 srkit 资源清单只覆盖 62,524 个资源，实体键里有大量未收录路径；
这**不影响**名字本身 —— 名字来自 locid，不依赖路径。）

**(c) 同一实体在别的组件表里的行**：AR-23 的键同时出现在 `WeaponData`(行 273) / `WeaponMagazine`(203) /
`ProjectileWeapon`(194) / `Wieldable`(412) / `Equipment`(251) / `LoadoutEntry`(103) / `Unit`(1578) /
`Encyclopedia`(561) —— 八张表指同一个实体，第 561 行解出 `Liberator/AR-23`，与游戏内一致。

---

## 5. `LoadoutEntryComponentData`（块 23）：装备条目 + 标签名

几何：哈希图 6,368 B（398 槽，已用 **199**），行数组 199 × 32 = 6,368，尾部 796 B = 199×u32 原生数组（+4 B 垫）。
行结构：`+0` 后端物品 id（u32）· `+4` `item_type` · `+8` dlc_pack_id · **`+12` 起 5 个 `equipment_tags`（locid）**。

* `item_type` 分布：`1`=59（主武器）`2`=46（支援武器）`3`=28（副武器）`4`=27（投掷物）`5`=3 `6`=36（背包）。
* 标签 locid 命中：`+12` **139**、`+16` 99、`+20` 42、`+24` 9、`+28` 1 = **290**；
  23 种标签：`MEDIUM ARMOR PENETRATING`(43) · `LIGHT ARMOR PENETRATING`(39) · `ONE HANDED`(38) ·
  `EXPLOSIVE`(32) · `ANTI-TANK`(18) · `ROUNDS RELOAD`(17) · `INCENDIARY`(14) · `HEAVY ARMOR PENETRATING`(11) ·
  `STUN`(10) · `STATIONARY RELOAD`(9) · `STICKY`(8) · `HEAT`(8) …
* 199 条里有 **191 条能从百科拿到名字**；8 条没有（含 3 条 `item_type=5`）。名字是**通过实体键**关联的
  （不是行内字段）：`LoadoutEntry` 与 `Encyclopedia` 指同一个实体。
* 尾部 199×u32 原生数组的值都是 1~400 的小整数（0 命中），不是 locid —— **不是名字字段**。

---

## 6. 其余 locid 字段（有文本，但不是实体名）

这些槽的判据同样通过统计（覆盖率 100% 的很多），但**去重数极低** ⇒ 共享 UI 文本。
JSON 的 `other_text_fields` 只收「≥2 命中 且 覆盖率 ≥10%」的 131 个槽（并**不导出逐行文本**），
完整槽表可用 `--all-slots` 打印。

| 组件 | 行数 | 命中槽 | ≥2 命中 | 覆盖率≥10% | 命中 | 去重 | 语义 |
|---|---:|---:|---:|---:|---:|---:|---|
| `InteractableComponentData` | 562 | 18 | 18 | 16 | 8,996 | 1~30 | 每个可交互物 8 组 `InteractZoneInfo`×136 B，每组 2 个提示 locid（相对 `+52/+56`，共 16 槽）：`INTERACT`/`ENTER`/`#ITEM`/`RELOAD` |
| `InteractableMinigameComponentData` | 76 | 137 | 118 | 87 | 5,582 | 1~37 | 小游戏 HUD 三行文本（目标/标记/计算中） |
| `StoryInteractableComponentData` | 60 | 9 | 8 | 8 | 284 | 2~40 | 海报/道具标题（`PATRIOTIC POSTER`）与说明 |
| `ObjectiveComponentData` | 217 | 9 | 6 | 2 | 174 | 1~74 | 目标文本（`Eradicate Terminid eggs`） |
| `CharacterNameComponentData` | 91 | 2 | 2 | 2 | 85 | 6~12 | 角色类别（`Civilian`/`SEAF Soldier`/`Person`） |
| `ObjectiveCarryComponentData` | 40 | 2 | 2 | 2 | 80 | 2~14 | 搬运目标文案 |
| `MinigameExternalSwitchesComponentData` | 21 | 3 | 3 | 3 | 46 | 6 | 开关提示 |
| `InteractableStateSwitchComponentData` | 25 | 5 | 5 | 5 | 24 | 1~2 | `>> BLOCKED <<` 等状态 |
| `HealthComponentData` | 507 | 3 | 3 | 0 | 21 | 2 | `+21996..+22004` 3 条状态文案（子数组，只 7 行有值） |
| `HellpodRackComponentData` | 73 | 1 | 1 | 1 | 19 | 9 | 货架上的战备名（`RESUPPLY`/`JUMP PACK`） |
| `ShowOnMapComponentData` | 26 | 1 | 1 | 1 | 15 | 14 | 地图图钉标签（`Colony`/`Place of Interest`） |
| `ObjectiveSecureAreaComponentData` | 5 | 3 | 3 | 3 | 15 | 1~2 | 目标文本 |
| `WeaponDataComponentData` | 374 | 2 | 2 | 0 | 6 | 3 | `+176/+180` 口径标签（只有 3 把枪有值） |
| `UploadDiscoveryComponentData` | 11 | 4 | 1 | 1 | 5 | 2 | HUD 提示 |
| 另 6 个块（巧合级） | — | 15 | 0 | 12 | 15 | 1 | `ObjectiveShuttleController` 4 · `ObjectivePreventInvasion` 3 · `0xF57457DA` 3 · `Thrower` 2 · `AbilityWeapon` 2 · `HintTrigger` 1（全部 hits=1，是巧合） |

---

## 7. 实体索引与覆盖率

`refs/entity-locid-names.json` 的 `entity_index` 是**完整**的 1,939 条：每个实体一条，
有名字填名字（`name`/`name_slot`/`name_upper`/`name_plural`/`code`/`kind`/`dev_name`），没有就 `null`。
`name_slot` 明确写出**名字来自哪个槽**（`EncyclopediaEntryComponentData+0` 或 `+8`）。

```jsonc
// entity_index[]（1,939 条）
{"key": "0x0002BA767DF856F3", "name": "Marauder", "name_slot": "EncyclopediaEntryComponentData+0",
 "name_upper": "MARAUDER", "name_plural": "Marauders", "code": "", "kind": "enemy",
 "has_encyclopedia_entry": true, "loadout_type": null, "loadout_tags": [], "dev_name": null}

// name_tables[]：两张名字表的槽证据 + 逐行数据
//   块 56  → role=entity_name，fields[] 给 6 个槽的 hits/distinct/coverage/exported
//   块 23  → role=loadout_entry，entries[] 给 item_type/tags/name/tags_slot
{"row": 4, "key": "0x0DF874E208040D2F", "name": "Bug Hole", "name_source": "name",
 "name_slot": "EncyclopediaEntryComponentData+0", "name_upper": "BUG HOLE",
 "name_plural": "Bug Holes", "code": "", "quality": "ok", "kind": "unit", "dev_name": null}

// other_text_fields[]：131 个「不是名字」的 locid 槽，只有统计（offset/hits/distinct/coverage），无文本
// census / entities / coverage：总账数字
```

```
实体总数                        1,939
有百科条目 / 有名字                643
有 LoadoutEntry                   199（其中 191 有名字）
有 dev_name（srkit 资源名）        327   ← 仅辅助定位，不是本地化文本
```

按类别（命名率从实体库实测统计得出）：

| kind | 实体数 | 有名字 | 命名率 |
|---|---:|---:|---:|
| 主武器 `primary_weapon` | 59 | 59 | 100% |
| 支援武器 `support_weapon` | 46 | 45 | 97.8% |
| 副武器 `sidearm` | 28 | 27 | 96.4% |
| 投掷物 `throwable` | 27 | 24 | 88.9% |
| 背包 `backpack` | 36 | 36 | 100% |
| 载具 `vehicle` | 20 | 15 | 75.0% |
| 敌人 `enemy` | 172 | 140 | 81.4% |
| 单位 `unit`（道具/建筑/可拾取物） | 761 | 165 | 21.7% |
| 可交互物 `interactable` | 371 | 131 | 35.3% |
| 目标 `objective` | 217 | 0 | 0% |
| 其它 `other` / `other_item` | 202 | 1 | 0.5% |
| **合计** | **1,939** | **643** | **33.2%** |

**没名字的 1,296 个是什么**（组件画像是**可重叠**的，同一个实体可能同时出现在多行）：
纯 `UnitComponent` 596 个（场景道具/装饰/可拾取物）、`Interactable` 240 个（没有再挂百科条目的可交互物）、
`ObjectiveComponent` 217 个（任务目标物件）、`Destructible` 215 个（可破坏物）—— 它们**本来就没有百科条目**，
所以也没有名字字段。这不是覆盖不全，而是数据里就没有。

---

## 8. 三态小结

**✓ 实测**

* 275 个块 / 273 个可拆块，几何自证（键数、行号、pad、越界）**全部通过**；三种块形态都处理了。
* 1,939 个实体、4,096 槽、27,050 个组件引用；尾部 u16 数组长度与组件数之和逐字节吻合。
* 整表 17,500 个 4 对齐命中 / 2,124 去重，随机期望 68.3（**富集 256×**）；可归因到行数组 17,483，行数组外 33（块 0，已解释）。
* 名字字段 = `EncyclopediaEntryComponentData +0/+8`（609/675、495/675），**643/675 行有名字**；
  211 条带代码的条目里 **205 条精确命中 wiki 标题**；8 个已知武器键逐字吻合游戏内名字。
* `LoadoutEntry.equipment_tags` 是标签名 locid（290 个命中、23 种标签）；`item_type` 枚举与 199 条装备一一对应。
* 实体分类的武器判据必须用 `LoadoutEntry.item_type`，**不能用"有没有 WeaponData"**（敌人也挂 WeaponData，
  会把 148 个敌人误判成武器 —— 这是本轮踩过的坑）。

**✗ 否证**

* "实体库里存武器/护甲的军械库显示名"：`WeaponData` 374 行、`Equipment` 352 行、`WeaponCustomization` 197 行
  **名字槽 0 命中**；军械库名字来自后端/资源开发名，不在本文件。
* "Interactable/Objective/Minigame 的 locid 是实体名"：去重数 1~37（共享 UI 文本），不是名字。
* "块 0 的 33 个命中是名字字段"：32 个来自同一对 u16 的结构性重复（去重后 1 个 ID）、1 个是偏移值恰好等于 locid。
* "非 4 对齐处还有 locid 字段"：16 个命中全部是那对 u16 在 2 对齐处的重复，总数 16 低于 3 种非对齐窗口的随机期望 51.3。
* "`WeaponRounds +108` 的 6 个 hash 是弹种显示名"（上一轮遗留的猜测）：本轮未在实体库里找到对应的 locid 槽，
  仍是 ⚠ 未定（它不在任何 locid 命中列表里）。

**⚠ 未定 / 边界**

* 32 行百科条目没有任何名字（`+0/+8` 都是 0），它们在实体表里都存在 —— 可能是未完成内容。
* 10 条占位名字（`Sample`/`Sample Container`）已标记 `quality=placeholder`。
* 1,296 个实体没有本地名字（§7 给出来源分布）；若需要"可读标识"，只能用 `dev_name`（327 条解析到）。
* srkit 资源清单只解析出 327/1,939 个实体键（路径 → 名字）；提高解析率需要更全的资源名索引（不在本轮范围）。
* 块 0 尾部 27,050 个 u16 组件索引未解码（不是块序号，实测 1,359 个实体越界）；解它可以得到"每个实体挂了哪些组件"。
* `+20` 描述、`+40` 实现状态按用户要求**未导出**；HUD/交互/目标文本同样未导出。

---

## 9. 复跑

```bash
# 需要：明文缓存 + typelib + 解开的 .strings（都是只读输入）
python tools/entity_locid_scan.py \
    --plaintext refs/dlbin/plaintext-26088801 \
    --typelib   refs/dlbin/plaintext-26088801/dl_library.dl_typelib \
    --strings   refs/strings-probe/all \
    --out       refs/entity-locid-names.json

# 排查单个槽的全部命中行（例：百科的 +0）
python tools/entity_locid_scan.py --dump-slot 56:0
```

工具做四件事：① 拆 275 个块并自证几何；② 全文件 4 种对齐扫 locid 并归因到 `(块, 行内偏移)`；
③ 按统计判据给槽排名（命中/去重/覆盖率/二项尾概率）；④ 按槽位表导出名字（只导出名字，不导出描述）。
只读：不碰游戏目录、不启动游戏、不写任何 `data/game` 文件。

---

## 10. 下一步建议

1. **直接用**：`refs/entity-locid-names.json` 的 `entity_index` 是 `实体键 → 名字` 的完整表，
   做 mod 时用 `Murmur64A(资源路径)` 当键即可反查名字（例如 `entities_modeb.py` 的 `WEAPON_KEYS` 就是这套键）。
2. 想把**军械库全部 199 件装备**的显示名补齐：现在 191/199 走百科拿到了，剩下 8 条只有 `dev_name`
   （srkit 资源名）或后端 id —— 要本地化文本只能去后端/`candidate_descs` 那条线找，实体库里没有。
3. 想给 UI 文案做本地化替换：§6 那 12 个组件的 131 个槽已经定位（HUD/交互/目标），
   这是"改写游戏内提示文字"的现成入口。
4. 解块 0 尾部的 u16 组件索引 → 能得到"实体 → 组件列表"，配合本表可以按组件类型批量筛选实体。

---

## 9. 复核补充（Lead，2026-10-22 晚）

### 9.1 `+8` 不是"大写名"，是**归属/父级显示名**

原文把 `+8` 当大写名（`name_upper`）。复核发现：517 条同时有 `+0/+8` 的条目里 **498 条**
`+8 == +0.upper()`，剩下 **19 条不是**，而其中 **18 条** 的 `+8` 正好是**另一个实体的名字**：

| 条目名（子） | `+8`（父） | 父实体类型 |
|---|---|---|
| `Fusion Repeater` | `FACTORY STRIDER` | unit |
| `Ballistic Missile` | `CANNON TURRET` | unit |
| `Chemical Backpack` ×2 | `BACKPACK` | backpack |
| `Larva Container` | `SPECIMEN VESSEL` | （名字变体，百科里没有同名实体） |
| `Wretch` | `WRETCH ` | enemy（尾随空格） |

结构性佐证：这两个"子"实体的组件里都有
`AttachableComponentData` + `TurretComponentData` + `WieldableComponentData` + `WeaponData` ——
它们是**可挂载的炮塔/部件**，不是独立单位。wiki 的
[Factory Strider](https://helldivers.wiki.gg/wiki/Factory_Strider) 也明写它"armed with twin
fusion gatling guns and a large burst-cannon"，伤害表里就有 `Fusion Gatling Guns` 与
`Repeater Cannon Impact / Blast`。

所以正确读法是：**`+8` = 这个实体"挂在谁身上"的显示名**。独立物品时它等于自己名字的大写
（`LIBERATOR`），部件/炮塔时它是**宿主**的名字（`FACTORY STRIDER`）。这也解释了为什么它
覆盖只有 73%、且与 `+0` 不成大小写关系。

### 9.2 爆炸类型 68 **不是孤儿**：被 `BombardmentComponentData +64` 引用

在全部 273 个可拆块里找"值集完全落在爆炸类型 id 集合内"的列，命中 851 列；其中**只有一列**
含 68：

```
BombardmentComponentData +64   23 行命中，17 个不同值：[68, 76, 79, 82, 86, 89, ...]
```

引用 68 的那一行（第 10 行）属于实体 `0xAEDC4A073FB4B925`，它的组件是：

```
BombardmentComponentData + LoadoutPackageComponentData
+ OrbitalShipComponentData + StratagemFiresupportComponentData
```

即**某个战备的火力支援弹幕**（轨道舰 + 火力支援 + 弹幕定义）。结合 §6.1 的
`fallback_damage_loc_name = 'Unknowable Forces'`，68 是"某战备的弹幕爆炸"，
归因文本写成"未知力量" —— 不是没人引用的孤儿，只是引用它的是**数据侧的战备弹幕**而不是投掷物。
（具体是哪一个战备仍未定：这条实体没有百科名，`dev_name` 也是空的。）

### 9.3 块 0 尾部那 27,050 个 u16：**不是块序号**（解码失败，但有替代品）

试了最自然的假设——"每实体一条组件块序号表"——**不成立**：

```
u16 个数 27,050（= 54,100 B / 2，与组件引用总数吻合）
去重 324 个值，值域 0..52,942（块序号只可能 0..274）
直方图与各组件块的键数逐块比较：完全一致 0/273
```

所以它是引擎侧的组件类型索引（另一套编号），当前没有映射表可以翻译它。

**替代方案已经做出来了**：不用这个数组，直接拿**每个组件块自己的哈希图**反查
（`refs/entity-components.json`，`tools/entity_components.py`）：

```
有组件记录的实体 1,932（另有 7 个块的类型没被 typelib 描述）
组件种类 272       最多的是 UnitComponentData 1,719 / Ability 994 / Behavior 993 / Attachable 812
```

**无名实体的成分**（1,289 个，支持"占位/未发布"的猜测但不全是）：

| 特征 | 数量 |
|---|---:|
| 组件数 ≤ 3（空壳/纯标记） | 422 |
| 含 `InteractableComponentData` | 254 |
| 含 `HealthComponentData` | 260 |
| 含 `DestructibleComponentData` | 216 |
| 含 `WeaponDataComponentData` | 92 |
| 含 `LoadoutEntryComponentData` | 8 |
| 含 `EncyclopediaEntryComponentData` 却没有名字 | **32** |

最后一行值得注意：**32 个实体有百科条目组件但名字槽是 0** —— 它们不是"没有名字"，是"百科条目
还没填名字"，典型的未完成/占位内容。
