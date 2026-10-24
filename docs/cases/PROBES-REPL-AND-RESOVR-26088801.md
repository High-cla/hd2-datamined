# 两个探针：复制层只读侦察 + 资源覆盖跨类型（任务内重测）

> build `26088801` · 2026-10-24 · 状态：**已装、等一局实机**（boot 段 + 进任务后的延后段）
> 产物：`data/9ba626afa44a3aa3.patch_5`（20,448 B，资源 `mods/auto/5` = `0xF2EFDB8354D99D1D`）
> 生成器：`D:\mod\probe-both\build.py`（`--remove` 一键撤；`--only repl|resovr` 单独装）

## 0. 为什么能"一个补丁测两件事"

我们装的 `patch_0`（BootProbe 1.3.0）在 boot 时会 `require` 存在的 `mods/auto/1..6`。
两个探针合成为一个模块放进去，boot 段各跑一遍；**延后段靠包一层全局 `update`** 实现：

> BootProbe 在第 20 行就 `update = noop`，而它在第 355 行才 `require` 模块 ——
> 所以模块拿到的 `update` 一定是函数，**包一层就能拿到每帧钩子，不需要改 patch_0**。
> （这正是 LuaJIT 时代 mod 的老办法；v21 的 `on_update` 做的也是同一件事。）

## 1. 探针 A：`probe_repl.lua` —— 复制层（这是 HUD 信息面的根因修复）

**问的问题**：`Network.object_info` / `GameSession.game_object_field(_batched)` / `objects_owned_by`
这一套在 build 26088801 上**活着吗**、返回什么？

| 阶段 | 做什么 |
|---|---|
| boot | 数 `Network`/`GameSession` 的键数、打印 9 个关键方法是 function 还是 nil；对 4 个类型名（`un6y1d`=player + 3 个备选）调 `object_info`，打印 **字段表**（`id/type/bits/min/max`）；打印 boot 时刻 `game_session()` |
| 延后 | **等到真的拿到 owned 对象**（= 进任务了）才继续：`peers` 计数 → `objects_owned_by(session, 我的 peer)` → 第一个对象 `game_object_exists` + 4 个 `game_object_is_type` → 用 schema 的第一个字段 hash 做 `game_object_field` → `game_object_field_batched` 并打印返回表形状 |

**关键的时序修正**：船坞里 `game_session()`/`main_world()` 可能**已经非 nil**。
所以不是"第一帧有 session 就跑"，而是**每 120 帧重试一次，直到真的拿到 owned 对象**（上限 20000 帧 ≈ 5.5 min）。

## 2. 探针 B：`probe_resovr.lua` v1.2.0 —— 资源覆盖（这次在任务内测）

**问的问题**：`set_resource_override` 只对 `lua` 有效，还是 `material`/`texture` 也行？

v1.1.0 的死穴：boot 时刻 `can_get("material", 真名)` 就是 `false`，而 `can_get` 对一个它看不见的类型
返回 false 说明不了任何事。v1.2.0 因此**把非 lua 的判定挪到任务内**（美术 bundle 那时才挂载）：

| 阶段 | 做什么 |
|---|---|
| boot | ① `lua` 口径校准（override 前 false → 后 true → clear 后 false）；② 记录 boot 时刻 material/texture 真名的读数（**预期 false**，并注明这不构成否证） |
| 延后 | **等到 `can_get(material 或 texture 的真名) == true`**（每 120 帧重试）→ 此时才做：override 前查 → `set_resource_override` → **再查（决定性）** → `clear` → 复查 |

### 判读矩阵（探针 B）

| 日志 | 结论 |
|---|---|
| 真名在任务内变 `true`，override 后别名也 `true` | **✓ 覆盖对非 lua 类型生效** ⇒ 运行期热换美术资源成立 |
| 真名变 `true`，但 override 后别名仍 `false` | **✗ 覆盖只对 lua** ⇒ 这条轴关闭 |
| 一直 `false` 到 20000 帧 | **⚠ 口径不可用**（can_get 根本不索引非 lua 类型），需要"真消费者"才能测 |

## 3. 两个必须防住的坑（都已在离线 harness 里复现并修掉）

| 坑 | 说明 |
|---|---|
| **`if pcall(fn) then done = true end` 是错的** | `pcall` 只要不报错就返回 `true`，于是"这次还没到时候"被当成"已完成" ⇒ 探针只试一次就永久放弃。正确写法 `local ok, finished = pcall(fn)`；`done = ok and finished`。这个 bug 在离线 harness 上跑出来了，已修 |
| **船坞 ≠ 任务** | 见上；两个探针都改成"条件不满足就等，不是第一帧就判" |

## 4. 离线验证（已做，全部通过）

| 项 | 结果 |
|---|---|
| Lua 5.1 语法（`lupa.lua51`，真 5.1） | 三份都 OK（两个探针源 + 合成 payload） |
| 合成 payload 语法 | OK（20,239 B 源码） |
| 假引擎全链路 | 船坞阶段：两个探针各重试、**不判定**；切到任务后第 121 帧：**两者都完成**，日志内容与预期格式一致（探针 A 打出 `nfields`/字段表/`is_type`/`field`/`batched`；探针 B 打出 `before false → override → after true → cleared false`） |
| 容器 | `srkit list` 1 条 lua、id 匹配；`srkit check` 解码/重编码逐字节一致 |
| 补丁链 | 0..5 连续 |

## 5. 怎么读（启动 → 进主菜单 → 再进一局任务）

