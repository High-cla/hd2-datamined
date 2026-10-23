# 引擎侧只读数据通路：总账（build 25988413，2026-10-20 夜）

> 这份文档回答一个问题：**内存路全死之后，还能从哪里读到游戏数据，读得到什么，读不到什么。**
> 每一条都标了三态，每条都有实测出处。细节见 `docs/boundaries/MEMORY-ACCESS-25988413.md`（内存）与
> `docs/engine/STINGRAY-API-25988413.md`（API 面）。

## 0. 一句话

**能读到"物体在哪、是什么"，读不到"它身上挂着什么数值"。**
前者靠 `world:units()` + `Unit.world_*`；后者要么在实体组件里（拿不到），要么在资源文件里（`srkit` 离线读）。

## 1. 三条内存路，全封死

| 路 | 结果 | 依据 |
|---|---|---|
| 进程内 `ffi`（memscan 的老路） | ✗ `ffi` 是 nil，payload 第 11 行就死 | `MEMORY-ACCESS` §1 |
| 进程外句柄（旧全量转储管线） | ✗ EAC 在句柄创建时剥掉 `PROCESS_VM_READ`；`ReadProcessMemory` err=5，`MiniDumpWriteDump` `E_ACCESSDENIED` | `MEMORY-ACCESS` §1；三次进程实例 + 提权均复现 |
| 抢"保护生效前"的句柄 | ✗ 进程创建后 **10.6 ms** 拿到的句柄已被剥权 | `MEMORY-ACCESS` §9 |

API 层没有替代品：`NtReadVirtualMemory` / `QueryWorkingSetEx` / `PssCaptureSnapshot` / `GetThreadContext` /
从 EAC 进程复制句柄 —— 全部 err=5。

## 2. 引擎侧唯一出数的通路：`world:units()`

```lua
local w = stingray.Application.main_world()      -- [World]，boot 时就在
local units = w:units()                          -- 任务世界里 6,610 个
-- 必须逐个 Unit.alive(unit) 过门禁，且不要遍历整张表
local p = stingray.Unit.world_position(unit)     -- Vector3(110.699356, -944.186157, -313.060883)
```

| 能读 | 实测值 |
|---|---|
| 身份 | `Unit.resource_name` → `IdString64 0x465F4895F3DC98D1`；`Unit.debug_name` |
| 位置 / 朝向 / 位姿 | `Vector3` / `Vector4` / `Matrix4x4`（16 float） |
| 计数 | `World:num_units()`、`num_levels()`、`time()`、`Application.time_since_launch()` |
| 存活 | `Unit.alive(unit)` —— **必须先问再碰** |

## 3. 三条纪律（都是拿崩溃换的）

1. **句柄会过期。** `units()` 返回快照；遍历到第 5 个失效句柄时 `movsd xmm0,[rdi+rbx+0x30]` 越界崩溃
   （`crash-2026-10-20-2144`）。拿到就用、只用极少数个、用前过 `Unit.alive`。
2. **错参数/未知字段 = 崩溃，不是 Lua 错误。** `pcall` 接不住。三次崩溃同形：
   查不到 → 非指针 → 不检查就解引用（`unit_by_id(错id)` / `units()[5]` / `entity.id`）。
3. **名字查询是安全的** —— `Unit.has_data` / `Unit.get_property` 对未知名字返回 `false` / `nil`（实测）。

## 4. 读不到的部分，以及为什么

| 想读 | 为什么读不到 |
|---|---|
| 实体 → `DataComponent` → 游戏数据 | `entities()` 给的实体是**已销毁**的（`UnitComponent.unit` → `[Unit (deleted)]`）；传错类型的句柄只得到空代理 |
| 命名属性 `Unit.get_property` | 安全可用，但 **unit 资源里没有 property 段** —— srkit 解码 `0x465F4895F3DC98D1` 证实。门是数据关的 |
| 组件上的任意字段 | 同上；且组件对象只在空实体上拿得到 |

## 5. 资源侧：最干净的一条，且已可用

```bash
python -m srkit extract --id 0x465F4895F3DC98D1 --decoded -o <out> "<game>/data"
```

单位/物体资源（srkit 里叫 `mesh`，**别名就是 `unit`**，type `0xE0A48D0BE9A7453F`）解码后带：
`header`(bones/geometry/state_machine 引用) · `lights` · `lod_group_list` · `transform_info` ·
**`customization`（body_type / slot / weight / piece_type）** · `materials` · `meshes`。
**护甲重量/部位分类这类数据，离线就能读，不需要引擎、不需要内存。**
代价：每次 `extract` 要扫一遍 23 GB（约 6 分钟），适合批量而非交互。

## 6. 探针现状（现场）

| patch | 内容 | 说明 |
|---|---|---|
| `patch_0` | `boot_probe` 1.3.x | boot 锚点 + 发现 + 加载 `mods/auto/N`，已证明可加载别的补丁里的 mod |
| `patch_1` | `live_census` 1.0.0 | 第一个读取类探针（boot / after-startup 两段 census） |
| `patch_2` | `vfcprobe` 9.0.0-kit | 旧 ffi 探针对照组，自己进入惰性（`kernel32 unavailable`） |
| `patch_3` | `world_api`（末版 1.17.0） | 引擎 API 探针；末版只做文件路线验证，**不写磁盘** |

产线：`build_test_mod.py` → `rehearse_mod.py`（**钉死 lupa.lua51**，游戏同款 5.1）→
`install_boot_probe.install_from`（写后 md5 回读）。

## 7. 还没试过的路（按性价比排序）

1. **`string.dump` 挖游戏 Lua 的字符串常量** —— 零引擎风险，可能挖出游戏真正用的
   `get_property` / `get_data` 名字。目前 `package.loaded` 里只有 2 个游戏模块（覆盖面小）。
2. **`World.get_data` / `Level.get_data` / `Application.get_data`** —— 引擎自带的数据存储，
   都是名字查询。风险未知（不在 Unit 上验证过），建议先用一个名字试探。
