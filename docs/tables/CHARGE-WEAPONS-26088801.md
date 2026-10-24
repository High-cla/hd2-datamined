# 蓄力武器（charge-up）—— 组件表定位与字段图（build 26088801）

> **状态：run 1 ✓ 实机（ARC-3 蓄满时间 1.1→0.05 后「按下几乎立刻能放电」）；
> 过蓄（overcharge）线已定位到爆炸行与伤害行，run 2（Railgun 过蓄不自伤）已装盘待测。**
> 相关：[LOCKON-TARGETING](LOCKON-TARGETING-26088801.md)（锁定线）· 社区结构来源：`xypwn/filediver`
> `datalibrary/weapon_charge_component.go`

---

## 0 一句话

蓄力在 **`WeaponChargeComponentData`**（`0xEAC335A1` @ 明文 **`0x0075E5D0`**）里，
每把武器一行 **216 B**，里面是 **三档蓄力状态（Min / Full / Over）× {蓄力时间, 弹丸类型}** + 一整组
**蓄力倍率**（速度/伤害/穿甲/电弧距离/分裂/链数）+ 音效与材质句柄。
**「能不能不蓄满就开火」直接对应 `Min` 档的 `ProjType` 是否为 0**（见 §2）。

---

## 1 表的几何

| 项 | 值 |
|---|---|
| 组件类型 | `WeaponChargeComponentData` = `0xEAC335A1`（旧 build schema 与本 build 同值） |
| 块头 | `0x0075E5D0`（`payload = 块头 + 28`） |
| payload | 3,456 B = **20 槽 × 16 + 11 行 × 216** |
| 行 stride | **216 B**（与社区 `WeaponChargeComponent` 的结构尺寸**逐字节吻合**） |
| 键 | 武器 GUID（不是行号）；行基址 = `payload + 20×16` = `0x0075EC6C`… 见 §4 |

> 同族还存在 `WeaponHeatComponentData`（`0x4C981CD9` @`0x1A8E660`，60 槽 / 31 行 × 592）
> 与 `WeaponWindUpComponentData`（`0x84CE7EEE` @`0xC5BB8`，18 槽 / 10 行 × 36）——
> 前者是激光类"过热"，后者是前摇/摇把，**都不是**蓄力；查蓄力只看 Charge 表。

---

## 2 行内字段图（216 B，已用数据逐项校准）

```
+0x00 ChargeStateSetting[0]  Min 档   ┐
+0x18 ChargeStateSetting[1]  Full 档  ├ 每档 24 B：
+0x30 ChargeStateSetting[2]  Over 档  ┘  +0x00 ChargeTime(f32,秒) +0x04 ProjType(u32)
                                         +0x08 ProjectileParticle(u64) +0x10 ThinHash(u32) +0x14 pad

+0x48 ProjectileMultipliers = 12 × f32（48 B）
        SpeedMin / SpeedOver · DamageMin / DamageOver · PenetrationMin / PenetrationOver
        DistanceMin / DistanceOver · ExtraArcSplitsMin / Over · ExtraArcChainsMin / Over

+0x78 ChargeStartSoundID      +0x7C ChargeStopSoundID
+0x80 ReadyToFireSoundID      +0x84 DangerOverchargeSoundID
+0x88 ChargeMesh  +0x8C ChargeMaterial  +0x90 ChargeVariable   (+0x94 pad)
+0x98 ChargeUpMuzzleFlash(u64)  +0xA0 ChargeUpMuzzleFlashLoop(u64)
+0xA8 ChargeAnimID  +0xAC ChargeEndAnimID  +0xB0 ChargeRateAnimID  +0xB4 SpinSpeedAnimID
+0xB8 AutoFireInSafety(u8)   ← 关掉 = 按住扳机能一直保持蓄力
+0xB9 ExplodesOnOvercharged(u8)
+0xBC ExplosionAudioEvent(u32)  +0xC0 UnknownFloat(f32)
+0xC4 DryFireAudioEvent(u32)    +0xC8 ExplodeType(u32)
+0xCC StateValue.State(u32)     +0xD0 StateValue.Value(f32)   (+0xD4 pad) → 合计 216 ✓
```

**校验方式**：`0xB8` 处四把枪读出 `u32=256` ⇒ 字节 `0xB8=0`、`0xB9=1`
（`AutoFireInSafety=0`、`ExplodesOnOvercharged=1`），与社区 bool 顺序一致；结构总长 216 = 我们的 stride。

---

## 3 ★ 关键相关性：「要不要蓄满」= `Min.ProjType` 是否为 0

`ChargeStateSettings` **每一档都有自己的 `ProjType`**。实测（`+0x04` / `+0x1C` / `+0x34`）：

| 武器 | Min 档 type | Full 档 type | 玩家行为（用户描述） |
|---|---:|---:|---|
| **PLAS-101 Purifier** | **131** | 301 | **不蓄满也能开火** ✓ |
| PLAS-15 Loyalist | **72** | 346 | 能（同类三档弹丸） |
| PLAS-45 Epoch | **168** | 196 | 能（同类三档弹丸） |
| **PLAS-39 Accelerator** | **0** | 0 | **必须蓄满** ✓ |
| **ARC-3 Arc Thrower** | **0** | 0 | **必须蓄满** ✓ |
| RS-422 Railgun | 0 | 0 | 必须蓄满（实际一致） |

