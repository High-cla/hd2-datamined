# HUD+ 0.5.3 实机可用性验证 —— 兼 `game_object_field` 正确调用形态

- build：**26088801**（`data/settings.ini` 的 `build = 19411`，HUD+ 的硬闸门要求匹配）
- 日期：2026-10-24
- 载荷：`HD2_HUD_Plus_Full_Repair_0.5.3_build26088801.zip`
- 部署：`D:\mod\hudplus-deploy\install_hudplus.py --install`，patch_0..9 全占，30 个文件
- 结论：**✓✓ 实机可用**（用户目视 HUD 正常 + 日志计数器自证）；本文同时给出我们此前两次崩溃的根因候选

---

## 0 一句话

HUD+ 0.5.3 在本 build 里**跑通了**，而且日志证明它把
`GameSession.game_object_field` / `game_object_field_batched` 调了上万次、0 异常、0 被拒。
它调法与我们的唯一区别有三处：**goid 来源**、**5 道前置闸**、**第 3 参是字段名而不是 hash**。

---

## 1 部署记录

| 项 | 值 |
|---|---|
| 备份 | `D:\mod\backups\hudplus-deploy\before-hudplus-20261024-123554`（17 文件 + manifest.json） |
| 装前占用 | patch_0..5 + 伴生（我们的 BootProbe / rtt_hud / plugin_probe / 10x scope / ArmoryForge / probe_types） |
| 装后占用 | patch_0..9（COMMON×3、WEAPON_ON、BACKPACK_ON、NUMBERS_BOTH、ICON_FULL、ICONPOSITION_CROSSHAIR、IDLE_FIX、SQUAD_ALL） |
| patch_0 | 229,078 B（boot 载荷 `lua/lua_F476DF93691895FA`） |
| patch_2 `.gpu_resources` | 1,048,576 B（图标图集） |
| 回滚 | `python D:\mod\hudplus-deploy\install_hudplus.py --restore`（逐个校验 sha256 前缀） |
| 日志采集 | `python D:\mod\hudplus-deploy\read_log.py --snap` → `D:\mod\logs\hudplus-run-20261024-124246\` |

---

## 2 日志全文（10 行，1,733 B，sha256 `236dc992ab319905…`）

```
[HUDPlusRepair 0.5.3] RUN product install=ok hook=global-update
[HUDPlusRepair 0.5.3] installed=true; original=0.1.6; original optional features retained; gameplay pending
frame=60    resolved=0    unknown=60   reason=no-session-world-or-peer body=unbound hand=nil gui=false batches=0     batch_errors=0 columns=0     gui_calls=0     gui_faults=0 rejected=0
frame=300   resolved=0    unknown=300  reason=no-session-world-or-peer body=unbound hand=nil gui=false batches=0     batch_errors=0 columns=0     gui_calls=0     gui_faults=0 rejected=0
frame=341   resolved=0    unknown=341  reason=no-session-world-or-peer body=unbound hand=nil gui=false batches=0     batch_errors=0 columns=0     gui_calls=0     gui_faults=0 rejected=0
frame=900   resolved=0    unknown=900  reason=no-session-world-or-peer body=unbound hand=nil gui=false batches=0     batch_errors=0 columns=0     gui_calls=0     gui_faults=0 rejected=0
frame=1800  resolved=0    unknown=1800 reason=no-session-world-or-peer body=unbound hand=nil gui=false batches=0     batch_errors=0 columns=0     gui_calls=0     gui_faults=0 rejected=0
frame=3600  resolved=0    unknown=3600 reason=no-session-world-or-peer body=unbound hand=nil gui=false batches=0     batch_errors=0 columns=0     gui_calls=0     gui_faults=0 rejected=0
frame=5035  resolved=0    unknown=4854 reason=the-avatar-is-the-ship-avatar body=unbound hand=nil gui=false batches=0 batch_errors=0 columns=0 gui_calls=0 gui_faults=0 rejected=0
frame=13140 resolved=3984 unknown=4908 reason=no-avatar:no-avatar-right-now body=unbound hand=nil gui=true batches=11548 batch_errors=0 columns=51267 gui_calls=17544 gui_faults=0 rejected=0
```

### 2.1 时间线

| 帧 | 状态 | 含义 |
|---|---|---|
| 60–3600 | `no-session-world-or-peer` | 主菜单/加载，`game_session()` 还没给到真 session |
| 5035 | `the-avatar-is-the-ship-avatar` | **飞船上的 avatar**——它专门有一道闸把它认出来并跳过 |
| 13140 | `gui=true`、`resolved=3984` | 任务内：GUI 已在画，且**3,984 次完整身份绑定成功** |

### 2.2 计数器含义（源码对齐）

| 字段 | 源码 | 读数 |
|---|---|---|
| `resolved` | `counters.resolves`，在 `seal()` 里 `+1`（script.lua:1583）——seal 只在「body+grip+手上武器」全绑上时调用 | **3,984** |
| `unknown` | `counters.unknowns`（:1419） | 4,908 |
| `batches` | `counters.batched_calls`，每次 `game_object_field_batched` 调用 `+1`（:2555） | **11,548** |
| `batch_errors` | `pcall` 失败才 `+1`（:2559） | **0** |
| `columns` | `columns_filled`，只在**值非 nil** 时 `+1`（:2684） | **51,267** |
| `gui_calls` / `gui_faults` | 引擎 GUI 调用数 / 异常数 | 17,544 / **0** |
| `rejected` | `check_read` 判不通过（:134） | **0** |

> `columns=51,267` 不是"尝试次数"，是**真拿到非 nil 值的次数**。
> `rejected=0` 意味着 11,548 次批读里**没有一次被它的校验闸拦下**——闸门条件每次都满足。

> 末帧 `body=unbound hand=nil` 出现在一次 **session 切换后 180 帧**（`R.followup = frames + 180`，:145），
> 是 `reset()`（:539 把 body_binding 置 unbound）之后的瞬时态，**不是全程没绑上**；
> 3,984 次 seal 才是全程结论。

---

## 3 我们两次崩溃的根因（三处差异）

我们崩在：`GameSession.game_object_field(session, 0, "a3df1643")` 与 `…, 0, "0xcd889dbc")`。

### 3.1 差异一：第 3 参是**字段名**，不是 hash ★

HUD+ 的每次单读都走：

```lua
-- script.lua:1156
return call(self.counters, GS.game_object_field, session, goid, field_row.call)
-- script.lua:1144  硬性要求 field_row.call 是 string
if type(field_row.call) ~= "string" then return nil, "no-authored-field" end
```

而 `field_row` 来自它内嵌的生成表，形如：

```lua
["bind_field"]      = { ["hash"]="0xc3a3f66c", ["call"]="dvpupm" }
["carry_field"]     = { ["hash"]="0x788b9753", ["call"]="enabled_mask" }
["underbarrel_field"]={ ["hash"]="0x67526982", ["call"]="underbarrel_goid" }
["player"]          = { ["call"]="un6y1d", ["type"]="0x803159b3",
                        ["avatar_field"]={ ["hash"]="0x0f27c68e", ["call"]="baegche" } }