3. **`stingray.UnitSynchronizer`** —— 有 `unit_to_game_object_id` / `game_object_id_to_unit` /
   `set_world`，是游戏对象 id 与 Unit 之间的桥；可能拿到更"游戏内"的身份。
4. **`Unit.flow_variable` / `FlowComponent`** —— flow 变量里可能有任务/载具状态。
5. **反汇编三份崩溃转储里的映像页** —— 离线、免费；转储带 4.3 MB 映像页，含故障点代码。
6. **`stingray.Material` / `Unit.query_material`** —— 材质变量（队伍色、受击闪光等）。

### 7b. 补两条（写完上面那节才想到，价值都不低）

7. **★★ 把游戏自己的 Lua 资源抠出来读源码** —— `srkit list --type lua` 能列出 `lua` 类型资源，
   `srkit extract` 能导出。我们的 `package.loaded` 里只有 2 个游戏模块，但**包体里的 lua 资源远不止**。
   如果它们是明文 Lua（不是字节码），那就是**游戏自己的逻辑源码**：属性名、数据结构、伤害/护甲
   表怎么算，全在里面。**这是目前性价比最高的一条未试路线**，而且完全离线。
   ⚠ 未知：HD2 的 lua 资源是否明文、srkit 的 lua codec 能否解、逐个 6 分钟扫描的成本。
8. **`stingray.Gui` / `Window`（30 键）—— 读 UI 上显示的数字**。HUD 上本来就摆着弹药、血量、
   计时；如果能枚举控件并读文本，就是"通过界面读游戏状态"，绕过所有组件问题。
   ⚠ 未知：GUI 控件对象是否可枚举、文本是否可读。
9. **`stingray.Script` / `ScriptComponent`**（issue #13 的顶层清单里有 `Script`）——
   我们 1.0.0 只枚举了 16 个子命名空间，**没有枚举 `Script`**。脚本组件可能挂着游戏对象。

### 6b. 收口后的现场（2026-10-20 22:4x）

`patch_1` / `patch_2` / `patch_3` 已备份到 `D:\mod\backups\probes-2026-10-20\`（9 个文件，md5 已记）
并从游戏目录移除。**现在 `data\` 里只剩 `patch_0`（我们的 boot 加载器，23,120 B）**，
也就是一次部署的最小形态：一个补丁、一个锚点、加载器自己。

⚠ 随之而来的已知现象：boot 探针的发现日志会从 `3 found / 3 loaded / 3 absent` 变成
`0 found / 0 loaded / 6 absent`，而它括号里的文案仍写着"expected 2/2/4" —— 那是写死在
补丁里的旧文案，**不是故障**。要改需要重建 patch_0。

## 8. lua 资源源码路线：试完了，天花板在哪（2026-10-20 23:0x）

**做法**：`srkit list --type lua` → `srkit unpack --type lua --no-gpu --no-stream`。
**结果**：全部 lua 资源都在**一个包**（`9ba626afa44a3aa3`，正是我们补丁覆盖的那个）里，
**一共 6 个**，合计约 7.6 KB。

| 资源 | 内容 |
|---|---|
| `boot`（`0xF476DF93691895FA`） | 锚点脚本本体：`init`/`shutdown`/`update`/`render`、`stingray`、`Application.build()`、`require` |
| `core/animation/lua/runtime/animationflowcallbacks` | 动画回调：`get_animation_wanted_root_pose`、`get_animation_curve_value` |
| `core/wwise/lua/wwise_bank_reference` | bank 引用计数 |
| `core/wwise/lua/wwise_visualization` | 编辑器可视化：`add_soundscape_unit`、`unit_node`、`world_pose` |
| `core/wwise/lua/wwise_preview` | 编辑器预览：`play_event`/`stop_event`/`active_banks` |
| `ANIM_REQUIRES`（175 B） | 一行 `require("core/animation/lua/runtime/animationflowcallbacks")` |

**它们是 LuaJIT 字节码（`\x1bLuaQ`），不是明文源码** —— 但**字符串常量是明文**，直接可读（见上表）。

★ **这条路的结论是"天花板很低"，不是"不成"**：

1. **游戏只带 6 个 Lua 脚本，且全是引擎辅助/编辑器工具** —— **没有游戏逻辑 Lua**。
   所以"把游戏的数据表/属性名从源码里挖出来"这个期待**不成立**：游戏逻辑在 C++（`game.dll`）里。
2. 但字符串常量确实给出了**引擎侧的真实用法**，其中最有价值的一条是：
   `wwise_visualization` 里用了 **`get_data` / `has_data`**，而且取的名字是**带命名空间的**
   （`get_data("Wwise")` 之类，紧随其后的常量是 `Wwise`、`event_name`）。
   ⇒ 这解释了为什么我们的 107 词表全空：**data 节点是按命名空间取的**，不是 `"data"` 这种通用名。
   ⚠ 但只对带相应 data 的单位有意义（如 soundscape 单位），不是通用后门。
3. 成本：`unpack --type lua` 要遍历 31 个 bundle / 23 GB，**跑了 20 分钟没跑完**，最后手动中止 ——
   因为它会给**每个** bundle 都写一个 `package.json`，只有 1 个真的有 lua 资源。
   以后要再取这 6 个，用 `srkit extract --id <id>` 单独取更快（约 6 分钟/个）。

**判定：这条路线 ✓ 已试完，✗ 不承担"读出游戏数据"的期望。**

## 9. 更正（2026-10-20 23:2x）：`customization` 不是护甲重量数据的来源

§5 里我写过"资源的 `customization` 段直接带着 body_type / slot / weight / piece_type ——
正是老内存线追过的护甲重量/部位分类数据"。**这句话被实测打翻了，就地更正。**

拿一件**确定的护甲**验证：`Helmet CE-81 Juggernaut`，mesh id `0xB7F3329A848D2AF4`
（名字来自旧索引，`--type mesh` 指定后成功抠出）：

```
python -m srkit extract --id 0xB7F3329A848D2AF4 --type mesh --decoded -o <out> "<game>/data"

