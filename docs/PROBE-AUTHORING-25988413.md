# How to write a probe for build 25988413

Everything here was measured on this build, in game, today. It exists because the old probe pattern is
dead in a specific, nameable way — and because "the old probes fail" is *not* what happens: they load and
quietly switch themselves off, which is worse, because it looks like nothing is wrong.

Measured 2026-10-20 20:15, loading our own `vfcprobe` (revision 9.0.0-kit) through the boot-anchored mini
loader, with no other mods installed:

```
[9.0.0-kit] loaded | revision 9.0.0-kit | lua Lua 5.1 | jit none | READ-ONLY
[9.0.0-kit] kernel32 unavailable - staying inert
[9.0.0-kit] status: hooked (10 entry point(s), 8 global(s))
```

It ran, correctly noticed there is no `jit`, correctly noticed there is no `ffi`, and went inert. **No
crash, no error, no data.** A probe that fails loudly is a probe you can fix; this one fails silently.

---

## 1. The four hard constraints

| constraint | measured fact | consequence |
|---|---|---|
| no `ffi` | `type(ffi) == nil` in game | **no process memory access of any kind**, no `kernel32`, no struct packing |
| no `bit`, no `jit` | both `nil` | replace with arithmetic; `jit.version` prints must go |
| stock Lua 5.1 | `_VERSION == "Lua 5.1"`; LuaJIT chunks refused with `bad header in precompiled chunk` | payload must be **source** (or a 5.1 chunk with `sizeof(size_t) = 4`, unproven) |
| `\x` escapes silently change | `"\x41"` is `"x41"` here, `"A"` under LuaJIT | a byte-generating payload that used `\x` produces **different bytes with no error** |

Two more traps that are not about the VM but bite anyway:

- **`loadstring` reports failure by returning `nil`.** `pcall(loadstring, s)` gives `ok=true, value=nil` for a
  refused chunk. Check the returned value, not the pcall.
- **`can_get` is the existence check.** `Application.can_get('lua', name)` → boolean. Use it before
  `require`; a missing resource must never reach the engine's require path.

---

## 2. What a probe can still read

Measured on this build, all without `ffi`:

| source | example | status |
|---|---|---|
| engine identity | `Application.build()` → `release`, `platform()` → `win32`, `process_id()` | works |
| engine hashing | `Application.make_hash(path)` → equals `murmur64(path)` | works |
| resource existence | `can_get('lua', name)`; deleted resource returns `false` | works |
| **live engine lua modules** | `require('core/wwise/lua/wwise_bank_reference')` → table with keys `add, count, remove` | works |
| loaded-module census | `package.loaded` (13 entries at boot) | works |
| package state | `ResourcePackage.has_loaded` / `load` / `unload` by name | works |
| entity/component API | `EntityManager` (21 keys), `DataComponent` (10 keys incl. `instances`, `get_property`, `set_property`) | present; see caveat |
| filesystem by known name | `io.open(<game>\\data\\<bundle>.patch_N)` | works (proven) |
| directory listing | — | **not available** |

Caveat on the component API: whether it is reachable *at boot* is untested — `EntityManager` methods
probably need a live world. A probe that wants component data should gate on having one (see §4).

**What is gone for good: reading raw component tables out of memory.** That was `ffi` + RVAs, and there is
no substitute. Any probe whose purpose was "read table X at RVA Y" has no future on this VM.

---

## 3. The probe skeleton

This is the shape that worked today. Copy it; each numbered note is a mistake we already made once.

```lua
-- <name> <version> -- READ ONLY. Writes one log file, touches nothing else.
local module_argument = ...          -- (1) capture varargs at chunk top level, not inside a function

local lines = {}
local function report()              -- (2) flush per line; buffering loses the tail when a probe dies
    local path
    if type(os) == "table" and type(os.getenv) == "function" then
        local ok, base = pcall(os.getenv, "LOCALAPPDATA")
        if ok and type(base) == "string" and base ~= "" then
            path = base .. "\\CowboyBingus\\Helldivers2\\Logs\\<Name>.log"
        end
    end
    if not path or type(io) ~= "table" then return "NOWHERE" end
    local ok, handle = pcall(io.open, path, "a")
    if not ok or not handle then return "NOWHERE" end
    pcall(handle.write, handle, table.concat(lines, "\n") .. "\n")
    pcall(handle.close, handle)
    lines = {}
    return path
end
local function add(text) lines[#lines + 1] = tostring(text) report() end

local ok, err = pcall(function()
    add("===== <name> | " .. tostring(os.date and os.date("%Y-%m-%d %H:%M:%S") or "?") .. " =====")
    add("required as: " .. tostring(module_argument))

    -- (3) capability gate: say what is missing ONCE, then stop. Never silently return.
    local application = type(stingray) == "table" and rawget(stingray, "Application") or nil
    if type(application) ~= "table" or type(application.can_get) ~= "function" then
        add("ABORT: Application.can_get unavailable; this probe cannot read anything")
        return
    end

    -- (4) measure, then (5) state a verdict the log can be judged by
    add("build = " .. tostring(application.build()))
    local present = application.can_get("lua", "core/wwise/lua/wwise_bank_reference")
    add("resource present = " .. tostring(present))
    add("RESULT: <one line that says whether this run answered the question>")
end)
if not ok then add("RAISED: " .. tostring(err)) end   -- (6) a raise must still produce a log line
add("===== <name> end =====")
return { module = tostring(module_argument), ok = ok }   -- (7) return a table, not true/nil
```

