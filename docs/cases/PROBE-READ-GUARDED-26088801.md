# probe_read 运行记录 —— `game_object_field` 正确形态实机验证（run 4）

- build：**26088801**；日期 2026-10-24 13:13
- 载荷：`mods/auto/5` = probe_read 1.0.0（17,824 B，patch_5）；patch_0 = BootProbe
- 日志：`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\ReadProbe.log`（352 行，20,935 B）
- 结论：**✓✓ 名字形态跑通**，同时**推翻**我此前两条判断

---

## 0 三条结论（按重要性）

| # | 结论 | 判定 |
|---|---|---|
| 1 | `game_object_field(session, goid, **字段名**)` 能读到真值 | ✓✓ 实机 |
| 2 | **`goid = 0` 是合法的**——它就是 player 对象 | ✓✓ 实机（推翻旧假设） |
| 3 | 上次崩溃的变量是**第 3 参传 hex**，不是 goid | ✓✓ 实机对照（goid 恒为 0，只换参数） |

### 0.1 对照表（同一 build、同一函数、**goid 都是 0**）

| 第 3 参 | 结果 | 出处 |
|---|---|---|
| `"a3df1643"`（裸 hex） | **硬崩** | 探针 run 1 |
| `"0xcd889dbc"`（带 0x 的 hex） | **硬崩** | 探针 run 2 |
| `"baegche"`（字段名） | **OK → number(493)** | 本次 run 4 |

⇒ 判别变量是**参数形态**，不是 goid，也不是字段是否存在
（`cd889dbc` 在 un6y1d 声明里确实存在，127 个类型共有）。

---

## 1 闸门实机表现

| 闸 | 实机读数 |
|---|---|
| 0 `game_session()` | 主菜单就能拿到 session，但 `in_session = false`（attempt 2–28 全部 bail 在这） |
| 0 `peer_id()` | **string** `a50da53b1ab77c2f`（不是数字） |
| 1 `objects_owned_by` | 刚上船 `owned=1`；进任务后 `owned=295` |
| 2 `game_object_exists` | 295/295 全活 |
| 3 `game_object_is_type(_, "un6y1d")` | 恰好 1 个 → **goid 0** |
| 4 `baegche` | 上船早期读到 **32767** → bailed「no avatar right now」；之后读到 287 / 493 |
| 5 `game_object_is_type(avatar, "gl7xl2w")` | `true` |

**32767 哨兵实机出现了**（attempt 29，刚上船那几十秒）——这是 HUD+ `NO_OBJECT` 常量的直接实证。

---

## 2 读到的真值

| 字段 | 飞船上（avatar **287**） | 地面（avatar **493**） |
|---|---|---|
| `gls4w9b` | **30** | **100** |
| `state` | 0 | 0 |
| `motion_enabled` | `true` | `false` |
| `rotation_enabled` | `true` | `true` |
| `health` | **125** | **125** |
| `enabled_mask` | 5 | 5 |
| `position` | `Vector3(-0.00388526917, 2.51448154, 20.0099983)` | `Vector3(10.3889923, 98.6930542, 900)` |

- `gls4w9b`：**30 = 在飞船上，100 = 地面**。HUD+ 的 `ship_field.value = 30` 常量**逐字命中**。
- `position` 返回的是 **userdata `Vector3`**（不是表），可直接 `v.x/v.y/v.z` 用。
- 飞船上 z≈20（舰内），地面 z=900 —— 两套坐标，说明船与任务世界确实不同。
- `health` 两处都是 125（同一条命，没受伤）。
- ⚠ `motion_enabled` 地面那次是 `false`：那一刻玩家可能正处于空降/动画锁定。**不能**把 `motion_enabled` 当成「玩家在不在控制中」的稳定判据。

---

## 3 schema 与离线字典完全吻合

| 类型 | 实机 `object_info` | 我们的离线字典 | 一致 |
|---|---|---|---|
| `un6y1d`（player） | **36 fields** | 36 | ✓ |
| `gl7xl2w`（avatar） | **72 fields** | 72 | ✓ |

