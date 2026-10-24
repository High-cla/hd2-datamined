-- probe_repl 1.0.0 — 只读侦察「网络复制层」：Network.object_info + GameSession
--
-- QUESTION: our HUD work only ever walked main_world() -> unit -> component, which by
-- construction cannot see other players (a remote player is not a locally simulated unit).
-- HD2 HUD+ 0.5.3 reads the *replication layer* instead:
--     stingray.Network.object_info(type_name)        -> { fields = [ {id="8 hex", type, bits, min, max} ] }
--     stingray.GameSession.game_object_field(session, goid, "<field id>")
--     stingray.GameSession.game_object_field_batched(session, goid, out)
--     stingray.GameSession.objects_owned_by(session, peer) / peers / game_object_is_type / game_object_exists
--
-- This probe asks ONE question: are those calls alive on build 26088801, and what do they return?
-- It is read-only on the game state: no set_game_object_field, no create/destroy_game_object.
--
-- Timing: at boot there is no game session yet, so the schema part runs at boot and the
-- object-read part is deferred to the first frame where Network.game_session() is non-nil.
-- The deferral uses a per-frame hook obtained by WRAPPING the global `update` that our
-- patch_0 (BootProbe) installed -- modules are required after that, so this is safe.
--
-- Every step writes+flushes a marker BEFORE the call, so a hard crash still names the call.

local SELF = "mods/auto/5"
local SINK = "ReplProbe.log"
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
        mark(string.format("<<< AFTER  %-56s OK   %s", label, tostring(r[2])))
    else
        mark(string.format("<<< AFTER  %-56s LUA-ERR  %s", label, tostring(r[2])))
    end
    return r[1], r[2]
end

local function type_of(t, key)
    return type(t) == "table" and type(rawget(t, key)) or "no-table"
end

local function describe(value)
    if value == nil then return "nil" end
    local kind = type(value)
    if kind == "userdata" then
        local ok, shown = pcall(tostring, value)
        return "userdata(" .. (ok and shown or "?") .. ")"
    end
    if kind == "number" or kind == "string" or kind == "boolean" then
        return kind .. "(" .. tostring(value) .. ")"
    end
    if kind == "table" then
        local n = 0
        for k in pairs(value) do n = n + 1 if n > 999 then break end end
        return "table(keys=" .. tostring(n) .. ")"
    end
    return kind
end

mark("")
mark("===== probe_repl 1.0.0 | required as " .. SELF .. " =====")

local SR = type(stingray) == "table" and stingray or nil
mark("stingray = " .. type(stingray))
if not SR then mark("ABORT: no stingray"); return { ok = false } end

local Net, GS = rawget(SR, "Network"), rawget(SR, "GameSession")
mark(string.format("Network=%s(%s keys)  GameSession=%s(%s keys)",
    type(Net), type(Net) == "table" and tostring((function() local n=0 for _ in pairs(Net) do n=n+1 end return n end)()) or "-",
    type(GS), type(GS) == "table" and tostring((function() local n=0 for _ in pairs(GS) do n=n+1 end return n end)()) or "-"))
mark("  Network.game_session   = " .. type_of(Net, "game_session"))
mark("  Network.peer_id        = " .. type_of(Net, "peer_id"))
mark("  Network.object_info    = " .. type_of(Net, "object_info"))
mark("  Network.message_info   = " .. type_of(Net, "message_info"))
mark("  GS.game_object_field   = " .. type_of(GS, "game_object_field"))
mark("  GS.game_object_field_batched = " .. type_of(GS, "game_object_field_batched"))
mark("  GS.objects_owned_by    = " .. type_of(GS, "objects_owned_by"))
mark("  GS.game_object_is_type = " .. type_of(GS, "game_object_is_type"))
mark("  GS.peers               = " .. type_of(GS, "peers"))

-- ---------------------------------------------------------------- 1) boot 时刻能问 schema 吗
-- 类型名是乱码串（HD2 HUD+ 的 224 条 allowlist），player 那条是 "un6y1d"
local NAMES = { "un6y1d", "0bq5t3", "aacde2e", "baj_bt" }
local schema = {}
mark("--- (1) Network.object_info at boot ---")
for _, name in ipairs(NAMES) do
    if type(Net) == "table" and type(rawget(Net, "object_info")) == "function" then
        mark(">>> BEFORE object_info(\"" .. name .. "\")")
        local ok, info = pcall(Net.object_info, name)
        if ok and type(info) == "table" then
            local nfields = type(info.fields) == "table" and #info.fields or -1
            mark(string.format("<<< AFTER  object_info(%-9s) OK   nfields=%s", "\"" .. name .. "\"", tostring(nfields)))
            schema[name] = info
            if nfields > 0 then
                for i = 1, math.min(6, nfields) do
                    local f = info.fields[i]
                    mark(string.format("      field[%d] id=%s type=%s bits=%s min=%s max=%s",
                        i, tostring(f and f.id), tostring(f and f.type), tostring(f and f.bits),
                        tostring(f and f.min), tostring(f and f.max)))
                end
            end
        else
            mark(string.format("<<< AFTER  object_info(%-9s) %s   %s", "\"" .. name .. "\"",
                ok and "not-a-table" or "LUA-ERR", tostring(info)))
        end
    end
end

local sess_boot_ok, sess_boot = pcall(function() return Net and Net.game_session and Net.game_session() end)
mark("Network.game_session() at boot = " .. tostring(sess_boot_ok) .. "/" .. describe(sess_boot))

-- ---------------------------------------------------------------- 2) 每帧钩子：等到有 session 再读对象
local FRAME_LIMIT = 20000          -- ~5.5 分钟（60 fps）后放弃
local RETRY_EVERY = 120            -- 约 2 s 重试一次
local pending = true
local frames = 0
local next_try = 0
local tries = 0
local prev_update = rawget(_G, "update")
local installed = type(prev_update) == "function"

