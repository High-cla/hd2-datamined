# 武器射击模式 / 射速档位（fire modes & ROF）—— 数据表能力模型（build 26088801）

> **状态：核心已实机打通。** 能给**任意武器**加「全自动」「齐射」「全射」，能造/删安全模式，
> 也能改 rpm 三档。尚未打通：槽位上限 3、齐射的"多发"（受枪管数约束，在模型侧）。
> 相关：[CHARGE-WEAPONS](CHARGE-WEAPONS-26088801.md)（蓄力 / 过蓄 / 爆炸）·
> 依据：`refs/hd2runtime-repo/docs/fire-modes.md`、`docs/fire-rate-modes.md`、
> `sdk/WeaponFireModeCapabilities.json`。

---

## 0 一句话

武器有**两套独立的选择器**，都由 `WeaponDataComponentData.function_info` 绑定：
**`Firemode(3)` = 射击模式**（模式值写在 `+0x90…0x9C` 四连槽里）、**`ROF(2)` = 射速档位**
（三档 rpm 写在 `ProjectileWeaponComponentData +4/+8/+12`）。往空槽写枚举值就能给别的武器加模式。

---

## 1 字段位置

### 1.1 射击模式（`WeaponDataComponentData`）

| 偏移 | 字段 | 说明 |
|---|---|---|
| `+0x8C` | `num_burst_rounds` (u32) | 连发轮数（**十进制 140 = 0x8C**） |
| `+0x90` | **`primary_fire_mode`** | 默认模式（槽 1） |
| `+0x94` / `+0x98` / `+0x9C` | secondary / tertiary / quaternary | 依次可选；**0 = 空槽** |
| `+0xB8` / `+0xBC` | `function_info.left` / `.right` | `WeaponFunctionType`；**3 = `Firemode` 选择键、2 = `ROF` 射速选择键** |

⚠ **偏移坑**：上游文档写的是**十进制** `+140 / +144`。按十六进制读 `0x140` 会读到浮点数
（`0.7`、`0.9`），白查一轮 —— `+140 = 0x8C`、`+144 = 0x90`。

### 1.2 射速档位（`ProjectileWeaponComponentData`）

| 偏移 | 字段 | 说明 |
|---|---|---|
| `+4` / `+8` / `+12` | `rounds_per_minute` X / Y / Z（三个 f32） | **Y 是默认档**，也是没有选择器时唯一生效的 |
| — | `WeaponDataComponentData +0xB8/+0xBC` = `2` | `ROF` 选择器；按键按 `Y→Z→X→Y` 循环、跳过 0 槽 |

**射速不随射击模式变**：`rpm` 只有一份，所有模式共用（`fire-modes.md` 原文）。

---

## 2 `FireMode` 枚举表（**已基本填满**）

| 值 | 名字 | 游戏内中文 | 验证 |
|---:|---|---|---|
| 0 | None（空槽） | — | ✓ 空位一律 0 |
| 1 | **Automatic** | 自动 | **✓ 实机**（APW-1 加全自动后可切可连发） |
| 2 | **Single** | 半自动 | ✓ 官方命名 + 57 把只有 `[2]` |
| 3 | **Burst** | 连发 | ✓ 官方命名（AR-23 第三档） |
| **4** | **Volley** | **齐射** | **✓✓ 实机**：AR-23 切过去面板显示「齐射」；SDK 猜的 `Safety_Off` **✗ 错** |
| **5** | **Safe**（安全蓄力，蓄满即发） | 安全 | **✓ 实机**（删掉 Railgun 第二槽后只剩「安全」） |
| **6** | **Unsafe**（可过蓄） | 不安全 | **⚠ 强推断**（Epoch `[6,6]` 能过蓄 + Railgun `[5,6]`） |
| **7** | **Total**（倾泻全部剩余弹药） | **全射** | **✓✓ 实机**：AR-23 一次扣扳机打完整个弹匣、伤害叠加、弹壳全喷 |
| 8 | 未使用 | — | 373 把无一把出现 |