⇒ `type-schema-dictionary.json` 的 224 类型 schema 提取**整体可信**（不只是数量，座位号也对：
`gls4w9b`=68、`state`=38、`motion_enabled`=27、`rotation_enabled`=61、`health`=42、`enabled_mask`=49、`position`=23）。

---

## 4 `game_object_field_batched` —— 部分否证

两次调用（船/地面）**返回同一批 9 个 key：64..72**，72 个字段只给了 9 个。

| key | schema 座位 | 字段 | 船上 | 地面 |
|---|---|---|---|---|
| 64 | `b2205a6e` t11 b31 | （容器） | `table(keys=63)` | `table(keys=63)` |
| 65 | `1023782c` t0 | bool | `false` | `false` |
| 66 | `ce125651` t0 | bool | `false` | `false` |
| 67 | `e4d00fe1` t2 b7 | 0..1 | `1` | `1` |
| **68** | **`dae681f4`** | **`gls4w9b`** | **30** | **100** |
| 69 | `6d976352` t2 b8 | | 40 | 100 |
| 70 | `a33df340` t1 b32 | | 0 | 0 |
| 71 | `c20428c6` t10 | 容器 | `table(0)` | `table(0)` |
| 72 | `6d1d5cfb` t10 | 容器 | `table(0)` | `table(0)` |

| 推断 | 判定 |
|---|---|
| 返回表**按 schema 座位号对齐** | ✓ 实机（seat 68 与单读 30/100 逐值相同，且两个样本值不同仍对上） |
| 返回**全部**字段 | ✗ 否证（只 9 个，恒为末尾 9 个座位） |
| 子集规则 | ⚠ 未证：是「最后 9 个」？是「类型 ≥10 的容器块」？是「需要预填 out 作选择器」？ |

> HUD+ 的 `seated()` 里那段「值可能被嵌在子表里」的兜底，多半就是为了兼容这种形态。

**下一个实验（一次跑完）**：
1. 对 **player**（36 字段）调一次 batched → 看是 `28..36`（=最后 9）还是别的规律；
2. 同一 goid 连调两次 → 看是不是「增量」；
3. 传 `out` 预填 `out[1]=true` 等 → 看是不是「选择器」语义。

---

## 5 探针自身的缺陷（下次修）

| 缺陷 | 影响 | 修法 |
|---|---|---|
| `FIELDS[baegche].hash` 写成 `f27c68e`，未过 `norm_id` | 座位显示 `-`，batched 对位时 baegche 被算成「单读缺」 | 对 FIELDS 里的 hash 统一 `norm_id` |
| 飞船上重复 dump 了 1 次后仍每 180 帧跑一遍 gate 1–5（14 次 ship pass） | 日志变长（352 行），无功能影响 | 船态命中 2 次后把重试间隔拉长到 900 帧 |
| 离线夹具里 `peer_id` 用数字 1001，实机是 string | 不影响（探针只透传） | 夹具改成 string，保持逼真 |

---

## 6 三态判定汇总

| 主张 | 判定 |
|---|---|
| 字段名形态可读 `game_object_field` | ✓✓ 实机 |
| `goid = 0` 合法（= player） | ✓✓ 实机 |
| 崩溃源于第 3 参传 hex | ✓✓ 实机对照（goid 恒定） |
| `32767` = 无 avatar | ✓✓ 实机 |
| `gls4w9b` 30=船 / 100=地面 | ✓ 实机（各 1 样本） |
| `health`/`position`/`state`/`enabled_mask` 可读且语义合理 | ✓✓ 实机 |
| lint：`position` 是 Vector3 userdata | ✓✓ 实机 |
| batched 座位对齐 | ✓ 实机（9 个 key 中 68 精确匹配） |
| batched 返回全集 | ✗ 否证 |
| batched 子集规则 | ⚠ 未证 |
| `motion_enabled` = 「在控制中」 | ⚠ 存疑（地面为 false） |
| 「名字 vs hash」在同一 session 内单变量复测 | ⚠ 未做（会崩；目前是跨 session 对照） |