⇒ **有 Min 档弹丸 = 可以"打弱的一发"；三档全 0 = 只能等 Full**。
（三档全 0 并不意味着"没弹丸"，而是本组件不按蓄力换弹丸，弹丸来自 `ProjectileWeapon`/`ArcWeapon` 等其它组件。）

⚠ 这是**离线强相关**（6/6 与现象一致），运行期因果**未证**——见 §6 的判据设计。

---

## 4 六把蓄力武器的实际数值（本 build）

| 武器 | 行 | Min 时间 | Full 时间 | Over 时间 | Speed Min/Over | Dmg Min/Over | Pen Min/Over | Dist Min/Over |
|---|---:|---:|---:|---:|---|---|---|---|
| PLAS-39 Accelerator | 2 | 0.45 | **0.50** | 0.90 | 0.7 / 1.0 | 1.0 / **2.5** | 1 / 1 | 0.7 / 1.4 |
| PLAS-101 Purifier | 4 | **0.01** | 1.00 | 1.00 | — | — | — | — |
| PLAS-15 Loyalist | 5 | **0.01** | 0.75 | 3.00 | 1 / 1 | 0.5 / 1 | 0.55 / 1 | 0.7 / 1.4 |
| **ARC-3 Arc Thrower** | 6 | **1.00** | **1.10** | 1.20 | 0.7 / **1.4** | 1 / 1 | 1 / 1 | 1 / 1（电弧倍率另有 `Splits/Chains`，ARC-3 全 0） |
| PLAS-45 Epoch | 8 | 1.00 | 2.50 | 2.60 | 1 / 1 | 1 / 2 | 1 / 1 | 0.7 / 1.4 |
| RS-422 Railgun | 9 | 0.45 | 0.50 | 3.00 | 0.7 / 1.0 | 1.0 / 2.5 | 1 / 1 | 0.7 / 1.4 |

> Accelerator 与 Railgun 的倍率组**完全相同**（0.7/1.0 · 1.0/2.5 · 1/1 · 0.7/1.4），像是同一套"单发重击"模板。

---

## 5 怎么改

与锁定线同一套（实体表通用原语），只需换 `--block` / `--key` / `--field`：

```bash
python tools/entity_field_set.py show --block 0xEAC335A1 --key 0x96DE9CD50F7306E6 --width 216   # ARC-3
python tools/entity_field_set.py set  --plain <in> --block 0xEAC335A1 --key <武器 GUID> \
    --field 0x18 --type f32 --value 0.05 --expect-old 1.1 --out <out>
# 封装 / 装机 / 回读 同 LOCKON-TARGETING §5
```

可改的旋钮（按有用程度）：

| 目标 | 字段 |
|---|---|
| 蓄满更快 / 几乎不用蓄 | `+0x18` Full.ChargeTime（配合 `+0x00` Min、`+0x30` Over） |
| 允许"不蓄满就开火" | `+0x04` Min.ProjType（要填一个合法的弹丸类型 id） |
| 蓄力对伤害的加成 | `+0x54` DamageMin / `+0x58` DamageOver |
| 过充会炸自己 | `+0xB9` ExplodesOnOvercharged |
| 按住扳机保持蓄力 | `+0xB8` AutoFireInSafety |

---

## 6 run 1：ARC-3 蓄满时间 → 0.05（**已装盘，待实机**）

| 项 | 值 |
|---|---|
| 变量 | **ARC-3 `WeaponChargeComponentData`：Min `1.00→0.02` · Full `1.10→0.05` · Over `1.20→0.06`**（一个逻辑变量：三档蓄力时间） |
| 其余 | 只叠加已证的 `P-92 锁定距离 300` + `Spear lock_t 0.05`；Accelerator 等**未动** |
| 离线 | G1–G9 全 PASS ×3 次链式；哈希 `0x8E49771B181FFAA1` 不变 |
| 装盘 | 相对上一版**只差 11 字节**（三个 f32 + 末块尺寸）；封包 sha256 `a5b7c49d…` |
| 盘上回读 | ARC-3 `Min=0.02 / Full=0.05 / Over=0.06`；Accelerator 仍 `0.45/0.50/0.90` |

**实机结果（用户原话）**：「**按下几乎立刻能放电**」✓ —— `ChargeTime` **就是蓄力时长（秒）**。

⇒ 三档时间可任意压短；同样的做法可套到 Accelerator（`0.50`）、Railgun（`0.50`）、Epoch（`2.50`）。

---

## 6.5 过蓄（overcharge）：伤害怎么变、爆炸是哪一行

### 6.5.1 伤害随蓄力变化的机制 = `ProjectileMultipliers`

社区结构里每项属性**只有两个端点**：`…Min`（最小蓄力时）与 `…Over`（完全过蓄时），
中间由引擎按蓄力程度插值。实测：

