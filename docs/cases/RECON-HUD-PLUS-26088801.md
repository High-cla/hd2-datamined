# 侦察：`HD2_HUD_Plus_Full_Repair_0.5.3` —— 它**怎么拿数据**（我们 HUD 信息面窄的根因）

> 样本 `D:\QQ\1427814410\FileRecv\HD2_HUD_Plus_Full_Repair_0.5.3_build26088801.zip`
> sha256 `9b59174ea31a610cfec68beb00b09eed9bc13d97a0bf1d366ff1a1005572500b`，50 个条目
> 原作者 DDRK1NG（nexusmods 15298），本包是 0.1.6 的 "Full Repair"；**只读侦察**，未安装、未运行。

## 0. 一句话

它显示的不是"本机世界的实体"，而是**网络复制层的游戏对象**：靠
`stingray.Network.object_info(类型名)` 拿到字段表，再用
`stingray.GameSession.game_object_field(session, goid, 字段hash)` **按字段读任意 peer 的对象**。
远程队友在本机不是被模拟的 unit，所以**走 world-unit 路线永远拿不到**——这就是我们信息面窄的根因。

## 1. 包结构与形态

| 项 | 值 |
|---|---|
| 启动方式 | **覆盖 `boot` 资源**（`data/…patch_0` 里 id = `0xF476DF93691895FA`），228,886 B 明文 Lua / 5,066 行 |
| 依赖 | README 明说"**不需要 FFI、HD2Runtime 或旧 Bingus Shared Loader**"，自启动 |
| 冲突 | "本包占用 boot 资源；同时启用其它独立覆盖 boot 的 Mod 会冲突" ⇒ **与我们 patch_0（BootProbe）互斥** |
| 硬 build gate | 读 `data/settings.ini` 的 `build=`，要求 **`19411`**（本机 build 26088801 的 settings 内号），不匹配就 `return {installed=false}` |
| 可选功能 | 独立小补丁，是**数据 chunk**：`mods/hd2_hud/frag_{weapon,backpack,numbers,icon,iconposition,idle,squad}`。我们验过 id：`murmur64("mods/hd2_hud/frag_squad")` = `0x46A894DEB4EE737A` = SQUAD_ALL 补丁的真实 id ✓ |
| 资源 | COMMON/patch_1、patch_2 = `texture`+`material` 同一 id（图标图集，1 MB gpu） |
| 代码组织 | 13 个模块（`00-boot-state` … `90-main`）自带 mini 打包器，每模块用 **`setfenv` 白名单沙箱**（访问未声明全局直接 `error`，写全局也 `error`） |

## 2. ★ 它怎么拿信息（7 层）

| 层 | 手段 | 证据 |
|---|---|---|
| **A. 类型反射** | `stingray.Network.object_info(类型名)` → `{fields = [{id="8位hex", type, bits, min, max}, …]}` | `script.lua:2465`；它把 `id` 补齐成 `"0x%08x"` 存成 slot 表（`:2475-2485`） |
| **B. 单字段读** | `GameSession.game_object_field(session, goid, "0x3b12bd49")` | `:1156`、`:2534` |
| **B'. 批量读** | `GameSession.game_object_field_batched(session, goid, out)` —— 结果**按 seat 索引、可能是嵌套表**，所以它有 `seated()` 去嵌套里掏值 | `:2550-2595`、`:2522-2527` |
| **C. 找人/找物** | `GameSession.objects_owned_by(session, peer)` + `peers` + `in_session` + `game_object_is_type` + `game_object_exists` | `:101`、`:117`、`:132`、`:891` |
| **D. 三重校验后才用** | 每次读前 `<类型名>.repair_ids[字段hash]`、`game_object_is_type(session, goid, 类型名)`、`owned/squad_owned` | `Repair.check_read` `:126-134` |
| **E. 静态表** | 武器/背包/容量/配件/模式/瞄具/蓄力表按**当前实体表**烘焙进载荷（README：LAS-44 用实体哈希 `0x17783758` 补 heat 适配） | README + 载荷 |
| **F. 可选模块** | `Core.load(name)` = `require(name)`，期望返回 table（数据 chunk） | `:1910-1917` |
| **G. 渲染** | `World.create_screen_gui` + `Gui.text / text_extents / bitmap_uv / triangle / set_visible / destroy_*` + `Gui.resolution` | `callable(Gui,…)` 清单 |

