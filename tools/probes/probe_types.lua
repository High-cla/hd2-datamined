-- probe_types 1.0.0 — 批量问 Network.object_info，把「类型名 → 字段表」整张地图打出来
--
-- WHY: 上一版（probe_repl v1.2.0）在 `game_object_field(session, 0, "0xcd889dbc")` 上又崩了一次。
-- 那个调用已经带 0x 前缀、字段也在 schema 里、类型是 1/32（最安全的整数）—— 仍然崩 ⇒
-- 问题不在字段 id 格式，而在 goid 或参数形态本身。HD2 HUD+ 0.5.3 的 README 自己写着
-- "尚未进行当前游戏显示、多人稳定性验收"，所以它的调用约定**不能当已证事实**。
--
-- 这一版只做**已经两次证明安全**的那一半：boot 时（不需要进任务、不需要 session）
-- 对一批类型名逐个调用 `Network.object_info(name)`，把返回的字段表整张打出来。
--   * 不碰 GameSession 的任何函数
--   * 不碰 game_object_field / _batched
--   * 不需要每帧钩子
-- ⇒ 零崩溃面。产出是一张「类型名 → 字段 id/type/bits/min/max」的运行时反射字典。
--
-- 类型名来源：HD2 HUD+ 的 `Repair.allowed_types`（224）+ `GeneratedCommon` 里的 `call` 值（238），
-- 由 build.py 以 `TYPES` 上值注入。

local SINK = "TypeSchema.log"
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

add("")
add("===== probe_types 1.0.0 =====")

local SR = type(stingray) == "table" and stingray or nil
if not SR then add("ABORT: no stingray"); flush(); return { ok = false } end
local Net = rawget(SR, "Network")
if type(Net) ~= "table" or type(rawget(Net, "object_info")) ~= "function" then
    add("ABORT: no Network.object_info"); flush(); return { ok = false } end

local names = (type(TYPES) == "table" and #TYPES > 0) and TYPES or { "un6y1d" }
add("candidates = " .. #names)

local resolved, failed, total_fields = 0, 0, 0
local field_lines = 0
local FIELD_LINE_CAP = 4000          -- 防御性上限，避免日志爆掉

for index = 1, #names do
    local name = names[index]
    local ok, info = pcall(Net.object_info, name)
    if ok and type(info) == "table" and type(info.fields) == "table" and #info.fields > 0 then
        resolved = resolved + 1
        total_fields = total_fields + #info.fields
        local parts = {}
        for i = 1, #info.fields do
            local f = info.fields[i]
            if type(f) == "table" then
                local bits = f.bits and ("/" .. tostring(f.bits)) or ""
                local rng = ""
                if f.min ~= nil or f.max ~= nil then
                    rng = ("[%s,%s]"):format(tostring(f.min), tostring(f.max))
                end
                parts[#parts + 1] = ("%s:t%s%s%s"):format(tostring(f.id), tostring(f.type), bits, rng)
            end
        end
        if field_lines < FIELD_LINE_CAP then
            add(("%s n=%d | %s"):format(tostring(name), #info.fields, table.concat(parts, " ")))
            field_lines = field_lines + 1
        end
    else
        failed = failed + 1
        if failed <= 40 then
            add(("MISS %s  (%s)"):format(tostring(name), ok and "not-a-table" or tostring(info)))
        end
    end
    if index % 50 == 0 then
        add(("... %d/%d done, resolved=%d, fields=%d"):format(index, #names, resolved, total_fields))
        flush()
    end
end

add(("SUMMARY candidates=%d resolved=%d miss=%d total_fields=%d")
    :format(#names, resolved, failed, total_fields))
add("===== probe_types 1.0.0 end =====")
flush()
return { ok = true, resolved = resolved }
