-- probe_resovr 1.2.0 — set_resource_override 对非 lua 类型到底生效吗（这次在任务内测）
--
-- WHY THIS VERSION EXISTS
--   v1.0.0 (one launch) crashed inside the first non-lua case; the log proved the "lua" oracle
--   but the material case never flushed, so the guilty call was unknown.
--   v1.1.0 (stepwise, one launch) did NOT crash and produced a decisive-looking but useless
--   reading: can_get("material", <hash-verified real path>) was already false at boot, and
--   can_get cannot see a type it returns false for -- so the post-override false meant nothing.
--   It also showed set_resource_override accepts a *garbage* type string and returns nil, so
--   "the call succeeded" is not evidence of anything.
--
--   v1.2.0 fixes the oracle problem by moving the non-lua test INTO A MISSION, where the art
--   bundles are actually mounted. Same structure otherwise: every call is bracketed by a marker
--   that is written+closed to disk before the call runs, so a hard crash names the guilty call.
--
-- Answer matrix this run produces
--   (a) in-mission can_get(material, REAL) = false          -> can_get simply does not index
--                                                             non-lua types; the axis stays unmeasured
--   (b) in-mission can_get(material, REAL) = true           -> the boot-time false was "not mounted";
--        and then can_get(material, ALIAS) after override    -> decides whether the override works
--   (c) set_resource_override raises for material/texture   -> clean "unsupported" verdict

local SELF = "mods/auto/5"
local SINK = "ResOvrTypes.log"
local lines = {}

local function add(line) lines[#lines + 1] = tostring(line) end

local function flush()
    if #lines == 0 then return end
    local path
    if type(os) == "table" and type(os.getenv) == "function" then
        local ok, base = pcall(os.getenv, "LOCALAPPDATA")
        if ok and type(base) == "string" and base ~= "" then
            path = base .. "\\CowboyBingus\\Helldivers2\\Logs\\" .. SINK
        end
    end
    local batch = lines
    lines = {}
    if not path or type(io) ~= "table" then return end
    local ok, handle = pcall(io.open, path, "a")
    if not ok or not handle then return end
    pcall(handle.write, handle, table.concat(batch, "\n") .. "\n")
    pcall(handle.close, handle)
end

local function mark(text) add(text); flush() end

local function step(label, fn, ...)
    mark(">>> BEFORE " .. label)
    local r = { pcall(fn, ...) }
    if r[1] then
        mark(string.format("<<< AFTER  %-56s OK   ret=%s", label, tostring(r[2])))
    else
        mark(string.format("<<< AFTER  %-56s LUA-ERR  %s", label, tostring(r[2])))
    end
    return r[1], r[2]
end

mark("")
mark("===== probe_resovr 1.2.0 | required as " .. SELF .. " =====")

local SR = type(stingray) == "table" and stingray or nil
if not SR then mark("ABORT: no stingray"); return { ok = false } end
local app = rawget(SR, "Application")
if type(app) ~= "table" then mark("ABORT: no Application"); return { ok = false } end
if type(app.can_get) ~= "function" then mark("ABORT: no can_get"); return { ok = false } end

local LUA_REAL  = "core/wwise/lua/wwise_bank_reference"
local MAT_REAL  = "content/art_shared/base_shaders/nature/terrain_parent_material"
local TEX_REAL  = "content/env_shared/assets/terrain_materials/textures/generic_bug_acid_displacement.tga"
local LUA_ALIAS = "dsh/res/ovr/alias_lua"
local MAT_ALIAS = "dsh/res/ovr/alias_material"
local TEX_ALIAS = "dsh/res/ovr/alias_texture"

local function can_get(kind, name)
    return (select(2, pcall(app.can_get, kind, name)))
end

local function can_get_text(kind, name)
    local ok, value = pcall(app.can_get, kind, name)
    if not ok then return "ERR(" .. tostring(value) .. ")" end
    if value == true then return "true" end
    if value == false then return "false" end
    return "other(" .. tostring(value) .. ")"
end

-- ---------------------------------------------------------------- 0) 口径校准（boot 就能做）
mark("--- (0) lua control: the oracle must reflect overrides for lua ---")
mark("  can_get(lua, REAL)          = " .. can_get_text("lua", LUA_REAL))
if can_get("lua", LUA_REAL) == true then
    step("set_resource_override(lua, ALIAS, REAL)", app.set_resource_override, "lua", LUA_ALIAS, LUA_REAL)
    mark("  can_get(lua, ALIAS) after   = " .. can_get_text("lua", LUA_ALIAS) .. "   <== must be true")
    step("clear_resource_override(lua, ALIAS)", app.clear_resource_override, "lua", LUA_ALIAS)
    mark("  can_get(lua, ALIAS) cleared = " .. can_get_text("lua", LUA_ALIAS))
