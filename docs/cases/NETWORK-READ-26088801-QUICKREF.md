# 网络复制层读取 —— 一页速查（build 26088801）

> 本文是这次「HUD+ → 抄正确调用形态 → 自建探针 → 钉字段」全过程的**入口页**。
> 详细证据与逐轮日志在 [`PROBE-READ-GUARDED-26088801.md`](PROBE-READ-GUARDED-26088801.md)（§0–§19）
> 与 [`HUDPLUS-0.5.3-LIVE-PROOF-26088801.md`](HUDPLUS-0.5.3-LIVE-PROOF-26088801.md)。

---

## 0 一句话

在 build 26088801 上，**`GameSession.game_object_field(goid, "字段名")` + `game_object_field_batched(goid, {})`
可以稳定读到玩家/替身的实时状态**（血量、坐标、是否在飞船、是否被击倒），
**前提是 goid 来自 `objects_owned_by` 且过六道闸**；**写**则要求知道字段名，而名字只能从第三方 mod 里抄。

---

## 1 能力边界（三态）

| 能力 | 判定 | 说明 |
|---|---|---|
| 读自己 player 的全部 36 字段 | ✓✓ 实机 | 一次 `batched(player, {})` 全出 |
| 读自己 avatar 的 9 个复制字段 | ✓✓ 实机 | 复制集 = 座位 64..72；其余 63 个只能用**名字**单读 |
| 读自己 avatar 的具名字段（health/position/…） | ✓✓ 实机 | 见 §4 字典 |
| 0.5 秒粒度的实时状态轮询 | ✓✓ 实机 | 两次击倒事件均在翻转当帧捕获，0 崩溃 |
| 读**队友** | ⚠ 部分（HUD+ 已证） | HUD+ 只读 2 个字段：`booster` + `gbgqot6`（取 bit64 判死） |
| 读**任意 hash 的名字** | ✗ 否证 | `Network.object_info` 只给 id/type/bits/range，**不给名字**；短名非编码，无法推导 |
| **写**字段（`set_game_object_field`） | ✗ 被堵 | 写需要字段名；我们要动的 `a33df340` 名字无从获得 |
| 读非己方对象 | ⚠ 未证 | 需走 HUD+ 的 `squad_owned` 特例（仅对 `3b12bd49`/`cd889dbc`） |

---

## 2 正确调用形态（照抄这段）

```lua
-- 闸 0：session 身份 + 真的在局内（主菜单 game_session() 有值，但 in_session=false）
local session = Network.game_session()
assert(GameSession.in_session(session) == true)
local peer = Network.peer_id()                      -- 注意：返回**字符串**

-- 闸 1：goid 只能来自 objects_owned_by
local owned = GameSession.objects_owned_by(session, peer)
-- 进任务后约 295 个；刚上船可能只有 1 个（player=0）

-- 闸 2/3：还活着 + 类型对
GameSession.game_object_exists(session, goid)            == true
GameSession.game_object_is_type(session, goid, "un6y1d") == true   -- 类型名是乱码串

-- 读单个字段：第 3 参是**字段名**，传 hex 会硬崩（已实测两次）
local avatar = GameSession.game_object_field(session, player_goid, "baegche")

-- 读整张快照：按 object_info 的座位号对齐
local batch = GameSession.game_object_field_batched(session, avatar_goid, {})
local health = batch[42]                            -- gl7xl2w 的 seat 42 = health
```

**六道闸**（每次读之前）：session 一致 → `in_session` → goid ∈ owned → `exists` → `is_type` → 字段在该类型声明里。
**全部调用套 `pcall`**；每次调用前先 flush 一行 markers 到磁盘（崩了也能定位）。

---

## 3 关键常量（全部实机验证）

| 项 | 值 | 判定 |
|---|---|---|
| `NO_OBJECT` 哨兵（无对象） | **32767** | ✓✓（`un6y1d.baegche` 是 15 bit，range 0..32767，max 就是哨兵） |
| `gls4w9b` 在飞船上 | **30** | ✓✓（多次） |
| `gls4w9b` 在地面 | **100** | ✓✓（多次） |
| avatar `seat 70` `a33df340` | **1 = 被击倒/失控**，0 = 受控 | ✓✓（2 次爆炸击倒 + health 同时掉血；自主蹲/趴不触发） |
| `gbgqot6`（`cd889dbc`）死亡位 | **比特 64**（第 8 字节第 0 位） | ✓ 源码（HUD+ `bits={8,0}`）+ 实测值 257 自洽 |
| `health` | 满血 125；被爆炸掉到 95、67 | ✓✓ |
| `motion_enabled` | 船上 true / 地面 false | ⚠ **不能**当「在控制中」用 |

---

## 4 字段字典（hash ↔ 名字 ↔ 座位）

