# `stratagem_settings` 解码（build 25988413）

> 153 行 × 400 B，12 个组（每组一个系族）。**行名由每行自带的指针解析，153/153。**
> 整表导出：`refs/exports/stratagem_settings.csv`（153 行 × 68 字段，含 name / name_key / desc_key）。

**本版与上一版的三处实质改变**（上一版有两处结论被自己的数据否证了，这里直接改掉，不保留旧说法）：

| 上一版说法 | 现在的判定 | 依据 |
|---|---|---|
| 行名从尾部字符串块按行序取（153/153） | **✗ 否证** | 字符串池里一个行对应 2–4 条字符串（显示名 + `_name` 键 + `_desc` 键），按行序取会错位 |
| `+84` 像冷却秒数 | **✗ 否证** | 冷却在 `+104`（见 §4） |
| `+56` 只有 4 个值 ⇒ 对应 wiki 四类 | **✗ 否证** | `+56` 的 4 个值横跨 wiki 全部四类，不构成分类（见 §6） |

## 1. 结论摘要

| 判定 | 结论 |
|---|---|
| ✓ 实测 | **`+16` / `+24` / `+32` 是每行自带的 payload 相对 u64 指针**，分别指向显示名 / `_name` 键 / `_desc` 键。153/153 行解析出显示名，151 个不同值 |
| ✓ 实测 | **`+104` 是冷却秒数（f32）**。按名字逐条对 HD2Runtime 的 96 条目录，轨道系 11/12 精确相等 |
| ✓ 实测 | **`+392` 是"解锁格位"编号 1–36**。同一格 = 同一解锁槽的不同型号，0 = 不在战备面板上 |
| ⚠ 推断 | wiki 的红/蓝/绿三色 = `+392` 的三个区间（1–10 / 11–28 / 29–36）；黄色不是区间，是"不在面板上"那批 |
| ✗ 否证 | `+56`、`+60` 都不是 wiki 的许可分类 |

## 2. 文件结构：12 个组，不是 1 个

上一版把整张表当成一个组写「153 行」。实际是 **12 个 LDLD 组**，每组行数不等，合计 153：

| 组 | 行数 | 系族（`+16` 名字前缀） | 池大小 |
|---:|---:|---|---:|
| 0 | 13 | BACKPACK | 1,964 |
| 1 | 2 | CONSUMABLES | 344 |
| 2 | 11 | EAGLE | 1,420 |
| 3 | 9 | EMPLACEMENTS | 1,588 |
| 4 | 2 | （无前缀：EAGLE FLY BY / ORBITAL CONFETTI） | 276 |
| 5 | 36 | MISSIONS（含 1 条 BACKPACK） | 4,712 |
| 6 | 13 | ORBITAL | 1,800 |
| 7 | 7 | PRESIDENT REWARDS | 992 |
| 8 | 36 | TEAM WEAPONS | 4,892 |
| 9 | 9 | SENTRYS / SENTRIES | 1,244 |
| 10 | 2 | （教程：TUTORIAL…） | 264 |
| 11 | 13 | VEHICLES / TANK | 1,204 |

**每个组有自己的字符串池**，所以指针只对所属组的池有效。24 B 组头里 `+20` 的 4 字节在 12 个组里
**全是 0**；组身份只由"在文件里的顺序"决定，没有组级 id 字段。

## 3. 行自带名字指针（这一轮的关键）

### 3.1 判据：不是"能不能解析"，而是"每行解析出的是不是不同的串"

把每个 8 字节对齐的槽当 payload 相对偏移去取 NUL 结尾可打印串。**偏移 0 会对每一行都"命中"**
（都指向池里第一条串），所以必须看跨行有多少个**不同**的字符串：