-- 返回 true = 拿到至少一个 owned 对象（= 真的在任务里），false = 还没到时候，等下一轮
local function one_attempt()
    tries = tries + 1
    local ok, session = pcall(function() return Net.game_session() end)
    if not ok or session == nil then return false end
    local okp, peer = pcall(function() return Net.peer_id() end)
    if not okp or peer == nil then return false end

    local ids = {}
    if type(GS) == "table" and type(rawget(GS, "objects_owned_by")) == "function" then
        local oko, owned = pcall(GS.objects_owned_by, session, peer)
        if oko and type(owned) == "table" then
            for _, id in pairs(owned) do ids[#ids + 1] = id end
        end
    end
    if #ids == 0 then
        if tries <= 3 then
            mark("attempt " .. tries .. ": session ok but no owned object yet (still in the ship?)")
        end
        return false
    end

    mark("--- (2) in-session reads --- attempt " .. tries .. ", frame " .. frames ..
         ", owned objects = " .. #ids)
    mark("peer_id() = " .. describe(peer))
    if type(GS) == "table" and type(rawget(GS, "peers")) == "function" then
        local okr, peers = pcall(GS.peers, session)
        local count = 0
        if okr and type(peers) == "table" then for _ in pairs(peers) do count = count + 1 end end
        mark(string.format("GS.peers(session) = %s/%s  count=%d", tostring(okr), describe(peers), count))
    end
    mark("GS.objects_owned_by(session, my peer) = ok, count=" .. tostring(#ids))

    -- ⚠ 上一局崩在这里：`game_object_field(session, 0, "a3df1643")`。
    -- 那次传的是 **schema 里的第一号字段**（id=a3df1643, type=0, bits=nil）且**没带 0x 前缀**。
    -- 三个可疑点：(a) 少 0x；(b) type=0 是引擎没实现的类型；(c) goid=0 是否合法。
    -- 这一版把 (a)(b) 都堵掉：一律 "0x%08x"，且**只读在 schema 里存在、类型是 1/2/3 的字段**。
    -- 仍然无法排除 (c)，所以只试最多 3 次，按"最可能是普通数值"的顺序。
    local ok_info, live_info = pcall(function() return Net.object_info("un6y1d") end)
    local by_id, picks = {}, {}
    if ok_info and type(live_info) == "table" and type(live_info.fields) == "table" then
        for i = 1, #live_info.fields do
            local f = live_info.fields[i]
            if type(f) == "table" and type(f.id) == "string" then
                by_id[string.lower(f.id)] = f
            end
        end
        mark("in-session object_info(\"un6y1d\") = " .. #live_info.fields .. " fields")
        -- 优先 HUD+ 自己用过的那个（cd889dbc，在 un6y1d 的 field[3]，type=1 bits=32）
        for _, want in ipairs({ "cd889dbc", "3b12bd49" }) do
            local f = by_id[want]
            if f then picks[#picks + 1] = { id = want, desc = f }
            else mark("  candidate " .. want .. " not in this type's schema -> skipped") end
        end
        -- 再补一个纯数值型字段（type 1/2/3）
        for i = 1, #live_info.fields do
            if #picks >= 3 then break end
            local f = live_info.fields[i]
            local t = type(f) == "table" and f.type or nil
            if type(f) == "table" and type(f.id) == "string"
               and (t == 1 or t == 2 or t == 3)
               and not (by_id[string.lower(f.id)] == nil) then
                local dup = false
                for _, p2 in ipairs(picks) do if p2.id == f.id then dup = true end end
                if not dup and f.id ~= "cd889dbc" and f.id ~= "3b12bd49" then
                    picks[#picks + 1] = { id = f.id, desc = f }
                end
            end
        end
    else
        mark("in-session object_info failed: " .. tostring(ok_info) .. "/" .. tostring(live_info))
    end

    for _, pick in ipairs(picks) do
        local d = pick.desc
        mark(string.format("  trying field %s (type=%s bits=%s min=%s max=%s)",
            pick.id, tostring(d.type), tostring(d.bits), tostring(d.min), tostring(d.max)))
        local okf, value = step("GS.game_object_field(session, player, \"0x" .. pick.id .. "\")",
                                GS.game_object_field, session, player_goid, "0x" .. pick.id)
        if not okf then
            mark("     -> the engine raised; stopping before any further read")
            mark("--- (2) done (aborted) ---")
            return true
        end
        mark("     value = " .. describe(value))
    end

    if type(GS) == "table" and type(rawget(GS, "game_object_field_batched")) == "function" then
        mark(">>> BEFORE GS.game_object_field_batched(session, player, {})")
        local okb, batch = pcall(GS.game_object_field_batched, session, player_goid, {})
        mark(string.format("<<< AFTER  game_object_field_batched = %s/%s", tostring(okb), describe(batch)))
        if okb and type(batch) == "table" then
            local n = 0
            for k, v in pairs(batch) do
                n = n + 1
                if n <= 8 then mark("      batch[" .. tostring(k) .. "] = " .. describe(v)) end
            end
            mark("      batch keys = " .. tostring(n))
        end
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
                mark("GAVE UP after " .. FRAME_LIMIT .. " frames / " .. tries .. " attempts (no owned object seen)")
            else
                next_try = frames + RETRY_EVERY
            end
        end
        return prev_update(...)
    end)
    mark("per-frame hook installed (wrapping global update); retry every " .. RETRY_EVERY ..
         " frames, give up at " .. FRAME_LIMIT)
else
    mark("WARNING: global update was not a function; the in-session part cannot be deferred")
end

mark("===== probe_repl 1.0.0 boot section done =====")
return { ok = true }
