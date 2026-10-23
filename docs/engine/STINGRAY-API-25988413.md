# Stingray API surface on build 25988413 (measured in game)

Captured by the boot-anchored probe (`boot-probe/`, v1.3.0) on 2026-10-20 18:07, while the game was
running its own boot. Every line below is a key the probe actually enumerated through `pairs()`;
nothing here is from documentation or from the old build.

Total: **446 entries** - 126 under `stingray`, 70 under `stingray.Application`, and 250 under
16 sub-namespaces the probe opened.

## ⚠ 索引修正（2026-10-21 20:2x，先读这段）

这份文档有三个会让人读漏的地方，是 10-21 那天重新枚举后发现的：

1. **只开了 19 个命名空间，不是全部。** 当次是**人工挑**了 16 个子表 + Application + stingray 顶层。
   `stingray` 下面实际有 **125 个**命名空间。完整机器枚举见
   [LUA-API-25988413.md](LUA-API-25988413.md)（125 个命名空间 / **2,483** 个成员，2026-10-21）。
   因为挑着开，**`Camera`(37) / `TransformComponent`(23) / `AI`(3) / `UnitSynchronizer` /
   `SceneGraphComponent` / `LODObject` / `Light` / `InfluenceMap` / `Speedtree` 全都没开** ——
   其中包括 `Camera.world_to_screen`（世界坐标转屏幕，世界锚定 HUD 的前提）。

2. **§612「✗ 否证：Entity / Unit 的方法名不可枚举」这个标题只说了负的那一半。**
   同一次运行其实**拿到了正结果**：`stingray.Unit` **119 键**、`stingray.World` **72 键**
   （见该节正文）。死的只是"从实例的 `__index` 闭包里挖方法表"这条路，**类表本身一直是可读的**。
   而 119 键的完整清单只存在于当次日志里，文档只摘了"对读数有用的"约 12 个 ——
   `teleport_local_position` / `disable_physics` / `enable_physics` / `set_unit_visibility`
   就是这样丢的。

3. **结尾的「★ 判死」判的是 `get_property` 命名属性，不是整条读世界线。**
   它证明的是 unit 资源里没有 property 段（✓ 有物证），因此"用名字查属性"这条路走不通。
   它**没有**否证 `Unit.world_position` / `Unit.world_rotation` / `World.units` / `Camera.*`
   这些**直接 getter** —— 那些当晚报过值（`Vector3(110.699356, -944.186157, -313.060883)`）。
   读这份文档时不要因为看到「判死」就以为读世界整条路是死的。


## Why this matters now

With `ffi` gone, this table IS the toolkit: there is no memory access, so anything a mod can do it
does through one of these. It is also the first thing to check when deciding whether a given idea is
even expressible on this build.

## What this answers

Four things came out of the same run, in order of usefulness:

1. **The engine exposes its own hash function, and it is the one we use.**
   `stingray.Application.make_hash('boot')` returned `f476df93691895fa` - byte for byte our
   `murmur64("boot")`, which is the id the `boot` override rides on. So a loader can derive and verify
   resource ids from names **at runtime, without `ffi`**.

2. **Package-level discovery is dead.** `stingray.ResourcePackage` has exactly six keys -
   `load`, `unload`, `has_loaded`, `flush`, `__index`, `_name`. It can load a package **by name** and say
   whether it is loaded; it cannot list anything. The `LOADER-SPEC` idea of "enumeration via the engine's
   own package view" is therefore **refuted by measurement**, not by preference.

3. **There is a component API that needs no memory access at all.** `EntityManager` (21 keys:
   `create`, `destroy`, `spawn`, `alive`, `data_component`, `unit_component`, `mesh_component`,
   `transform_component`, `script_component`, `tag_component`, ...) plus `DataComponent` (10 keys:
   `instances`, `instances_with_tag`, `instances_with_tag_in_entity`, `get_property`, `set_property`,
   `create`, `destroy`) is the documented way to reach game component data - the thing this project used
   to do by reading raw memory. Technically this is the replacement for the memory route; whether it may
   be *used* is a policy question, not an engineering one (see `BUILD-25988413.md` §3).

4. **No command console, but a plugin manager.** `Console` offers only `graph` / `perfhud` / `statistics`.
   `PluginManager` does have `loaded_plugins()` and `load_plugin` / `load_relative_plugin` /
   `unload_plugin` / `add_hot_reload_directory` - an enumeration primitive and a native-loading
   primitive. Not the same as discovering lua mods, but it is the one remaining "ask the engine what is
   loaded" surface, and worth one measurement in a future probe.

