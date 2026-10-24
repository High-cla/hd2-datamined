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

## 7. 结果（待填）

| 项 | 值 |
|---|---|
| 局次 | — |
| A：`object_info("un6y1d")` 字段数 | — |
| A：`objects_owned_by` 计数 / 首对象类型 | — |
| A：`game_object_field` / `batched` 读数 | — |
| B：任务内真名可见？/ override 后别名 | — |
| 判定 | — |