```
slot   hits/rows  distinct  kinds
 +16    153/153      151    {'display': 148, 'other': 5}   <== 指针
 +24    128/153      116    {'nameKey': 128}               <== 指针
 +32    128/153      116    {'descKey': 128}               <== 指针
 +72      5/153        1    {'other': 5}                   巧合
+152      1/153        1    {'other': 1}                   巧合
```

`hits ≈ rows` 且 `distinct ≈ hits` ⇒ 每行拿到自己的串。`+72`/`+152` 只有三五次命中且全是同一个串
⇒ 小整数碰巧落在池里，排除。

### 3.2 直接读数

```
row 0  +16 -> 'BACKPACK. SUPPLY BACKPACK'
       +24 -> 'nui_stratagem_backpack_ammo_name'
       +32 -> 'nui_stratagem_backpack_ammo_desc'
```

`+24` 只有 128/153 命中，另外 25 行 `+24`/`+32` 为 0——都是没有本地化键的条目
（`(NOT USED)`、`Cyborg Carry Data`、教程串、`SEAF Squad`、`TANK RELOAD *` 这类）。

### 3.3 为什么这解决了一切

名字一旦可靠，之前做不了的事就都做得了：组 = 系族（直接从名字前缀读出）、`+392` 的语义（§5）、
逐名对冷切（§4）。**武器配件表是 1:1 行名数组，这张表是显式指针——两张表用两套命名机制**，
上一版的错误就来自把武器表那套照搬到这张表。

## 4. `+104` = 冷却秒数（按名字逐条验）

前一轮只是"数值集合与 wiki 吻合"。现在有名字，可以逐条对。用 HD2Runtime 0.28.1 的
`StratagemAuthoringCapabilities.json`（96 条具名战备，带 `cooldown`）做同系族内模糊配对，
阈值 0.80：**配对 22 条，冷却相同 20 条**。

轨道系全部 12 条（这是最有判别力的一族，冷却跨 70–300）：

| 名字 | 本表 `+104` | HD2Runtime |
|---|---:|---:|
| ORBITAL. PRECISION STRIKE | 80 | 80 ✓ |
| ORBITAL. GATLING BARRAGE | 70 | 70 ✓ |
| ORBITAL. GAS STRIKE | 75 | 75 ✓ |
| ORBITAL. AIRBURST STRIKE | **90** | **100** ⚠ |
| ORBITAL. 120MM HE STRIKE | 180 | 180 ✓ |
| ORBITAL. NAPALM BARRAGE | 240 | 240 ✓ |
| ORBITAL. 380MM HE BARRAGE | 240 | 240 ✓ |
| ORBITAL. WALKING BARRAGE | 240 | 240 ✓ |
| ORBITAL. SMOKE STRIKE | 75 | 75 ✓ |
| ORBITAL. STATIC FIELD CONDUTORS | 75 | 75（目录里叫 EMS Strike）✓ |
| ORBITAL. LASER | 300 | 300 ✓ |
| ORBITAL. RAILCANNON | 180 | 180 ✓ |

**Airburst 是唯一分歧**：本机 90.0，目录 100。90.0 是干净值、不是解码噪声，所以这更像
**两个 build 的数值差异**（⚠ 未定），不是字段读错。鹰式一族全是 15 s，冷却对配对没有判别力，
只能作旁证。

## 5. `+392` = 解锁格位（1–36）

三条独立证据：

**① 按系族连续分块**（`+392` 的取值区间与系族严格对应）：

| cell | 系族 | cell | 系族 |
|---|---|---|---|
| 1–6 | ORBITAL | 26–28 | VEHICLES |
| 7–10 | EAGLE | 29–32 | SENTRYS |
| 11–21 | TEAM WEAPONS | 33–36 | EMPLACEMENTS |
| 21–24 | BACKPACK | 0 | 不在面板上 |

**② 同一解锁槽的不同型号共用同一个号**——这是最硬的一条，因为"共用"不可能是巧合：

