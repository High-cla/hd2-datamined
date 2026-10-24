#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_read.lua 的离线夹具（rehearsal）。

用真实 schema（从 type-schema-dictionary.json 取 un6y1d / gl7xl2w 的完整字段表）
伪造一个 stingray，驱动 probe_read 的每帧状态机，验证：

  S1 语法能过 Lua 5.1 解析器
  S2 主菜单态（no session）→ 只 bail，不调用任何读
  S3 船态（owned 为空）→ bail
  S4 飞船态（gls4w9b == 30）→ 标 [SHIP]，并继续等地面态
  S5 baegche == 32767（无 avatar 哨兵）→ bail 而不是把 32767 递进读取
  S6 地面态 → 走完全部闸门，单读 + batched 对位一致
  S7 全程不出现 LUA-ERR（说明每个引擎调用都在 pcall 里）
  S8 若把 goid 换成不在 owned 里的值，guarded_read 必须 REFUSED 而不是调用引擎

    python offline_test.py            # 跑全部用例
    python offline_test.py --keep     # 保留临时目录
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
DICT = pathlib.Path(r"D:\mod\recon-hudplus\type-schema-dictionary.json")
LUAJIT = r"C:\Users\Admin\LuaJIT\bin\luajit.exe"
WORK = HERE / "_offline"

PLAYER_TYPE, AVATAR_TYPE = "un6y1d", "gl7xl2w"
PROBE_PATH = HERE / "probe_read.lua"


def emit_schema() -> str:
    with open(DICT, encoding="utf-8") as fh:
        d = json.load(fh)
    out = ["local SCHEMAS = {}"]
    for tname in (PLAYER_TYPE, AVATAR_TYPE):
        tv = d["types"][tname]
        rows = []
        for f in tv["fields"]:
            rows.append('{id="%s",type=%s,bits=%s,min=%s,max=%s}' % (
                f["id"], f.get("type") if f.get("type") is not None else "nil",
                f.get("bits") if f.get("bits") is not None else "nil",
                '"%s"' % f["range"].split(",")[0] if f.get("range") else "nil",
                '"%s"' % f["range"].split(",")[1] if f.get("range") else "nil"))
        out.append("SCHEMAS[%r] = {fields={%s}}" % (tname, ",".join(rows)))
    return "\n".join(out) + "\n"