> 反查方法：把「武器在数据里的模式集合」与「wiki 页面的 Firing Modes 一栏」联立。
> `4` 由 SG-88「Semi • Volley」↔ `[2,4]` 与 VG-70「Total • Volley • Auto」↔ `[1,4,7]` **两边独立钉死**，
> 再由游戏内中文名「齐射 / 全射」**实机确认**。

---

## 3 编辑器规则（哪些能做、哪些做不了）

| 规则 | 判定 |
|---|---|
| 加模式 = 往空槽写枚举值 | **✓ 实机** |
| **必须**有 `Firemode(3)` 绑在某个输入上，否则**只能有一个模式**（换掉而非可选） | **✓ 实测结构**（APW-1 原本 `[0,0]` 无选择键） |
| **槽位上限 = 3**（写第 4 槽不显示） | **✓ 实机**（AR-23 第四槽 = 4 后，面板仍三档）<br>SDK 的 `maxModes: 4` **✗ 否证** |
| 非多管武器也接受 `Volley(4)` | **✓ 实机**（AR-23 单管照样能加能切） |
| `Volley` 的发数 = **枪管数**；枪管数**不在数据表**（社区 schema 无 `barrels`，只有 `pellet_count`） | **✓ 实机**：单管 AR-23 加齐射 = 一次一发 |
| `Total(7)` 对任意武器成立，一次打完整个弹匣、**伤害叠加** | **✓✓ 实机**（AR-23 一枪拆 1000 血 E/MG-101 炮台） |
| 射速 rpm 三档可改、可加选择器 | ✓ 离线（MG-43/M-105/MG-206 三档实测值见 §4.2） |

---

## 4 实验台账

### 4.1 射击模式（5 轮，3 ✓ / 1 ✗ / 1 部分）

| run | 变量 | 结果 |
|---:|---|---|
| 3 | Railgun `+0x94`（第二模式 Unsafe）`6 → 0` | **✓ 实机**：面板只剩「安全」⇒ 5 = Safe |
| 4 | APW-1 `+0x94` `0→1`（Automatic）+ `+0xBC` `0→3`（选择键） | **✓ 实机**：半自动/全自动可切、全自动能连发 |
| 5 | AR-23 `+0x9C`（第四槽）`0 → 4` | **✗ 实机**：面板不显示第四档 ⇒ 槽位上限 3 |
| 6 | AR-23 `+0x94`（Single）`2 → 4`（Volley） | **✓ 实机**：面板显示「齐射」能切；单管 ⇒ 一次一发 |
| 7 | AR-23 `+0x94`（Single）`2 → 7`（Total） | **✓ 实机**：一次扣扳机打空弹匣、伤害叠加、弹壳全喷 |

### 4.3 run 8：任意枪加射速切换（**已装盘，待实机**）

| 项 | 值 |
|---|---|
| 目标 | **AR-23 Liberator**（原版 `rpm = 0 / 640 / 0`，只有一个默认档） |
| 变量（一个逻辑能力） | ① `ProjectileWeapon +4/+8/+12` 写成 **100 / 500 / 1000**<br>② `WeaponData +0xB8`（`function_info.left`）`0 → 2`（`ROF` 选择键） |
| 结果 | `rpm = 100 / 500 / 1000`（默认 Y = **500**）；`function_info = (2, 3)` = 左 ROF / 右 Firemode |
| 模式槽 | 保持原版 `[1, 2, 3, 0]`（不掺入射速实验） |
| 为什么绑左输入 | **Railgun 的安全切换就绑在 `+0xB8` 且实机可用** ⇒ 左输入是能按到的真实绑定 |
| 离线 | 4 次链式 set，G1–G9 全 PASS；哈希不变；封包 sha256 `22391afb…` |