| cell | 同格条目 |
|---:|---|
| 19 | EXPENDABLE ANTI-TANK / (Booster) / NAPALM LAUNCHER / MASSIVE ROCKET / COMMANDO / EXPENDABLE MACHINEGUN / MINI MISSILE SILO |
| 20 | AUTOMATIC CANNON / BELT FED GRENADE LAUNCHER / RECOILLESS RIFLE / AIR BURST ROCKET / SPEAR / WASP / MINIGUN / HEAVY FLAMETHROWER / SNIPER RIFLE DUO |
| 24 | 5 个 GUARD DOG 变体 |
| 26 | 3 个 FRV 变体 |
| 28 | 4 个 COMBAT WALKER 变体 |
| 36 | 4 个 MINE DEPLOYER 变体 |
| 11 | MELEE FLAG / CHAINSAW GREATSWORD / SLEDGE HAMMER |

**③ `0` 是"不在面板上"**：50 行，全是任务物件、信标、教程、总统奖励、坦克装填
（`MISSIONS. EXTRACTION`、`REINFORCEMENT BEACON`、`PRESIDENT REWARDS.*`、`TANK RELOAD *`）。

> ⚠ 语义边界：说它是"战备面板的格子编号"是从上面三条**推**出来的（面板格 = 一个解锁槽，
> 上下箭头切型号），**没有在游戏 UI 里逐格核对过**。能确定的只有"同号 = 同一解锁槽、
> 号连续且按系族分块、0 = 非面板条目"。字段在导出的 CSV 里叫 `+392` / `ui_cell`。

## 6. wiki 四色：是 `+392` 的区间，不是一个字段

wiki（<https://helldivers.wiki.gg/wiki/Stratagems>）的四个许可色，对照 `+392`：

| wiki 类别 | 颜色 | `+392` 区间 | 系族 |
|---|---|---:|---|
| Offensive | 红 | **1–10** | ORBITAL 1–6、EAGLE 7–10 |
| Supply | 蓝 | **11–28** | TEAM WEAPONS 11–20、BACKPACK 21–24、VEHICLES 26–28 |
| Defensive | 绿 | **29–36** | SENTRYS 29–32、EMPLACEMENTS 33–36 |
| Mission | 黄 | **0** | 补给/增援/信标等非面板条目 |

⚠ 这是**从区间分布推出来的**（三段区间与三色严格重合），没有官方文档说过"颜色 = 格位区间"。
但黄色那类不适合当区间：`0` 里既有玩家能叫的 `RESUPPLY`/`SOS Beacon`，也有 ~40 条纯任务脚本物件。

**`+56` 的 4 个值不是这四类**——`0x2d96f9e6` 同时出现在 TEAM WEAPONS / BACKPACK / EAGLE /
MISSIONS / EMPLACEMENTS / SENTRYS / PRESIDENT REWARDS 上，横跨 wiki 全部四色，所以
"4 个值 ⇒ 4 类"只是数量巧合。`+56` 也不是任何已知类型哈希（对 6,698 条名字全表比对，无命中），
也不由 `+112/+116/+120/+148/+184/+212/+260/+272/+372` 任一字段决定。**含义仍未定**，
像某种投送/授权分组。

## 7. 字段表（本表 400 B 内目前能命名的）