| 武器 | DamageMin | **DamageOver** | PenMin / PenOver | SpeedMin / SpeedOver | DistMin / DistOver |
|---|---:|---:|---|---|---|
| **RS-422 Railgun** | 1.0 | **2.5** | 1 / 1 | 0.7 / 1.0 | 0.7 / 1.4 |
| **PLAS-45 Epoch** | 1.0 | **2.0** | 1 / 1 | 1 / 1 | 0.7 / 1.4 |
| PLAS-39 Accelerator | 1.0 | **2.5** | 1 / 1 | 0.7 / 1.0 | 0.7 / 1.4 |
| PLAS-15 Loyalist | 0.5 | 1.0 | 0.55 / 1 | 1 / 1 | 0.7 / 1.4 |

⇒ **这正是「蓄满到过蓄之间伤害会变」的来源**：从 `DamageMin` 一路涨到 `DamageOver`。
Railgun 是 **1.0× → 2.5×**（涨 150%），Epoch 是 **1.0× → 2.0×**。

另有一条**独立**的变化通道：Epoch 的三档 `ProjType` 不同（Min `168` → Full/Over `196`），
即"换弹丸"；Railgun 三档全 0（不换弹丸，只吃倍率）。

### 6.5.2 过蓄爆炸对应的爆炸行（`generated_explosion_settings.dl_bin`）

蓄力行 `+0xC8` = `ExplodeType`，指向爆炸表里的行。**逐武器实测 + wiki 对照**：

| 武器 | `AutoFireInSafety` `+0xB8` | `ExplodesOnOvercharged` `+0xB9` | `ExplodeType` `+0xC8` | 爆炸行 | 半径（内/中/外） | 伤害类型 | 伤害 / 耐久 |
|---|---:|---:|---:|---:|---|---:|---:|
| **RS-422 Railgun** | 0 | **1** | **326** | 209 | **0.4 / 2 / 3 m** | 362 | **300 / 300** |
| **PLAS-45 Epoch** | 0 | 0 | **321** | 107 | 3 / 4 / 5 m | 68 | **800 / 800** |
| PLAS-39 Accelerator | 0 | 1 | 326 | 209 | 0.4 / 2 / 3 m | 362 | 300 / 300 |
| Purifier / ARC-3 / Loyalist | 0 | 1 | 269 | 208 | 0.4 / 2 / 3 m | 362 | 300 / 300 |

**★ 关键：爆炸行 `+0x4` 是「伤害类型 id」，不是「伤害行号」。**
`type 362` → damage 表 **行 350**，逐字段与 wiki 的 *Railgun Overcharge E* 完全吻合：

| damage 行 350（type 362） | 值 | wiki「Overcharge E」 |
|---|---:|---|
| `+4` 伤害 / `+8` 耐久 | **300 / 300** | 300 / 299-0 ✓ |
| `+12` 内圈 AP | **3** | 3 Medium ✓ |
| `+28` 爆破力 | **20** | 20 ✓ |
| `+32` 硬直 | **5** | 5 ✓ |
| `+36` 推力 | **40** | 40 ✓ |

⇒ **爆炸 type 326（行 209）就是「RS-422 Railgun Overcharge E」**（半径 0.4/2/3 m 也一致）。
Epoch 的 type 321 则是 **800 伤害、3-4-5 m** 的大爆炸 —— 但它的 `ExplodesOnOvercharged=0`，所以
"过蓄会不会炸"可能还有别的判据（**未证**）。

⚠ **踩过的坑（记下来）**：最初把 `+0x4` 当成"伤害行号"去查 `damage row 362`，读出 2000 伤害，
与 wiki 的 300 冲突 —— 是 wiki 图把它逼出来的。**伤害表是「type → 行」的间接引用，不是行号。**

### 6.5.3 run 2：Railgun 过蓄不再自伤（**已装盘，待实机**）

| 项 | 值 |
|---|---|
| 文件 | **`generated_explosion_settings.dl_bin`**（不是实体表，独立备份/回滚） |
| 变量 | **爆炸 type 326 行内 `+0x4`（伤害类型 id）：`362` → `32`** |
| 为什么选 `32` | damage 表 `type 32` = 行 31，**伤害 0 / 耐久 0**，且**当前没有任何爆炸行引用它** ⇒ 零副作用 |
| 只影响 | type 326 这一条；**type 269 仍指 362、type 321 仍指 68**（盘上回读确认） |
| 离线 | G1–G6 全 PASS；哈希 `0x2ABCD21D2536373D` 不变；封包 sha256 `b2e6bf0f…`（68,204 B） |
| 保留 | 爆炸的**视觉与音效不变**（半径/音效句柄都没动），只是不再造成伤害 |

**实机判据**：带 **RS-422 Railgun** 进图，蓄满后**继续按住到过蓄**——

- ✓ 若**照旧爆闪/爆响但自己不掉血** ⇒ 确认 type 326 + 伤害类型 362 就是过蓄自毁
- ⚠ 若**完全不爆了**（连特效都没）⇒ `+0x4` 同时兼作"是否爆炸"的开关，应改回 362 并改伤害行 350 的 `+4/+8`
- ✗ 若**照旧被炸死** ⇒ 过蓄自毁走的是另一条路（不在 `ExplodeType` 里）

---

## 6.6 安全模式（Railgun 安全 / 不安全）—— 由「开火模式槽」的 FireMode 值决定

### 6.6.1 开火模式块（在 `WeaponDataComponentData` 里）