else
    mark("  ABORT control: the lua oracle is not even true; run is void")
end

-- ---------------------------------------------------------------- 1) boot 时刻的非 lua 读数
mark("--- (1) boot-time reading for the non-lua types (expected false: bundles not mounted) ---")
mark("  can_get(material, REAL)     = " .. can_get_text("material", MAT_REAL))
mark("  can_get(texture,  REAL)     = " .. can_get_text("texture", TEX_REAL))
mark("  (a false here is NOT evidence against the override -- see the deferred section)")

-- ---------------------------------------------------------------- 2) 每帧钩子：任务内再测
local FRAME_LIMIT = 20000        -- 约 5.5 分钟后放弃
local RETRY_EVERY = 120          -- 约 2 s 重试一次
local pending = true
local frames = 0
local next_try = 0
local tries = 0
local prev_update = rawget(_G, "update")
local installed = type(prev_update) == "function"

-- 返回 true = 这次真正做完了判定（成功或确定失败），false = 条件还没到，等下一轮
local function one_attempt()
    tries = tries + 1
    local mat_now = can_get_text("material", MAT_REAL)
    local tex_now = can_get_text("texture", TEX_REAL)
    local ready = (mat_now == "true") or (tex_now == "true")
    if not ready then
        if tries <= 3 then
            mark("attempt " .. tries .. ": non-lua real paths still invisible "
                 .. "(material=" .. mat_now .. ", texture=" .. tex_now .. ") -- still in the ship?")
        end
        return false
    end

    mark("--- (2) IN-MISSION re-test --- attempt " .. tries .. ", frame " .. frames)
    mark("  can_get(material, REAL) = " .. mat_now)
    mark("  can_get(texture,  REAL) = " .. tex_now)
    mark("  => the boot-time false was 'not mounted', not 'not supported'")

    if mat_now == "true" then
        mark("  can_get(material, ALIAS) before = " .. can_get_text("material", MAT_ALIAS))
        step("set_resource_override(material, ALIAS, REAL)", app.set_resource_override, "material", MAT_ALIAS, MAT_REAL)
        mark("  can_get(material, ALIAS) after  = " .. can_get_text("material", MAT_ALIAS) .. "   <== DECISIVE")
        step("clear_resource_override(material, ALIAS)", app.clear_resource_override, "material", MAT_ALIAS)
        mark("  can_get(material, ALIAS) cleared= " .. can_get_text("material", MAT_ALIAS))
    end
    if tex_now == "true" then
        mark("  can_get(texture, ALIAS) before = " .. can_get_text("texture", TEX_ALIAS))
        step("set_resource_override(texture, ALIAS, REAL)", app.set_resource_override, "texture", TEX_ALIAS, TEX_REAL)
        mark("  can_get(texture, ALIAS) after  = " .. can_get_text("texture", TEX_ALIAS) .. "   <== DECISIVE")
        step("clear_resource_override(texture, ALIAS)", app.clear_resource_override, "texture", TEX_ALIAS)
        mark("  can_get(texture, ALIAS) cleared= " .. can_get_text("texture", TEX_ALIAS))
    end
    mark("--- (2) done ---")
    return true
end

if installed then
    rawset(_G, "update", function(...)
        frames = frames + 1
        if pending and frames >= next_try then
            local ok_call, finished = pcall(one_attempt)
            local done = (ok_call == true) and (finished == true)
            if done then
                pending = false
            elseif frames >= FRAME_LIMIT then
                pending = false
                mark("VERDICT(a) GAVE UP: non-lua real paths never became visible in "
                     .. FRAME_LIMIT .. " frames / " .. tries .. " attempts")
                mark("  => can_get does not index non-lua types; the override question stays UNMEASURED by this oracle")
            else
                next_try = frames + RETRY_EVERY
            end
        end
        return prev_update(...)
    end)
    mark("per-frame hook installed; waiting until a non-lua real path becomes visible "
         .. "(retry every " .. RETRY_EVERY .. " frames, give up at " .. FRAME_LIMIT .. ")")
else
    mark("WARNING: global update was not a function; cannot defer to a mission")
end

mark("===== probe_resovr 1.2.0 boot section done =====")
return { ok = true }
