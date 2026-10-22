#!/usr/bin/env python3
"""hud_layout_check.py — 离线把 HUD 的绘制坐标算出来，免得为一个坐标烧一次游戏启动。

它做三件事：
  1. 用 lupa(lua51) 起一份**只含 rtt_hud 实际触碰到的表面**的假引擎；
  2. 把 ``Gui.text`` 的 (文本, x, y, 字号) 记下来；
  3. 跑若干帧让 ``update`` 钩子把 render 刷出来，然后断言版式断言。

假引擎里每个函数都是 25988413 上已被实机验证过的形状（见 docs/STINGRAY-API-25988413.md）：
``World.create_screen_gui(world,"scale",1,1)`` 返回保留模式句柄、``Gui.text(self,text,font,size,
material,pos,color)``、``Network.ping(peer)`` 返回秒。坐标约定与已实机验证的 1.2.0 一致：
**y 是文本左下角，屏幕原点在左下角，向上为正**（1.2.0 用 ``SCREEN_H-60`` 顶对齐并实测成功）。

用法
    python hud_layout_check.py <hud.lua> --scenario host|client|none [--screen 1920x1080]
"""
from __future__ import annotations

import argparse
import sys

from lupa import lua51

FAKE = r"""
DRAWS = {}

local function vec(x, y) return { x = x, y = y } end
Vector2 = function(x, y) return vec(x, y) end
Color = function(r, g, b, a) return { r = r, g = g, b = b, a = a } end

local gui_handle = {}
local seq = 0
Gui = {}
function Gui.text(self, text, font, size, material, pos, colour)
    if type(text) ~= "string" then error("Gui.text: text must be a string", 2) end
    if type(pos) ~= "table" then error("Gui.text: pos must be a Vector2", 2) end
    seq = seq + 1
    DRAWS[#DRAWS + 1] = { text = text, size = size, x = pos.x, y = pos.y, id = seq }
    return seq
end
function Gui.destroy_text(self, id) end
function Gui.set_visible(self, id, state) return true end
function Gui.is_visible(self, id) return true end

World = {}
function World.create_screen_gui(world, ...) return gui_handle end

local world = {}

-- ---- 网络桩：场景在 run 里注入 ----
Network = {}
GameSession = {}
NETWORK_SCENARIO = nil

function Network.peer_id() return NETWORK_SCENARIO.mine end
function Network.ping(peer) return NETWORK_SCENARIO.ping[tostring(peer)] end
function Network.game_session() return {} end
function GameSession.in_session(session) return NETWORK_SCENARIO.in_session end
function GameSession.peers(session)
    local out = {}
    for i, p in ipairs(NETWORK_SCENARIO.peers) do out[i] = p end
    return out
end
function GameSession.game_session_host(session) return NETWORK_SCENARIO.host end

Application = {}
function Application.back_buffer_size() return TARGET_W, TARGET_H end
function Application.main_world() return world end
function Application.time_since_launch() return 120.0 end

stingray = {
    Application = Application, World = World, Gui = Gui,
    Vector2 = Vector2, Color = Color, Network = Network, GameSession = GameSession,
}

-- 日志走 os.getenv：返回 nil 让模块自己短路，不落盘
local real_getenv = os.getenv
function os.getenv(name) return nil end
"""

SCENARIOS = {
    # 我是 host：ping 所有远端（4 个）
    "host": dict(mine=1, host=1, peers=[1, 2, 3, 4], in_session=True, ms=42),
    # 我是 client：只 ping host（1 行）
    "client": dict(mine=7, host=1, peers=[1, 7], in_session=True, ms=118),
    # 不在会话：只有状态行
    "none": dict(mine=1, host=1, peers=[1], in_session=False, ms=0),
}


def scenario_table(runtime, scenario: dict):
    """嵌套表必须逐个建：table_from() 只转换最外层，Python 列表会变成 userdata。"""
    table = runtime.table()
    table["mine"] = scenario["mine"]
    table["host"] = scenario["host"]
    table["in_session"] = bool(scenario["in_session"])
    peers = runtime.table()
    for index, peer in enumerate(scenario["peers"], start=1):
        peers[index] = peer
    table["peers"] = peers
    ping = runtime.table()
    for peer in scenario["peers"]:
        ping[str(peer)] = scenario["ms"] / 1000.0
    table["ping"] = ping
    return table


def run(source: str, scenario: dict, screen: tuple[int, int], frames: int) -> list[dict]:
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    runtime.execute(FAKE)
    g = runtime.globals()
    g.TARGET_W = screen[0]
    g.TARGET_H = screen[1]
    g.NETWORK_SCENARIO = scenario_table(runtime, scenario)

    chunk = g.loadstring(source, "@hud")
    if chunk is None:
        raise SystemExit("hud_layout_check: lua syntax error")
    chunk("mods/auto/3")

    for _ in range(frames):
        g.update(1.0 / 60.0)

    # 清空记录，只留最后一帧 render 的绘制
    g.DRAWS = runtime.table_from([])
    for _ in range(30):
        g.update(1.0 / 60.0)

    out = []
    for item in g.DRAWS.values():
        out.append({k: item[k] for k in ("text", "size", "x", "y")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lua")
    ap.add_argument("--scenario", default="host", choices=sorted(SCENARIOS))
    ap.add_argument("--screen", default="1920x1080")
    ap.add_argument("--frames", type=int, default=960)
    ap.add_argument("--lift", type=int, default=0,
                    help="预期整块中心相对屏幕中线的偏移（px，正数=往上）")
    args = ap.parse_args()

    width, height = (int(v) for v in args.screen.lower().split("x"))
    source = open(args.lua, encoding="utf-8").read()
    draws = run(source, SCENARIOS[args.scenario], (width, height), args.frames)

    print(f"{args.lua}  scenario={args.scenario}  screen={width}x{height}")
    if not draws:
        print("  FAIL: nothing drawn")
        return 1
    for d in draws:
        print(f"  x={d['x']:6.1f} y={d['y']:6.1f} size={d['size']:>3}  {d['text']}")

    problems = []
    xs = {d["x"] for d in draws}
    if xs != {12}:
        problems.append(f"x 不是贴边 12：{sorted(xs)}")

    tops = max(d["y"] + d["size"] for d in draws)
    bottoms = min(d["y"] for d in draws)
    centre = (tops + bottoms) / 2.0
    want = height / 2.0 + args.lift
    if abs(centre - want) > 20:
        where = "屏幕中线" if args.lift == 0 else f"屏幕中线+{args.lift}"
        problems.append(f"整块中心 {centre:.0f} 偏离目标 {where} {want:.0f}")

    # 不许碰到游戏自带的左上角 HUD（战略配备/罗盘）和底部 HUD
    if tops > height * 0.85:
        problems.append(f"顶边 {tops:.0f} 进入屏幕上部 15%（会和左上角 UI 撞）")
    if bottoms < height * 0.15:
        problems.append(f"底边 {bottoms:.0f} 进入屏幕下部 15%（会和弹药/战略 HUD 撞）")

    if problems:
        for p in problems:
            print("  FAIL:", p)
        return 1
    print(f"  OK: 左边距 {xs.pop():.0f}px，块中心 {centre:.0f} = 目标 {want:.0f}，"
          f"竖直占用 {bottoms:.0f}..{tops:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