| 偏移 | 字段 | 说明 |
|---|---|---|
| `+0x8C` | `num_burst_rounds` (u32) | 连发轮数，武器级 |
| `+0x90` | **`primary_fire_mode`** (FireMode) | **默认模式（槽 1）** |
| `+0x94` / `+0x98` / `+0x9C` | secondary / tertiary / quaternary | 依次可选；**0 = 空槽** |
| `+0xB4` … `+0xC0` | `function_info` (WeaponFunctionType) | **值 3 = `Firemode` 选择键**（绑到左/右输入） |

**`FireMode` 枚举**：`None 0` · `Automatic 1` · `Single 2` · `Burst 3`；
**`4–8` 是 charge 与 safety 档，无名、只读、游戏里不会提供**
（来源：`refs/hd2runtime-repo/docs/fire-modes.md` + `sdk/WeaponFireModeCapabilities.json`）。

⚠ **偏移坑**：文档写的是**十进制** `+140 / +144`。按十六进制去读 `0x140` 会读到浮点（如 `0.7`、`0.9`），
白查一轮 —— `+140 = 0x8C`、`+144 = 0x90`。

### 6.6.2 本 build 的模式组合分布（373 把）

| 组合 | 数量 | 例子 |
|---|---:|---|
| `[1]` | 252 | 绝大多数自动武器 |
| `[2]` | 57 | 单发 |
| `[1,2,3]` | 25 | 自动 / 单发 / 连发 |
| `[1,2]` | 11 | — |
| `[3]` | 9 | 只有连发 |
| **`[2,4]`** | 3 | **DBS-2 Double Freedom · SG-22 Bushwhacker · SG-88 Break-Action Shotgun** |
| **`[5,6]`** | **2** | **ARC-3 Arc Thrower · RS-422 Railgun** |
| `[1,4,7]` | 2 | VG-70 Variable |
| **`[6,6]`** | 1 | **PLAS-45 Epoch** |
| **`[5]`** | 1 | **PLAS-15 Loyalist** |

⇒ `4` 出现在折管霰弹枪（手动上膛类），`5/6` 出现在蓄力枪上。

### 6.6.3 ★ 谁是安全、谁是不安全

| 武器 | 模式槽 | `function_info` 绑了 Firemode(3)？ | 玩家可切换？ |
|---|---|---:|---|
| **RS-422 Railgun** | `[5, 6]` | **是（`+0xB8` = 3）** | **能切安全/不安全** |
| ARC-3 | `[5, 6]` | 否 | 第二槽不可达（等于只有一个模式） |
| **PLAS-45 Epoch** | `[6, 6]` | 否 | 只有 **6** 这一档 |
| PLAS-15 Loyalist | `[5]` | 否 | 只有 **5** |

**推断（强，但需 run 3 定案）**：Epoch 唯一档位是 **6**，而用户实测它**能过蓄** ⇒ **6 = 不安全**；
反推 Railgun 的默认槽 1（**5**）= **安全**（蓄到满即发、不过蓄）。

⇒「安全模式」**不是某个布尔开关**，而是**模式槽里填的是 5 还是 6**；
`charge` 组件的 `AutoFireInSafety`（`+0xB8`）在 11 行里**全都是 0**，与"该武器有几种模式"无关 ⇒ 它不是这个开关。

### 6.6.4 run 3：Railgun 恒定安全模式（**已装盘，待实机**）

| 项 | 值 |
|---|---|
| 变量 | **`WeaponDataComponentData` Railgun 行 `+0x94`（第二模式）：`6` → `0`** ⇒ 删掉"不安全"档 |
| 结果 | 模式槽 `[5, 6, 0, 0]` → **`[5, 0, 0, 0]`**；选择键仍绑着（`function_info[1]=3`） |
| 其余 | 沿用已证改动（ARC-3 瞬蓄 · P-92 距离 300 · Spear 快锁）；挂闸 `function_info` 未动 |
| 离线 | G1–G9 全 PASS，diff 仅 2 B；哈希 `0x8E49771B181FFAA1` 不变；封包 sha256 `e09babac…` |

**实机判据**：带 **RS-422 Railgun** 进图——

- ✓ 若**蓄满就自动发射、怎么按都过不了蓄** ⇒ `5 = 安全` 确认，且"删掉第二槽"= 永久安全模式（可直接用）
- ⚠ 若**仍然能过蓄** ⇒ 说明 5 才是"不安全"，下一轮把 `+0x90/+0x94` 都改成 `6` 再验
- ✗ 若**按模式键出错/武器异常** ⇒ 选择键绑着但只有一个模式会出问题，那就把 `function_info` 的 3 也清掉

---

## 6.7 用模式槽给别的武器加射击模式（run 4：APW-1 加全自动）

### 6.7.1 两条规则（缺一不可）

| 要什么 | 改哪里 |
|---|---|
| **多一个模式可选** | 往四连槽 `+0x90/+0x94/+0x98/+0x9C` 的空位（0）里写 `FireMode` 值 |
| **能切换** | `function_info` 必须绑定 `WeaponFunctionType Firemode (3)`：**`+0xB8` = left 输入、`+0xBC` = right 输入** |