## stingray (top level) (126)

- `AI` - table
- `Achievement` - table
- `AnimationBlenderBoneMode` - table
- `AnimationBlenderComponent` - table
- `AnimationBlenderRootMode` - table
- `AnimationCurves` - table
- `AnimationStateMachineComponent` - table
- `Application` - table
- `BakedLighting` - table
- `Broadphase` - table
- `Camera` - table
- `Cloud` - table
- `CloudToken` - table
- `Color` - function
- `CommandWindow` - table
- `Console` - table
- `ConsoleHelp` - table
- `DataComponent` - table
- `DebugNameComponent` - table
- `DisplayAdapter` - table
- `DynamicData` - table
- `EntityManager` - table
- `Float32Array` - table
- `FlowComponent` - table
- `Friends` - table
- `GameSession` - table
- `Gui` - table
- `Http` - table
- `INT` - table
- `IdString32` - table
- `IdString32Box` - table
- `IdString64` - table
- `IdString64Box` - table
- `InfluenceMap` - table
- `Input` - table
- `InputEventType` - table
- `Keyboard` - table
- `LODObject` - table
- `LanClient` - table
- `LanLobby` - table
- `LanLobbyBrowser` - table
- `Leaderboard` - table
- `LeaderboardTransactionToken` - table
- `Level` - table
- `LevelResource` - table
- `Light` - table
- `LightUserData` - table
- `LineObject` - table
- `Localizer` - table
- `Material` - table
- `Math` - table
- `Matrix4x4` - table
- `Matrix4x4Box` - table
- `Mesh` - table
- `MeshComponent` - table
- `Mouse` - table
- `Network` - table
- `Pad1` - table
- `Pad2` - table
- `Pad3` - table
- `Pad4` - table
- `Pad5` - table
- `Pad6` - table
- `Pad7` - table
- `Pad8` - table
- `PluginManager` - table
- `Prefab` - table
- `Presence` - table
- `ProceduralMesh` - table
- `Profiler` - table
- `Quaternion` - table
- `QuaternionBox` - table
- `RPC` - table
- `RefTracker` - table
- `RenderBuffer` - table
- `RenderDataComponent` - table
- `Renderer` - table
- `ResourcePackage` - table
- `Rotation2D` - function
- `STRING` - table
- `SaveSystem` - table
- `ScatterSystem` - table
- `SceneGraphComponent` - table
- `Script` - table
- `ScriptComponent` - table
- `Sensor` - table
- `ShadingEnvironment` - table
- `ShadingEnvironmentBlendComponent` - table
- `SimulatedTouchPanel` - table
- `SimulatedTouchPanel1` - table
- `Speedtree` - table
- `Stats` - table
- `Steam` - table
- `SteamClient` - table
- `SteamLobby` - table
- `SteamLobbyBrowser` - table
- `SteamVoip` - table
- `SteamVoipClient` - table
- `SteamVoipRoom` - table
- `SwipeDirection` - table
- `Tablet` - table
- `TagComponent` - table
- `Terrain` - table
- `TerrainOffset` - table
- `TouchPanel` - table
- `TouchPanel1` - table
- `TransformComponent` - table
- `UINT` - table
- `Unit` - table
- `UnitComponent` - table
- `UnitResource` - table
- `UnitSynchronizer` - table
- `Utf8` - table
- `Vector2` - table
- `Vector2Box` - table
- `Vector3` - table
- `Vector3Box` - table
- `Vector4` - table
- `Vector4Box` - table
- `VectorField` - table
- `VideoPlayer` - table
- `Viewport` - table
- `WebSocket` - table
- `Window` - table
- `World` - table
- `WwiseBankReference` - table

## stingray.Application (70)