type_name: mesh   file_id: 13254993767511698164
customization: null           ← 这个段根本不存在
meshes: 5   transforms: 18   materials: 1
```

对照先前那个 `0x465F4895F3DC98D1`：它有 `customization` 段，但值是
`body_type = "\x01" · slot = "0" · weight = "" · piece_type = "X"` —— **空的默认记录**。

| 断言 | 判定 |
|---|---|
| 资源能被抠出来并解码 | ✓ 两次都成功（`--type` 必须指定，同一 id 在不同包里是**不同类型**的资源） |
| `customization` 段是护甲重量/部位数据的来源 | ✗ **否证** —— 真护甲 mesh 没有这个段；有的那个是空默认值 |

**资源侧路线本身仍然成立**（能读到 mesh/材质/骨骼/几何/变换），但"护甲重量分类"这个具体目标
**没有**在这条路上被证实。它可能在任何地方（另一个资源类型、或纯 C++ 表），目前**未知**。

★ 顺带一条可复用的操作要点：**同一个 file id 在不同包里可以是不同类型**（`0xFFC28EF4B7C57C38`
既是 `bones` 又是 `mesh`）。`srkit extract` 不加 `--type` 时取到的可能是错的那一个 ——
我第一次就拿到了 bones。

## 10. 类表全景（routes 1.0.0，2026-10-20 23:23:28）

⚠ **本节第一句已被 1.1.0 更正，见 §10b。** 当时枚举的是一张**硬编码的 17 项清单**，
"17 个命名空间全部在场"只证明清单里那 17 个在场，**不证明引擎只有 17 个**。
下表对这 17 个命名空间的判定仍然有效。

17 个命名空间全部在场，**371 个键**。对未试路线的判定：

| 路线 | 类表给了什么 | 判定 |
|---|---|---|
| **读 HUD 数字**（Gui/Window） | `Gui` 46 键（`text`/`update_text`/`rect`/`material`/`is_visible`…）、`Window` 35 键 | ✗ **没有"枚举已有 GUI 对象"的接口** —— 只能自建，读不到游戏自己那块 HUD |
| **脚本对象**（Script/ScriptComponent） | `Script` 23 键：`load` · `exists` · `serialize` · `deserialize` · `callstack` · `new_table/map/array`；`ScriptComponent` 12 键：`entities_with_script` · `instances_with_script` · `broadcast` · `dispatch` | ⚠ **两条新线索**：① `Script.load/exists` 是**按名字加载脚本**的接口（对 loader 也有意义）；② `entities_with_script` 是**按脚本枚举实体** —— 可能是拿到"活实体"的第二个入口 |
| **flow 变量**（FlowComponent） | 10 键：`instances` · `flow_variable` · `trigger_flow_event` | ⚠ `instances` 又要先有组件对象，和老墙一样 |
| **unit ↔ game object id 桥** | `UnitSynchronizer` 7 键：`game_object_id_to_unit` · `unit_to_game_object_id` · `set_world` · `spawn_unit` | ⚠ 可试，需要 game object id |
| **材质变量**（Material） | 19 键，**全是 setter**（`set_color`/`set_scalar`/`set_vector3`…）+ `id`/`id64` | ✗ **只写不读** —— 读材质这条路不存在 |
| 补充 | `TagComponent.get_entities` / `has_tag` · `DebugNameComponent.instances` · `Level.get_data` · `SaveSystem` · `Network` 58 键（消息类型含 `IDSTRING64`/`VECTOR3`/`RESOURCE_ID`） | ⚠ `get_entities` 是**第三个"枚举活实体"的入口** |

**三条最有价值的新线索**（都是"枚举活实体"，正是我们一直缺的）：
`ScriptComponent.entities_with_script` · `TagComponent.get_entities` · `FlowComponent.instances`。
前两个**可能直接给实体**，不经过 `entities()` 那张会过期的表。

**顺带坐实了补丁连续性**（对照实验）：`patch_0+patch_1` 连续时
`mods/auto/3 -> present, required OK`（探针装在 patch_1、模块名仍是 mods/auto/3）；
断号时是 `0 found`。⚙ **规则确认：`.patch_N` 必须连号。**

### 10b. 更正：不是 17 个类，是 **124 个类 / 2,357 键**（routes 1.1.0，2026-10-20 23:35:42）

`recon/routes110/run1.log`（同一份日志里两次启动，除时间戳外**逐字节一致**）：

| 来源 | 数量 |
|---|---|
| `stingray` 顶层类表 | **124 个**（`Color` / `Rotation2D` 是纯 Lua 类，`type` 为 function）|
| 类表键总数 | **2,357** |
| 其中函数 | **1,877 —— 全是 C 函数（F5 = 0 个 Lua 包装）** |
| `debug.getregistry()` 的 userdata metatable | **127 个**（124 类 + `FILE*` / `LOADLIB:` 两个我们自己测 loadlib 留下的残留）|
| `_G` / `package.loaded` | 52 / 13（不变）|
| 收集到的可打印名字 | **1,330**（原 371）|

**注册表这条路成立**：`registry[类名] = metatable`，127 个类名一次全出。
§11 的"绑定名是运行期构造的"因此有了着落 —— **它就在 Lua 注册表里**，只是从没 `getregistry()` 过。

**新门（都不在旧 17 项清单里，按价值排）**

| 类 | 关键键 | 为什么值得注意 |
|---|---|---|
| `GameSession`（33） | `game_object_field` · `game_object_field_batched` · `objects_owned_by` · `unit_synchronizer` · `peers` · `create_game_object` | ★ **网络复制字段** —— HD2 是联机权威服，运行期玩法状态很可能在这 |
| `Level`（32） | `units` · `entities` · `unit_by_index` · `prefabs` · `spline` · `object_set_names` · `get_data`/`has_data` | **`world:entities()` 之外的第二套枚举**，实现不同，可能不过期 |
| `Application`（**70**） | `get_data`/`has_data`/`set_data` · `flow_callback_context_unit/_entity/_world/_level` · `worlds` · `settings` · `export_mesh_geometry` | 全局数据仓 + 四个**无参上下文 getter** |
| `LevelResource`（9） | `unit_data` · `unit_indices` · `unit_position` · `unit_rotation` · `get_unit_data` | 关卡资源侧的单位表 |
| `UnitResource`（4） | `get_data` · `has_data` | 单位**资源**上的命名数据 |
| `DynamicData`（4） | `get` | 一种"按名取值"的数据对象 |
| `Network`（58） | `game_session` · `connections` · `has_connection` · `MESSAGES` | 拿 session 实例的入口 |
| `UnitSynchronizer`（7） | `unit_to_game_object_id` · `game_object_id_to_unit` · `set_world` | Unit ↔ 网络对象 id 的桥 |
| `Prefab`（8） | `units` · `unit_by_index` · `unit_index` | 预制体侧单位枚举 |
| `Broadphase`（9） | `all` · `query` · `query_item_data_pairs` | 物理宽相全量枚举 |
| `AI`（3） | `find_intersecting_units` | 空间查询拿活单位 |

### 10c. `string.dump` 挖常量（§7 第 1 条）：✓ 试完，✗ 否证

```
E0 gathered functions by source: loaded=142 stingray=458 _G=0
E1 candidates=600 dumped=6 refused(C function)=594 unparsable=0
E3 distinct printable string constants: 18
```

全图可达的 Lua 函数只有 **6 个**（就是 §8 那 6 个 lua 资源里的），其余全是 C 函数
（`string.dump` 直接拒绝）。挖出的 18 个常量（`angle` `delta_position` `local_rotation` …）
**全是我们已经知道的名字** ⇒ **这条路给不出新名字**，与 §8 的天花板判断一致，现在有数据了。

## 11. ✗ 否证：崩溃转储里没有可挖的名字表（2026-10-20 23:3x）

三份崩溃转储（`crash-2026-10-20-2107 / 2144 / 2149`）里落在映像区间内的内存页，逐份统计：

```
ranges in images: 4,811 KiB (每份都一样)
  game.dll                        2,429 KiB
  helldivers2.exe                 1,563 KiB
  runtime.dll                       432 KiB
  wwise_pluginw64_release.dll       359 KiB
  level_generation_plugin   25 KiB