```

⇒ `hash` **只用于校验**（`info.repair_ids[hash]`、`declared_fields[hash]`），
真正传给引擎的是 `call`——一个**名字串**（`dvpupm` / `enabled_mask` / `rotation_enabled` / `baegche`）。
`R.hash32()`（:30-35）负责把 `0x…`、`#id[…]`、裸 hex 统一成 `"0x%08x"` 供校验用，
这也解释了为什么它要写这个归一化函数却**不拿它去调用**。

我们传的是 `"0xcd889dbc"` 这种 hash 形态 ⇒ 语义错。

### 3.2 差异二：goid 必须来自 `objects_owned_by`，`0` 不是有效对象 ★

HUD+ 的 goid 只有一个来源：`objects_owned_by(session, peer_id)`（:891、:101、:117），
再经 `type_of()` 用 `game_object_is_type` 逐类型试（:857-887），从不用别的数字。

而且它的哨兵值不是 0：

```lua
local NO_OBJECT = 32767          -- :475
if goid == NO_OBJECT then return nil, "no-avatar-right-now" end   -- :1305
```

⇒ 字段读出来是 `32767` 表示「这个字段现在指向空」，是**合法返回值**；
真正的"空"是 32767，而不是 0。我们拿 `0` 当 goid 去调，引擎**不做校验**（这一点我们此前已证：绑定层接受任意参数不报错），
于是进到 `game_object_field` 内部拿空对象去取字段 ⇒ 访问违例。这是目前最强的根因候选。