- `DISABLE_PARALLEL_DISPATCH` - number
- `DISABLE_RENDERING` - number
- `DISABLE_SOUND` - number
- `ENABLE_REPLAY` - number
- `WIN32` - string
- `__index` - table
- `_name` - string
- `apply_user_settings` - function
- `apply_win32_user_settings` - function
- `argv` - function
- `back_buffer_size` - function
- `build` - function
- `build_identifier` - function
- `can_get` - function
- `clear_resource_override` - function
- `clear_resource_override_flag` - function
- `create_render_target` - function
- `create_viewport` - function
- `destroy_viewport` - function
- `enum_display_modes` - function
- `export_mesh_geometry` - function
- `flow_callback_context_entity` - function
- `flow_callback_context_level` - function
- `flow_callback_context_unit` - function
- `flow_callback_context_world` - function
- `get_animation` - function
- `get_data` - function
- `has_data` - function
- `main_world` - function
- `make_hash` - function
- `new_world` - function
- `open_url_in_browser` - function
- `performance_hud_command` - function
- `platform` - function
- `process_id` - function
- `quit` - function
- `refresh_shader_templates` - function
- `release_world` - function
- `render_caps` - function
- `render_config` - function
- `render_setting` - function
- `render_world` - function
- `resolution` - function
- `restart_file_log` - function
- `save_render_target` - function
- `save_user_settings` - function
- `save_win32_user_settings` - function
- `scan_for_windows_ps4_controllers` - function
- `session_id` - function
- `set_background_render` - function
- `set_data` - function
- `set_max_frame_stacking` - function
- `set_render_setting` - function
- `set_resource_override` - function
- `set_resource_override_flag` - function
- `set_time_step_policy` - function
- `set_user_setting` - function
- `set_win32_user_setting` - function
- `settings` - function
- `source_platform` - function
- `string_to_id32` - function
- `string_to_id64` - function
- `sysinfo` - function
- `time_since_launch` - function
- `update_raw_buffer` - function
- `update_render_world` - function
- `user_setting` - function
- `user_settings_load_error` - function
- `win32_user_setting` - function
- `worlds` - function

## stingray.ResourcePackage (6)

- `__index` - table
- `_name` - string
- `flush` - function
- `has_loaded` - function
- `load` - function
- `unload` - function

## stingray.EntityManager (21)

- `__index` - table
- `_name` - string
- `alive` - function
- `animation_blender_component` - function
- `animation_state_machine_component` - function
- `create` - function
- `data_component` - function
- `debug_name` - function
- `debug_name_component` - function
- `destroy` - function
- `flow_component` - function
- `mesh_component` - function
- `render_data_component` - function
- `scene_graph_component` - function
- `script_component` - function
- `set_debug_name` - function
- `shading_environment_blend_component` - function
- `spawn` - function
- `tag_component` - function
- `transform_component` - function
- `unit_component` - function

## stingray.DataComponent (10)

- `__index` - table
- `_name` - string
- `add_instance_to_tags` - function
- `create` - function
- `destroy` - function
- `get_property` - function
- `instances` - function
- `instances_with_tag` - function
- `instances_with_tag_in_entity` - function
- `set_property` - function

## stingray.Console (5)

- `__index` - table
- `_name` - string
- `graph` - function
- `perfhud` - function
- `statistics` - function

## stingray.CommandWindow (7)

- `__index` - table
- `_name` - string
- `close` - function
- `open` - function
- `print` - function
- `read_line` - function
- `update` - function

## stingray.PluginManager (8)

- `__index` - table
- `_name` - string
- `add_hot_reload_directory` - function
- `load_plugin` - function
- `load_relative_plugin` - function
- `loaded_plugins` - function
- `remove_hot_reload_directory` - function
- `unload_plugin` - function

## stingray.Material (19)

- `__index` - table
- `_name` - string
- `id` - function
- `id64` - function
- `reinitialize_shader` - function
- `set_color` - function
- `set_matrix4x4` - function
- `set_resource` - function
- `set_scalar` - function
- `set_scalar_array` - function
- `set_shader_pass_flag` - function
- `set_texture` - function
- `set_uint_vector` - function
- `set_vector2` - function
- `set_vector2_array` - function
- `set_vector3` - function
- `set_vector3_array` - function
- `set_vector4` - function
- `set_vector4_array` - function

## stingray.Mesh (24)

- `__index` - table
- `_name` - string
- `bounding_volume` - function
- `bounding_volume_components` - function
- `get_geometry_stats` - function
- `has_material` - function
- `local_pose` - function
- `local_position` - function
- `local_rotation` - function
- `material` - function
- `material_slot_id` - function
- `name` - function
- `node` - function
- `num_materials` - function
- `refresh_instance_hash` - function
- `set_explicit_sort_value` - function
- `set_local_pose` - function
- `set_local_position` - function
- `set_local_rotation` - function
- `set_shader_pass_flag` - function
- `visibility` - function
- `world_pose` - function
- `world_position` - function
- `world_rotation` - function

## stingray.Renderer (20)