```

把 `helldivers2.exe` 与 `game.dll` 的这几 MB 抠出来扫可打印字符串（>=6），并与**盘上同名文件**的
字符串做差：

| 来源 | 字符串 | **盘上没有的** |
|---|---|---|
| `helldivers2.exe` 映像页（1,563 KiB） | 9–10 | 7–9，**全是 `&p%\`$0#P` 这类噪声** |
| `game.dll` 映像页（2,429 KiB） | **1** | 1（`#p"\`!P 0`） |

⇒ **抓到的都是高熵代码/数据区，没有名字表。** 绑定名既不在盘上的 `.rdata`（前面搜过
`main_world`/`can_get` 等，一个都没有），也不在转储的映像页里 —— 它是运行期构造的。

**判定：✗ 转储挖绑定表这条路不成立**（这不是"没试"，是试过并否证）。
转储唯一还站得住的用途仍然是**故障归因**：三份都带故障页，能反汇编出出事的那几条指令。

---

## 12. ✗ 玩法数值：全表枚举后的结论（2026-10-20 23:35）

1.1.0 把 **124 个类 / 2,357 个键**全枚举了。**没有一个键是"读玩法数值"的接口。**

所有像"数据"的入口只有四种形状：

| 形状 | 例子 | 实测结论 |
|---|---|---|
| 命名属性 | `Unit.get_property/get_data` · `DataComponent.get_property` · `UnitResource.get_data` · `Application.get_data` | 名字查询**安全**（Unit 上实测），但 HD2 **不往这些桶里放玩法数值** —— 107 个常见名字 0 命中（1.15.0）|
| 组件实例 | `DataComponent.instances` · `*Component.instances` | 前提是**先有一个活实体**，那正是过不去的墙 |
| 网络字段 | `GameSession.game_object_field` | ⚠ **唯一没试过、原理上能承载运行期状态的一条** |
| 资源侧 | `LevelResource.get_unit_data` · `srkit` 离线解包 | 关卡/单位资源的**作者期**数据，不是运行期数值 |

⇒ **✗「引擎 API 能读玩法数值」这个假设，现在是被穷举否证的，不再只是"没找到"。**
剩下唯一值得打的是 `GameSession.game_object_field`（网络复制字段）。

---

## 13. routes 1.2.0（本版待跑）：按风险升序打 §10b 的新门

一次运行，14 个调用点；**每个调用点先 flush 再走下一个**，崩在哪一步是确定的。
所有"类方法"调用前都先 `type(rawget(class, name)) == "function"`，绝不踩非函数键。
所有返回值只 `type()`；是表就只数个数，**不索引**。

| 步 | 调用 | 风险 |
|---|---|---|
| 1 | `world:num_units()`（基线，已证） | 0 |
| 2 | `world:level()` | 低 |
| 3 | `Level.units(level)` / `Level.entities(level)` | 中 |
| 4 | `Application.flow_callback_context_unit/_entity/_world/_level()` ×4 | 低（无参）|
| 5 | `world:units()` → 前 8 个过 `Unit.alive` | 已证 |
| 6 | `Network.is_used()` / `Network.game_session()` | 低 |
| 7 | `GameSession.in_session/peers/unit_synchronizer(session)` | 中 |
| 8 | `UnitSynchronizer.unit_to_game_object_id(sync, unit)` | 中 |
| 9 | `Application.has_data/get_data("dsh_absent_42")` | 中（名字查询族收尾确认）|

---

## 14. ✗ 实测崩溃：`Network.is_used()` 在 **boot 期**致死（routes 1.2.0，2026-10-20 23:42–23:43）

