-- probe_read 1.4.0 — 秒表式定点观察：只盯 avatar 复制集尾部 9 个座位（64..72）
--
-- 由来（run7）：160 秒监视里 player 的 36 个字段**一处都没变**，
-- 唯一变化是 avatar 的 seat 70 `a33df340`（t1 b32）0 -> 1 -> 0，持续约 24 秒。
-- HUD+ 的 8 个文件（boot + 7 frag）里 `a33df340` 出现 **0 次**，没有语义可抄。
-- ⇒ 只能靠受控动作实验把它的语义钉下来。
--
-- 本版做法：
--   · 每 30 帧（0.5 s）静默采一次 avatar 的 batched（9 个座位）
--   · 每 600 帧（10 s）打一条 TICK 时间线（供把动作时间对上来）
--   · 任何座位发生标量变化 -> 打一条 CHG，**同时打出当时全部 9 个座位 + health**
--   · avatar 句柄失效时，用 player.baegche 重绑（复活/换 avatar 不会中断观察）
--   · 结束（时长到 / session 变）时打一张「全部变化」汇总
--
-- 用户脚本（各隔 15 秒）：① 举枪瞄准 ② 蹲下 ③ 使用治疗剂
--   —— 若 24 秒的「1」是被击倒，这三个都不会触发，那反而把范围缩到「战斗/受击相关」。

local SELF = "mods/auto/5"
local VERSION = "1.4.0"
local SINK = "ReadProbe.log"
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

local function describe(value)
    if value == nil then return "nil" end
    local kind = type(value)
    if kind == "number" or kind == "string" or kind == "boolean" then
        return tostring(value)
    end
    if kind == "userdata" then
        local ok, shown = pcall(tostring, value)
        return "ud(" .. (ok and shown or "?") .. ")"
    end
    if kind == "table" then
        local n = 0
        for _ in pairs(value) do n = n + 1 if n > 999 then break end end
        return "t[" .. tostring(n) .. "]"
    end
    return kind
end

local function scalar(v)
    local t = type(v)
    return t == "number" or t == "boolean" or t == "string"
end

local function norm_id(id)
    if type(id) ~= "string" then return nil end
    local hex = string.lower(id)
    hex = string.gsub(hex, "^0x", "")
    hex = string.gsub(hex, "^0+", "")
    if hex == "" then hex = "0" end
    while #hex < 8 do hex = "0" .. hex end
    return hex
end

local GUARD = "__probe_read_instance"
if rawget(_G, GUARD) ~= nil then
    mark("(second load) 已有实例在跑（" .. tostring(rawget(_G, GUARD)) ..
         "），本次加载不安装钩子")
    return { ok = true, duplicate = true }
end
rawset(_G, GUARD, VERSION)

mark("")
mark("===== probe_read " .. VERSION .. " | required as " .. SELF .. " =====")

local SR = type(stingray) == "table" and stingray or nil
if not SR then mark("ABORT: no stingray") return { ok = false } end
local Net, GS = rawget(SR, "Network"), rawget(SR, "GameSession")
mark(string.format("Network=%s  GameSession=%s", type(Net), type(GS)))

local PLAYER_TYPE, AVATAR_TYPE = "un6y1d", "gl7xl2w"
local row_at, nfields = {}, {}

local function load_schema(typename)
    if type(Net) ~= "table" or type(rawget(Net, "object_info")) ~= "function" then return nil end
    local ok, info = pcall(Net.object_info, typename)
    if not ok or type(info) ~= "table" or type(info.fields) ~= "table" then
        mark("object_info(" .. typename .. ") FAILED: " .. describe(info))
        return nil
    end
    local by_seat, n = {}, 0
    for i = 1, #info.fields do
        local f = info.fields[i]
        if type(f) == "table" and type(f.id) == "string" then
            by_seat[i] = f
            n = n + 1
        end
    end
    row_at[typename], nfields[typename] = by_seat, n
    mark(string.format("object_info(\"%s\") = %d fields", typename, n))
    return by_seat
end

load_schema(PLAYER_TYPE)
load_schema(AVATAR_TYPE)