- `GPU_0` - number
- `GPU_1` - number
- `GPU_2` - number
- `GPU_3` - number
- `GPU_4` - number
- `GPU_5` - number
- `GPU_6` - number
- `GPU_7` - number
- `GPU_ALL` - number
- `__index` - table
- `_name` - string
- `begin_stream_captures` - function
- `create_resource` - function
- `destroy_resource` - function
- `end_stream_captures` - function
- `is_d3d12_supported` - function
- `resource` - function
- `run_resource_generator` - function
- `save_captured_frame` - function
- `update_texture_base64` - function

## stingray.Level (30)

- `__index` - table
- `_name` - string
- `entities` - function
- `flow_variable` - function
- `get_data` - function
- `has_data` - function
- `has_volume` - function
- `is_point_inside_volume` - function
- `nested_levels` - function
- `next_random_point_inside_volume` - function
- `num_nested_levels` - function
- `num_prefabs` - function
- `num_splines` - function
- `object_set_names` - function
- `pose` - function
- `prefabs` - function
- `random_point_inside_volume` - function
- `set_data` - function
- `set_flow_variable` - function
- `spawn_all_layers` - function
- `spawn_background` - function
- `speedtrees` - function
- `spline` - function
- `spline_by_index` - function
- `trigger_event` - function
- `trigger_level_loaded` - function
- `trigger_level_shutdown` - function
- `trigger_level_update` - function
- `unit_by_index` - function
- `unit_index` - function

## stingray.Prefab (8)

- `__index` - table
- `_name` - string
- `nested_prefabs` - function
- `num_nested_prefabs` - function
- `speedtrees` - function
- `unit_by_index` - function
- `unit_index` - function
- `units` - function

## stingray.Network (30)

- `ARRAY` - number
- `BOOL` - number
- `DIRECTION` - number
- `FLOAT` - number
- `IDSTRING32` - number
- `IDSTRING64` - number
- `INT` - number
- `MESSAGES` - number
- `QUATERNION` - number
- `RESOURCE_ID` - number
- `SILENT` - number
- `SPEW` - number
- `STEAM_LOBBY_FRIENDS_ONLY` - number
- `STEAM_LOBBY_INVISIBLE` - number
- `STEAM_LOBBY_PRIVATE` - number
- `STEAM_LOBBY_PUBLIC` - number
- `STRING` - number
- `UINT64` - number
- `VECTOR3` - number
- `WARNINGS` - number
- `__index` - table
- `_name` - string
- `config_hash` - function
- `connections` - function
- `create_game_session` - function
- `create_lan_lobby` - function
- `create_steam_lobby` - function
- `enable_qos` - function
- `fatal_error` - function
- `game_session` - function

## stingray.Float32Array (22)

- `__add` - function
- `__div` - function
- `__gc` - function
- `__index` - function
- `__len` - function
- `__mul` - function
- `__newindex` - function
- `__sub` - function
- `__unm` - function
- `_name` - string
- `add` - function
- `div` - function
- `get` - function
- `interleave` - function
- `mul` - function
- `push` - function
- `resize` - function
- `set` - function
- `size` - function
- `sqrt` - function
- `sub` - function
- `swap` - function

## stingray.Localizer (4)

- `__index` - table
- `_name` - string
- `lookup` - function
- `set_language` - function

## stingray.Profiler (6)

- `__index` - table
- `_name` - string
- `record_statistics` - function
- `render_stats` - function
- `start` - function
- `stop` - function

## stingray.Gui (30)

- `__index` - table
- `_name` - string
- `bitmap` - function
- `bitmap_3d` - function
- `bitmap_3d_uv` - function
- `bitmap_uv` - function
- `destroy_bitmap` - function
- `destroy_bitmap_3d` - function
- `destroy_rect` - function
- `destroy_rect_3d` - function
- `destroy_text` - function
- `destroy_text_3d` - function
- `destroy_triangle` - function
- `destroy_video` - function
- `destroy_video_3d` - function
- `has_all_glyphs` - function
- `has_video_player` - function
- `is_visible` - function
- `material` - function
- `move` - function
- `rect` - function
- `rect_3d` - function
- `render_resolution` - function
- `reset` - function
- `resolution` - function
- `resolution_unsafe` - function
- `set_visible` - function
- `text` - function
- `text_3d` - function
- `text_extents` - function


## 实测补记：World / Entity / Component 的真实形状（2026-10-20 20:56–21:08）

三版探针 `world_api` 连续实机测出来的，全部只读：