三次启动（`23:42:22` / `23:43:09` / `23:43:34`）**全部崩在同一个位置**。日志最后一行：

```
===== routes 1.2.0 | 2026-10-20 23:43:34 =====
required as: mods/auto/3
PURPOSE: hit the new doors from ENGINE-API 10b, risk-ascending
STEP B01 Application.main_world()
   ok, value = userdata
                                        <- 到此为止
```

**定位**：B01 与 B02 之间只有三件事 —— `add()`（内存缓冲，不可能致命）、两个 `rawget`、
以及 `Network.is_used()`。Lua 错误会被 `pcall` 接住并走 SKIP/RAISED 分支，日志会留下痕迹；
所以这是**原生访问违例**，崩点在 `Network.is_used()` 内部。

**同时暴露了一个流程错误**：`add()` 是 20 行缓冲，崩掉时正好把「崩在哪一步」这句话本身丢了。
这与本项目「每行立刻 flush」的纪律相悖。⚠ 修正：`invoke()` 现在**先 add、再 flush、再 call**。

**为什么 boot 期不能调它**：三次启动里 `Application.main_world()` 都成功（BOOT 行三次都有），
而 `Network.*` 在 boot 期崩 —— 两种解释都还成立：

| 解释 | 判据 |
|---|---|
| ⚠ 时机：boot 期网络子系统还没起来，内部指针为空 → 解引用 | 在任务里调不崩，就是它 |
| ⚠ 需实例：`Network.is_used` 是实例方法，缺 `self` 时走了**未检查**的 userdata 提取（与 `entity.id` 同一个模式） | 在任务里照样崩，就是它 |

routes 1.3.0 把这条调用**挪到 stage C 的最后一个**：不崩 ⇒ 时机问题；照样崩 ⇒ 需实例。
两种结果都值钱，且不占用前面任何一步的风险预算。

**新纪律（第 0 条）**：**STEP 行先落盘再调用**。崩了也要留得下崩点。

### 14b. ⚠ 更正：飞船世界也是"有世界的" —— 1.3.0 那轮根本没进任务

用户指出「上次测试还没进任务就跑完了」。核对触发条件 `num_units > 100`：

| 世界 | num_units（实测） |
|---|---|
| **飞船（Super Destroyer）** | **2,231** |
| 任务世界 | 6,561 – 6,597 |

**飞船自己就有 2,231 个单位**，所以 `> 100` 在飞船里立刻满足，A/B 两段全在飞船上跑完。
因此 1.3.0 的这两条结论**只对飞船成立，任务里未知**：

- `GameSession.unit_synchronizer = nil` ⚠ 飞船答案
- `flow_callback_context_unit/_entity/_world/_level = nil` ⚠ 飞船答案（但这四个**无参调用本身不崩**）

1.3.0 里**仍然成立**的结论（与在哪个世界无关）：

- `World.has_data(world,'absent')` → `false` 不崩；`Application.has_data('absent')` → `false` 不崩
  ⇒ **名字查询族在 World/Application 上安全**（旧推断"未知键在 World 上崩"被否证）
- `World.level` → 可 catch 的弃用错误，引擎自己点名 **`World.levels`**
- `Network.is_used()` → **飞船里也崩** ⇒ 需真实例 self，不是时机问题，路线关闭

**触发条件已改成「离开飞船」**（routes 1.4.1）：记基线，等 `num_units` 相对基线变化 > 500
（2,231 → 6,597 差 4,366，不会误判）；基线本身 > 4,000（直接进任务）也立刻跑；9,000 帧兜底。

---

## 15. routes 1.4.1 实测（2026-10-20 23:50:45，崩在 B06；A/B 前半落盘）

⚠ **这一轮也还是在飞船上**：`baseline at frame 1: num_units=1` —— 第 1 帧世界还没加载，
基线抓到 **1**，于是「船加载完成」被当成「离开飞船」。触发条件第三次修正见 §16。

### 15a. ✓ Level 门成立（第二套枚举，实打实能用）

```
A04 World.levels(world)          → table(n=1, userdata)     level #1 是真句柄
A05 Level.units(level1)          → table(n=597)
A06 Level.entities(level1)       → table(n=2)
A07 Level.has_data(level1,'...') → false（不崩）
A08 Level.num_prefabs(level1)    → 0
A09 Level.pose(level1)           → userdata
```

**这是 `world:entities()` 之外的第二套实体/单位枚举，实现不同、能用。**

### 15b. ★★ 引擎第二次自己点名新 API

```
A08 Level.object_set_names(level1)
    RAISED (contained): Level.object_set_names has been deprecated.
                        Use LevelResource.object_set_names instead.
```

和 `World.level → World.levels` 是**同一手法**：绑定层对部分接口抛**可 catch 的弃用错误**
并在消息里点名替代品。⇒ **故意的弃用调用是免费的情报来源** —— 主动去调可疑接口，
错误消息会告诉我们正确的名字。这比猜名字便宜得多。

### 15c. ✗ 网络复制字段：需要真实字段名，而字段名无法枚举 —— 这条路关闭

```
B04 GameSession.objects_owned_by(session, peer[1]) → table(n=297)   owned[1] = number:0
B05 GameSession.game_object_exists(session, 0)     → true
B06 GameSession.game_object_field(session, 0, 'dsh_absent_42')      ← 崩
```

`game_object_exists(0)` 给 `true` ⇒ id `0` 是**有效**对象；崩掉的是**未知字段名**进了原生
hash 查找（与 `unit_by_id(1)` 同一个模式）。`GameSession` 的 33 个键里**没有任何字段名枚举接口**
⇒ 这个形状只能靠"知道真实字段名"才能用，而我们没有来源。

**判定：✗ 关闭。** §12 表里"网络字段"那一行从"⚠ 唯一没试过"改为"✗ 试过，需字段名，无法获得"。

---

## 16. routes 1.5.0（本版待跑）：Level 的**活实体** → 组件 → 实例

