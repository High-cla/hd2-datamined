# 锁定 / 制导武器（lock-on / seek）—— 武器线遗漏项（build 26088801）

> **状态：锁定距离 ✓ 实机已证（P-92 60→300）；锥角 run 2 已装盘待测。**
> 本篇把 memmod 时期 `c9-seek` 那条线与当前 build 的**明文表**对上，给出可编辑落点、映射与已跑通的做法。
> 情报侧：`D:\mod\c9-recon\web-intel-hd2-lockon.md`（公开资料）· 当年写载物：`D:\mod\c9-seek-write\`（patch_3）。

---

## 0 一句话

「锁定」不是一张表，而是**三张组件表分工**：

| 你想要的 | 在哪 |
|---|---|
| **多远能锁** | `SensorEyeComponentData` → 行内 **`+0x00 distance`**（f32，米） |
| **多宽算锁上** | `GuidanceTargetComponentData` → **`+0x20 target_lock_dot`**（0.95 ⇒ 半角 18.19°） |
| **锁多久 / 丢多久** | 同上表 `+0x10 / +0x14 / +0x18` |
| **导弹怎么追** | `SeekingMissileComponentData` → 速度 / 加速度 / 转向 / PID |

三张表**都在 `generated_entities.dl_bin` 明文里**，走护甲那条「改字节 + 保内容哈希 + 重新封装」路线 ——
**不需要 memmod，重启不掉**。

---

## 1 三张表 + 两张辅助表（本 build 离线实测）

块头偏移是**文件绝对偏移**；`payload = 块头 + 28`。几何全部按 `slots×16 + rows×stride == payload` 校验通过。

| 组件 | type | 块头 | payload | 几何 |
|---|---|---|---:|---|
| **`SensorEyeComponentData`** | `0x14729B6A` | `0x00724D68` | 23,984 | 630 槽 + **316 行 × 44 B** |
| **`GuidanceTargetComponentData`** | `0x84957034` | `0x00785AC0` | 1,528 | 18 槽 + **10 行 × 124 B** |
| **`SeekingMissileComponentData`** | `0xBF3A6789` | `0x0072E460` | 8,816 | 58 槽 + **29 行 × 272 B** |
| `WeaponDataComponentData`（准星） | `0x88E4DBB1` | `0x0193CCE8` | 475,696 | 746 槽 + 374 行 × 1240 |
| `ProjectileWeaponComponentData`（投射物） | `0x45171B68` | `0x02CDE0B8` | 180,760 | 556 槽 + 279 行 × 616 |
| ~~`TargetingComponentData`~~（**不是锁定**，见 §6） | `0x2C0968D2` | `0x01932290` | 28,512 | 594 槽 + 297 行 × 64 |

**键都是实体 GUID**（不是行号）。行基址 = `payload + slots×16`。

文件级锚点（**必须保住**）：`MurmurHash64A(plaintext, seed 0xDEADBEEFABAD1DEA) == 0x8E49771B181FFAA1`，
明文 sha256 `dc6d52a1…`，47,259,396 B。

---

## 2 `SensorEyeComponentData` —— 锁定距离

行 44 B：

```
+0x00 distance(f32,米)  +0x04 peripheral  +0x08 back  +0x0C angle_h  +0x10 angle_v
+0x14 sight_node(u32)   +0x18 flags       +0x1C raycast  +0x20 eye_type
+0x24 ignore_inside_foliage(8.0)  +0x28 inside_foliage(0.5)
```

玩家能锁的 5 把（**5/5 与公开实测锁定距离吻合**）：

| 武器 | 行 | `distance` | `angle_h/v` | 有 `GuidanceTarget` 行 |
|---|---:|---:|---|---|
| P-92 Warrant | 202 | **60** | 20 / 20 | ✓ |
| P-33 Missile Pistol | 203 | **100** | 20 / 20 | ✓ |
| FAF-14 Spear | 305 | **300** | 20 / 20 | ✓ |
| StA-X3 W.A.S.P. | 306 | **300** | 20 / 20 | ✓ |
| MLS-4X Commando | 307 | **300** | 20 / 20 | ✓（激光制导，`requires_target_lock=0`） |

对照：**AR-23 / AR-2 / P-4 都没有 `SensorEye` 行** ⇒ 无锁定。全表 316 行里玩家物品只占 8 行，
其余是 AI 视觉（距离 8–2000、锥 20–360）。另外 3 行玩家物品（**G-50 Seeker 50 m** 等）有传感器但**没有 GT 行**
⇒ 形态上是自动索敌无人机/护卫类，不是锁定武器。

> ⚠ `angle_horizontal = 20` 是**全角还是半角未定**：AI 那批有 170/180，看起来是全角；若全角则 ±10°，
> 比 dot 的 18.19° **更窄** ⇒ 两者谁先卡死，未分离过。

---

## 3 `GuidanceTargetComponentData` —— 锥角与时序

行 124 B（声明顺序 + 自然对齐；用 `target_node` 默认值 `0xBCCF91E5` 定位）：

```
+0x00 always_active(u8)  +0x01 use_target_node(u8)  (+0x02 补齐 2B)
+0x04 target_node(u32, 默认 0xBCCF91E5)   +0x08 priority(f32)
+0x0C owner_priority(100)  +0x10 lock_on_target_time  +0x14 lost_target_time
+0x18 lock_lost_target_time  +0x1C requires_target_lock(u8)
+0x20 target_lock_dot(0.95)  +0x24 target_crosshair_scale(1.75)  +0x28 tracking_loop_start(u32)
```

本 build 全表 9 行（键 = 武器 GUID）：

| 武器 | 行 | `lock_on_target_time` | `lost_target_time` | `lock_lost_target_time` | `requires_target_lock` |
|---|---:|---:|---:|---:|---:|
| P-92 Warrant | 4 | **0.10** | 0.10 | 2.00 | 1 |
| P-33 Missile Pistol | 5 | 0.75 | 0.15 | 2.00 | 1 |
| FAF-14 Spear | 6 | 1.00 | 0.15 | 2.00 | 1 |
| StA-X3 W.A.S.P. | 7 | 0.50 | 0.10 | 2.00 | 1 |
| MLS-4X Commando | 8 | 2.00（默认） | 1.00 | 1.00 | 0 |

**★ 关键结论：`target_lock_dot` 9 行全是 `0.95`、`target_crosshair_scale` 9 行全是 `1.75`**
⇒ **锁定锥角不是逐武器调的**，是统一默认值。
`acos(0.95) = 18.19°` 半角（全锥 36.4°）。
（这也解释了当年 c9 把 `cone` 从社区惯例 12° 改成 18° 为什么"感觉对了" —— 18 正好贴着原版 18.19°。）

---

## 4 `SeekingMissileComponentData` —— 制导参数（映射已建）

键是**投射物实体**，不是武器。映射链：
**武器 GUID → `ProjectileWeaponComponentData` 行 `+0x28`（u64 投射物实体）→ `SeekingMissile` 行**
（4 把锁定武器的 `+0x28` 全部命中该表键 —— 这条链是**实证**，不是猜的。）

| 武器 | SM 行 | Starting / Min / Preferred 速度 | Accel | MaxAngle | Min/Max TurnSpeed | P / I / D |
|---|---:|---|---:|---:|---|---|
| P-92 Warrant | 4 | 90 / 90 / 90 | 200 | 45 | **30 / 30** | 0.01 / 1.0 / 1e-4 |
| FAF-14 Spear | 7 | 10 / 10 / 100 | 200 | 45 | 10 / 13 | 0.01 / 1.0 / 1e-4 |
| StA-X3 W.A.S.P. | 9 | 10 / 10 / 100 | 200 | 45 | 15 / 18 | 0.01 / 1.0 / 1e-4 |
| MLS-4X Commando | 10 | 30 / 75 / 120 | 200 | 45 | 2 / 12 | 0.5 / 1.0 / 1e-4 |

字段偏移（沿用社区 `filediver` schema，本 build 未逐项验）：`MaxLifetime +0x40`、
`Starting/Minimum/PreferredSpeed +0x44/+0x48/+0x4C`、`Acceleration +0x50`、`MaxAngleToTarget +0x54`、
`Min/MaxTurnSpeed +0x58/+0x5C`、`P/I/D +0x60/+0x64/+0x68`、`TargetUpdateInterval +0x6C`。

> ⚠ 教训（当年 §94）：**schema 默认值 ≠ 逐行值**。曾据默认 `min_turn_speed=1` 推断"P-92 转得慢"，
> 实测是 **30/30**（全表最快）—— 差点把它改钝。本页按逐行实测记录。

---

## 5 怎么写（工具已存在，不用新写）

底层原语 **`tools/entity_field_set.py`**：给组件 type + 实体键 + 行内偏移，块定位 / 行定位 / 尾部宿主 / 门禁全自动。

```bash
# 看一行
python tools/entity_field_set.py show --block 0x14729B6A --key 0xCF8934FF6567A42D --width 44