-- 焦点座位：avatar 复制集尾部 9 个
local SEATS = { 64, 65, 66, 67, 68, 69, 70, 71, 72 }
mark("--- 焦点座位（id 来自实机 object_info）---")
for _, s in ipairs(SEATS) do
    local row = row_at[AVATAR_TYPE] and row_at[AVATAR_TYPE][s]
    mark(string.format("  seat %d  id=%s  type=%s  bits=%s%s",
        s, row and tostring(row.id) or "?", row and tostring(row.type) or "?",
        row and tostring(row.bits) or "?",
        (row and row.id == "dae681f4") and "   {gls4w9b: 30=船上 100=地面}" or ""))
end

local passes, ship_passes, finished = 0, 0, false
local FRAME_LIMIT = 200000
local HEARTBEAT = 3000
local RETRY_EVERY = 180
local RETRY_SHIP = 900
local SAMPLE_EVERY = 30                 -- 0.5 s
local TICK_EVERY = 600                  -- 10 s 时间线
local WATCH_FRAMES = 18000              -- 5 分钟
local MAX_CHG = 200
local frames, next_try, tries = 0, 0, 0
local owned_set = {}

local WATCH = {
    active = false, session = nil, player = nil, avatar = nil,
    prev = nil, start = 0, changes = 0, samples = 0, health = nil,
    next_frame = 0, next_tick = 0, log = {},
}

-- ------------------------------------------------------------------ 读取（静默）
local function guard_ok(session, goid, typename)
    if type(goid) ~= "number" or goid == 32767 or owned_set[goid] ~= true then return false end
    local oke, alive = pcall(GS.game_object_exists, session, goid)
    if not oke or alive ~= true then return false end
    local okt, is = pcall(GS.game_object_is_type, session, goid, typename)
    return okt and is == true
end

local function quiet_batch(session, goid, typename)
    if not guard_ok(session, goid, typename) then return nil end
    local ok, batch = pcall(GS.game_object_field_batched, session, goid, {})
    if ok and type(batch) == "table" then return batch end
    return nil
end

local function quiet_read(session, goid, typename, name)
    if not guard_ok(session, goid, typename) then return nil end
    local ok, v = pcall(GS.game_object_field, session, goid, name)
    if ok then return v end
    return nil
end

-- 带日志版（只在一次性基线与异常时用）
local function loud_read(session, goid, typename, name)
    mark(">>> BEFORE game_object_field(" .. tostring(goid) .. ", " .. name .. ")")
    local ok, v = pcall(GS.game_object_field, session, goid, name)
    if ok then
        mark(string.format("<<< AFTER  OK %s", describe(v)))
    else
        mark(string.format("<<< AFTER  LUA-ERR %s", tostring(v)))
    end
    return ok, v
end

