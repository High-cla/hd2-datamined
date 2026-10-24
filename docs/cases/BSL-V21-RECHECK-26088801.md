# BSL v21 复核：上一份分析漏了什么 + 它比我们的 patch_0 多什么

> 2026-10-24 · 样本：`D:\Downloads\Bingus Shared Loader V21 Fix 17798 1 2026-10-23T21-13Z 5V4gvqUkA.zip`
> sha256 `0ad76084…d0`（与上一份分析一致）；重新解包与 `Bingus Shared Loader V21 Fix Analysis\extracted\`
> **逐字节相同** ⇒ 上一次分析看的字节没问题，问题只在"读得够不够深"。
> 本轮把 payload 重新取出来（`data/9ba626afa44a3aa3.patch_0` 偏移 `192`，`u32 50665 + u32 2`，1383 行）
> 逐段复核，并**首次与上游 v19 源码逐个对照**。

## 1. 上一份分析漏掉 / 说浅的 8 条

| # | 漏掉的点 | 代码位置 | 为什么重要 |
|---|---|---|---|
| 1 | **健康观察是逐 `require` 接线的，且会优雅降级** | `observed_require` L1328-1341：`observer.mark()` → `require` → `observer.changes(mark)`；一旦测量失败就 `observer = nil` **永久关掉健康**并记 `unavailable` | 上一份只写"健康报告记录了什么"，没写**怎么挂上去、坏了怎么办** |
| 2 | **"上一局崩溃归因"是靠刷盘顺序换来的** | 加载循环 L1361-1363：先把 `<module>: loading` **写盘**，再 `observed_require`；`health.previous_session` L973-997 解析上一局日志，答出"停在 loading 某个模块 / 停在 after_startup" | ★ 这正是我们刚才为定位崩溃**自己重新发明**的东西（v1.1.0 的 `>>> BEFORE` 刷盘）。上一份只写了一句"上一局日志结局" |
| 3 | **`capabilities` 从"按实际可用性算"退化成"硬编码 true"** | v19 `src/shared_loader.lua:25` 是 `discovery = addon_discovery ~= nil, health = loader_health ~= nil`；v21 L1015-1020 直接写 `health = true, after_startup = true, on_update = true` | 用 `capabilities` 做能力判定会被骗；只有 `jit_budget=false` 是真话 |
| 4 | **与另一个 loader 的逐模块共存检查** | L1344-1347：每个模块加载前看 `_G.HD2ModLoader.modules[name]`，`loaded/loading` 就直接沿用状态、**不重复 require** | 上一份只提了"`_G.CowboyBingusModLoader` 已存在就早退"，那是**全局**级；这是**逐模块**级 |
| 5 | **失败模块永不重试 + 回调上限 256 后拒绝** | L1346 `Never retry a previous initialization attempt`；`refuse()` L1240-1249（只记一次日志） | 决定"装错的 mod 会不会每次启动都拖慢/重试" |
| 6 | **回调有 owner 归属** | `callbacks.starting = name` 在 require 前后设/清（L1361/L1364），`after_startup` 记录 `callbacks.owner`；失败时日志写 `callback of <module> failed` | 多 mod 时能定位是谁的回调炸了；上一份只写"可注册回调" |
| 7 | **健康快照还会抓 `string` 的 metatable 和 `_G` 的 metatable，并记录 GC 参数的"变化"而不只是当前值** | L904-913 的 `scopes` 列表（`""`、每个库、`package.loaded.`、`string metatable.`、`_G metatable.`）；L874-877 `setting_change` 比 before/now | 能抓到"mod 偷改 `string` 方法 / 换 `_G` 元表"这类隐蔽副作用 |
| 8 | **`-- HD2-Addon:` 是首行锚定 + 一条硬排除** | L561-568：`prefix:match("^%-%- HD2%-Addon: (mods/[A-Za-z0-9_]+/[A-Za-z0-9_/]+)\r?\n")`，且排除含 `//`、以 `/` 结尾、以及 **`mods/codex/loader`** | 上一份原文写"正文**前 256 B** 里有"——**不准确**，`^` 决定必须是第一行；另外有条写死的黑名单 |

### 1.1 顺带纠正上一份的两处措辞

| 上一份说法 | 实际 |
|---|---|
| "§2.4 用纯 Lua 重写 MurmurHash64A"（暗示必要） | 我们实测 `Application.make_hash(path) == murmur64(path)` ⇒ **有引擎就不必自己实现**；只有"无引擎环境"才需要这 74 行 |
| "§2.2 复刻 stock boot" | 对，而且与我们的 BootProbe **逐行等价**；真正的增量在别处（见 §2），不在入口 |

### 1.2 与 v19 对照后确认的两件事