| 偏移 | 类型 / 宽度 | 内容 | 判定 |
|---:|---|---|---|
| `+0` | `StratagemType` u32 | 每行一个 id，153 个不同值 | ✓ |
| `+16` | u64 指针 | **显示名**（如 `BACKPACK. SUPPLY BACKPACK`） | ✓ |
| `+24` | u64 指针 | **`_name` 本地化键**（128/153） | ✓ |
| `+32` | u64 指针 | **`_desc` 本地化键**（128/153） | ✓ |
| `+56` | u32 | 4 个值，含义未定，不是分类 | ⚠ |
| `+60` | `StratagemCategoryType` | 8 个值（2×94、3×17、0×12、1×11、4×11、5×6、6×1、7×1） | ⚠ 未映射 |
| `+64` | `StratagemButtonDirection` 16 B | 152 个不同值 ⇒ 方向键输入序列 | ⚠ |
| `+80` | u32 | `max_uses`：`0xFFFFFFFF`×125、1×12、3×7、2×6、4×2、5×1 | ✓ 外部佐证 |
| `+84` | f32 | 3.0×50、0×42、5.0×40 | ⚠ 不是冷却 |
| `+96` | f32 | 4.0×36、6.0×9、0×83 | ⚠ 未定 |
| **`+104`** | **f32** | **冷却秒数** | ✓ 逐名验证 |
| `+112` | `StratagemOriginType` | 来源类型 | ⚠ |
| `+116` | `StratagemCallInType` | 呼叫方式 | ⚠ |
| `+120` | `StratagemCallInLogic` 2 B | | ⚠ |
| `+124` | `StratagemObjectiveDropRequirement` | 18 个值 | ⚠ |
| `+148` | `StratagemCooldownType` | 3 个值 | ⚠ |
| `+184` | `StratagemHUDType` | 5 个值 | ⚠ |
| `+212` | `StratagemBeaconColor` | 3 个值 | ⚠ |
| `+260` | `StratagemInfoFlag` | 83 个值（疑为位域） | ⚠ |
| `+272` | `StratagemCustomizationTypeInfo` | 2 个值 | ⚠ |
| `+372` | `UnitCustomizationCollectionType` | 11 个值 | ⚠ |
| `+392` | u32 | **解锁格位 1–36，0 = 非面板** | ✓ 格位关系 / ⚠ UI 语义 |

## 8. 还没解决的

* **枚举取值没有名字**。类型库给了成员的类型名（`StratagemCategoryType` 等），但没给取值名，
  所以 `+60` 的 0–7 各自是什么分类仍然不知道。
* **`+56` 的 4 个值含义未定**。
* **`+392 = 面板格`的 UI 语义未实测**（见 §5 的边界说明）。
* `+84` / `+96` 未定。
* 上一版曾提出"用 `+0` 的 `StratagemType` 值反查名字表"这条路——**不需要了**，`+16` 直接给了名字。

## 9. 复现

```bash
# 整表导出（名字走行内指针，自动跳过位置配对）
python tools/table_export.py --table stratagem_settings --sk <你的>/recipient.sk --out out/st

# 全 55 张表扫一遍"行内名字指针"（这张表的 +16 就是它找到的）
python tools/row_pointer_sweep.py --sk <你的>/recipient.sk

# 单表判据：证明 +16/+24/+32 是每行自带的指针（并排除小整数巧合）
python tools/probe_row_name_offsets.py --table stratagem_settings --stride 400 --sk <你的>/recipient.sk

# 分类字段扫描：拿系族当标签，给每个槽打分（这一轮用它否证了 +56）
python tools/stratagem_field_scan.py --sk <你的>/recipient.sk

# 与 HD2Runtime 目录逐名对冷却
python tools/stratagem_join.py --sk <你的>/recipient.sk \
    --sdk refs/hd2runtime/HD2Runtime-0.28.1-sdk.zip
```

## 10. 出处

* 偏移 / 成员 / 组结构：本机 `generated_stratagem_settings.dl_bin`（解密后）与
  `dl_library.dl_typelib`（`StratagemInfo`，400 B / 67 成员）。
* 名字指针：本表行内数据自证（§3 的判据 + `tools/probe_row_name_offsets.py`）。
* 冷却 / 系族 / 战备名：**HD2Runtime 0.28.1** `StratagemAuthoringCapabilities.json`
  （96 条具名战备，MIT）。
* 四色分类：<https://helldivers.wiki.gg/wiki/Stratagems>。
* `+80 = max_uses` 与 `0xFFFFFFFF`：HD2Runtime 0.26.0 发布说明。