### 3.3 差异三：五道前置闸（我们一道都没有）

`R.owned()` + `R.check_read()`（:95-136）每次读之前都要过：

| # | 闸 | 代码 |
|---|---|---|
| 1 | session 身份一致 | `net.game_session() == session` |
| 2 | 真的在局内 | `gs.in_session(session) == true` |
| 3 | goid 属于本 peer | `goid ∈ objects_owned_by(session, peer_id)` |
| 4 | 对象还活着 | `gs.game_object_exists(session, goid) == true` |
| 5 | 类型对得上 | `gs.game_object_is_type(session, goid, type_name) == true` |
| + | 字段在该类型声明里 | `object_info(name).fields[*].id` 里含该 hash |

而且**全部**外部调用都套 `pcall`（`R.attempt` :37-41、`one_by_one` :2534、`batched` :2556）。

### 3.4 附带结论：`game_object_field_batched` ✓ 实机可用

我此前把它列为"唯一没试过的读取形态（可能是第三次崩溃）"。现在**不用试了**：
11,548 次调用、0 异常、51,267 个非 nil 值。这是 HUD+ 在任务内的主数据通路。

它的语义（:2549-2580 + :2447-2496）：

```lua
game_object_field_batched(session, goid, out)   -- out 是复用表，调用前清空
```

- 返回的表按**该类型 schema 的字段声明顺序**位置对齐 ⇒ `out[seat]`，
  `seat` 就是 `Network.object_info(name).fields[seat]` 的下标；
- **不需要知道字段名**——这正是它规避 3.1 那条限制的办法；
- `seated()`（:2498）还兼容"值被嵌套在子表里"的情形。

⇒ 对我们「批量取出某对象所有字段」的需求，这是正解；单读才需要名字。

---

## 4 顺带拿到的字典（新资产）

### 4.1 字段 hash ↔ 名字（13 条，全部来自载荷内嵌表）

| 字段 hash | 名字 | 出处 |
|---|---|---|
| `0xcb0453ea` | `health` | — |
| `0x8bbeb160` | `position` | — |
| `0x82830aed` | `state` | — |
| `0x49c250a6` | `fire_mode` | — |
| `0x788b9753` | `enabled_mask` | `carry_field`（174 类型共有） |
| `0x67526982` | `underbarrel_goid` | `underbarrel_field` |
| `0x58c2060b` | `shield_goid` | — |
| `0xa5ae4500` | `drone` | — |
| `0x4441caf8` | `rotation_enabled` | `avatar.rotation_field` |
| `0xd49efb40` | `motion_enabled` | `avatar.motion_field` |
| `0x0f27c68e` | `baegche` | `player.avatar_field`（注意：9 位 hex，实为 `f27c68e`） |
| `0xc3a3f66c` | `dvpupm` | `bind_field` |
| `0xe144c5e3` | `mm9hm0` | — |
| `0xdae681f4` | `gls4w9b` | `avatar.ship_field`（**飞船判据**，见 §4.6） |

> 我此前记的"14 个 schema 失配标签"就是这批**字段名**——**14/14 全部拿到 hash**。
> `gls4w9b` 藏在 `avatar.ship_field` 里，形如 `{hash, value, call}`（三键，hash 与 call 不相邻），
> 原先"相邻对"正则扫不到；`extract_names.py` 已改成"按最内层表块配对"→ 14 条全出。

### 4.6 飞船 avatar 的判据：读一个字段跟常量比，**不是**数实体