# 改一个字段（f32：P-92 锁定距离 60 → 300）
python tools/entity_field_set.py set --block 0x14729B6A --key 0xCF8934FF6567A42D \
    --field 0x0 --type f32 --value 300 --expect-old 60 --out out/X.plain
```

**门禁 G1–G9**（任一不过就不写文件）：长度 = 原长+pad+8 · 差异 ⊆ 字段∪末块尺寸∪校正字 ·
**重算 Murmur == 原值** · 字段读回 == 目标 · 旧值 == 期望 · 容器重解析自洽 · 校正字 8 对齐 · 追加区除校正字全 0。

封装 / 部署 / 回滚：

```bash
python tools/dlbin_seal.py seal-key out/X.plain --key refs/dlbin/keys/recipient.pk --out out/generated_entities.dl_bin
python tools/dlbin_seal.py open-key <盘上文件> --key refs/dlbin/keys/recipient.sk --out out/readback.plain   # 回读验证
python tools/dlbin_deploy.py install --file generated_entities.dl_bin --sealed out/generated_entities.dl_bin
python tools/dlbin_deploy.py restore --file generated_entities.dl_bin
```

**为什么必须保住哈希**：`seal-key` 每次新随机 ephemeral，封包字节必然不同（正常）；但**明文的内容哈希**
要等于 `0x8E49771B181FFAA1`。工具做法 = 末块 payload 尺寸 += pad+8、文件尾追加 pad+8 零字节、
再把 8 字节校正字解在尾部 —— 锚点不变、容器重解析自洽。
封装模型与陷阱见 [DLBIN-SEALED-BOX](../engine/DLBIN-SEALED-BOX.md)、
文件路线全流程见 [FILE-ROUTE-WORKFLOW](../cases/FILE-ROUTE-WORKFLOW-26088801.md)。

---

## 6 ✗ 更正：`TargetingComponentData` 不是锁定

本篇早前版本把 `TargetingComponentData`（`0x2C0968D2`，594 槽 / **297 行 × 64 B**）当成锁定主数据。**两点更正**：

| 项 | 错的 | 对的 |
|---|---|---|
| 块头偏移 | `0x1932294`（那是 `LDLD` 魔数位置） | **`0x1932290`** |
| 语义 | 锁定 / 炮塔归零 | **AI / 角色索敌瞄准** |

证据：该表 297 个键里 **5 把锁定武器一个都不在**；能解出名字的键全是角色实体（`content/fac_bugs/cha_*`），
行值是 `25.0 / 0.5 / 5.0 / 90.0 / 180.0` 这类**角色视角 / 索敌**参数，与「距离 / 锥角 / 锁定时序」无一对应。
⇒ 改它不会改玩家锁定，别按名字误伤。

`crosshair_type`（`WeaponDataComponentData +0x190`，值 **16 = Javelin**）仍然成立，但它只给**准星样式**，
**不给锁定能力** —— 真正的开关是 `SensorEye.distance` + `GuidanceTarget` 行。

---

## 7 单变量实验记录

### run 1 —— 锁定距离（**✓ 实机通过**）

| 项 | 值 |
|---|---|
| 变量 | **P-92 Warrant `SensorEyeComponentData +0x00 distance`：60.0 → 300.0** |
| 只改了 | 3 字节（字段高字节 ×2 + 末块尺寸字段），其余与基线逐字节相同 |
| 离线门禁 | G1–G9 全 PASS；哈希 `0x8E49771B181FFAA1` 不变 |
| 封装 | `out/lockon-1/generated_entities.dl_bin`，47,259,456 B，sha256 `0c5a5f49…` |
| 盘上回读 | live sha256 == 我们的密文；解封逐字节一致；字段读回 **300.0** |
| **实机** | **✓「能锁上超过 60 m 的」** |
| 原版备份 | `D:\mod\backups\dlbin-deploy\game\generated_entities.dl_bin`（`cac4a228…`） |

⇒ **`SensorEye.distance` 就是锁定距离**；且**引擎接受重新封装的实体表**（详见
[ENTITIES-TABLE-LIVE-EDIT](../cases/ENTITIES-TABLE-LIVE-EDIT-26088801.md)）。
实测单位是米、写入值直接生效（60 → 300 后跨过 60 m 仍能锁）。

### run 2 —— 锥角（**已装盘，待实机**）

在 run 1 基础上**只加一个变量**（距离保持 300，便于对照"同一个瞄偏量"）：

| 项 | 值 |
|---|---|
| 变量 | **P-92 `GuidanceTargetComponentData +0x20 target_lock_dot`：0.95 → 0.50** |
| 含义 | 锁定判定半角 `acos(dot)`：**18.19° → 60°**（全锥 36.4° → 120°） |
| 范围 | **只改 P-92 那一行**（GT 行 4）；另 8 行仍 0.95 ⇒ 其它锁定武器不受影响 |
| 离线 | G1–G9 全 PASS；哈希不变；封装 sha256 `6501d324…`（47,259,464 B） |
| 盘上回读 | 解封 == 我们的明文；P-92 `distance=300` / `lock_dot=0.5`；**对照项未动**（P-33 仍 100、Spear 300 且 dot 0.95） |

**实机结果（用户原话）**：「偏得比较多也能锁，但是**锁定进度会卡在一开始，无法锁成功**。」

| 观察 | 推论 |
|---|---|
| 偏得多也出现可锁提示（锁定圈 / 候选框） | **✓ `target_lock_dot` 是运行期判据**，放宽后候选范围真的变宽了 |
| 进度条卡在起始、锁不成功 | **✗ 单靠 dot 不够** —— 存在**第二道门禁**：候选 ≠ 被传感器看见 |

⇒ 两级门禁模型：**`target_lock_dot` 决定「算不算候选」，`SensorEye.angle_h/v` 决定「能不能持续看见并攒进度」**。
这正好解释当年 c9 的「明明瞄着却不锁」：候选框出来了（dot 放行），但传感器看不全（±10°），进度攒不起来。

### run 3 —— 传感器视锥（**已装盘，待实机**）

dot 退回**原版 0.95**（去掉 run 2 那个「候选过多」的混淆因素，基线回到 run 1），只动视锥：

| 项 | 值 |
|---|---|
| 变量 | **P-92 `SensorEyeComponentData +0x0C angle_h` 与 `+0x10 angle_v`：20 → 90**（一个逻辑变量：传感器视锥） |
| 含义 | 若 20 是**全角** ⇒ ±10° → ±45°；若是**半角** ⇒ ±20° → ±90° |
| 离线 | 两次链式 set，G1–G9 全 PASS；哈希不变；封装 sha256 `61f40836…`（47,259,472 B） |
| 盘上回读 | `distance=300 / angle_h=90 / angle_v=90 / lock_dot=0.95`；对照 P-33 仍 `100 / 20` |

**实机判据**：复现 run 2 那张图（目标偏在一侧、锁定圈出现）——

- ✓ 若**进度能攒满、锁成功** ⇒ `SensorEye.angle_h/v` 是完成锁定的门禁，两级模型成立
- ✗ 若**仍然卡在起始** ⇒ 门禁不在 `SensorEye`，转查 `+0x1C raycast`（射线可见性）与 `+0x18 flags`
- 对照：瞄准正中时**原本就能锁**（run 1 已证），所以本局只需看「偏置时能不能锁成功」

> 组件表在**游戏启动时**读 ⇒ 改完必须**重启**，再进任务拿到武器。

---

## 8 三态

| 结论 | 态 |
|---|---|
| 三张表的块头 / payload 几何 / 行 stride 全部离线校验通过（`slots×16+rows×stride==payload`） | **✓ 离线** |
| 5 把锁定武器的 `SensorEye.distance` = 60/100/300/300/300，非锁定武器**无该行** | **✓ 离线** |
| 武器 → `ProjectileWeapon +0x28` → `SeekingMissile` 行 的映射（4/4 命中） | **✓ 离线** |
| `target_lock_dot` 全表统一 0.95（锥角非逐武器） | **✓ 离线** |
| `TargetingComponentData` 是角色索敌、与玩家锁定无关 | **✓ 离线** |
| 改 `SensorEye.distance` 能改变实机锁定距离 | **✓ 实机**（P-92 60→300，能锁 60 m 以外） |
| 引擎接受改过并重新封装的 `generated_entities.dl_bin` | **✓ 实机**（同上；见 [案例](../cases/ENTITIES-TABLE-LIVE-EDIT-26088801.md)） |
| `target_lock_dot` 是运行期判据（放宽后候选范围变宽） | **✓ 实机**（run 2） |
| 锁定「能攒满进度」还需第二道门禁（传感器看得见） | **⚠ 待 run 3** |
| `angle_h/v = 20` 是全角还是半角 | **⚠ 未证**（run 3 用 90 做定性判据，不区分全/半角） |
| `angle_h/v` 与 `dot` 谁卡「完成锁定」 | **⚠ 待 run 3**（run 2 已把 `dot` 从「完成」里排除） |
| `requires_target_lock` / `tracking_loop_start` 的实机语义 | **⚠ 未证** |
| 能否让**非锁定武器**获得锁定（需同时加 `SensorEye` 行 + `GT` 行 + `crosshair=16`，≥3 变量） | **⚠ 未试** |
| `Tag_CanBeLockedOn`（`0x07F0ADE3`）能否扩大"可被锁"的目标集合 | **⚠ 未试**（改实体标签，波及敌人/队友，**不要先动**） |

---

## 9 遗留 / 下一步

1. ~~收锁定距离那一变量~~ → **✓ 已收**（run 1 实机通过）。
2. ~~收 run 2（锥角）~~ → **✓ 部分收**：dot 是候选判据，但单靠它锁不成功。**收 run 3（传感器视锥 20→90）**。
3. 再下一个：`lock_on_target_time` 缩到 0.05（瞬间锁）—— **Spear 的 1.0 s** 是最明显的那个
   （P-92 本来只有 0.1 s，改了看不出差别）。
4. `SeekingMissile` 的转向/速度：P-92 是 90/90/90 + 30°/s（全表最快），要看得出来得挑
   **Commando（30/75/120，turn 2/12）** 或 **Spear（10/10/100，turn 10/13）**。
5. 想给非锁定武器加锁定 ⇒ **三变量**（传感器行 + GT 行 + 准星），必须分三次单变量各自验证，不要一次上。
6. 想锁"不该能锁"的东西 ⇒ `Tag_CanBeLockedOn`，改实体标签，波及敌人/队友，**最后再碰**。