这是"读玩法数值"唯一还没被证死的链条。理由：1.5.0 时代"实体永远是死的、组件永远是空代理"
那批实体来自 `world:entities()`；而 1.4.1 证明 **`Level.entities` 是另一套实现**。如果其中
某个实体 `Unit.alive` 为真，它身上的组件就不是空代理，`DataComponent.instances` 就有机会
给出真实数据实例。

调用形状按 §上一版实测校正：**`EntityManager.*(world, entity)` —— World 当 self**
（写成 `(entity)` 等于把实体当 World 传，那正是会打死引擎的形状）。

| 步 | 调用 |
|---|---|
| A | `World.levels` → `Level.units/entities/has_data/num_prefabs/pose` |
| B | 前 2 个实体：`EntityManager.alive(world, e)` → 为真才 `unit_component` → `UnitComponent.unit` → `Unit.alive` → 为真才 `data_component`/`script_component`/`tag_component` → `*.instances` |
| C | `Application.worlds` → 每个世界 `num_units`/`num_levels` |

**触发条件第三次修正**：基线必须**稳定**（连续 90 帧变化 ≤ 2）且 **> 500**，
换世界要 `|delta| > 2000`（船 2,167 → 任务 6,597，差 4,430）。

---

## 17. routes 1.5.0 实测（2026-10-20 23:55:54，没崩，但**跑在任务加载期间**）

用户观察：「这次在加载任务的时候就跑完了」。日志证实了，并且暴露两个新事实：

```
stable baseline at frame 4663: num_units=3545
stage A trigger at frame 6500: num_units=23        <- 过渡期凹坑
A02 num_units=23   A03 num_levels=0   A04 World.levels=table(empty)
C01 Application.worlds() → table(n=8)
C02 worlds[1] → num_units=509, num_levels=491      <- 真世界在这里
C04 worlds[2] → num_units=1,   num_levels=0
C06 worlds[3] → num_units=1,   num_levels=0
```

### 17a. ⚠ 世界切换有一个"凹坑"，`|delta| > N` 这个判据在凹坑里也成立

`num_units` 的轨迹是 `3545 → 23 → …(加载)… → 6597`。旧世界拆掉、新世界还没装满时，
count 会掉到个位数 —— 而「变化超过 2000」对**下降**同样成立，于是触发点落在最坏的位置。
⇒ 判据不能只看"变了多少"，要看"**变成了什么**"（见 §18）。

### 17b. ★★ `main_world()` 不是真世界，`Application.worlds()[1]` 才是

同一时刻：`main_world()` = 23 units / **0 levels**，而 `worlds[1]` = 509 units / **491 levels**。
一个加载中的任务世界，它的 level 列表在 `worlds[1]` 上已经存在了。

⇒ **不要只信 `main_world()`**：扫描 `Application.worlds()`（8 个），挑 `num_levels` 最多的那个。
`num_units`/`num_levels` 在任意 world 句柄上都安全（1.5.0 在 3 个世界上实测，1.6.0 扫 8 个）。

---

## 18. routes 1.6.0（本版待跑）：等加载完 + 挑最富的世界

用户建议「变化后延迟 30 秒到一分钟」，按 45 秒实现：

| 阶段 | 判据 |
|---|---|
| 等 | 每 30 帧扫一次 8 个世界，出现 `num_levels > 100 且 num_units > 3000` 的世界 ⇒ 进入延迟 |
| 延迟 | **2700 帧（约 45 秒）**，期间每 300 帧打一行扫描结果（卡在哪可见）|
| 跑 | 重新扫描挑最富世界 → `World.levels` → 扫前 4 个 level，挑**实体最多**的交给 stage B |
| 兜底 | 24,000 帧（约 6.7 分钟）没等到就照跑 |

`EntityManager.*(world, entity)` 的调用形状不变（World 当 self），`alive` 门禁全部保留。

---

## 19. routes 1.6.0 实测（2026-10-21 00:00:18–00:02:42）：✓ **第一次在真正加载完的任务世界里跑完三段**

触发与延迟**完全按设计工作**：

```
waiting [frame 6600]: #1 u=3 l=0 ...              <- 过渡期凹坑（3 个单位）
MISSION-LOOKING WORLD at frame 6780: #1 u=6522 l=491
  -> waiting 2700 frames (~45 s)
delay [frame 9300, 180 to go]: #1 u=6580 l=491    <- 加载稳定
stage A trigger at frame 9480
```

| 步 | 结果 |
|---|---|
| `World.num_levels` | **491** |
| `World.num_units` | **6,580** |
| `World.levels` | **491 个** level 句柄（`table(n=491)`）|
| `Level.units(levels[1..4])` | **395 / 90 / 26 / 47** ✓ **每个 level 自己的单位表，能用** |
| `Level.entities(levels[1..4])` | **table(empty) ×4** ✗ 前 4 个 level 没有实体 |
| `Level.num_prefabs` / `pose` / `has_data` | 22 / userdata / false |

⇒ 世界侧结论：**`Level.units` 是第三个可用的单位枚举**（另有 `world:units()` 与
`LevelResource`）；但 `Level.entities` 在前 4 个 level 里是空的，所以"活实体 → 组件"那条链
在 1.6.0 里没有样本可喂。

⚠ 顺手修了一个**显示 bug**：`levels[1]: units=true` —— 曾把 `invoke()` 的第二个返回值
（成功标志）当 units 数打了出来。1.7.0 改用 `count_of()`。

---

## 20. routes 1.7.0（本版待跑）：实体链的最后两条路径 + flow 变量名字安全性