| 事实 | 判定 | 证据 |
|---|---|---|
| `main_world()` 的 metatable 与 `stingray.World` 是同一套 **72 个方法** | ✓ | 1.0.0：`entities`/`units`/`unit_by_id`/`num_units`/`level`/`levels`/`spawn_unit`/`time`/`delta_time`/`get_data`/`has_data`/`set_data`… |
| `world.entity_manager` 不存在；`EntityManager` **不**混在方法表里（`__index` 链在 level 1 就断） | ✓ | 1.1.0：`level 1: metatable is nil` |
| 零参 getter 能拿到真数据 | ✓ | `num_units()=1` · `num_levels()=0` · `time()` 由 2.10 涨到 9.89 |
| `Application.worlds()` 有 **7** 个 World | ✓ | 1.0.0 |
| **`EntityManager.*(world, …)` 接受 World 当 `self`** | ✓ | 1.2.0：`alive` 返回 boolean，`data_component` 返回 `[DataComponent]` userdata（带全部 10 个方法） |
| **B 路线成立**：组件可以从 Lua 摸到 | ✓ | 同上 |
| `world:entities()` 返回的是**表**，表项的**值**才是 `[Entity "" 1:0]` userdata，键只是数组下标 | ✓ | 1.2.0 |
| **`world:unit_by_id(错 id)` 会让引擎空指针崩溃** | ✗ 事故 | 1.2.0 把下标 1 传进去 ⇒ `0xC0000005` @ `helldivers2.exe+0x3C07D9`；转储里那页可读，反汇编是 `mov rax,[rax+8]` 且 `rax=0`（查不到 → 返回 null → 直接解引用） |

类表规模（实测）：`Unit` 119 · `World` 72 · `Level` 32 · `TransformComponent` 23 · `EntityManager` 21 ·
`DataComponent` 10 · `UnitComponent` 8。

**纪律**：这里的"错参数"不是 Lua 报错，是引擎崩溃。所以取到实体句柄后，必须先
`EntityManager.alive(world, entity) == true` 再往下调 —— 1.3.0 已按这个守卫改写，并删掉了
`unit_by_id`。

## ★ 里程碑：引擎侧第一次读到真数据（2026-10-20 21:14:22）

`world_api 1.4.0`。**内存路全死之后，这是替代路线第一次产出实际数值。**

```
world:units()             -> 1 个 entry，值 = [Unit '#ID[465f4895f3dc98d1]'] (userdata)
Unit.resource_name(unit)  -> IdString64 "#ID[465f4895f3dc98d1]" 0x465f4895f3dc98d1
Unit.debug_name(unit)     -> "#ID[465f4895f3dc98d1]"
Unit.world_position(unit) -> Vector3(1, 1, 1)
Unit.world_rotation(unit) -> Vector4(3.08e-08, -0.2149, 0.8227, -0.3039)
Unit.world_pose(unit)     -> Matrix4x4(...)   16 个 float 的完整矩阵
Unit.id(unit)             -> nil              （身份走 IdString64，不是数字）
```

boot 与 frame 1800 两次采样**逐字段相同**。

要点：
- `Unit` 的门是 `world:units()`，不是 `world:entity_manager`（没有这个字段），也不是 `unit_by_id`
  （用错 id 会空指针崩溃，见上一节）。
- 单位身份是 `IdString64`：`0x465F4895F3DC98D1`。⚠ 在**旧 build** 的资源索引
  `D:\mod\index\all_entries.json` 里，这个 id 对应的是 **mesh** 类型 —— 旧索引不能直接套到本 build，
  要认这个 unit 还得用本 build 的索引或 `Application.can_get` 反查。
- 由此可读的旧路线用例：**单位/载具的位姿、身份、数量**。仍然读不到的：任意实体上的
  DataComponent 属性（`get_property` 的形参形状未测）。

## ✗ 事故：`units()` 发出来的句柄表会过期（2026-10-20 21:44:37）

1.9.0 在任务世界里遍历 `world:units()` 的前 6 个，逐个读 `debug_name` / `world_position`：
前 4 个正常（`(1,1,1)` `(1,1,1)` `(100,100,100)` `(0,0,0)`），**读第 5 个时游戏崩溃**。