```lua
-- 数据（内嵌表）
ship_field = { hash = "0xdae681f4", value = 30, call = "gls4w9b" }

-- script.lua:1320
function Identity:on_ship(session, avatar)
  local spot = self.avatar.ship_field
  if spot == nil then return false end                 -- ① 没有这个字段 → 闸自动失效（放行），不报错
  local memo = self.ship_memo
  if memo ~= nil and memo.goid == avatar.goid then     -- ② 按 avatar goid 记忆，goid 不变不重读
    return memo.aboard
  end
  local value = self:avatar_value(session, avatar, spot)  -- ③ game_object_field(session, avatar_goid, "gls4w9b")
  if value == nil then return false end                -- ④ 读不到 → 当作不在船上（fail-open）
  local aboard = value == spot.value                   -- ⑤ 与 30 比较
  self.ship_memo = { goid = avatar.goid, aboard = aboard }
  return aboard
end
```

`reset()`（:539 附近）清 `ship_memo`；`avatar_goid` 变化时 `find` 会先 `reset()` 再重读（:1300-1304）。

**离线交叉验证**（`type-schema-dictionary.json`）：

| hash | 声明它的类型 | schema |
|---|---|---|
| `dae681f4` | **只有 `gl7xl2w`（= avatar）** | `type=2, bits=8, range=-1..255` |

⇒ 这个字段**只存在于 avatar 类型上**，是普通 8 位值（不是 2 bit 枚举）⇒ `30` 是一个正常状态编号。
而 avatar 类型名 `gl7xl2w` / 类型 hash `0x5d9752f9` 与内嵌表完全一致。

**同家族的另外四道闸**（同一套「读语义字段」思路）：

| 判据 | 字段 | hash | 常量 | 源码 |
|---|---|---|---|---|
| 是否在飞船上 | `gls4w9b` | `dae681f4` | `== 30` | :1320 |
| 是否死亡 | `state` | `82830aed` | `== 2`（`AVATAR_LIVING, AVATAR_DEAD = 0, 2`，:441） | :605-607 |
| 是否在玩家控制中 | `motion_enabled` | `d49efb40` | bool | :1309-1311 |
| 旋转是否解锁 | `rotation_enabled` | `4441caf8` | bool | :1332 |
| 备注用（诊断） | `health` / `state` / `rotation_enabled` | `cb0453ea` / `82830aed` / `4441caf8` | — | `gate_note_fields` |

`state` 的 schema 是 `type=1, bits=2, range=0..3`（20 个类型共用）⇒ 4 态枚举，`2 = 死`，与常量自洽。
`health` 的 schema 是 `type=1, bits=18, range=-100000..162143`，且**只在 `gl7xl2w`** 出现。

**与我们"数加载实体"的对比**：

| | HUD+ 的做法 | 我们此前的做法 |
|---|---|---|
| 判据性质 | **语义状态**（官方自己定的字段值） | **环境代理**（实体数量） |
| 是否需要阈值 | 不需要，直接等于常量 | 需要，且阈值随版本/场景漂 |
| 过渡态（运输机/复活/降落） | 字段值直接给出真值 | 计数可能暂时"像在局内" |
| 换 build 后 | 字段改名则闸自动失效（fail-open），不崩 | 阈值失效则误判，且**误判后照样去调 API** |
| 额外收益 | 死亡/受控/旋转锁定一并精确判定 | 只知道"加载差不多了" |

提取物：`D:\mod\recon-hudplus\derived\field-names.json`、`REPORT.md`（`extract_names.py`）。

### 4.2 类型 hash ↔ 类型名（222 条）

`equipment` / `backpacks` / `underbarrels` / `pack_links` 四张表的行首都是 `["0x<hash>"]={["call"]="<名字>", …}`。
222 条全部提取，0 冲突：`D:\mod\recon-hudplus\derived\type-names.json`。

其中两条身份关键项（不在 222 里，单独硬编码）：

| 身份 | 类型 hash | 类型名（`object_info` 与 `game_object_is_type` 都用它） |
|---|---|---|
| player | `0x803159b3` | **`un6y1d`** |
| avatar | `0x5d9752f9` | **`gl7xl2w`** |

### 4.3 身份链的完整字段名（可直接抄）