| 段 | 内容 | 为什么 |
|---|---|---|
| A | 扫**前 12 个** level；另外先挑一个活单位备用 | 491 个 level 里实体可能集中在后面 |
| B 路 1 | best level 有实体 ⇒ 直接跑组件链 | 原计划 |
| B 路 2 | **level 全空 ⇒ 退回 `world:entities()`，对前 8 个逐个问 `EntityManager.alive(world, e)`**，第一个为真的往下走 | ★ 那批"实体永远是死的"测量**从没做过 `alive` 过滤**，这个组合没试过 |
| C | `Unit.flow_variable(unit,'absent')` / `Level.flow_variable(level,'absent')` | ★ flow 变量是**有名字**的引擎状态，而名字可以**离线**从关卡资源用 srkit 挖。先确认未知名字不崩，才有下一次 |

**这是"活实体 → 组件 → 实例"最后一块没试过的路径。** 如果 B 两条路都空，这条链就彻底关闭，
§12 的结论从"穷举后的判定"升级为"定论"，之后应当把所有力气放回**资源侧**（patch_N 覆盖 + srkit）。

---

## 21. routes 1.7.0 实测（2026-10-21 00:07:17–00:07:30）：实体链的两条路都空

触发/延迟第二次正常：`MISSION-LOOKING at frame 7530 (#1 u=6521 l=491)` → 45 s → `6580 / 491`。

| 探测 | 结果 |
|---|---|
| `Level.entities(levels[1..12])` | **table(empty) ×12 —— 12 个 level 一个实体都没有** |
| `Level.units(levels[1..12])` | 395 / 90 / 26 / 47 / 55 / 60 / 50 / 53 / 75 / 8 / 16 / 16（合计 891）|
| `world:entities()` | **table(n=205)** |
| `EntityManager.alive(world, entities[1..8])` | **全 false** |
| `Unit.flow_variable(unit, 'absent')` | **nil，不崩** ✓ |
| `Level.flow_variable(level, 'absent')` | **nil，不崩** ✓ |

### 21a. ★★ 结构数字：**6,580 个单位 对 205 个实体**

这不是"我们没摸到"，是**HD2 基本不用实体/组件系统** —— level 里只有 unit（891 个分布在 12 个
level 里），整个世界 205 个 entity。这解释了为什么 `DataComponent` 一直给空代理：
**它本来就没内容。** 组件那条链不是技术问题，是架构上就没有货。

### 21b. ✓ flow 变量族是安全的名字查询，但名字撞同一堵墙

`Unit.flow_variable` / `Level.flow_variable` 在未知名字上都返回 nil 不崩 ⇒ 词表攻击在原理上可行。
**但名字是 64 位哈希**：`srkit codecs` 里 `flow`(0x92D3EE038EEB610D) 与 `level`(0x2A690FD348FE9AC5)
都是 `raw fallback`（无解码器），资源里存的是哈希而不是明文名。
⇒ 和 `get_data` / `get_property` **撞的是同一堵墙**：能安全地问，但没有名字可问。

---

## 22. routes 1.8.0（本版待跑）：实体表的**两端**都探

1.7.0 只看了 `world:entities()` 的**前 8 个**，全死。假设：如果这是追加式列表，上个世界的尸体
留在开头、**当前世界的活实体在末尾**。所以这一版探 `1-8, 100, 150, 200-205` 两段，
每个都先过 `EntityManager.alive`，第一个为真的立刻走组件链。

**这是实体链的最后一次尝试。** 如果两端都没有活实体，那么：
- 实体/组件路线**彻底关闭**（且已由 21a 的结构数字说明是架构原因）；
- `§12`「引擎 API 读不到玩法数值」成为定论；
- 引擎侧资产盘点完毕：`world:units()` / `Level.units` / `Unit` 的 119 个键（身份、位姿、资源名、
  mesh、bones、材质**引用**）是全部可读内容；
- 之后所有力气回到**资源侧**（`patch_N` 覆盖 + srkit），那是已经被证明能改东西的路。

---

## 23. ⚠ 更正：routes 1.8.0 **没有真正探到"末尾"**（2026-10-21 00:11:46）

```
B50 World.entities(world) → table(n=196)
candidate #1..#8, #100, #150 → EntityManager.alive 全 false
no live entity at ANY probed index (1-8, 100, 150, 200-205)
```

候选索引是**写死**的 `{1..8, 100, 150, 200..205}`，而这张表只有 **196** 项 ——
`200..205` 全部被 `i <= total` 跳过。**所以"两端都探"里末尾一个都没探到**，
1.8.0 不能作为"实体链关闭"的依据。这是我自己的索引 bug，不是引擎的结论。

`routes 1.8.1` 修正：末尾改成**按 `total` 现算**——头 `1..8` + 中间 `total/2` + 末尾 `total-7..total`
（196 项时共探 17 个索引），命中活实体后照旧走组件链。

**教训**：把"探末尾"写成固定下标，等于把一次实验的有效性绑定到一个会变的量上。
凡是范围随数据变化的探测，边界必须**现算**。

---

## 24. ✗ 定论：实体/组件链关闭（routes 1.8.1，2026-10-21 00:16，含真正的末尾）

1.8.1 修正了 1.8.0 的索引 bug，末尾按 `total` 现算：

```
B50 World.entities(world) → table(n=203)
probing 17 index(es): 1,2,3,4,5,6,7,8,101,196,197,198,199,200,201,202,203
B001..B008 / B101 / B196..B203 → EntityManager.alive 全部 false
no live entity among the 17 probed index(es) (head 1-8, middle, tail)
```

**头、中、尾 17 个候选，一个活实体都没有。** 加上结构比例（**6,568–6,580 个单位 对 196–203 个实体**），
这条链的关闭现在是**架构层面的**，不是技巧问题：

| 判定 | 依据 |
|---|---|
| ✗ 活实体不可得 | 17 个候选全死（含末尾）|
| ✗ 组件无内容 | `DataComponent.instances` 从未给过东西 |
| ✗ HD2 不用组件系统 | 6,580 unit vs 203 entity |
| ✗ 玩法数值 | §12 + 本节，穷举后的定论 |

### 24a. 引擎侧资产的最终清单（这就是全部）