**切换顺序**（`fire-rate-modes.md`，game.dll `0x617960`）：按键循环 `Y → Z → X → Y`、跳过 0 槽。
⇒ 实测应按出 **500 → 1000 → 100 → 500**，三档差别极大（每发 0.6 s / 0.06 s / 0.1 s 间隔）。

**判据**：

| 你看到 | 结论 |
|---|---|
| 按功能键能在三档之间循环、射速明显变化 | **✓ 射速路线对任意武器成立** ⇒ 能给任何枪加"慢/标准/极速"三档 |
| 按功能键没反应、射速恒定 500 | 左输入没有对应的按键绑定 ⇒ 改成 `function_info.right = 2` 再试（把 Firemode 挪到左） |
| 射速变化但**不是 500/1000/100** 那个顺序 | 记录实际顺序，修正"菜单顺序 = X/Y/Z"这条假设 |
| 射速改了但**只有一档** | 需要把 `rpm` 三档都非 0（本次已全非 0，若仍失败说明槽位另有条件） |

### 4.2 射速档位（离线）

| 武器 | rpm X / Y / Z | 射击模式槽 | `function_info`（左/右） |
|---|---|---|---|
| **MG-43 Machine Gun** | **630 / 760 / 900** | `[1]` | (0, **2 = ROF**) |
| **M-105 Stalwart** | **700 / 850 / 1150** | `[1]` | (0, **2 = ROF**) |
| MG-206 HMG | 450 / 600 / 750 | `[1]` | (0, **2 = ROF**) |
| **VG-70 Variable** | 300 / 550 / 750 | `[1,4,7]` | (**3**, **2**) ← 两套选择器都有 |
| APW-1（改后） | 0 / 400 / 0 | `[2, 1]` | (0, **3**) |
| AR-23（改后） | 0 / 640 / 0 | `[1, 7, 3]` | (0, **3**) |

---

## 5 能做什么（配方）

| 想要 | 写入 |
|---|---|
| 任意枪加**全自动** | 空槽（或替换现有档）写 `1`；没选择键的先给 `+0xB8`/`+0xBC` 写 `3` |
| 任意枪加**一键倾泻整个弹匣**（伤害叠加） | 写 `7`（**已验证可用**，`Total` 不依赖枪管数） |
| 任意枪加**连发** | 写 `3`（配 `+0x8C` 轮数） |
| 加**齐射** | 写 `4`（但只有多管枪会真打多发；单管 = 一发） |
| 让某把枪**恒定安全模式 / 永久不安全** | 改 `5` / `6` 两个槽 |
| 给任意枪加**射速切换** | `ProjectileWeapon +4/+8/+12` 写三个 rpm + `function_info` 某输入写 `2`（**run 8 待验**） |

---

## 5.5 双弹源 = 主武器 + **下挂武器（两个独立实体）**

有一类武器能切两种弹头，而且**弹匣与备弹都各自独立**（不像 `fnable ammo` 那样共用弹匣）：
**AR/GL-21 One-Two · AR-11 Arbitrator · SMG/FLAM-34 Stoker**。

### 5.5.1 机制：不是"一把枪两个弹池"，是**两个实体**

> 官方研究原文（`research/underbarrel-weapons-F5FEE03DCFDB.json`）：
> *"An underbarrel is a **separate weapon entity** named by the host's default underbarrel item —
> its delta sets **`WeaponCustomization +192 underbarrel_path`** to the entity;
> the host entity carries none of its records."*

⇒ 主武器与下挂**各有一套** `WeaponData` / `ProjectileWeapon|SprayWeapon` /
`WeaponRounds|WeaponMagazine` / `WeaponReload`，所以弹药天然不共用。

### 5.5.2 字段链（三层）