转储（`E:\hd2-dumps\kept\crash-2026-10-20-2144\`，9,827,100 B）里的故障指令：

```asm
0x7ff7dab15654: movsd xmm0, qword ptr [rdi + rbx + 0x30]   ; rdi = index<<6  <== RIP
```

按 `index<<6` 偏移读固定大小记录 —— **越界读**。也就是说句柄指向的记录已经不在了。

**教训（进纪律）**：`world:units()` 返回的是**快照**，在活的多人/任务世界里其中一些句柄随时会失效。
**不允许** `for` 一遍列表再逐个调 getter —— 拿到就立刻用、而且只用极少数几个。
`tostring(unit)` 也可能踩同样的路（它要读名字指针）。

> **2026-10-21 20:34 同一个错又犯了一次**：`exp_hud 0.7.0` 对快照做全量遍历（3,554 个单位）
> 并逐个调 getter，游戏在世界加载后立刻崩溃，无转储。修法见
> [CASE-STUDY-20261021.md](../cases/CASE-STUDY-20261021.md) §18.6。**这条纪律不写在代码里就会再犯。**

这条和 1.2.0 的 `unit_by_id(错 id)` 空指针是同一条道理的两面：**引擎侧的句柄不是安全的引用，
错一个/晚一步都是崩溃，不是 Lua 报错。**

## ✗ 否证：Entity / Unit 的方法名不可枚举（2026-10-20 21:55:19，零崩溃）

`getmetatable(entity).__index` 与 `getmetatable(unit).__index` **都是函数**，而
`debug.getupvalue` 在这个分发器上拿不到任何表 —— 两次都是 `no table upvalue found`。
所以"读出闭包里的方法表"这条零风险的路**不成立**，方法名只能靠文档/类表，不能靠猜
（猜的代价已经用三次崩溃量过了，见上一节）。

同一次运行（纯表读取，**一次引擎 getter 都没调**）确认了两张类表的完整内容：

- `stingray.Unit` —— **119** 个键，其中对读数有用的：
  `alive` · `id` · `debug_name` · `resource_name` · `name_hash` · `world` · `world_position` ·
  `world_rotation` · `world_pose` · `local_*` · `get_property` / `set_property` ·
  `get_data` / `has_data` / `set_data` · `material_id` · `bones` · `num_meshes`
- `stingray.EntityManager` —— 21 个键（`alive` / 各 `*_component` / `create` / `destroy` / `spawn`）
- `stingray.DataComponent` —— 10 个键（`instances*` / `get_property` / `set_property` / `create` / `destroy`）
- `stingray.World` —— 72 个键

★ 其中 **`Unit.alive`** 是前三次崩溃一直缺的那把锁：**在碰一个 Unit 句柄之前，先问它自己还活着没有**，
而不是相信 `units()` 快照里的每个句柄。下一次要用 Unit 的动作必须先过这一关。

## ✗ 否证（第二次，满负载世界复测）：方法名不可枚举，组件对象也只是同一张表

`world_api 1.12.0`，2026-10-20 21:59:11，**世界已完全加载**（`num_units=6597`、`num_levels=491`、
引擎运行 159.7 s）：

| 对象 | `__index` | 结果 |
|---|---|---|
| Unit 句柄（活世界） | function | **no table upvalue** |
| Entity 句柄（活世界） | function | **no table upvalue** |
| **DataComponent userdata** | **table** | 10 个方法 —— 与类表逐字相同 |
| **UnitComponent userdata** | **table** | 8 个方法 —— 与类表逐字相同 |

结论三条：
1. **换时机不改变答案** —— metatable 按类型挂，加载期与满载期扫出来一样（这次是实测，不是推断）。
2. Unit / Entity 的方法名**不可枚举**，只能来自类表或文档。
3. 两个组件 userdata 的 `__index` **是表**，但内容就是那 10 / 8 个已知方法 —— **没有新名字**。
   也就是说组件对象是"真对象、熟名字"，问题从来不是它们，而是**拿不到一个活实体**去喂给它们。

**边界（截至 2026-10-20 22:00）**

| 能力 | 判定 |
|---|---|
| `world:units()` → Unit 身份 + 位姿 | ✓ 实测（任务世界读过真实坐标） |
| 遍历 `units()` 列表 | ✗ 快照会过期，摸到失效句柄即崩（1.9.0） |
| `entities()` → 组件 → 游戏数据 | ✗ 实体句柄字段不可碰（1.10.0）；组件永远是空代理（`[Unit (deleted)]` / `instances=nil`） |
| 命名属性 `get_property` | ⚠ 未测；形参形状与属性名都未知 |

## ★★ 破局：名字查询是安全的，而且单位是活的（2026-10-20 22:05:17）

`world_api 1.13.0`，任务世界（`num_units=6561`、`num_levels=491`、引擎 124.8 s）：

```
CALL Unit.alive(unit)                                -> ok=true  value=**true**
CALL Unit.has_data(unit, "dsh_probe_absent_key_42")  -> ok=true  value=false
CALL Unit.get_property(unit, "dsh_probe_absent_key_42") -> ok=true  value=nil
```

两个都在这之前不可能出现的事实：

1. **`Unit.alive` 第一次返回 true。** 之前所有读数都是在死代理上量的 —— `entities()` 给的实体
   是死的，而 `units()` 给的**第一个单位是活的**。这道门禁前三次崩溃都没有。
2. **未知名字是无害的。** `has_data` 给 false，`get_property` 给 nil，**不崩**。
   `entity.id` 那种"查不到就解引用"的模式**不适用于 Unit 上的名字查询** ——
   所以词表攻击从"抽奖"变成了"合法手段"。

这两条一起把"能不能读命名属性"这个尾巴解开了：**能，而且可以放心地用词表去找名字。**

## 命名属性：**有效样本上的 0 命中**（2026-10-20 22:17:56）

`world_api 1.15.0`，任务世界（`num_units=6610`、`num_levels=491`、引擎 160.0 s）：

```
checked 2 handle(s), 2 alive, chose #2 at Vector3(-4.69336796, -7.10257244, 16.5056152)
CALL Unit.alive(chosen) -> true
probing 107 candidate names on the chosen unit
SUMMARY: 107 name(s) probed on a REAL alive unit, 0 data hit(s), 0 property hit(s)
```

**这次样本是干净的**：选中的是第 2 个句柄、`alive` 为真、位置不是占位 `(1,1,1)`。所以
"107 个名字全不命中"不能再归因于占位物。

两种读法，及我的判断：

| 读法 | 判断 |
|---|---|
| ① HD2 的单位**本来就没有**命名属性（Stingray 的 property 定义在 unit 资源里，这款游戏不用） | ⚠ **更像** —— `has_data` 与 `get_property` 是通用访问器，两者对 107 个常见名字全是 false/nil |
| ② 名字不同（HD2 用的是别的命名） | ⚠ 可能，但 107 个涵盖引擎层与游戏域的常见词一个都不中，概率不高 |

**要判死需要一步**：把 unit 资源（`Unit.resource_name` 给出的 IdString64）从 bundle 里抠出来，
直接看它有没有 property 表、表里叫什么。有 → 拿真名字再测一次；没有 → 这条门就是数据关的，
结案。

## ★ 判死：这门是**数据**关的，不是安全性关的（2026-10-20 22:3x，srkit 侧）

前面的 0 命中终于有了物证。用 srkit 把 `Unit.resource_name` 给出的资源
`0x465F4895F3DC98D1` 从 bundle 里抠出来并解码（`D:\mod\recon\unitres2\`）：

- 类型 `0xE0A48D0BE9A7453F` —— srkit 叫它 `mesh`，而 **它的别名正是 `unit`**
  （`srkit codecs`：`mesh 0xE0A48D0BE9A7453F yes unit`）⇒ **在这款游戏里，Stingray 的"unit 资源"
  就是这种 mesh 资源**，我们抠的就是对的那一份。
- 解码结果的顶层结构：`header`（bones / geometry_group / state_machine 引用）· `lights` ·
  `lod_group_list` · `transform_info` · `customization` · `stream_info` · `meshes` · `materials`。
- **没有 property 段，没有 data 节点表** —— 一个都没有。

于是三件事同时成立：

1. `Unit.has_data` 107 个名字全 false、`Unit.get_property` 107 个名字全 nil —— **不是名字猜错，
   是资源里根本没有可命名的属性**。
2. `world:units()` 里的"单位"是**视觉实例**（mesh 实例 + 变换），任务世界 6610 个 = 场景里所有渲染物。
   这解释了为什么它们有位置、有资源名，却没有游戏属性。
3. **命名属性这条路，终点就在这**：`get_property` 是安全的、可用的，但它没有东西可返回。

**顺带挖到一个真有用的东西**：资源的 `customization` 段直接带着
`body_type` / `slot` / `weight` / `piece_type` —— 正是老内存线追过的护甲重量/部位分类数据。
这条不需要引擎：**srkit 离线读资源就够**。

### 最终边界（收口用）

| 想读什么 | 现在怎么读 | 判定 |
|---|---|---|
| 单位/物体的**位置·朝向·矩阵·身份** | `world:units()` + `Unit.alive` 门禁 + `Unit.world_*` | ✓ 引擎侧可用 |
| 单位的**命名属性** | `Unit.get_property` | ✗ 资源里没有属性，接口再安全也没用 |
| **游戏数据**（护甲重量/部位/材质…） | `srkit extract --decoded` 读资源 | ✓ **离线**，不需要引擎、不需要内存 |
| 任意实体上的组件数据 | `entities()` → 组件 | ✗ 三次崩溃 + 实体是死的 |
| 内存（进程内/进程外） | — | ✗ 三条路全封死 |

## ★ 资源覆盖 API 的官方签名（2026-10-21 20:5x，Autodesk Stingray Lua Reference）

在线文档在 `help.autodesk.com`，抓取工具会在页面中段截断（`set_resource_override` 恰好落在
截断点之后）。**用 chrome-devtools MCP 打开真实浏览器 + 在 iframe 里跑 JS 取片段**才拿到全文：

```
set_resource_override ( type, name, override )      三个参数**全是 string**，无返回
  type     : string  要覆盖的资源类型
  name     : string  被覆盖的资源名
  override : string  拿来替换它的资源名
  原文：whenever any engine system requests the resource `name`, the resource
        `override` will be returned instead. To remove an override, use clear_resource_override().