| 项 | 结论 |
|---|---|
| "v21 把所有模块内联进一个 payload" | ✗ **不是 v21 的变化**：v19 的 `scripts/build.py` 也是把 `discover/jit_budget/health/coordinator` 拼进同一段源码（`--probe` 才额外拼 `frame_probe.lua`） |
| `frame_probe.lua`（v19，387 行）在 v21 里没有 | ✓ 但它**本来就不进公共构建**（源码首行注释："Only `build.py --probe` embeds this file; public loader builds never contain it"）⇒ **不是功能回退** |

## 2. 它有哪些我们的 `patch_0` 没有的东西

**先说清两边是什么**：

| | 我们的 `patch_0`（BootProbe 1.3.0） | BSL v21 |
|---|---|---|
| 定位 | **一次性诊断探针**：扫 `mods/auto/1..6` → `can_get` → `require`，把引擎事实写进日志 | **常驻加载器**：发现、加载、钩子、健康、崩溃归因 |
| 体量 | 22.4 KB / ~380 行 | 50.7 KB / 1,383 行 |

| 能力 | v21 | 我们的 BootProbe | 对我们意味着什么 |
|---|---|---|---|
| boot 覆盖 + 复刻 stock 行为 | ✓ 且**链 `prev_init/update/render/shutdown`** | ✓ 但置 `noop`、不链 | 我们暂时无第二个 boot 要链 |
| 模块来源 | **声明式**（`-- HD2-Addon:` + id 校验）+ **44 条白名单** + 遮挡检测 | **硬编码** `mods/auto/1..6` | 我们每加一个 mod 就得改 patch_0 |
| **每帧 `update` 钩子** | ✓ `on_update(id, fn)`，出错即摘该钩子 | ✗ | ★ **正是我们刚才缺的那个**（任务内延后探针） |
| `shutdown` 钩子 / `after_startup` 回调 | ✓ / ✓（启动结束后按序跑，上限 256） | ✗ | 可用于"世界加载完再做一次" |
| 错误熔断 | ✓ 两层：钩子出错即摘；`BingusRuntime.guard` 再给 mod 级暂停/恢复 | ✗ | 长期常驻 mod 的必备 |
| **健康差分** | ✓ 逐 require：堆 KB 增量、耗时 ms、全局/库/**string 元表、_G 元表**、GC 参数变化 | ✗ | 我们的验收一直只有"看游戏内表现"，这是另一层证据 |
| **崩溃/卡死归因** | ✓ 刷 "loading" → 下一局读上一局日志 | ✗ | 直接补我们刚才的痛点（那次不可复现的崩溃） |
| 统一日志 + `open_log()` 给 mod | ✓（限 `[%w_%-]+%.log`） | 单一 sink | 中等 |
| 纯 Lua `bit` / `ffi` stub / murmur64 | ✓ | ✗ | bit/ffi 对我们是**噪音**（还有假阳性风险）；murmur64 可由 `Application.make_hash` 顶替 |
| `capabilities` 能力表 | ✓（但硬编码） | ✗ | 中等 |
| **引擎侦察**（`stingray` API 面、环境事实、`package.loaded`、resource require 试验） | ✗ | **✓ 只有我们有** | 我们很多结论出自它 |

**一句话**：差的不是"功能多少"，而是**运行时基础设施**——**每帧钩子、错误熔断、健康差分、崩溃归因**这四件。前三件是为了"常驻 mod 不把游戏拖死"，第四件是为了"崩了能定位"。

## 3. 若要补，最小代价不是装 v21

| 方案 | 内容 | 代价 | 风险 |
|---|---|---|---|
| **A. 给自己的 patch_0 加三件**（推荐） | ① `update` 里跑 `update_hooks`；② `after_startup` 队列；③ 加载每个模块前把 `loading` **刷盘** | ≈60 行，改的是我们自己的 22 KB 载荷 | 自己可控；最坏情况是 mods 不加载，游戏照常起 |
| B. 装 v21 | 直接拿 `on_update` 等全套 | 覆盖 BootProbe，丢掉引擎侦察；`_G.ffi` 假阳性会污染我们"ffi 不可用"的证据链 | 中等 |
| C. 合并 | 用 `patch_compose.py merge` 把 v21 的 boot 与 patch_3/4 的数据条目合成一个 patch_0 | 每次更新 v21 都要重跑合成器 | 中 |

⇒ 我们真正需要的只是 **A 里的三件**（约 60 行），**不需要** v21 的 bit/ffi/murmur64/白名单/发现协议。

## 4. 证据文件

| 文件 | 内容 |
|---|---|
| `D:\mod\tmp\v21fresh\v21.lua` | 从 zip 的 patch_0 取出的 1,383 行源码（偏移 192，`u32 50665 + u32 2`） |
| `D:\mod\tmp\v21fresh\data\*` | zip 原样解包（与上一份分析逐字节相同） |
| `D:\mod\refs\BingusSharedLoader-fresh\src\*.lua` | 上游 v19 源码（5 个模块，1,847 行），用于 §1.2 的对照 |