| 层 | 字段 | 本 build 实测 |
|---|---|---|
| ① 切换键 | **`WeaponDataComponentData +0xB8`（`function_info.left`）= `11`**<br>`WeaponFunctionType 11` = 第二弹源/下挂 | **全表 373 把里只有 3 把是 11**，正是这三把（其余：`0`×355、`3`×5、`8`×6、`2/4/6/10` 各 1） |
| ② 链接 | **`WeaponCustomizationComponentData +192` `underbarrel_path`**（由"默认下挂配件"的**实体 delta** 写入） | 基础组件里该格**全为 0** ⇒ 链接在 `generated_entity_deltas.dl_bin`，不在实体表本体 |
| ③ 下挂自身 | 下挂实体自己的 `ProjectileWeapon +0` / `WeaponRounds +72/+80` / `WeaponReload +56` | 见下表 |

### 5.5.3 三把武器 + 它们的下挂（本 build 实测）

| 宿主 | 下挂实体 | 家族 | 弹丸类型 | 容量 | 备弹 | 射速 | reload |
|---|---|---|---:|---:|---:|---:|---:|
| **AR/GL-21 One-Two** | `0x02CD7321CD8445F5`（"Grenade Launcher Grenadier"，与 **GP-31 Grenade Pistol 共用根**） | Projectile（榴弹） | **267** | **1** | **5** | 900 | 0 |
| **AR-11 Arbitrator** | `0xB9C209B4F99B5335`（"shotgun risk"） | Projectile（霰弹） | **201** | **4** | **20** | 80 | 0 |
| **SMG/FLAM-34 Stoker** | `0x992B6F65A5BAB53D`（"Flamerthrower SMG Flamer"，与 **P-72 Crisper 共用根**） | SprayWeapon（喷火） | `+200`=22 | mag **50** | — | — | 2.5 |

- 下挂的 `WeaponData.function_info = (0, 0)` ⇒ 它自己没有选择键，全靠宿主那个 `11` 切进来。
- 下挂的弹丸在**两处**都写着同一个值（`ProjectileWeapon +0` 与 `WeaponRounds +64` 均为 267/201），
  **究竟哪个生效未证**（研究文件把它列为 unproven）。

### 5.5.3b run 9：把 AR/GL-21 的榴弹下挂换成 **GP-20 Ultimatum** 的弹头（**已装盘，待实机**）

| 项 | 值 |
|---|---|
| 变量 | 下挂实体 `0x02CD7321CD8445F5`：`ProjectileWeapon +0` 与 `WeaponRounds +64` 同时 **267 → 105** |
| 为什么改两处 | 两处现在写着同一个弹丸 id，研究文件把「到底哪个生效」列为 unproven ⇒ 一起改 |
| GP-20 的弹丸 | **105**（其 `ProjectileWeapon +0`，行 240） |
| 弹丸 105 的效果 | 命中/到期爆炸 = **type 44** → 伤害 100、半径 **2.5 / 5 / 14 m**、无破片 |
| 对照 | **GP-31 的根是另一个实体** `0x52E4334E6A128CAF`（`+0` 仍 267）⇒ 理论上**不会**跟着变；带 GP-31 可验证 |
| 离线 | G1–G9 全 PASS；哈希不变；封包 sha256 `f1f60cb6…`；回读 `+0`=105、`+64`=105、GP-31 仍 267 |
| **实机** | **✓ 下挂打出来就是 GP-20 的弹头；GP-31 完全不变** |

⇒ 两个结论同时坐实：

1. **下挂的弹丸可以任意换**（改 `ProjectileWeapon +0` 与 `WeaponRounds +64`），宿主武器本体不受影响；
2. **catalog 的"共用根"说法是错的** —— `catalogCorrections` 里那条把下挂根误列进 GP-31，
   实际两者是两个实体、**只是引用同一个弹丸 id 267**；改下挂弹丸 ⇒ **GP-31 不动**（实机）✓。

### 5.5.4 由此得到的操作面