HARNESS = r"""
-- 离线夹具：驱动 probe_read 的每帧状态机
local real_os = os
local SCENARIO = ...
local SCHEMAS = {}
%(schema)s

local out_lines = {}
local function say(s) out_lines[#out_lines+1] = tostring(s); print('HARNESS: '..tostring(s)) end

-- ---- 场景状态机 -----------------------------------------------------------
-- phase 由外部驱动：每次 update 前 G.frame = 当前帧号
local G = {
  frame = 0,
  -- 场景脚本：给定帧号返回本帧的"世界状态"
}
local function world()
  local f = G.frame
  local s = SCENARIO
  if f < s.menu_until then
    return { sess = nil, owned = {} }
  elseif f < s.empty_until then
    return { sess = "SESSION", owned = {} }
  end
  local w = { sess = "SESSION", owned = {7, 8, 9} }
  local avatar_ok = f >= (s.avatar_at or 0)
  local ship_value = (f >= (s.ground_at or 1e9)) and 3 or 30
  if f >= (s.mutate_at or 1e9) then ship_value = 100 end
  local bag = (avatar_ok and 8) or 32767
  w.fields = {
    [7] = { baegche = bag },
    [8] = { gls4w9b = ship_value, state = 0, motion_enabled = true,
            rotation_enabled = true, health = 100, enabled_mask = 255,
            position = 42 },
    [9] = { enabled_mask = 1 },
  }
  w.types = { [7] = "%(player)s", [8] = "%(avatar)s", [9] = "e5j54r" }
  -- 换装对照测试：到 mutate_at 帧之后，player seat 20 从 55 变 56
  local mut = (f >= (s.mutate_at or 1e9))
  w.seat_extra = { [7] = { [20] = mut and 56 or 55 },
                    [8] = { [70] = mut and 1 or 0 } }
  return w
end

local W = { sess = nil, owned = {} }

-- 只读 API 的假实现
local calls = { field = 0, batched = 0, is_type = 0, exists = 0 }
local function batch_for(goid, passed)
  -- 复刻实机行为（run 4+5 观测）：
  --   gl7xl2w（avatar）= 只回**最后 9 个座位**
  --   un6y1d （player）= 回**全部**字段
  --   且引擎把传入表的键「带过去」（run5 E3：预置键原样保留）
  local tname = (W.types and W.types[goid]) or "%(avatar)s"
  local n = #SCHEMAS[tname].fields
  local bag = W.fields and W.fields[goid] or {}
  local out = {}
  if type(passed) == "table" then
    for k, v in pairs(passed) do out[k] = v end
  end
  local seats = %(seats)s
  local first = (tname == "%(avatar)s") and math.max(1, n - 8) or 1
  for i = first, n do out[i] = 0 end
  for name, value in pairs(bag) do
    local seat = seats[name]
    if seat and seat >= first then out[seat] = value end
  end
  for seat, value in pairs((W.seat_extra and W.seat_extra[goid]) or {}) do
    out[seat] = value
  end
  return out
end

_G.stingray = {
  Network = {
    game_session = function() return W.sess end,
    peer_id = function() return 1001 end,
    object_info = function(name) return SCHEMAS[name] end,
  },
  GameSession = {
    in_session = function(s) return s ~= nil and s == W.sess end,
    objects_owned_by = function(s, peer) return W.owned end,
    game_object_exists = function(s, id)
      calls.exists = calls.exists + 1
      for _, v in ipairs(W.owned) do if v == id then return true end end
      return false
    end,
    game_object_is_type = function(s, id, name)
      calls.is_type = calls.is_type + 1
      return (W.types and W.types[id]) == name
    end,
    game_object_field = function(s, id, fname)
      calls.field = calls.field + 1
      local bag = W.fields and W.fields[id]
      if type(bag) ~= "table" then return nil end
      return bag[fname]
    end,
    game_object_field_batched = function(s, id, out)
      calls.batched = calls.batched + 1
      return batch_for(id, out)
    end,
  },
}

-- 把日志重定向到临时目录（probe 用 os.getenv("LOCALAPPDATA")）
os = { getenv = function(k)
  if k == "LOCALAPPDATA" then return SCENARIO.root end
  return nil
end }
io = real_os and io or io   -- 保持真实 io

-- 假 update 供 probe 包裹
_G.update = function() end

local chunk = assert(loadfile(SCENARIO.probe))
local ok, err = chunk()
if not ok then say("PROBE LOAD FAILED: " .. tostring(err)) end

-- 双实例回归：模拟 BootProbe 把同一个模块 require 两遍（run 5 真实发生过）
if SCENARIO.double_load then
  local chunk2 = assert(loadfile(SCENARIO.probe))
  local ok2, err2 = chunk2()
  if not ok2 then say("PROBE LOAD FAILED (2nd): " .. tostring(err2)) end
  say("DOUBLE_LOAD_DONE")
end

-- 驱动
for f = 1, SCENARIO.frames do
  G.frame = f
  W = world()
  local okc, e = pcall(_G.update)
  if not okc then say("UPDATE RAISED at frame " .. f .. ": " .. tostring(e)) break end
end

os = real_os
return {
  field = calls.field, batched = calls.batched,
  is_type = calls.is_type, exists = calls.exists,
}
"""


def build_harness(scenario: dict, seats: dict) -> str:
    return HARNESS % {
        "schema": emit_schema(),
        "player": PLAYER_TYPE,
        "avatar": AVATAR_TYPE,
        "seats": "{" + ",".join('%s=%d' % (k, v) for k, v in seats.items()) + "}",
    }


