# 老 build（LuaJIT）的 shared loader ⇄ v21：功能复现对照

> 2026-10-24 · 老 build 侧取**上游 v19 源码**（`D:\mod\refs\BingusSharedLoader-fresh\src\`，5 个模块 1,847 行，
> 上游最后一个 LuaJIT 版本）；新 build 侧取 **v21 payload**（1,383 行，从 zip 的 `patch_0` 偏移 192 取出，
> `u32 50665 + u32 2`）。两边**都逐行读过**，不是照 README 抄。

## 0. 一句话

**API 面 1:1 复现，一个字段不缺**；但**底层能力有三处降级、五处彻底没有** ——
其中"彻底没有"里最重的是老 loader 的**头号功能**：共享 LuaJIT code cache（512 KB → 64 MB）。

## 1. 1:1 复现（公开 API 面完全对齐）

| 老 loader（v19）导出 | v21 | 备注 |
|---|---|---|
| `state.version = 17` / `api = 1` | ✓ 同值 | mod 靠它判兼容，v21 故意不改 |
| `state.modules` | ✓ | 状态机同款（`loaded / not installed / load failed / loading`） |
| `state.discovery` | ✓ | 声明式发现 + 副本/遮挡检测 |
| `state.health`（`header` / `changes`） | ✓ | 结构同款 |
| `state.capabilities` | ✓ | 但**取值方式退化了**（见 §2.5） |
| `state.open_log` / `state.log_directory` | ✓ | 同名同语义，日志路径也一致 |
| `state.after_startup` | ✓ | 起完所有 mod 后按序跑，上限 256 |
| `state.jit` | ✓ | 两边都是"声明没有 JIT"的信息位 |
| `BingusRuntime.shared` / `.guard` | ✓ | 纯 Lua 重写，语义保留（熔断/暂停恢复） |
| 声明协议 `-- HD2-Addon:` + `murmur64(name)==资源 id` | ✓ | 正则、首行锚定、黑名单都一致 |
| `previous_session` 上一局崩溃归因 | ✓ | 刷 "loading" 再 require 的顺序也一致 |

**v21 反而多出 3 个 API**（v19 没有）：`state.on_update`、`state.on_shutdown`、`state.build`（含 exe/game.dll sha256，但不校验）。

## 2. 复现了，但**降级**（同一功能换了实现，能力变弱）

| # | 功能 | 老 build（v19 / LuaJIT） | v21（Lua 5.1） | 实际后果 |
|---|---|---|---|---|
| 2.1 | **找游戏根目录** | `GetModuleFileNameA(nil, buf, 32768)` → 从 exe 路径硬截（`discover.lua:292-294, 335`） | 从 `package.path` 反推候选（`L754-L791`） | **本机实测踩过**：`package.path` 被 `LUA_PATH` 污染成 `C:\Users\Admin\LuaJIT\bin`，v21 的第一个候选就是错的，只能靠"patch_0 试开失败"筛掉 |
| 2.2 | **枚举补丁文件** | `FindFirstFileA(family.patch_*)` + `FindNextFileA` + `FindClose`（`discover.lua:297-325`，配套 `ffi.load('kernel32')` 在 `shared_loader.lua:57-100`） | `io.open` 逐个**猜** `patch_0..255`（`L782-L789`） | 只能发现符合 `patch_<数字>` 规律的；目录里别的文件永远看不见。这正是我们 `PATCH-LOADER-DESIGN §8.4` 记的"唯一还没测的真枚举" —— 老 loader **有**，新 loader **没有** |
| 2.3 | **MurmurHash64A** | `ffi.new('uint64_t')` 真 64 位整数（`discover.lua:29-57`） | 4×16 位肢纯 Lua 模拟（`L168-L241`） | 结果逐位一致（已对 5 个名字验证），但慢；且**没必要**——引擎有 `Application.make_hash` |
| 2.4 | **`bit` 库** | 原生 LuaJIT `bit` | 纯 Lua 实现（`L60-L166`） | 语义一致、慢一个量级；每帧大量位运算的 mod 会掉帧 |
| 2.5 | **`capabilities` 的取值** | **按实际可用性算**（`discovery = addon_discovery ~= nil`、`health = loader_health ~= nil`，`shared_loader.lua:25`） | **硬编码 true**（`L1015-L1020`） | 拿它做能力判定会被骗 |
| 2.6 | **健康报告内容** | 还记 **JIT 状态/变化**（`jit_state`/`jit_changes`，`health.lua:127-153`） | 无 JIT 可记（`jit_budget=false`） | 少一类观测 |
| 2.7 | **"保护 Windows 函数声明不被 mod 改"** | 载入时先 `ffi.load('kernel32')` 并缓存函数指针（`shared_loader.lua:90-100`） | 只能保护 **Lua 内建**（`L1006` 一次性捕获 `pcall/tostring/...`） | 没有 kernel32 声明可保护 |
| 2.8 | **`ffi` 本身** | 真 FFI：任意 `cdef`、调 Win32、读写内存 | **metamethod 化的桩**：`CreateFileW→1`（假成功）、`ReadProcessMemory→0`、`ffi.string→""` | ★ **所有依赖 ffi 的老 mod 从"能用"变成"静默空转"**；而且会让 `type(ffi)=="table"` 的能力判定集体假阳性 |

## 3. **不能复现**（环境里根本没有这个东西了）

| 能力 | 老 build 的实况 | v21 | 为什么不可能 |
|---|---|---|---|
| ★ **共享 LuaJIT code cache** | 老 loader 的**头号功能**（v19 README 第一节）：把机器码上限从 **512 KB 抬到 64 MB**、trace 从 1000 抬到更高，并在检测到冲刷时**翻倍**；`jit_budget.lua` 128 行，实测两次任务峰值 1,344 KB 从未冲刷 | `capabilities.jit_budget = false`，代码里没有 | 5.1 没有 JIT、没有机器码缓存 |
| 内存读写 | ffi 直接 `ReadProcessMemory`/`WriteProcessMemory` | ✗ | 无真 ffi；**且 EAC 也会拦**（我们实测 VM_READ 被剥、MiniDump 被拒） |
| LuaJIT 字节码 mod（`\x1bLJ` / `\x1bLua`） | 老 loader 直接 `require` | 只标成 `compiled`，**不加载** | 5.1 解析器拒绝"bad header in precompiled chunk" |
| `jit.*` 全套（`on/off/flush/opt.start/attach`、code cache 预算） | 大量使用 | ✗ | 无 JIT |
| LuaJIT 扩展语法（`goto`、`table.new`/`table.clear`） | 可用 | ✗（无 polyfill） | 5.1 解析器不认识，loader 也补不了语法 |
| JIT 带来的性能 | 热路径编成机器码 | 解释执行 | 帧成本归因（v19 的 `frame_probe`）也随之失去意义 |

## 4. 对我们项目的三条实际含义

1. **v21 不是"老 loader 的新版"**，而是"**老 loader 的接口 + 5.1 能兑现的那部分实现**"。
   凡是走 `CowboyBingusModLoader.*` 这套 API 的 mod，只要不碰 ffi/字节码/jit，**代码不用改**。
2. **数据类/资源类 mod 不受影响**（它们不依赖 ffi）；**内存类 mod 全部失效**——
   而且失效方式是**静默的**（假 ffi 返回"成功"），比直接报错更难查。
3. 我们若是自己补基础设施（`BSL-V21-RECHECK §3` 的 A 方案，≈60 行），
   直接照 §1 那张表对齐 API 名，就能让 v21 生态的 mod 与我们的 patch_0 兼容；
   **但别照抄 2.1/2.2 两个降级**——找根目录和枚举补丁，我们有 `GetModuleFileNameA` 之外更可靠的路（依赖 `bin\lua` 与 `data\` 的相对关系，已实测）。

## 5. 证据

| 文件 | 内容 |
|---|---|
| `D:\mod\refs\BingusSharedLoader-fresh\src\{shared_loader,discover,health,jit_budget}.lua` | 老 build 侧源码，行号即上表引用 |
| `D:\mod\tmp\v21fresh\v21.lua` | v21 payload 源码（1,383 行），行号即上表 `L…` 引用 |