| 想做什么 | 可行性 |
|---|---|
| 改某把武器的**下挂**弹丸 / 容量 / 备弹 / 射速 | **✓ 实机**（run 9：AR/GL-21 下挂换成 GP-20 弹头；容器/备弹仍独立） |
| 把下挂**换成别的武器**（例：给它换成火焰喷射下挂） | ⚠ 需改 `generated_entity_deltas.dl_bin` 里那条默认配件的 `WeaponCustomization +192`，属另一张表，**未试** |
| 给**没有下挂**的枪加下挂（例：AR-23 加榴弹） | ⚠ 同上：必须写 entity delta + 配件 item，且要给宿主 `function_info.left` 写 `11`；**三件事**，未试 |
| 把下挂的弹匣/备弹和主武器**合并** | ✗ 结构上它们本就是两个实体，没有"共享"字段 |

---

## 5.6 输出族：喷火/毒气是**第 4 族 `Spray`**，不是弹丸

### 5.6.1 五族模型

一个武器实体**只能拥有一个输出族组件**（社区原文：*"A weapon entity owns exactly one output-family component
(ProjectileWeapon, BeamWeapon, ArcWeapon, **SprayWeapon** or MeleeWeapon)"*）：

| 族 | 组件 | type | 它的"弹丸"是什么 |
|---|---|---|---|
| 弹丸 | `ProjectileWeaponComponentData` | `0x45171B68` | `+0` ProjectileType → 射弹表一行 |
| 光束 | `BeamWeaponComponentData` | `0xF0721C2C` | `+0` BeamType |
| 电弧 | `ArcWeaponComponentData` | `0xB845669E` | `+0` ArcType |
| **喷流** | **`SprayWeaponComponentData`** | **`0x8E551126`** | **没有弹丸**：`+0xC8`（=十进制 200）`DamageInfoType` |
| 近战 | `MeleeWeaponComponentData` | `0xBBA9003F` | `+12` DamageInfoType |

⇒ **喷火器/毒气枪属于 `Spray`**：它不发射任何 projectile，而是"喷一段带伤害类型的锥形流"，
伤害与命中由 `+200` 那个小枚举决定，视觉由行内若干哈希（粒子/材质）决定。

### 5.6.2 本 build 实测（`SprayWeaponComponentData` @`0x2CD4E50`，46 槽 + 23 行 × 224 B）

| 武器 | 行 | `+200` | 备注 |
|---|---:|---:|---|
| **FLAM-40 Flamethrower** | 20 | **20** | 装备侧用 `WeaponMagazineComponentData`（弹匣，不是 Rounds） |
| FLAM-66 Torcher | 17 | 21 | |
| **P-72 Crisper** | 13 / 18 | **22** | 与 **Stoker 的喷火下挂**共用同一行（`0x992B6F65A5BAB53D` → row 13） |
| **TX-41 Sterilizer**（毒气） | 19 | **35** | 实体 `0x88F61AFFF48AC8A4`；`func/attack` 图里标 `kind: Spray` |
| G-142 Pyrotech | 10 | 32 | |
| 其它未命名行 | 3 / 7 / 11 / 15 / 16 / 21 / 22 | 591 / 24 / 24 / 21 / 36 / 23 / 23 | 敌人喷火（`flamer/conscript_flamer` 等）与未发布武器 |

### 5.6.3 行内结构（FLAM-40，224 B）

```
+0x00 f32 = 0.7        +0x04 f32 = 10
+0x0C / +0x18 / +0x1C  三个哈希（粒子 / 音效 / 材质之类）
+0x30 / +0x68 / +0xA0  ★ 三段重复结构，每段 (f32 2.0, f32 5.0, hash, hash, ...)
                          ⇒ 像是"近/中/远"或"起始/持续/收尾"三段喷流参数（⚠ 未证）
+0xC0 =1  +0xC8 = ★DamageInfoType  +0xCC =2  +0xD0 =1
+0xD4 / +0xD8 两个哈希  +0xDC =3
```