clear_resource_override      ( type, name )
set_resource_override_flag   ( flag, priority )     ← dev 用的另一套机制
clear_resource_override_flag ( name )
```

⇒ 这是**名字→名字的运行时别名**，不是"塞资源字节"。三个字符串，是最安全的调用形态
（不需要任何引擎句柄，不涉及二进制）。

### ★★ 覆盖机制**在正式版可用**（2026-10-21 20:59 实测，代价是游戏卡死）

`resource_override_probe 1.2.0` 的日志自证了这一点 —— 它把**本模块以别名重新执行了一遍**：

```
STEP 2 set_resource_override("lua", "dsh_override_src", "mods/auto/4")
     OK   returns=0
STEP 3 require("dsh_override_src")
     nargs=1
===== resource_override_probe 1.2.0 ... required as: dsh_override_src     ← 引擎以别名重新加载
```

⇒ ✓ `set_resource_override(type, name, override)` 在 release 构建里**真的生效**：请求 `name`
    会拿到 `override` 指向的那份资源。运行时换资源不必打补丁、不必重启，这条打开了。

**但同一次运行把游戏挂死了**（未响应，不是崩溃），原因是探针**自引用**：
模块第一件事是 `require(被覆盖的名字)` 做对照，覆盖生效后这个名字解析回自己 ⇒ 无限递归 require。

**纪律（补）**：
1. **做覆盖实验时，被覆盖的名字绝不能是"加载时会再次被请求"的路径**；用别名指向自己更是自杀式设计。
2. 任何会被"重新执行"的 Lua 模块，**第一行必须是重入门闩**（`module_argument` 等于某个别名就立刻返回），
   第二道是深度闩（递归超过 N 层直接退出）。`1.3.0` 已按此写，并有专项测试：
   把 payload 直接以别名调用 ⇒ 立刻返回 `{via="override"}`，不再递归。
3. 卡死没有 minidump、没有事件日志，**只有日志的最后一行**能定位；所以每个危险调用点前后都要 flush。

### ✗✗ 事故：`set_resource_override()` 传 0 参直接崩（2026-10-21 20:53，两次）

`exp_hud` 时期留下的坏习惯是"用错误信息当神谕"——逐级补参让引擎报出签名。
**这一招对这个绑定无效**：它不校验参数个数，内部直接取第 1 个参数解引用，nil 一到就 AV。
两次启动都停在日志的同一行：

```
PROBE set_resource_override   nargs=0 () 0 args      ← 之后没有任何输出
```

且**没有 minidump、没有事件日志**，只留下一行日志。

**纪律（补）**：
1. **先查官方文档，再动手**。Stingray 的 Lua 参考是公开的，一次 `chrome-devtools` 抓取的成本
   远低于一次崩溃。这次正是靠浏览器直读才拿到 `(type, name, override)` 三字符串的真实签名。
2. **"错误信息当神谕"只对会校验参数的绑定有效**。判断依据：该函数是否出现在官方文档的
   `bad argument #N` 惯例里 —— 不确定时按"不校验"处理，别拿它试第一发。