1. `...` inside an inner `function() ... end` is a **compile error** in 5.1 ("cannot use '...' outside a
   vararg function"). Capture it at the chunk's top level.
2. Line-by-line flush. A buffered logger that flushes once, after the last `add`, loses the block's closing
   marker when the probe ends early — we shipped that bug and the log looked truncated.
3. **No silent early return.** If a capability is missing, log one line naming it, then return. "Stays
   inert and says nothing" is exactly the failure mode that wasted this session's predecessor.
4. Wrap the body in `pcall`; one probe must not take down the loader.
5. End with a `RESULT:` line. A log you have to interpret is a log you will misinterpret.
6. `if not ok then add("RAISED: " .. err) end` — otherwise a raise leaves no trace at all.
7. `return {...}`. `require` returns `true` when a module returns nothing, which is indistinguishable from
   "loaded and did nothing useful" — return a table with a field so the caller can see success.

---

## 4. If the probe needs a world (entity/component data)

The boot payload runs **before** any world exists. A probe that wants `EntityManager`/`DataComponent` data
has to wait. The old loader's mechanism for that is an `update` hook — the same trick `vfcprobe` used:

```lua
local original = rawget(_G, "update")
rawset(_G, "update", function(...)
    frames = frames + 1
    if not done and frames == 300 then      -- ~5 s at 60 fps
        local ok, err = pcall(pass)          -- do the real work here, once
        if not ok then add("pass error: " .. tostring(err)) end
    end
    if type(original) == "function" then return original(...) end
end)
```

Note the guard `if type(original) == "function"` — a loader and a probe both wrapping `update` must not
break each other's chain.

---

## 5. Build and verification pipeline (all of it exists in `boot-probe/`)

| step | tool | what it refuses |
|---|---|---|
| syntax | `tools/lua51_check.py <file>` | anything stock 5.1 will not compile |
| dialect lint | `tools/lua51_check.py --lint <file>` | `ffi.`, `bit.`, `jit.`, `table.new/clear`, `string.buffer`, `\x` escapes |
| resource id | `build_test_mod.py` | id is **derived** as `murmur64(module)`, never typed; a non-`mods/` path is refused |
| artifact | `build_test_mod.py` | reopens the built patch and compares id/type/payload byte for byte |
| install | `install_boot_probe.py --update [--extra-slot N --extra-dir D]` | every write is read back and md5-compared |
| offline rehearsal | `simulate_boot_probe.py` | runs the payload from the **built patch** under real 5.1 with a faked engine, so both branches (`can_get` true and false) are exercised without a game launch |
| in-game | — | one launch; then `tools/grab_logs.py --tag <tag>` archives before the next launch overwrites |

`--allow-lint` exists in `build_test_mod.py` and is only for loading a **known-bad** payload on purpose to
observe how it fails. It does not skip the syntax gate.

---

## 6. Do the old probes need redesigning?

Not all of them, and the answer is decidable per probe from its source — this is the verdict table from
scanning our own 22 patches (`tmp/survey_port.py`):

| class | what it uses | verdict | count in our set |
|---|---|---|---|
| data/definition mods | plain source, no VM-specific calls | **unchanged** - works as soon as a loader exists | 10 |
| logic with `bit`/`jit`/`\x` | mechanics, not capability | **mechanical port** - replace with arithmetic / remove / `\ddd` | 0 standalone |
| memory probes | `ffi`, `ReadProcessMemory` | **no port exists** - this VM cannot read memory; redesign the *question*, not the code | 7 |
| bytecode payloads (the loader family) | LuaJIT chunks | replaced wholesale by whatever ships next | 5 |

So: the probes that must be "redesigned" are exactly the ones whose **purpose** was memory access. Nothing
about how they are written will bring that back. Everything else is unchanged or a small edit.

And the measured behaviour to keep in mind: our old probes **do not crash** on this build — they load,
detect the missing capability, and disable themselves. Any claim that "the old probe fails" is wrong; it
succeeds at doing nothing, which is why it needs a log line when it does that.

---

## 7. ★ 多返回值必须整体捕获（这条坑过**两次**，每次白跑一轮实机）

| 次 | 版本 | 症状 | 真相 |
|---|---|---|---|
| 1 | routes 1.8.0 | 日志打出 `levels[1]: units=true` | 把 `invoke()` 的**第二个返回值**（成功标志）当成单位数打印 |
| 2 | routes 1.9.0 | 七次 `package.loadlib` 全 `pcall_ok=true, err=nil`，**连不存在的模块也一样** | **Lua 5.1 的 `package.loadlib` 失败时不抛错，它返回 `nil, <错误文本>`** —— 错误文本是第三个返回值，被 `local ok, value = pcall(...)` 截掉了 |

**规则**：

```lua
-- ✗ 把后面几个返回值全丢掉
local ok, value = pcall(f, ...)

-- ✓ 整体捕获，再按位置取
local res = {pcall(f, ...)}     -- res[1]=ok, res[2]=第一返回值, res[3]=第二返回值
```

已知会返回**多个值**、且第二个值才是答案的接口：

- `package.loadlib` → `nil, message`（失败时**不抛错**）
- `loadstring` → `nil, message`（同上，PROBE-AUTHORING §1 已记）
- 本项目自己的 `invoke()` → `value, ok`

推论：**"引擎没报错"不能当作"调用成功"**。`pcall_ok=true` 只说明没抛 Lua 错误，
真正的信息可能在后一个返回值里 —— 这也是为什么 `Network.is_used()` 那次崩溃反而是干净的：
它**没有返回值可丢**。
