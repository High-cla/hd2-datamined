# What a post-25988413 shared loader has to be

Written while waiting for the upstream loader to ship a fix. Everything below is constrained by
measurements from this build, not by preference; each constraint cites where it came from
(`docs/BUILD-25988413.md` has the full evidence trail).

The point of writing this now: the hard part of porting a loader is not the plumbing, it is the one
capability the old loader got from `ffi` and can no longer have. Naming that early is worth more than a
port that stalls on it later.

---

## 1. Getting execution: solved, and proven here

Measured against **v20** as well, not just v19: v20 (published 2026-10-18, two days before this update)
carries the same resource `7251FDD9BB62480A`, a 64,495 B **LuaJIT** chunk, and its manifest pins
`steam_build 25480438` with the pre-update exe/dll hashes. So the recipe below applies to whatever replaces
them, not to a specific version.

| requirement | value |
|---|---|
| resource to override | `boot`, id `murmur64("boot")` = `0xF476DF93691895FA` |
| lives in | bundle `9ba626afa44a3aa3` |
| patch file | `data/9ba626afa44a3aa3.patch_N` + empty `.gpu_resources` / `.stream` companions |
| payload | `u32 size · u32 2 · <lua source>` - **source works**, bytecode unnecessary |
| must define | globals `init`, `shutdown`, `update`, `render` |
| must also do | reproduce the game's own boot body (four no-ops, the `build ~= "release"` → `require "debug"` guard, `jit.off()` if `jit` exists) |

Proven in game on 2026-10-20 with `boot-probe/` (read-only probe, log at
`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\BootProbe.log`).

There is no second anchor to fall back on: `boot` is the only lua the engine loads by itself, and
`core/init` does not exist in either build.

---

## 2. The VM the loader runs on

Measured in game:

```
_VERSION = Lua 5.1     jit = nil   ffi = nil   bit = nil
io / os / debug / package / string / table / math / coroutine = present
loadstring = function   require = function   os.getenv = function   io.open = function
debug.getinfo / sethook / getregistry / getupvalue = present
package.loaders = 5 searchers
package.loadlib = function (real: a missing DLL yields the Win32 "module not found" error)
package.cpath   = .\?.dll;<game>\bin\?.dll;<game>\bin\loadall.dll
package.path    = <env LUA_PATH>;.\?.lua;<game>\bin\lua\?.lua;<game>\bin\?.lua;...
```

Two consequences that are easy to miss:

- **`\x` string escapes do not exist in stock Lua 5.1.** Any payload generating bytes (like our probes
  embedding chunks) must use `\ddd`. Our builder already does.
- **`loadstring` failure is a return value, not an exception.** `ok, value, message = pcall(loadstring, s)`
  reports `ok=true, value=nil` for a refused chunk. Two of our own probes were bitten by this; a loader
  that treats pcall success as load success will silently skip every module it fails to load.

---

## 3. The capability the old loader lost, and the open question it creates

The v19/v20 loader discovered mods by **enumerating `data/*.patch_N` through `ffi`** (`kernel32`
`FindFirstFile`-class calls plus its own hashing). That is gone: `ffi = nil`, and plain Lua 5.1 has **no
directory-listing API** - `io` can open a known path, it cannot ask "what is in this folder".

A design consequence worth recording, because v20 added a build gate for exactly this situation: that gate
lives **inside the lua payload**, so on this build it never executes and the "unsupported build, here are
the hashes" diagnostic never appears. An anchor on the load path can announce nothing when it is the thing
that failed; `boot` is executed unconditionally, so a gate placed there can always speak.

So a new loader cannot discover mods the old way.

**Candidate 1 is now measured and refuted.** `stingray.ResourcePackage` was the best hope and probe
v1.3.0 (2026-10-20 18:07, in game) settled it: it has exactly **six** keys - `load`, `unload`,
`has_loaded`, `flush`, `__index`, `_name`. It can load a package by name and say whether it is loaded; it
**cannot enumerate**. So "ask the engine's package view what exists" is not available either.

What is still open, in the order worth testing:

1. ~~**`stingray.PluginManager`**~~ — **measured 2026-10-20 18:31 and refuted.** `loaded_plugins()`
   returns exactly three names and they are engine plugins, not mods:
   `havok_physics`, `level_generation`, `wwise_plugin`. Nothing a patch installs can appear there, so
   PluginManager is not a discovery route either. That closes the last "ask the engine what exists"
   idea: **`ResourcePackage` cannot list, `PluginManager` lists only its own three plugins.**
2. **A declared manifest reached by `require`.** Every mod already ships a resource; if the loader knows a
   naming convention it can `require` candidates and treat "no lua resource `X`" as "not installed". A
   fixed candidate list works, but only if the manager and the loader agree on one.
3. **`package.loadlib` + a small native DLL** that does the directory walk. Mechanically available
   (`cpath` includes `<game>\bin\?.dll`), and under Easy Anti-Cheat it is exactly the kind of thing that
   should not be shipped without a deliberate decision.
