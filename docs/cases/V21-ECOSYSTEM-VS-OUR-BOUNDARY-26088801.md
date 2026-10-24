# 「v21 生态的 mod」vs 我们已探明的新 build Lua 路线边界

> 2026-10-24 · 结论先行：**引擎能力边界一点没拓宽**；拓宽的是**兼容面 / API 契约 / 研发效率**三样。
> 反过来，我们的研究在 6 个点上比 v21 深；还有 1 处是**缩小**（ffi 假阳性）。

## 1. 为什么说"引擎能力一点没拓宽"

判决依据只有一条：**v21 是一段 50 KB 的 Lua 5.1 源码，它跑在我们已经验证过的同一条执行链上**
（覆盖 `boot` 资源 → 明文载荷 → `require`）。它不可能给引擎增加任何东西，只能**组织**已有能力。

把 v21 用到的**全部**引擎/标准库设施列出来，逐条对到我们自己的实测记录：

| v21 用到的设施 | 我们的实测状态 | 出处 |
|---|---|---|
| 覆盖 `boot` 资源（`0xF476DF93691895FA`） | ✓ 2026-10-20 实机 | `LOADER-SPEC-25988413.md` §1 |
| 明文载荷 `u32 size · u32 2 · source` | ✓ 实机 | 同上 |
| `require("core/wwise/lua/…")` 跨补丁取资源 | ✓ 实机（BootProbe 日志） | 同上 |
| `Application.can_get("lua", name)` | ✓ 实机（booleans oracle） | 同上 §3b |
| `io.open` 读/写、`os.getenv` | ✓ 实机 | §"文件路线" |
| `debug` 库（`getinfo/sethook/getregistry/getupvalue`） | ✓ 实机存在 | §2 |
| `Application.build()` | ✓ 实机 = `"release"` | BootProbe 日志 |
| `print` | ⚠ 我们只测过"函数存在"，没真调用 | §2 只列了 `io/os/debug/...` 存在 |
| `os.date` / `os.clock` | ⚠ 未单测（`os` 表存在已测） | — |
| `collectgarbage("count"/"setpause"/"setstepmul"/"step")` | ⚠ 未单测 | — |
| `getmetatable("")`（string 元表） | ⚠ 未单测 | — |
| `package.preload` / `package.loaded` 注入 | ⚠ 未单测（我们走的是 `require` 路径） | — |

⇒ **表里没有一项是我们没见过的"新引擎能力"**。后 5 条是"我们没测过，但它用了并且它自述
`runtime_verified: true`" —— 属于**间接情报（⚠ 待我们自测）**，不是新能力。

**因此**：`v21 生态的 mod 能做的事` ⊆ `我们已探明的 Lua 路线边界`。

## 2. 它确实拓宽的三样东西（不是能力，是别的）

| 拓宽的东西 | 具体 | 对我们的价值 |
|---|---|---|
| **兼容面** | `require("bit")` → 纯 Lua 真实现；`require("ffi")` → 桩。老 LuaJIT mod 不再在 require 阶段炸 | 能**跑**更多社区 mod 的"非内存"部分 |
| **API 契约** | `on_update / on_shutdown / after_startup / capabilities / health / discovery` 一套稳定接口 | 社区 mod 只写逻辑；我们也**可以照这套名字**实现，从而双向兼容 |
| **研发效率** | 崩溃归因（刷 `loading` + 读上一局日志）、健康差分、两级错误熔断 | 我们刚为定位崩溃自己抄了一遍刷盘手法 |

## 3. 我们的研究在 6 个点上比 v21 深

| # | 我们独有 / 更深 | v21 的状况 |
|---|---|---|
| 1 | **`set_resource_override("lua", 别名, 目标)` 实证有效**（10-21 三次 `VERDICT: OVERRIDE WORKS`） | **完全没用这个 API**。它整个发现/加载都走 `can_get` + `require` |
| 2 | **`Application.make_hash(path) == murmur64(path)`**（实测） | 自己写了 74 行纯 Lua murmur64 —— 不必要 |
| 3 | **文件路线**：`.lua` 写到游戏根目录 + 手动建 `bin\lua` 就能 `require` | 只有补丁资源一条路，没有文件路线 |
| 4 | **`debug` 库可用**（`getinfo/sethook/getregistry/getupvalue` 实测存在） | 只在非 release 时 `require "debug"`，没利用 |
| 5 | **`package.loaders = 5`、`package.cpath` 含 `loadall.dll`、`loadlib` 门禁的三种 errno** | 没有探测过 |
| 6 | **数据表路线（`.dl_bin`）**：护甲三数字、被动行、战备槽…… | 完全在它的边界之外（且是我们实际在用的主力） |

外加一条"它没测、我们也没测"的空白：**`os.execute` / `io.popen` 从未真调用过一次**
（我们只测过 `type()`）。v21 也没调用，所以这一点它**同样没有推进**。

## 4. 有一处是**缩小**，别忽略

装 v21 会让 `type(ffi) == "table"` **恒真**（它无条件 `rawset(_G, "ffi", stub)`）。
于是：

- 任何用 `type(ffi)=="table"` 判"有没有内存能力"的探针/文档 → **假阳性**；
- 我们的 `BootProbe.log` 里那句 `type(ffi)=nil` 正是这种判据的证据 ⇒ 一旦装 v21，这条证据链失效；
- 桩的 `ReadProcessMemory → 0`、`CreateFileW → 1` 是**静默假成功**，比报错更难查。

⇒ **这不是拓宽，是证据边界的缩小。**

## 5. 一句话回答

> **v21 没有拓宽我们研究过的 Lua 路线能力边界（一项都没有）；它把"同样的能力"包装成了
> 一套稳定的 mod 生态。** 想拿它的好处，最省的做法是照它的 API 名在我们自己的 `patch_0` 里
> 补 60 行（钩子 + after_startup + 崩溃归因），而不是把 `patch_0` 换成它 ——
> 那样还能同时保住我们独有的 `set_resource_override`、引擎侦察和干净的能力判据。