**能显示"队友"的原因**：`objects_owned_by(session, peer)` 能列出**每个 peer** 拥有的对象
（含远程队友的角色/武器/背包），然后按同一套字段 hash 读他们的状态。本机不模拟远程玩家，
所以 `main_world()` 那条路的结构性上限就在这里。

## 3. 它自带的两份"字典"（可直接复用）

| 物 | 规模 | 用途 |
|---|---|---|
| `Repair.allowed_types` | **224 个**游戏对象类型名（乱码串，如 player = **`un6y1d`**） | `object_info` 只接受这些名字；已导出 `D:\mod\recon-hudplus\allowed_types.txt` |
| 8 位字段/类型 hash | 去重 **240 个**（如 `0x3b12bd49`、`0xcd889dbc` 是 player 类型的两种 hash） | 字段 id 白名单；配合 `object_info` 就能知道每个 hash 的 `type/bits/min/max` |

⇒ 我们要自己用这套接口，**缺的正是"类型名"**；这 224 个名字就是现成的候选表。

## 4. 它的诚实边界（README 自己说的 + 我们看的）

| 项 | 说明 |
|---|---|
| 蓄力环 | **"沿用网络状态 + 时钟估算"，不是读原生连续蓄力值** ⇒ 有些量网络里没有，只能估 |
| 换弹 | 用"当前网络换弹阶段"作门控 + 读角色**实际动画时间和长度** |
| 未验收 | README 明说"尚未进行当前游戏显示、多人和稳定性验收" |
| 与我们的关系 | 占 `boot`，装它就顶掉 BootProbe；`expected_build=19411` 硬 gate |

## 5. ★ 我们为什么没走这条路（自我更正）

**这些函数在我们自己的 API 枚举文档里，10-21 就记下来了**：

| 函数 | 我们的文档 |
|---|---|
| `GameSession.game_object_field` / `_batched` / `exists` / `is_type` / `objects_owned_by` / `peers` | `D:\mod\docs\LUA-API-25988413.md:219`（`stingray.GameSession`，33 个键） |
| `Network.object_info` / `message_info` | 同文件 `:473`（`stingray.Network`，58 个键） |

我们**枚举了 API 面，但只走了 `main_world()` → unit → component 一条路**。
所以"HUD 信息有限"不是引擎不给，是**我们没走复制层**。这条更正应写进 HUD 线的能力边界。

## 6. 顺带发现：引擎还有"写"和"造对象"的一半（⚠ 未测）

`GameSession` 33 个键里除读之外还有：

| 能力 | 键 |
|---|---|
| **写字段** | `set_game_object_field` |
| 造/销对象 | `create_game_object` / `destroy_game_object` / `migrate_game_object` |
| 会话控制 | `add_peer` / `remove_peer` / `make_game_session_host` / `shutdown_game_session_host` / `migrate_game_session_host` |
| 同步 | `unit_synchronizer` / `synchronized_peers` / `set_game_object_priority` / `set_interpolation_lag_compensation` |

⚠ 全部未测。**风险分类不同**：这是**运行期改多人联机的复制状态**，与"改本地数据表"不是一类；
在联机里用等于作弊，且 EAC 面未知。记录在案，不建议碰。

## 7. 建议的下一步（只读、不动这个 mod）

1. **写一个只读探针**（我们自己的 patch_0 体系内），只做三件事：
   `Net.object_info("un6y1d")` → 打印字段表；`GS.peers(session)` / `objects_owned_by` → 打印对象数；
   对第一个对象 `game_object_field(session, goid, <第一个字段 hash>)` 读一次并打印类型。
   —— 这一步就能确认这套接口**在本 build 上活着**，而且不需要装 HUD+。
2. 活着之后再谈"HUD 要显示什么"，那时我们有了**每个 peer 的字段流**。
3. 224 个类型名已导出，逐条 `object_info` 就能把**类型名→字段表**的地图一次建全（这是真·新数据源）。

## 8. 证据

| 文件 | 内容 |
|---|---|
| `D:\mod\recon-hudplus\unpacked\` | zip 原样解包（50 条目） |
| `D:\mod\recon-hudplus\lua\lua_F476DF93691895FA.payloads\script.lua` | boot 载荷 228,886 B / 5,066 行 |
| `D:\mod\recon-hudplus\allowed_types.txt` | 224 个类型名的原始 Lua 片段（可直接解析成列表） |
| `D:\mod\recon-hudplus\lua\opt9\…\script.lua` | 选项 chunk 样本（SQUAD_ALL，`GeneratedFragment` 数据表） |