4. **Out-of-band generation**: a manager (HDArsenal / HD2MM) writes one aggregate lua resource containing
   the list of installed mods, and the loader reads that single known resource. No enumeration needed at
   runtime. This is the option with the least new surface area, and it matches how the existing managers
   already deploy.

With (1) refuted, the ranked options are now **4 and 2** - both need a naming convention rather than an
enumeration primitive, and both get cheap because `Application.make_hash` reproduces our `murmur64`
exactly, so ids can be derived from names at runtime without `ffi`.

## 3b. Measured: the load path itself works, and existence checking has an API

Proven in game 2026-10-20 19:51 with two patches deployed (`patch_0` = `boot` only, `patch_1` = a read-only
test mod at module path `mods/test/boot_loader_test`):

```
make_hash('mods/test/boot_loader_test') -> d90a720ebc2f7d3c      = murmur64(module), our derivation
control can_get('lua', absent):            ok=true value=false    = it discriminates
can_get('lua', 'mods/test/boot_loader_test'): ok=true value=true
require('mods/test/boot_loader_test'):     ok=true type=table     (0.001 s)
RESULT: SUCCESS - a boot-anchored loader started a mod that lives in another patch
```

and the test mod's own log confirms it ran (`TEST MOD EXECUTED`, `... = mods/test/boot_loader_test`,
`BootLoaderTestShared.loaded = 1`).

**I have to correct the paragraph above**: I wrote that no discovery primitive was left. That was wrong.
`Application.can_get('lua', name)` is one - it was in the 70 `Application` keys we had already enumerated,
and the old loader had been using it all along (`assert application.can_get('lua', name)` before
`require(name)`). What actually died is **filesystem** enumeration (`ffi` + `FindFirstFile`), not
existence checking.

So the shape of a port is clearer than when this document started:

| need | answer |
|---|---|
| get execution | override `boot` (proven) |
| start another mod | `can_get` then `require(module_path)` (proven, cross-patch) |
| compute a mod's resource id | `Application.make_hash(path)` == `murmur64(path)` (proven) |
| know which mods exist | **still open** - no listing, so the candidate list has to come from a naming convention, a manifest, or the mod manager |

That last row is now the only real design decision left, and it is a deployment question rather than an
engine capability question.

---

## 4. What the loader must NOT assume any more

| old assumption | status |
|---|---|
| `ffi` for file enumeration, memory, struct packing | **gone** |
| `bit` for hashing helpers | **gone** (use arithmetic on numbers) |
| `jit.*` code-cache tuning (the v19 headline feature) | **meaningless** - no JIT |
| precompiled LuaJIT bytecode payloads | **cannot load** (`bad header in precompiled chunk`) |
| overriding `core/wwise/lua/wwise_flow_callbacks` to get execution | **resource deleted from the game** |
| mods may read/write game memory | no route, and now also an anti-cheat question |

Note the last row: **the loader itself does not need memory access, and should not use it.** The v19
loader's `ffi` use was discovery, not game manipulation. A port can be memory-free and still be a loader.

---

## 5. Minimum viable port (what "done" looks like)

1. Ships as one patch, overrides `boot`, reproduces boot's body, then runs.
2. Discovers installed modules by one of the four routes in §3 - with the choice **measured**, not assumed.
3. Loads each module's lua resource with `require`, isolating failures per module (`pcall` + clear log line).
4. Provides the shared services modules already expect: a log file (`io.open` works), a registration table,
   and an `after_startup` hook.
5. Writes a startup log that names, per module, one of: started / failed (with the error) / not found.
6. Runs no memory writes and no native code unless that decision is made explicitly.

Nothing in that list needs `ffi`. The port is possible; only discovery needs a new answer.

---

## 6. Watch item

`github.com/CowboyBingus/BingusSharedLoader` - still v19 / advertised for build 25480438 as of 2026-10-20.
Its README also documents the module API that our own probes were written against, so a rewrite by the
author is the cheapest path for everyone downstream.

## 实测：文件路线成立，但落点是**游戏根目录**而不是 `bin\lua`（2026-10-20 22:31:51）

回应 issue #13 的主张（磁盘上的普通 `.lua` 可以 `require`）。探针 `file-route probe 1.16.0`
自己写标记文件、再 `require` 回来，跑完从磁盘删除。

```
_VERSION       = Lua 5.1
package.path   = C:\Users\Admin\LuaJIT\bin\?.lua ; ... ; .\?.lua ;
                 <game>\bin\lua\?.lua ; <game>\bin\lua\?\init.lua ;
                 <game>\bin\?.lua ; <game>\bin\?\init.lua ;
os.execute     = function
io.popen       = function

A. 相对路径写 dsh_cwd_marker.lua -> ok ; require -> **OK**
B. 写 <game>\bin\lua\dsh_binlua_marker.lua -> **FAILED: No such file or directory**
```