local function fmt_seats(batch)
    local parts = {}
    for _, s in ipairs(SEATS) do
        local v = batch and batch[s]
        if v ~= nil then parts[#parts + 1] = tostring(s) .. "=" .. describe(v) end
    end
    return table.concat(parts, " ")
end

local function rel_seconds()
    return (frames - WATCH.start) / 60
end

-- ------------------------------------------------------------------ 监视
local function rebind(session)
    if type(WATCH.player) ~= "number" then return false end
    local ok, av = pcall(GS.game_object_field, session, WATCH.player, "baegche")
    if not ok or type(av) ~= "number" or av == 32767 then return false end
    if av == WATCH.avatar then return false end
    if owned_set[av] ~= true then
        mark(string.format("[REBIND] player.baegche = %d 但不在 owned 列表里，放弃重绑", av))
        return false
    end
    local okt, is = pcall(GS.game_object_is_type, session, av, AVATAR_TYPE)
    if not okt or is ~= true then return false end
    mark(string.format("[REBIND] avatar %d -> %d（复活/重建）", WATCH.avatar, av))
    WATCH.avatar = av
    WATCH.prev = nil
    return true
end

local function watch_tick()
    WATCH.samples = WATCH.samples + 1
    local oks, session = pcall(function() return Net.game_session() end)
    if not oks or session ~= WATCH.session then
        mark("[WATCH] session 变了或没了 -> 结束")
        return false
    end

    local batch = quiet_batch(session, WATCH.avatar, AVATAR_TYPE)
    if batch == nil then
        if not rebind(session) then
            mark(string.format("[WATCH] avatar %s 取不到且无法重绑（t=%.1fs）",
                tostring(WATCH.avatar), rel_seconds()))
            return true
        end
        batch = quiet_batch(session, WATCH.avatar, AVATAR_TYPE)
        if batch == nil then return true end
    end

    local health = quiet_read(session, WATCH.avatar, AVATAR_TYPE, "health")

    -- 变化检测（只认标量）
    if WATCH.prev ~= nil then
        local ch = {}
        for _, s in ipairs(SEATS) do
            local a, b = WATCH.prev[s], batch[s]
            if scalar(a) and scalar(b) and a ~= b then
                ch[#ch + 1] = string.format("%d: %s->%s", s, tostring(a), tostring(b))
            end
        end
        if #ch > 0 and WATCH.changes < MAX_CHG then
            WATCH.changes = WATCH.changes + 1
            local line = string.format("[CHG t=%.1fs w=%.1fs f=%d] %s | %s | health=%s",
                frames / 60, rel_seconds(), frames, table.concat(ch, ", "),
                fmt_seats(batch), describe(health))
            mark(line)
            WATCH.log[#WATCH.log + 1] = line
        end
    end
    WATCH.prev = batch
    WATCH.health = health

    if frames >= WATCH.next_tick then
        mark(string.format("[TICK t=%.1fs w=%.1fs] %s | health=%s",
            frames / 60, rel_seconds(), fmt_seats(batch), describe(health)))
        WATCH.next_tick = frames + TICK_EVERY
    end

    if frames - WATCH.start >= WATCH_FRAMES then
        mark(string.format("[WATCH] 到达时长上限 %.0f 秒 -> 结束", WATCH_FRAMES / 60))
        return false
    end
    return true
end

local function watch_end(why)
    mark(string.format("[WATCH] 结束（%s）：采样 %d 次，变化 %d 次", why, WATCH.samples, WATCH.changes))
    for i = 1, #WATCH.log do mark("   " .. WATCH.log[i]) end
    WATCH.active = false
    finished = true
    rawset(_G, GUARD, VERSION .. " (done)")
    mark(string.format("========== DONE (passes=%d, ship=%d, samples=%d, changes=%d) ==========",
        passes, ship_passes, WATCH.samples, WATCH.changes))
end

-- ------------------------------------------------------------------ 一次性定位
local function one_attempt()
    tries = tries + 1

    local oks, session = pcall(function() return Net.game_session() end)
    if not oks or session == nil then mark("--- attempt " .. tries .. ": no game_session()") return false end
    local okp, peer = pcall(function() return Net.peer_id() end)
    if not okp or peer == nil then mark("--- attempt " .. tries .. ": no peer_id()") return false end
    if type(GS) ~= "table" or type(rawget(GS, "in_session")) ~= "function" then
        mark("--- attempt " .. tries .. ": no GS.in_session") return false
    end
    local oki, inside = pcall(GS.in_session, session)
    if not oki or inside ~= true then
        mark("--- attempt " .. tries .. ": in_session = " .. describe(inside)) return false
    end

    owned_set = {}
    local oko, owned = pcall(GS.objects_owned_by, session, peer)
    if not oko or type(owned) ~= "table" then
        mark("--- attempt " .. tries .. ": objects_owned_by = " .. describe(owned)) return false
    end
    local ids = {}
    for _, id in pairs(owned) do
        if type(id) == "number" then ids[#ids + 1] = id; owned_set[id] = true end
    end
    if #ids == 0 then mark("--- attempt " .. tries .. ": owned 空") return false end
    table.sort(ids)
    mark(string.format("--- attempt %d, frame %d: owned=%d  peer=%s", tries, frames, #ids, describe(peer)))

    local players = {}
    for _, goid in ipairs(ids) do
        local okt, is = pcall(GS.game_object_is_type, session, goid, PLAYER_TYPE)
        if okt and is == true then players[#players + 1] = goid end
    end
    if #players ~= 1 then
        mark("--- attempt " .. tries .. ": player 数 = " .. #players) return false
    end
    local player = players[1]

    local okr, avatar = loud_read(session, player, PLAYER_TYPE, "baegche")
    if not okr or type(avatar) ~= "number" then
        mark("--- attempt " .. tries .. ": baegche = " .. describe(avatar)) return false
    end
    if avatar == 32767 then
        mark("--- attempt " .. tries .. ": baegche == 32767 = 此刻无 avatar") return false
    end
    if owned_set[avatar] ~= true then
        mark("--- attempt " .. tries .. ": avatar " .. tostring(avatar) .. " 不在 owned 列表") return false
    end
    local okt, isavatar = pcall(GS.game_object_is_type, session, avatar, AVATAR_TYPE)
    if not okt or isavatar ~= true then
        mark("--- attempt " .. tries .. ": avatar 不是 " .. AVATAR_TYPE) return false
    end

    passes = passes + 1
    local okship, ship = loud_read(session, avatar, AVATAR_TYPE, "gls4w9b")
    local aboard = (okship and ship == 30)
    mark(string.format("========== PASS %d (frame %d, t=%.1fs) player=%d avatar=%d  gls4w9b=%s -> %s",
        passes, frames, frames / 60, player, avatar, describe(ship), aboard and "SHIP" or "GROUND"))

    if aboard then
        ship_passes = ship_passes + 1
        if ship_passes <= 2 then
            mark("   [SHIP] 在船上，等地面局（不在船上做观察）")
        end
        return false
    end

    -- 地面局：先做一次完整基线
    local base = quiet_batch(session, avatar, AVATAR_TYPE)
    if base == nil then
        mark("--- 基线 batched 失败，等下一轮")
        return false
    end
    mark("")
    mark("########## 观察开始（基线）##########")
    mark("[BASE t=" .. string.format("%.1fs", frames / 60) .. "] " .. fmt_seats(base) ..
         " | health=" .. describe(quiet_read(session, avatar, AVATAR_TYPE, "health")))
    -- 8 个已知名字字段（保持与历史 run 可比，一次性）
    for _, nm in ipairs({ "state", "motion_enabled", "rotation_enabled",
                          "health", "enabled_mask", "position" }) do
        local okv, v = loud_read(session, avatar, AVATAR_TYPE, nm)
        if not okv then mark("   " .. nm .. " 读取失败，继续") end
    end
    mark("########## 每 0.5 秒采样；每 10 秒一条 TICK；只在座位变化时打 CHG ##########")
    mark("  脚本：① 举枪瞄准 ② 蹲下 ③ 使用治疗剂（各隔 15 秒）")

    WATCH.active = true
    WATCH.session = session
    WATCH.player = player
    WATCH.avatar = avatar
    WATCH.prev = base
    WATCH.start = frames
    WATCH.next_frame = frames + SAMPLE_EVERY
    WATCH.next_tick = frames + TICK_EVERY
    WATCH.next_frame = frames + SAMPLE_EVERY
    return true
end

local prev_update = rawget(_G, "update")
if type(prev_update) == "function" then
    rawset(_G, "update", function(...)
        frames = frames + 1
        if not finished then
            if WATCH.active then
                if frames >= WATCH.next_frame then
                    local okc, keep = pcall(watch_tick)
                    if not okc then
                        mark("[WATCH] 采样抛错: " .. tostring(keep))
                        keep = true
                    end
                    if keep == false then
                        watch_end("会话或时长结束")
                    else
                        WATCH.next_frame = frames + SAMPLE_EVERY
                    end
                end
            elseif frames >= next_try then
                if (frames % HEARTBEAT) == 0 then
                    mark(string.format("... heartbeat frame %d, attempts %d, passes %d, ship %d",
                        frames, tries, passes, ship_passes))
                end
                local okc, done = pcall(one_attempt)
                if not okc then
                    mark("attempt raised: " .. tostring(done))
                    next_try = frames + RETRY_EVERY
                elseif done == true then
                    next_try = frames + 1
                elseif frames >= FRAME_LIMIT then
                    finished = true
                    rawset(_G, GUARD, VERSION .. " (gave-up)")
                    mark("GAVE UP after " .. FRAME_LIMIT .. " frames")
                else
                    next_try = frames + ((ship_passes > 0) and RETRY_SHIP or RETRY_EVERY)
                end
            end
        end
        return prev_update(...)
    end)
    mark(string.format("hook installed; sample every %d (%.1fs), tick every %d, watch %d frames (%.0fs)",
        SAMPLE_EVERY, SAMPLE_EVERY / 60, TICK_EVERY, WATCH_FRAMES, WATCH_FRAMES / 60))
else
    mark("WARNING: global update 不是函数，无法延迟到局内")
end

mark("===== probe_read " .. VERSION .. " boot section done =====")
return { ok = true }