def run_case(name: str, scenario: dict, seats: dict, expect: list[str],
             forbid: list[str], keep: bool, counts: dict[str, int] | None = None) -> bool:
    WORK.mkdir(exist_ok=True)
    case_dir = WORK / name
    if case_dir.exists():
        shutil.rmtree(case_dir)
    (case_dir / "CowboyBingus" / "Helldivers2" / "Logs").mkdir(parents=True)

    lua_path = case_dir / "harness.lua"
    lua_path.write_text(build_harness(scenario, seats), encoding="utf-8")

    # 场景参数通过第二个参数注入：把 harness 里的 `local SCENARIO = ...` 改成直读全局
    src = lua_path.read_text(encoding="utf-8")
    src = src.replace("local SCENARIO = ...", "local SCENARIO = SCENARIO_G")
    lua_path.write_text(src, encoding="utf-8")

    driver = case_dir / "drive.lua"
    sc = dict(scenario)
    sc["root"] = str(case_dir)
    sc["probe"] = str(PROBE_PATH)
    driver.write_text(
        "SCENARIO_G = {%s}\n"
        "local r = assert(loadfile(%r))()\n"
        "print(string.format('calls field=%%d batched=%%d is_type=%%d exists=%%d',\n"
        "  r.field, r.batched, r.is_type, r.exists))\n"
        % (",".join("%s=%s" % (k, json.dumps(v) if isinstance(v, (str, bool)) else v)
                    for k, v in sc.items()), str(lua_path)),
        encoding="utf-8")

    proc = subprocess.run([LUAJIT, str(driver)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(HERE))
    print(f"--- {name} ---")
    if proc.returncode != 0:
        print(f"  luajit exit={proc.returncode}\n  stderr: {proc.stderr.strip()[:2000]}")
        return False
    if proc.stdout.strip():
        print("  " + proc.stdout.strip().replace("\n", "\n  "))

    log = case_dir / "CowboyBingus" / "Helldivers2" / "Logs" / "ReadProbe.log"
    if not log.exists():
        print("  FAIL: 没有产生日志（probe 没跑到 flush 或路径不对）")
        return False
    text = log.read_text(encoding="utf-8", errors="replace")
    ok = True
    for pat, want in (counts or {}).items():
        got = len(re.findall(pat, text))
        mark_ch = "✓" if got == want else "✗"
        print(f"  {mark_ch} 计数 {pat!r} 期望 {want} 次 / 实际 {got} 次")
        ok = ok and got == want
    for pat in expect:
        hit = re.search(pat, text)
        print(f"  {'✓' if hit else '✗'} 期望 {pat!r}" + ("" if hit else "  —— 没出现"))
        ok = ok and bool(hit)
    for pat in forbid:
        hit = re.search(pat, text)
        print(f"  {'✗' if hit else '✓'} 禁止 {pat!r}" + ("" if not hit else "  —— 出现了"))
        ok = ok and not hit
    if not keep:
        pass
    print(f"  => {'PASS' if ok else 'FAIL'}   日志 {log}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--dump", action="store_true", help="打印最后一个用例的完整日志")
    ap.add_argument("--probe", default=None, help="改成测某一份组装后的载荷")
    a = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    global PROBE_PATH
    if a.probe:
        PROBE_PATH = pathlib.Path(a.probe).resolve()
        print(f"被测载荷：{PROBE_PATH}")

    with open(DICT, encoding="utf-8") as fh:
        d = json.load(fh)

    def seats_of(tname: str) -> dict:
        out = {}
        for i, f in enumerate(d["types"][tname]["fields"], 1):
            out[f["id"]] = i
        return out

    av_seats = seats_of(AVATAR_TYPE)
    name_seats = {
        "gls4w9b": av_seats["dae681f4"],
        "state": av_seats["82830aed"],
        "motion_enabled": av_seats["d49efb40"],
        "rotation_enabled": av_seats["4441caf8"],
        "health": av_seats["cb0453ea"],
        "enabled_mask": av_seats["788b9753"],
        "position": av_seats["8bbeb160"],
    }
    pl_seats = {"baegche": seats_of(PLAYER_TYPE)["f27c68e"]}
    seats = dict(name_seats)
    seats.update(pl_seats)

    print(f"seat 映射（来自真实 schema）：{name_seats}")
    print(f"un6y1d.baegche seat = {pl_seats['baegche']}\n")

    ok = True

    # 主用例：主菜单 -> 空 owned -> 飞船态 -> 地面态 -> 秒表观察
    ok &= run_case(
        "ground", {
            "menu_until": 100, "empty_until": 200,
            "avatar_at": 300, "ground_at": 800, "mutate_at": 1300,
            "frames": 2400,
        }, seats,
        expect=[
            r"probe_read 1\.4\.0 \| required as",
            r'object_info\("un6y1d"\) = 36 fields',
            r'object_info\("gl7xl2w"\) = 72 fields',
            r"========== PASS 2 .*player=7 avatar=8  gls4w9b=3 -> GROUND",
            r"########## 观察开始（基线）##########",
            r"\[BASE t=[\d.]+s\] .*68=",
            r"\[CHG t=[\d.]+s w=[\d.]+s f=\d+\] .*70: 0->1",
            r"\[TICK t=",
        ],
        forbid=[r"LUA-ERR", r"REFUSED", r"UPDATE RAISED", r"PROBE LOAD FAILED",
                r"attempt raised", r"\(second load\)"],
        counts={r"hook installed; sample every": 1},
        keep=a.keep)

    # 哨兵用例：baegche 一直返回 32767 -> 必须 bail，绝不能把它递进读取
    ok &= run_case(
        "sentinel", {
            "menu_until": 50, "empty_until": 100,
            "avatar_at": 10 ** 9, "ground_at": 10 ** 9,
            "frames": 800,
        }, seats,
        expect=[r"baegche == 32767 = 此刻无 avatar"],
        forbid=[r'game_object_field\(goid=32767', r"LUA-ERR", r"UPDATE RAISED"],
        keep=a.keep)

    # 双实例回归
    ok &= run_case(
        "double_load", {
            "menu_until": 100, "empty_until": 200,
            "avatar_at": 300, "ground_at": 800, "mutate_at": 1300,
            "frames": 2400, "double_load": True,
        }, seats,
        expect=[
            r"\(second load\) 已有实例在跑（1\.4\.0），本次加载不安装钩子",
            r"\[BASE t=",
        ],
        forbid=[r"LUA-ERR", r"UPDATE RAISED"],
        counts={r"hook installed; sample every": 1,
                r"===== probe_read 1\.4\.0 \| required as": 1,
                r"\(second load\)": 1},
        keep=a.keep)

    print()
    print("=== 总判: " + ("PASS" if ok else "FAIL") + " ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