| 能力 | 手段 | 状态 |
|---|---|---|
| 世界里所有单位的句柄 | `world:units()`（6,568 个）| ✓ |
| 每个 level 的单位表 | `Level.units(level)`（491 个 level，891 个单位分布在扫过的 12 个里）| ✓ |
| 单位身份 | `Unit.resource_name` / `debug_name` / `name_hash` / `id` | ✓ |
| 单位位姿 | `Unit.world_position/rotation/pose`、`local_*`、`delta_*` | ✓ |
| 单位结构 | `mesh`、`bones`、`num_meshes`、`box`、`camera`、`light` | ✓ |
| 单位材质**引用** | `material_id`、`query_material`（`Material` 19 个键**全是 setter**）| ⚠ 只写不读 |
| 命名数据 | `Unit/World/Application/Level.get_data`、`flow_variable`、`get_property` | ✓ 安全，**但 HD2 不往里放东西**（107 名字 0 命中）|
| 网络复制字段 | `GameSession.game_object_field` | ✗ 需真实字段名，未知名字**崩**，无枚举接口 |
| 实体/组件 | `world:entities()` + `EntityManager.*` | ✗ 全死（本节）|
| HUD 数字 | `Gui`/`Window` | ✗ 无枚举已有 GUI 对象的接口 |

⇒ **引擎侧能读的只有"有什么东西、在哪、是什么资源"**；玩法数值一个都读不到。

### 24b. 这一轮真正攒下来的**可复用**东西（不是结论，是工具）

1. **名字挖掘法**：`debug.getregistry()` 一次拿到 127 个类名；`stingray` 顶层 124 个类 / 2,357 键。
2. **弃用消息当文档**：故意调可疑接口 → 引擎抛可 catch 的弃用错误并点名替代品
   （`World.level → World.levels`、`Level.object_set_names → LevelResource.object_set_names`）。
3. **分段 + 每步先落盘**的探针骨架：一崩就知道崩点，前面几段的结果不丢。
4. **世界选择**：`main_world()` 不是真世界，`Application.worlds()` 里 `num_levels` 最大的才是。
5. **加载判定**：`num_levels > 100 且 num_units > 3000`，然后**再等 45 秒**。
6. **一条硬纪律**：范围随数据变化的探测，边界必须**现算**（1.8.0 的固定索引教训）。

---

## 25. 网络字段线（routes 2.3.0 → 2.6.1，2026-10-21 00:51–01:07）：一半打通，另一半封死

### 25a. ✓ `Network.message_info` 打通了 —— 今晚第一条真正可用的文档化接口

数组名来自**离线**：`network_config` 资源（`0x9804FF263146EA3D`，801,456 B）里有一张
**595 条 RPC 名的明文表**（`rpc_set_zone_armor` / `rpc_reset_shield_state` /
`rpc_damage_zones_state_changed` / `rpc_fire_mounted_weapon` / `rpc_shared_stratagem_state` /
`rpc_restock` / `rpc_on_destroyed` / `rpc_set_visible` …）。8/8 命中：

```
message_info("rpc_set_zone_armor").arguments.1.bits = 32
message_info("rpc_set_zone_armor").arguments.1.id   = 2423589813   (0x90750BB5)
message_info("rpc_set_zone_armor").arguments.1.type = "entity"
message_info("rpc_set_zone_armor").arguments.2.bits = 96
message_info("rpc_set_zone_armor").arguments.2.id   = 2553399945
message_info("rpc_set_zone_armor").arguments.2.type = "vector3"
message_info(...).reliable = true
```

**⇒ 引擎用 32 位哈希标识字段/参数，用字符串标识类型**（`entity` / `vector3` / …）。

### 25b. 离线哈希规则（可复用）

```
IdString32 = murmur64(name) 的**高 32 位**
验证：srkit murmur64('shuttle') = 0xb4d3d2c4e46727cf，配置里就有 0xB4D3D2C4
```
- 字段表结构：`01 ?? 00 00 ff ff 7f 7f` + 4 字节 id32，24 字节步长；全文件 **183 条字段记录**。
- 对这 183 个 id 做字典攻击（182,783 个候选，含 12 万个 base+后缀 组合）命中 3 个真名字：
  `animation_event` / `door_state` / `entity`（另有 `rotation` / `state` 从 4 字节窗口命中）。

### 25c. ✗ `game_object_field` 封死 —— 需要"对象的类型"，而类型名没有明文

| 尝试 | 结果 |
|---|---|
| `game_object_field(session, 0, "dsh_absent_42")` | 崩（1.4.1）|
| `game_object_field(session, 0, "rotation")` | 崩（2.3.0）|
| `game_object_field(session, 392, "door_state")` | 崩（2.5.1）—— **非零 id + 字段表验证过的名字** |

字段标识是 32 位哈希（25a），而**字段属于类型**。要选一个合法 (对象, 字段) 对，必须知道
该对象的类型；但类型名在配置里**只存哈希、没有明文表**（明文表只有 595 个 rpc 名）。
`objects_owned_by` 只给 id 不给类型，`game_object_is_type` 又要先知道类型名。

⇒ **✗ 网络字段读这条线关闭**（不是"没试"，是试到第 3 次仍崩且原因明确）。
`message_info` 这一半留在台账里：它是**安全的**，将来若要观察某个 RPC 的线格式，随时可用。

### 25d. 经验（两次白跑换来的）

1. **离线挖名字前先确认"名字在哪张表里"**：我先用 6,000 个候选名轰 `object_info` 得 0 命中，
   根因是配置里的明文表是 **rpc 名**，而对象/字段名只存哈希。
2. **打印器要真递归**：2.6.0 的 dump 只打嵌套表的**键**不打键值，于是 `arguments` 里
   最关键的结构被漏掉，白跑一轮。2.6.1 换成递归 `dump_any` 才看到 `id/type/bits`。
3. **数值形式崩、字符串形式安全**是一个可用的分类器：
   `object_info(<数字>)` 崩 / `object_info(<未知字符串>)` 返回 nil ⇒ 数字走 id 查表、字符串走名字查表。