事后在磁盘上搜到标记文件落在 **`D:\SteamLibrary\steamapps\common\Helldivers 2\dsh_cwd_marker.lua`**
（74 B，已删），并且确认 **`<game>\bin\lua\` 这个目录在磁盘上根本不存在** ——
引擎的 `package.path` 里列出了它，但它没有被创建。

| 结论 | 判定 |
|---|---|
| 磁盘上的普通 `.lua` 能被 `require` | ✓ **实测成立**（#13 的核心主张对） |
| 落点是**游戏根目录**（cwd），可写 | ✓ 实测：`<game>\dsh_cwd_marker.lua` 写入成功并被 require |
| `package.path` 里的 `<game>\bin\lua\` 可用 | ✗ **该目录不存在** —— #13 提议的 `<game>\bin\lua\mods\` 需要先手工创建（路径条目已在，建出来大概率就能被搜到，⚠ 未验证） |
| `os.execute` / `io.popen` | ✓ 都是 function（本轮新测） |

★ 对移植的含义：**最省事的文件路线是"游戏根目录放一个 .lua + 清单也是 .lua"**，
而不是 #13 的 `bin\lua\mods\`。根目录放文件不需要建目录、已经证明可 require。
代价是文件散落在 `start_protected_game.exe` 旁边，不够整洁；且 **cwd 依赖启动方式**（Steam 启动时
是游戏根目录，本轮实测），换启动器就要重测。

## 实测（第二轮）：`bin\lua` 建出来之后，两条 entry **都命中**（2026-10-20 22:35:27）

上一轮只证明了"目录不存在"。这一轮由 Python 预先放好两个文件、探针**只 require 不写**：

```
<game>\bin\lua\dsh_binlua_marker.lua
<game>\bin\lua\mods\dsh_init_marker\init.lua
```

结果：

```
REQUIRE dsh_binlua_marker     -> OK      ok route=binlua        ← 命中 bin\lua\?.lua
REQUIRE mods.dsh_init_marker  -> OK      ok route=binlua_init   ← 命中 bin\lua\?\init.lua
REQUIRE dsh_absent_control    -> FAILED  module 'dsh_absent_control' not found   ← 控制组按设计失败
```

控制组的报错还顺带给出了**完整的查找顺序**，其中第一行是 `no lua resource 'dsh_absent_control'`
⇒ 引擎**先查资源、再查文件**。也就是说补丁型 mod 与文件型 mod 可以并存，资源优先。

| 结论 | 判定 |
|---|---|
| `<game>\bin\lua\?.lua`（建好目录后）可 require | ✓ **实测** |
| `<game>\bin\lua\?\init.lua` 嵌套目录可 require | ✓ **实测**（`require("mods.dsh_init_marker")` → `mods\dsh_init_marker\init.lua`） |
| **该目录默认不存在，部署器必须自己创建** | ✓ 实测（第一轮 `No such file or directory`） |
| 资源优先于文件 | ✓ 控制组报错序列 |
| 游戏根目录（cwd）也可 require、且可写 | ✓ 第一轮实测 |

**移植建议**：部署目录用 `<game>\bin\lua\mods\<author>\<name>\init.lua`（名字用点号 require），
部署器**必须创建 `bin\lua\`**；根目录那套只作为退路（杂乱且依赖 cwd）。

游戏目录已恢复原样：两个标记文件与 `bin\lua\` 目录均已删除（`ls` 确认只剩
`bin / data / EasyAntiCheat / start_protected_game.exe / tools`）。

## ★ 新发现（2026-10-20 23:17）：补丁序号**必须连续**，断开一个就整条链失效

收口时我把 `patch_1` / `patch_2` 删了、`patch_3` 留着，然后装了一份新探针到 `patch_3`。
时间上完全来得及（安装 23:16:47，游戏启动 23:17:31，差 44 秒），但 boot 探针的发现结果是：

```
mods/auto/1..6 -> 全部 absent
SWEEP RESULT: 0 found, 0 loaded, 6 absent
```

**`patch_3` 明明在磁盘上，md5 与构建产物逐字节一致，却完全不被看见。** 唯一的差别是
`patch_1` / `patch_2` 不在了 —— **序号从 0 直接跳到 3**。

⇒ **引擎按连续序号合并 `.patch_N`；中间缺号，后面的一律不生效。**

这条对部署有直接影响：
- 移植/交付时**不能跳号**，`patch_0..patch_N` 必须连号；
- "删掉中间某个补丁"不是无害整理，可能把**后面所有补丁一起废掉**；
- 反过来讲，这条也给了一个便宜的**开关**：想临时禁用第 N 个之后的全部补丁，删掉第 N 个即可。

⚠ 严格说这是**一次观察**（gap 态 0/0/6 vs 连续态 3/3/3，同一台机器、同一份资源），
要坐实还需要一次对照：保持 `patch_0+1` 连续并确认命中，再删 `patch_1` 只留 `patch_0+...`。
下一次启动就能顺手拿到这个对照。