⚠ **只改模式槽、不绑选择键 ⇒ 武器仍然只有一个模式**（等于换掉默认模式，而不是"可选"）。
这是 `refs/hd2runtime-repo/docs/fire-modes.md` 的原话：*"Switching modes in game needs the
fire-mode selector bound to an input. Weapons without it can only have one mode."*

⚠ 另一个必知：**射速不随模式变**。`rpm` 只有一份，在 `ProjectileWeaponComponentData` 里，所有模式共用
⇒ 给狙击枪加全自动，它会以**狙击枪自身的慢射速**连续开火，不会变成机枪。

### 6.7.2 本 build 实测对照

| 武器 | 模式槽 `+0x90…` | `function_info`（`+0xB8`/`+0xBC`） | 游戏里能切？ |
|---|---|---|---|
| **APW-1 Anti-Materiel Rifle** | `[2, 0, 0, 0]` | `[0, **0**]` | **不能**（只有半自动） |
| JAR-5 Dominator | `[2, 3, 0, 0]` | `[0, **3**]` | 能（单发/连发） |
| R-2 Amendment | `[2, 3, 0, 0]` | `[0, **3**]` | 能 |
| SG-225IE Breaker Incendiary | `[3, 2, 0, 0]` | `[0, **3**]` | 能 |
| AR-23 Liberator | `[1, 2, 3, 0]` | `[0, **3**]` | 能（自动/单发/连发） |
| RS-422 Railgun | `[5, 6, 0, 0]` | `[**3**, 0]` | 能（左输入） |

⇒ 绝大多数能切的武器把 `Firemode` 绑在**右侧**（`+0xBC`），Railgun 是唯一绑**左侧**（`+0xB8`）的。

### 6.7.3 run 4：APW-1 可选全自动（**已装盘，待实机**）

| 项 | 值 |
|---|---|
| 变量（一个逻辑能力：给它加"可选全自动"） | ① `+0x94`（第二模式）`0 → 1`（Automatic）<br>② `+0xBC`（`function_info.right`）`0 → 3`（`Firemode` 选择键） |
| 结果 | 模式槽 `[2,0,0,0]` → **`[2,1,0,0]`**（半自动 + 全自动）；`function_info` → `[0,0,3,…]`（与 JAR-5 同形） |
| 其余 | 沿用 Railgun 恒定安全 · ARC-3 瞬蓄 · P-92 距离 300 · Spear 快锁；diff 仅 4 B |
| 离线 | G1–G9 全 PASS；哈希 `0x8E49771B181FFAA1` 不变；封包 sha256 `332055cb…` |

**实机判据**：带 **APW-1** 进图——

- ✓ 若**按开火模式键能在「半自动 / 全自动」之间切**，且全自动能连续开火 ⇒ 模式槽 + 选择键这套完全成立
  （此时任何"只有单发"的枪都能这样加全自动）
- ⚠ 若**面板里出现两个模式但按不动** ⇒ 选择键绑错了输入（改试 `+0xB8`，Railgun 用的是左侧）
- ⚠ 若**只有半自动、没有新模式** ⇒ `FireMode Automatic(1)` 对狙击类被引擎拒绝，或需要在别处再开开关
- ✗ 若**武器异常/开不出火** ⇒ 说明 `function_info` 那两个输入不全是"功能键"，右侧原本有隐含用途被顶掉了

---

## 6.8 两套「模式」系统 + FireMode 枚举反查表

武器有**两套独立的选择器**，靠 `function_info` 里的枚举值区分：

| 选择器 | `WeaponFunctionType` | 改什么 | 数据在哪 |
|---|---:|---|---|
| **射击模式** | **`Firemode = 3`** | 单发 / 连发 / 全自动 / 齐射 / 总倾泻 / 安全 / 不安全 | `WeaponData +0x90…0x9C`（FireMode 四连槽） |
| **射速档位** | **`ROF = 2`** | rpm 三档切换（MG-43 / M-105 / MG-206 切的就是这个） | **`ProjectileWeapon +4 / +8 / +12`（X / Y / Z 三个 f32）** |

- `rpm` 三档里 **Y（+8）是默认档**，也是没有选择器时唯一生效的那档。
- 选择器按 `Y → Z → X → Y` 循环，遇到 0 的槽跳过（`docs/fire-rate-modes.md`，game.dll `0x617960`）。
- 两者可**同时存在**：`VG-70 Variable` 就是 `function_info = (3, 2)` —— 左键切射击模式、右键切射速。

### 6.8.1 实测：切射速的武器

| 武器 | rpm X / Y / Z | 射击模式槽 | `function_info`（左/右） |
|---|---|---|---|
| **MG-43 Machine Gun** | **630 / 760 / 900** | `[1]` | (0, **2 = ROF**) |
| **M-105 Stalwart** | **700 / 850 / 1150** | `[1]` | (0, **2 = ROF**) |
| MG-206 HMG | 450 / 600 / 750 | `[1]` | (0, **2 = ROF**) |
| **VG-70 Variable** | 300 / 550 / 750 | `[1,4,7]` | (**3**, **2**) ← 两套都有 |
| APW-1（本轮改后） | 0 / 400 / 0 | `[2, 1]` | (0, **3**) |

⇒ 给任何武器加射速切换 = 往 `+4/+8/+12` 写三个 rpm + 把 `function_info` 的某个输入写成 **2**。