⚠ `+200` 的取值（20/21/22/35 …）**不在** `names-all.json` 的 `DamageInfoType` 全局 id 空间里
（那份名表 252 条、id 6..661，其中 `12 = DamageInfoType_Projectile_Flamethrower`）。
⇒ 它是 **`SprayWeapon` 组件自己的小枚举**（含义 = 火焰/毒气/酸等），**命名尚未解出**。

### 5.6.4 毒气比喷火多一层：`Status`

TX-41 的 attack graph（`sdk/SupportWeaponAuthoringCapabilities.json`）：

```
TX-41 STERILIZER S            kind=Spray   role=primary
├─ Gas Var2                   kind=Status  role=primary_status_43
└─ Gas Confusion Var2         kind=Status  role=primary_status_45
```

⇒ **伤害来自 Spray，中毒/迷惑来自 `Status` 攻击**（两套独立数据；状态效果在
`generated_status_effect_settings.dl_bin`）。所以"把喷火器改成毒气枪"不是单改一个 id 能成的，
至少要动 Spray 的 `+200` **并且**给它挂上 Status 攻击。

### 5.6.5 三态

| 结论 | 态 |
|---|---|
| 存在第 4 个远程输出族 `SprayWeaponComponentData` | **✓ 离线**（社区模型 + 本 build 23 行实测，喷火/毒气/敌人喷火全在其中） |
| 喷火器不发射 projectile | **✓ 离线**（没有 ProjectileWeapon 组件；只有 Spray + Magazine） |
| `+200` = 喷流的伤害/命中类型 | **✓ 离线**（与社区 `+200 DamageInfoType` 一致；数值分火焰组 vs 毒气组） |
| `+200` 各值的具体名字 | **⚠ 未解**（不在全局 DamageInfoType 名表里） |
| `+0x30/+0x68/+0xA0` 三段结构的语义 | **⚠ 未证**（推测近/中/远或起/续/收） |
| 毒气的"中毒"来自 Status 攻击而非 Spray | **✓ 离线**（TX-41 的 attack graph） |

---

## 6 三态 / 未解

| 结论 | 态 |
|---|---|
| 模式槽 = `FireMode` 枚举、`0` 为空 | **✓ 离线** |
| `Firemode(3)` 是模式选择键、`ROF(2)` 是射速选择键 | **✓ 离线 + 实机**（APW-1 加 3 后能切） |
| 1 = 自动、2 = 半自动、3 = 连发 | **✓** |
| 4 = 齐射、5 = 安全、7 = 全射 | **✓ 实机** |
| 6 = 不安全 | **⚠ 强推断**（未单独验） |
| 槽位上限 = 3 | **✓ 实机**（并否证 SDK 的 `maxModes: 4`） |
| 齐射发数 = 枪管数，枪管数不在数据表 | **✓ 实机 + 离线** |
| `Total` 的"自伤/掀翻"阈值（VG-70 是 >22 发） | **⚠ 未证**（AR-23 打 45 发用户未报自伤，待确认） |
| 给任意枪加**射速切换** | **⚠ 待 run 8**（AR-23：100/500/1000 + 左输入绑 ROF） |
| 要把"齐射多发"给单管枪 | **✗ 数据表做不到** ⇒ 需改 `unit`/`state_machine` 的 muzzle 定位点（资源路线） |
| **双弹源 = 主武器 + 下挂武器两个独立实体**（非弹池共享） | **✓ 离线**（研究文件 + 本 build 三把实测） |
| 切换键 = `function_info.left = 11`（`WeaponFunctionType 11`） | **✓ 离线**：全表只有这 3 把是 11，一一对应 |
| 链接字段 = `WeaponCustomization +192 underbarrel_path`（本 build 基础值为 0，来自 entity delta） | **✓ 离线** |
| 改下挂的弹丸/容量/备弹 | **✓ 实机**（run 9）—— 这是「给主武器加一个**独立弹药池**的第二弹头」的现成入口，**不依赖 programmable ammo** |
| 给无下挂武器加下挂 | **⚠ 未试**（要写 entity delta + item + `func.left=11`） |