| 用途 | 所在类型 | hash | 名字 |
|---|---|---|---|
| player → avatar goid | `un6y1d` | `0x0f27c68e` | `baegche` |
| avatar 是否在玩家控制中 | `gl7xl2w` | `0xd49efb40` | `motion_enabled` |
| avatar 是否锁定旋转 | `gl7xl2w` | `0x4441caf8` | `rotation_enabled` |
| 手上武器绑定 | 武器类型 | `0x788b9753` | `enabled_mask` |
| 武器/背包绑定另一对象 | 各类型 | `0xc3a3f66c` | `dvpupm` |

**类型名不是编码，是人工命名**：222 条里出现 `vdvv_d`（带下划线）、`e5j54r`、`bgevul2` 等混排，
证明 6–7 字符短名不是 hash 的某种 base36/base32 编码（已实测排除）⇒ **任意 hash → 名字无法推导，
只能靠字典或 `object_info`**（而 `object_info` 只给 id/type/bits/range，不给名字，见 `type-schema-dictionary.json` 只有 4 个键）。

### 4.4 avatar 的 36 个 unit 变量名

`avatar.variables.third_person = { active_magazine, aim_horizontal, aim_vertical, arm_wrestle,
attach_backpack, attach_holster, attack_speed, character_state, drown_progress, element_type,
exertion, fall_pitch, fall_yaw, gunner_traverse, … }`（36 条）
——这是 **Unit 变量**（不是网络字段），配 `Unit.variable()` 之类使用。

### 4.5 `0xcd889dbc` 的身份

载荷里 `["action"]={["layer"]=11,["stage"]={["hash"]="0xcd889dbc",["relation"]="hand-weapon"},["gate"]="weapon-rig"}`

⇒ `cd889dbc` = player(`un6y1d`) 的 **action.stage** 字段，关联 `hand-weapon`，出现在 **127 个类型**的声明里。
`check_read` 对 `3b12bd49` / `0xcd889dbc` 有特殊照顾（:131）：**自己没拥有时允许读队友的**（`squad_owned`）——
这正是"读队友状态"要用的两个字段。

---

## 5 三态判定

| 主张 | 判定 | 依据 |
|---|---|---|
| HUD+ 0.5.3 在本 build 实机可用 | ✓✓ 实机 | 用户目视 + `gui=true`/`resolved=3984`/`gui_faults=0` |
| `game_object_field` 实机可调（有 goid + 名字） | ✓✓ 实机 | 载荷成功 seal 3,984 次，其间大量单读 |
| `game_object_field_batched` 实机可调 | ✓✓ 实机 | 11,548 次 / 0 异常 / 51,267 非 nil |
| 第 3 参是字段名而非 hash | ✓ 源码强证 | :1144/:1156 + 内嵌 `{hash, call}` 成对表 |
| 我们崩溃的直接原因是 `goid = 0` | ⚠ 未证（强候选） | 与 HUD+ 行为对比推出，尚未单变量实测 |
| `goid = 0` 以外的形态也不对 | ⚠ 未证 | 上与 3.1 两个变量尚未分离 |

---

## 6 未解决 / 下一步

1. **回滚并把探针改成正确形态**（单变量法，一次只动一处）：
   - 探针 A：`goid` 取自 `objects_owned_by` + 5 道闸 + **名字**形态（最安全，先跑通）
   - 探针 B：同上但改回 hash 形态 → 用来分离"名字 vs hash"到底哪个是必需的
   - 探针 C：只读用 `game_object_field_batched`，验证 `seat → fields[seat]` 对齐
   - 每个探针都必须**先落盘 marker** 再调用（我们既有的崩溃见证纪律）
2. **`foreign_calls` 全表还没拿到**：它来自 `mods/hd2_hud/frag_*` 这些**独立数据块**（`axis.resource`，:1943），
   不在 boot 脚本里。要拿到完整的 hash→名字 对照，需对 patch_1/3/4/5/6/7/8/9 做 `srkit extract --decoded`。
3. `body=unbound` 只在 session 切换的瞬时出现，不影响结论；但「换局后多久能重新绑上」值得记一笔。
4. 我们的 `type-schema-dictionary.json` 里有 `":/i0vEv`、`&"$#!XFm` 这类**不可能的类型名**，
   说明当初的类型名提取混入了噪声——与 222 条对表后可做一次清理（`object_info` 对这些串居然也返回了 schema，值得复核）。