### 6.8.2 ★ `FireMode` 枚举反查表（数据 + wiki 交叉）

方法：把「武器在数据里的模式集合」与「wiki 页面 Firing Modes 一栏」做联立。

| 值 | 名字 | 证据 |
|---:|---|---|
| 0 | **None（空槽）** | 四连槽的空位一律 0 |
| 1 | **Automatic 全自动** | 252 把只有 `[1]`；AR-23 `[1,2,3]` = 自动/单发/连发 |
| 2 | **Single（半自动）** | 57 把只有 `[2]`；APW-1、Purifier、Accelerator 都是 `[2]` |
| 3 | **Burst 连发** | AR-23 的第三槽；JAR-5 `[2,3]` = 单发/连发 |
| **4** | **Volley（多管齐射）** | **SG-88 wiki「Semi • Volley」↔ 数据 `[2,4]`** ✓；同组还有 DBS-2 / SG-22（都是多管） |
| **5** | **Safe（安全蓄力，蓄满即发）** | Railgun run 3 实机：删掉第二槽后只剩「安全」 |
| **6** | **Unsafe（不安全，可过蓄）** | Epoch 只有 `[6,6]` 且实测能过蓄；Railgun 的 `[5,6]` 即安全/不安全 |
| **7** | **Total（倾泻全部剩余弹药）** | VG-70 wiki「Total • Volley • Auto」↔ 数据 `[1,4,7]`；1=Auto、4=Volley ⇒ 7=Total |
| 8 | 未使用 | 全表 373 把无一把出现 8 |

⚠ 三态：`1/2/3` 有官方命名（type library 里名字长度对得上）⇒ **✓**；
`4` 由 SG-88 wiki 直接对上 ⇒ **✓ 离线**；`5` **✓ 实机**；`6` **⚠ 强推断**（间接）；
`7` **✓ 离线**（排除法 + VG-70 三个模式恰好三个值）。

⇒ **这套表可以直接用来"造模式"**：往空槽里写 4/7 就是给别的武器加齐射 / 总倾泻；
写 1 就是加全自动（run 4 已在 APW-1 上实机通过）。

---

## 6.9 run 5：给**单管枪**加 `Volley(4)` —— 能力边界探针（**已装盘，待实机**）

### 6.9.1 为什么选它

`4 = Volley` 是**唯一一个"语义依赖枪管数"的模式**（SG-88 `Barrels x 2` → 一次打 2 发）。
把它塞进一条**单管**武器，就能问清一件事：**模式值本身是否足够，还是引擎会去查枪管数 / 资产包**。

| 已知线索 | 结论 |
|---|---|
| 社区 schema 里**没有** `barrels` 字段（只有 `pellet_count` 这种"每发弹丸数"） | 枪管数很可能**不在明文数据里** |
| `volley_gun` 在 `player_weapon_composition_catalog.json` 里是一个 **资产包名**（`residency.package`，VG-70 的 loadout 包） | 齐射的**动画/多枪口事件**可能在那个包里，缺资源时行为不可预期 |

### 6.9.2 改动

| 项 | 值 |
|---|---|
| 目标 | **AR-23 Liberator**（单管自动步枪，已有选择器 `function_info = (0, 3)`） |
| 变量 | **`WeaponDataComponentData +0x9C`（第四模式槽）：`0` → `4`（Volley）** |
| 结果 | 模式槽 `[1, 2, 3, 0]` → **`[1, 2, 3, 4]`**（自动 / 半自动 / 连发 / 齐射） |
| 为什么单变量 | AR-23 本来就绑了 `Firemode` 选择键，**只需改一格**，不引入第二个改动 |
| 其余 | 沿用 APW-1 全自动 · Railgun 恒定安全 · ARC-3 瞬蓄 · P-92 距离 300 · Spear 快锁 |
| 离线 | G1–G9 全 PASS，diff 仅 2 B；哈希 `0x8E49771B181FFAA1` 不变；封包 sha256 `17195c7b…` |

### 6.9.3 实机结果：**第四档没有出现** ✗

AR-23 的模式面板仍然只有 **自动 / 半自动 / 连发** 三档（用户截图确认），第四槽写的 `4` 没被显示。

**但这不等于 `4` 无效** —— 因为有一层更基础的可能：**全表 373 把武器没有一把用过 4 个模式槽**（最多的 `[1,2,3]`）。

### 6.9.4 SDK 怎么说（`sdk/WeaponFireModeCapabilities.json`）

| 事实 | 原文/值 |
|---|---|
| `states.selectable` | 「Modes can be added, removed or reordered (**up to four**); the fire-mode selector is bound.」 |
| AR-23 | `modes=["automatic","single","burst"]` · **`maxModes: 4`** · `state: selectable` |
| APW-1 | `modes=["single"]` · `maxModes: 1` · `state: single_mode` |
| SG-88 | `modes=["single","**Safety_Off**"]` · `state: blocked`（"only Automatic, Single and Burst are proven"） |
| Railgun | `modes=[5, 6]` · `state: blocked` |

