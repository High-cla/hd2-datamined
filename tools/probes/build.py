#!/usr/bin/env python3
"""Build/install a single patch_5 module that runs BOTH probes at boot.

    data/9ba626afa44a3aa3.patch_5  ->  mods/auto/5 = probe_repl.lua + probe_resovr.lua

Our installed patch_0 (BootProbe 1.3.0) sweeps `mods/auto/1..6` and requires what exists,
so this module runs during boot. Both probes are self-contained and each installs its own
per-frame hook by wrapping the global `update` that BootProbe installed before requiring us
(modules are required at BootProbe line ~355, `update = noop` is set at line 20).

    python build.py            # build + install patch_5
    python build.py --remove   # rollback
    python build.py --only repl|resovr   # embed just one probe (debugging)
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

sys.path.insert(0, r"C:\Users\Admin\HD2SDK-CommunityEdition")

from srkit.container.package import Package, TocEntry          # noqa: E402
from srkit.util.hashing import murmur64_hash                  # noqa: E402
from srkit.util.ids import TYPE_LUA                           # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

BUNDLE = "9ba626afa44a3aa3"
GAME_DATA = pathlib.Path(r"D:\SteamLibrary\steamapps\common\Helldivers 2\data")
MODULE = "mods/auto/5"
INDEX = 5
HERE = pathlib.Path(__file__).resolve().parent
ENVELOPE = 2

PROBES = [("types", "probe_types.lua"), ("repl", "probe_repl.lua"),
          ("resovr", "probe_resovr.lua"), ("read", "probe_read.lua")]


def assemble(only: str | None) -> bytes:
    parts = [p for p in PROBES if only is None or p[0] == only]
    if not parts:
        raise SystemExit(f"unknown probe {only!r}")
    out = ["-- combined probe payload, assembled by build.py",
           "-- sections: " + ", ".join(n for n, _ in parts), ""]
    types_path = HERE / "types_list.lua"
    if types_path.is_file() and any(n == "types" for n, _ in parts):
        out.append("-- 类型名清单（HD2 HUD+ 的 allowed_types + GeneratedCommon.call 的并集）")
        out.append(types_path.read_text(encoding="utf-8"))
        out.append("")
    for name, filename in parts:
        src = (HERE / filename).read_text(encoding="utf-8")
        out.append(f"-- ==================== begin {filename} ====================")
        out.append(f"do  -- probe {name}")
        out.append("local __probe = (function()")
        out.append(src)
        out.append("end)()")
        out.append("end")
        out.append(f"-- ==================== end {filename} ======================")
        out.append("")
    out.append("return { probes = '" + "+".join(n for n, _ in parts) + "' }")
    return "\n".join(out).encode("utf-8")


def build(source: bytes):
    payload = struct.pack("<II", len(source), ENVELOPE) + source
    entry = TocEntry(file_id=murmur64_hash(MODULE.encode()), type_id=TYPE_LUA,
                     toc_data=bytearray(payload))
    package = Package(name=BUNDLE)
    package.add_entry(entry)
    return package.to_bytes()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--only", default=None)
    ap.add_argument("--out", default=None, help="也把组装后的源码写一份到磁盘（调试用）")
    a = ap.parse_args()

    if a.remove:
        n = 0
        for suffix in ("", ".gpu_resources", ".stream"):
            path = GAME_DATA / f"{BUNDLE}.patch_{INDEX}{suffix}"
            if path.exists():
                path.unlink()
                n += 1
        print(f"回滚：删除 patch_{INDEX} 的 {n} 个文件")
        return 0

    source = assemble(a.only)
    if a.out:
        pathlib.Path(a.out).write_bytes(source)
        print(f"源码写出 {a.out} ({len(source):,} B)")
    blobs = build(source)
    print(f"资源 id = murmur64({MODULE!r}) = 0x{murmur64_hash(MODULE.encode()):016X}")
    for suffix, blob in zip(("", ".gpu_resources", ".stream"), blobs):
        path = GAME_DATA / f"{BUNDLE}.patch_{INDEX}{suffix}"
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing {path} -- run --remove first")
        path.write_bytes(blob)
        print(f"  wrote {path.name} ({len(blob):,} B)")
    print("\n装好了。启动游戏 → 进主菜单（boot 段），再进一局任务（延后段）。日志：")
    print(r"  %LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\ReplProbe.log")
    print(r"  %LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\ResOvrTypes.log")
    print(f"\n回滚：python {pathlib.Path(__file__).name} --remove")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