| hash | 名字 | un6y1d 座位 | gl7xl2w 座位 |
|---|---|---|---|
| `0cb0453ea` | `health` | – | 42 |
| `8bbeb160` | `position`（Vector3 userdata） | – | 23 |
| `82830aed` | `state`（0=活 2=死，2bit） | – | 38 |
| `49c250a6` | `fire_mode` | – | – |
| `788b9753` | `enabled_mask`（carry 掩码） | – | 49 |
| `67526982` | `underbarrel_goid` | – | – |
| `58c2060b` | `shield_goid` | – | – |
| `a5ae4500` | `drone` | – | – |
| `4441caf8` | `rotation_enabled` | – | 61 |
| `d49efb40` | `motion_enabled` | – | 27 |
| `0f27c68e` | `baegche`（player→avatar 句柄） | **2** | – |
| `c3a3f66c` | `dvpupm`（bind 字段） | – | – |
| `e144c5e3` | `mm9hm0` | – | – |
| `dae681f4` | `gls4w9b`（飞船状态） | – | **68** |
| `3b12bd49` | **`booster`**（增益 id，steady） | **14** | – |
| `cd889dbc` | **`gbgqot6`**（状态位域，bit64=死） | **3** | 2 |

类型：**`un6y1d`** = player（hash `0x803159b3`，**36** 字段）；**`gl7xl2w`** = avatar（hash `0x5d9752f9`，**72** 字段，复制集只 9 个）。

---

## 5 证据链（run 4 → 8）

| run | 载荷 | 得到什么 |
|---|---|---|
| 4 | probe_read 1.0.0 | 名字形态跑通；**goid=0 合法**（推翻旧假设）；崩溃源于第 3 参传 hex；32767 哨兵实测 |
| 5 | 1.1.0 | batched 语义：player 回全 36、avatar 只回末尾 9；`out` 不是选择器；快照非增量 |
| 6 | 1.2.0 | 修好单实例/帧上限/截断；打出 `un6y1d` **完整 36 字段表** |
| 7 | 1.3.0 | 换装对照：**player 36 字段全程静止**（⇒ 携带状态在被携带对象上）；avatar 只有 seat 70 动了 |
| 8 | 1.4.0 | 定点观察：**seat 70 = 被击倒**（2 次事件 + health 交叉印证） |

日志存档：`D:\mod\logs\probe-read-runs\`（run4..run8，共 124 KB）。

---

## 6 工具与产物

| 路径 | 内容 |
|---|---|
| `tools/probes/probe_read.lua` | 最终版探针（1.4.0，定点观察） |
| `tools/probes/offline_test.py` | **离线夹具**：伪造 stingray 驱动状态机，含 3 个用例 + 变异测试 |
| `tools/probes/build.py` | 打包成 `patch_5`（`mods/auto/5`）并安装/回滚 |
| `tools/probes/probe_repl.lua` / `probe_resovr.lua` / `probe_types.lua` | 早期三个探针（复制层侦察 / 资源覆盖 / 类型 schema） |
| `tools/hudplus-derive/extract_names.py` | 从 HUD+ 载荷里提取 hash→名字 |
| `tools/hudplus-derive/field-names.json` | 14 条字段名（附 hash） |
| `tools/hudplus-derive/type-names.json` | **222** 条类型 hash→类型名 |

探针工作目录：`D:\mod\probe-both\`（含 `_offline/` 演练产物）。

---

## 7 未决 / 下次接续点

1. **找新的第三方 HUD/血量 mod 包** → 用 `extract_names.py` + `srkit extract --decoded` 再捞一批字段名。
   **这是唯一能解锁「写」的路**（写需要名字，而名字只能抄）。
2. **读队友**：`peers()` → 每个 peer 的 `objects_owned_by` → 其 `un6y1d` → `baegche` → 其 avatar 的
   `health`/`position`/`state`（需联机；HUD+ 只走通了 2 个字段的 squad 特例）。
3. 死亡瞬间 `seat 70` 是否也为 1（未证）；`seat 69` `6d976352` 的语义（船上 40 / 地面 100，与 68 成对）。
4. avatar 前 63 个字段为什么不在复制集里（只能按名字单读）。

---

## 8 当前部署状态（2026-10-24 收尾）

`data/` 里保留的补丁：`patch_0`(BootProbe) / `patch_1`(rtt_hud) / `patch_2`(plugin_probe) /
`patch_3`(10x scope + 2.8 MB gpu) / `patch_4`(ArmoryForge)。**读探针 `patch_5` 已卸载**。

| 操作 | 命令 |
|---|---|
| 卸载读探针 | `python D:\mod\probe-both\build.py --remove` |
| 重装读探针 | `python D:\mod\probe-both\build.py --only read` |
| 回到本系列之前的全套 | `python D:\mod\hudplus-deploy\install_hudplus.py --restore` |
| 全清（回到纯净游戏） | 删掉 `data/9ba626afa44a3aa3.*` 全部文件 |