⇒ HD2Runtime 的**模型允许 4 档**（`maxModes: 4`），但它对 `4–8` 的命名是**按别名长度猜的**：
它把**值 4 叫作 `Safety_Off`** —— 与 wiki 的 SG-88「Semi • **Volley**」**冲突**。
⚠ 因此 `4` 到底是 Volley 还是某个安全档，**仍待实机判定**（见 run 6）。

### 6.9.5 run 6：把「半自动」换成齐射（**已装盘，待实机**）

思路（用户提出）：既然 4 个槽可能不被支持，那就**不占第四槽**，直接把已有的一个模式换掉。

| 项 | 值 |
|---|---|
| 目标 | **AR-23 Liberator**，基线回到 pristine（`[1,2,3,0]`，不含 run 5 那个 4） |
| 变量 | **`+0x94`（第二模式，原本 Single `2`）→ `4`** |
| 结果 | 模式槽 `[1, 2, 3, 0]` → **`[1, 4, 3, 0]`**（自动 / **4** / 连发） |
| 为什么单变量 | 只改一格、不新增槽，把「槽位上限」这个变量彻底排除 |
| 离线 | G1–G9 全 PASS，diff 2 B；哈希不变；封包 sha256 `c1dea13a…` |

### 6.9.6 实机结果：**成功，而且一次定了三件事** ✓

用户截图与描述：第二档**变成新图标、新名字（游戏内显示「齐射」）且能切**；
切过去后**就是半自动、一次只打一发**。

| 问题 | 判定 |
|---|---|
| 值 `4` 到底是什么 | **✓ 实机：游戏内名字就是「齐射」** ⇒ wiki 的 *Volley* 正确，<br>SDK `WeaponFireModeCapabilities.json` 把它猜作 `Safety_Off` **✗ 错** |
| 非多管武器是否接受 `4` | **✓ 接受**（AR-23 单管步枪照样能加、能切） |
| run 5 为什么加不出第四档 | **槽位上限实际是 3** ⇒ SDK 的 `maxModes: 4` **✗ 被否证**（全表无一把用满 4 槽也与之一致） |
| 为什么齐射只打 1 发 | 齐射语义 = **每根枪管一发**；AR-23 只有 1 根 ⇒ 1 发。<br>**枪管数不在数据表里**（社区 schema 无 `barrels`，只有 `pellet_count` 这种每发弹丸数） |

⇒ **能力边界**：`4` 这个模式可以给任意武器加，但"齐射打几发"由**武器模型上的枪口数量**决定，
数据侧改不到；单管武器加上去就是"一次一发"（等效半自动）。

---

## 6.10 run 7：`Total(7)`（倾泻全部剩余弹药）—— **已装盘，待实机**

`Total` 是唯一**不依赖枪管数**的"多发"模式（VG-70：一次打完整个弹匣），所以它是单管武器上
最可能真的改变射击行为的模式。

| 项 | 值 |
|---|---|
| 目标 | **AR-23 Liberator**（基线 pristine `[1,2,3,0]`） |
| 变量 | **`+0x94`（第二模式，原本 Single `2`）→ `7`（Total）** |
| 结果 | 模式槽 `[1, 2, 3, 0]` → **`[1, 7, 3, 0]`**（自动 / **总倾泻** / 连发） |
| 离线 | G1–G9 全 PASS，diff 2 B；哈希不变；封包 sha256 `7c8c77f0…` |

**判据**：

| 你看到 | 结论 |
|---|---|
| 面板出现新档，扣一次扳机**把弹匣里剩下的全打出去** | `Total` 对任意武器成立 ⇒ **给任何枪加"一键倾泻"**，这条线可做成成品 |
| 出现新档但**只打一发/三发** | `Total` 也依赖多管或多发定义，只能在原生武器上用 |
| 出现新档、**打空后自伤/被掀翻**（VG-70 是 >22 发就掀） | 正常，与 VG-70 同一套规则；说明"自伤"是 `Total` 的固有行为 |
| 面板没有新档 | 值 `7` 被过滤（与 `4` 不同，说明不是所有 4–8 都能加） |

---

## 7 三态