```bash
# 探针 A：字段表 + 对象读取
cat "$LOCALAPPDATA/CowboyBingus/Helldivers2/Logs/ReplProbe.log"
# 探针 B：资源覆盖
cat "$LOCALAPPDATA/CowboyBingus/Helldivers2/Logs/ResOvrTypes.log"
```

**任务里待 15–30 秒**再退出（延后段最多每 2 s 试一次）。两份日志都以 `===== … boot section done =====`
分段；延后段以 `attempt N` / `--- (2) … ---` 开头。

## 6. 风险与回滚

| 项 | 说明 |
|---|---|
| 只读范围 | 探针 A **不调用** `set_game_object_field` / `create_game_object` / `destroy_game_object`，只读 |
| 可能有副作用的两处 | 探针 B 的 `set_resource_override`（对 material/texture/垃圾类型各一次，随后立刻 `clear`）；早前 v1.0.0 崩过 1 次、v1.1.0 未复现 |
| 每步先落盘 | 两个探针都是"先写 `>>> BEFORE <调用>` 并 close，再调用"，所以硬崩也能指出凶手 |
| 回滚 | `python D:\mod\probe-both\build.py --remove`（只删 patch_5 的 3 个文件） |

## 7. 第 1 局结果（2026-10-24）

### 7.1 ✓✓ 探针 B：**`set_resource_override` 对 `material` 也生效**

| 阶段 | 读数 |
|---|---|
| boot | `can_get(material, 真名) = false`、`can_get(texture, 真名) = false` |
| 任务内（第 3361 帧 / attempt 29） | **`can_get(material, 真名) = true`** ⇒ boot 时的 false 是"**没挂载**"，不是"不支持" |
| override 前 | `can_get(material, 别名) = false` |
| `set_resource_override("material", 别名, 真名)` | `OK ret=nil` |
| **override 后** | **`can_get(material, 别名) = true`** ← **决定性：覆盖被采纳** |
| `clear_resource_override` 后 | 回到 `false`（撤销干净） |

⇒ **"运行期热换材质"这条轴成立**，而且这是 v21 完全没用到的一条 API。
`texture` 那次没测成：那条地形贴图在该任务里没被挂载（`can_get(texture, 真名) = false`），换一张任务内确实加载的贴图即可复核。

### 7.2 探针 A：拿到了 schema，但**崩在字段读**

| 项 | 读数 |
|---|---|
| `Network`/`GameSession` | 方法齐全（9/9 都是 function） |
| **`object_info` 在 boot 就能用** | `un6y1d` → **36 个字段**；`0bq5t3` → 20；`aacde2e` → 22；`baj_bt` → 20 |
| 字段元数据形态 | `{id="8 位 hex", type=0..10, bits, min, max}`，例：`f27c68e type=1 bits=15 min=0 max=32767`、`8bbeb160 type=3 bits=24 min=-2000 max=2000` |
| 进任务 | `peer_id()` = **字符串** `a50da53b1ab77c2f`；`peers` = 1；`objects_owned_by` = 1 个 → **goid = 0** |
| `game_object_exists(session, 0)` | `true` |
| `game_object_is_type(session, 0, "un6y1d")` | **`true`** ⇒ **id 0 就是玩家**；另外 3 个候选类型都是 `false` |
| 崩点 | `GS.game_object_field(session, 0, "a3df1643")` —— 日志最后一行是 `>>> BEFORE`，没有 `<<< AFTER` |
| BootProbe 侧 | 正常跑完（`===== BootProbe end =====`）⇒ 崩在**延后段**，不在 boot |

**三个可疑点**（当时无法区分）：

| # | 疑点 | 依据 |
|---|---|---|
| (a) | **字段 id 少了 `0x` 前缀** | HD2 HUD+ 传给引擎的一律是 `"0x%08x"`；它拿到 schema 的 `id`（无前缀）后**自己补 `0x`** 再当 key 存 |
| (b) | **读的是 type=0 的字段** | 那次读的 `a3df1643` 正是 `un6y1d` 的 **field[1]，type=0，bits=nil**。type 0 可能是引擎没实现的复合类型 |
| (c) | `goid = 0` 是否合法 | `exists`/`is_type` 都接受 0，但字段读可能走另一条解引用路径 |

### 7.3 探针 A v1.2.0 的加固（已装）

| 加固 | 做法 |
|---|---|
| 堵 (a) | 一律 `"0x" .. id` |
| 堵 (b) | **只读在 schema 里存在、且 `type ∈ {1,2,3}`（纯数值）的字段**；type 0/4/10 一律跳过 |
| 优先用第三方验证过的字段 | `cd889dbc`（`un6y1d` 的 field[3]，type=1 bits=32）就是 HUD+ **SQUAD_ALL 里 player 关系的字段**之一，先试它 |
| 限制次数 | 最多 3 次字段读 + 1 次 batched；任一 `pcall` 报错就停 |
| 只装 A | `build.py --only repl`，payload 13 KB，去掉探针 B 的写入动作 |

> 说明：`3b12bd49`（HUD+ 的另一个 player 字段）**不在** `un6y1d` 的 36 个字段里，探针会跳过它并打印出来
> —— 这本身也是一条信息（HUD+ 的那条数据可能属于另一种类型，或该字段在新 build 被去掉了）。

## 8. 结果（待填，第 2 局）

| 项 | 值 |
|---|---|
| 局次 | — |
| A：`object_info("un6y1d")` 字段数 | — |
| A：`objects_owned_by` 计数 / 首对象类型 | — |
| A：`game_object_field` / `batched` 读数 | — |
| B：任务内真名可见？/ override 后别名 | — |
| 判定 | — |