| 结论 | 态 |
|---|---|
| `WeaponChargeComponentData` 块位置 / 几何（20 槽 + 11 行 × 216） | **✓ 离线** |
| 216 B 行结构 = 三档 ChargeStateSetting + 12 倍率 + 句柄 + 布尔，与社区 schema 逐项对齐 | **✓ 离线** |
| 「不蓄满能否开火」与 `Min.ProjType ≠ 0` 6/6 相关 | **✓ 离线**（强相关，非因果） |
| `ChargeTime` 是蓄力时长（秒） | **✓ 实机**（ARC-3 1.1→0.05，按下几乎立刻放电） |
| `Min.ProjType` 填值可让"必须蓄满"的枪提早开火 | **⚠ 未试** |
| 倍率区对实际弹丸生效 | **⚠ 未试** |
| 伤害随蓄力在 `DamageMin`→`DamageOver` 间变化（Railgun 1.0→2.5 · Epoch 1.0→2.0） | **✓ 离线**（结构+数值；实机幅度未量化） |
| Railgun 过蓄自毁 = 爆炸 type 326（行 209，0.4-2-3 m）→ 伤害类型 362 → damage 行 350 = **300/300、AP 3、爆破 20、硬直 5、推力 40**（**与 wiki 逐项吻合**） | **✓ 离线** |
| 爆炸行 `+0x4` 是「伤害类型 id」而非行号 | **✓ 离线**（wiki 对照逼出，见 §6.5.2 的坑） |
| Railgun 过蓄不再自伤 | **⚠ 待 run 2**（伤害类型 362→32） |
| Epoch 过蓄自毁：`ExplodeType=321` → 伤害类型 68 → **800/800、3-4-5 m**，但 `ExplodesOnOvercharged=0` | **⚠ 未证**（布尔与现象不一致） |
| Railgun 过蓄触发但**不再伤己** | **✓ 实机**（run 2：爆闪照旧、不掉血） |
| 「安全/不安全」= `WeaponDataComponentData +0x90/+0x94` 里的 FireMode 值（5=安全 / 6=不安全） | **⚠ 待 run 3**（推断来自"Epoch 只有 6 且能过蓄"） |
| 能否切换 = `function_info` 是否绑定 `WeaponFunctionType Firemode(3)`（Railgun 绑在 `+0xB8`） | **✓ 离线**（4 把蓄力枪对照，只有 Railgun 绑定） |
| Railgun「恒定安全」= 删掉第二模式槽（`+0x94` 6→0） | **✓ 实机**（run 3：面板只剩「安全」） |
| 模式槽 + 选择键 = 可给任意武器加射击模式 | **✓ 实机**（run 4：APW-1 能在半自动/全自动之间切并连续开火） |
| 射速切换 = `ProjectileWeapon +4/+8/+12` 三档 rpm + `function_info` 写 `ROF(2)` | **✓ 离线**（MG-43/M-105/MG-206 三者 rpm 三档与右侧选择键） |
| `FireMode 4` = Volley | **✓ 离线**（SG-88 wiki「Semi • Volley」↔ 数据 `[2,4]`） |
| `FireMode 7` = Total | **✓ 离线**（VG-70 wiki 三模式 ↔ `[1,4,7]` 排除法） |
| `FireMode 6` = Unsafe | **⚠ 强推断**（Epoch `[6,6]` 能过蓄 + Railgun `[5,6]`） |
| 给 AR-23 加**第四档**模式（`+0x9C` = 4） | **✗ 实机**：面板仍只有三档，第四档不显示 |
| 引擎是否允许 4 个模式槽 | **✗ 否证**（run 5：第四槽不显示；SDK 的 `maxModes: 4` 不成立，实际上限 **3**） |
| 值 `4` 能否被非多管武器接受 | **✓ 实机**（run 6：AR-23 能加能切） |
| `FireMode 4` = **齐射 / Volley** | **✓ 实机**（run 6：游戏内就显示「齐射」；SDK 的 `Safety_Off` 命名 ✗ 错） |
| 齐射"打几发"由枪管数决定，且枪管数不在数据表里 | **✓ 实机 + 离线**（单管 AR-23 = 1 发） |
| `Total(7)` 能否给任意武器加、是否真倾泻弹匣 | **⚠ 待 run 7** |

---

## 8 下一步

1. ~~收 run 1（ARC-3 时间）~~ → **✓ 已收**。
2. **收 run 2（Railgun 过蓄不自伤）**。若 ✓ ⇒ 同法可给 Epoch 试（先确认它用的爆炸 type）。
3. 把 ARC-3 的短蓄力做法推广：Accelerator `0.50`、Railgun `0.50`、Epoch `2.50` → 0.05。
4. 倍率区单独验：**把 Railgun `DamageOver` 2.5 → 5.0**，看蓄满伤害是否翻倍
   （同时验证"倍率线性插值"这个假设）。
5. `Min.ProjType` 路线（让"必须蓄满"的枪能提早开火）：给 ARC-3 的 Min 档填一个合法电弧弹丸类型。
6. 收 run 3（Railgun 恒定安全）。若 ✓ ⇒ 同法可给 Epoch/ARC-3 定档（它们没绑选择键，改槽即等于改行为）。
7. 之后可试"反向"：把 ARC-3 加上 `Firemode` 选择键（`function_info` 写 3）+ 第二槽 6，看能否给它加出"不安全"档。
8. ~~run 4~~ → **✓ 已收**。可批量给单发武器加全自动；也可试加 `Burst(3)` / `Volley(4)` / `Total(7)`。
9. 想验证 `6 = Unsafe`：给某把能过蓄的枪**删掉 6 槽**（像 run 3 那样）看是否只剩安全。
10. 射速路线：给 APW-1（或任意单档枪）写 `+4/+12` 两个新 rpm + `function_info` 写 `ROF(2)`，看能否加出射速切换。
11. ~~收 run 6~~ → **✓ 已收**（4 = 齐射；槽位上限 3；枪管数在模型侧）。
12. **收 run 7**（`Total(7)`）。若 ✓ ⇒ 可做成"任意枪一键倾泻"的成品。
13. 若要把"齐射多发"移植给单管枪 ⇒ 得改**模型/枪口定义**（`unit` / state_machine 的 muzzle 定位点），
    属资源路线，不是数据表路线。
12. 若 run 5 表明 `4` 依赖资产包 ⇒ 查 `volley_gun` 包里到底有什么（`srkit` 可解包），判断能否移植。
