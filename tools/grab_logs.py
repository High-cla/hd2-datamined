#!/usr/bin/env python3
"""Archive the live game logs before the next session overwrites them.

The Runtime truncates `HD2Runtime.log` at every game start, and the mods write into the same log
folder, so two test runs are only both recoverable while they share one game session:

    %LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs/

This copies the interesting ones into a dated folder and prints their session window, so a run can be
cited later (and re-grepped) instead of being re-tested.

    python grab_logs.py --tag pods                 # HD2Runtime + probe + loader logs
    python grab_logs.py --tag pods --grep resupply # ... and print matching lines
    python grab_logs.py --all --tag full           # every small log (< 8 MB) in the folder
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import shutil
import sys
from pathlib import Path

LOGS = Path.home() / "AppData" / "Local" / "CowboyBingus" / "Helldivers2" / "Logs"
OUT = Path("logs")          # default is relative; pass --out to choose
# KitVerify.log was MISSING from this set until 2026-10-14 22:5x, which made the tool useless for the
# one job it exists for: it is our own probe's log, it is truncated at every launch, and running this
# with its defaults archived everything EXCEPT it - so the answer to "did you archive the run?" was
# "yes" while the evidence was still being destroyed.  The archives show the cost: 10-09 x7, 10-10
# x19, 10-12 x2, and then NOTHING on 10-13 and 10-14, the two days whose runs cannot be re-checked.
# hd2_carrierprobe.log is another line of work's log and it is 63 MB - left in the default set
# rather than dropped, because silently removing somebody else's evidence to save disk is not a
# trade this tool gets to make.  --all covers everything under --max-mb.
# ★ 2026-10-16: ArmorStatRows.log joins the set the day the e17 deliverable is installed.  The list is
#   hard-coded, and the tool's worst failure is silence - a new probe/deliverable is a new log name, and
#   the log is truncated by the next launch.  (The same trap hit KitVerify.log for two days in October.)
# ★★ 2026-10-17: the trap bit a THIRD time - MountRecon.log (g2's probe) was not in the set, so
#   `grab_logs.py --tag ...` archived a dozen logs and NOT the one the session was run for; it had to be
#   copied by hand while it was still live.  MountRecon.log and Lua51Watch.log join the set now.
#   The structural fix would be "archive every .log this project's payloads can write", i.e. derive the
#   list from the payload sources; until someone writes that, ADD THE LOG NAME WHEN YOU INSTALL A PROBE.
# ★★★ 2026-10-20: BootProbe.log joins on the day the boot-anchored probe exists.  This one is the
#   sharpest case yet: it is written from a replacement of `boot`, so if the probe DOES run, that log is
#   the only evidence in existence, and the next launch appends to it.  Added before installing.
DEFAULT = ("KitVerify.log", "ArmorStatProbe.log", "ArmorStatRows.log", "MountRecon.log",
           "Lua51Watch.log", "BootProbe.log", "LiveCensus.log", "WorldApi.log", "BytecodeLeak.log", "ExpHud.log", "PluginProbe.log", "HD2Runtime.log", "hd2_carrierprobe.log",
           "BingusSharedLoader.log", "ResourceOverride.log", "P2PPing.log")
BIG = 8 * 1024 * 1024


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run", help="a name for this run, e.g. pods")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--logs", default=str(LOGS))
    ap.add_argument("--all", action="store_true", help="every log under 8 MB, not just the default three")
    ap.add_argument("--max-mb", type=float, default=8.0)
    ap.add_argument("--grep", action="append", default=[], help="print the lines matching this pattern (regex)")
    args = ap.parse_args()

    logs = Path(args.logs)
    if not logs.is_dir():
        print("no log folder at " + str(logs), file=sys.stderr)
        return 2
    limit = int(args.max_mb * 1024 * 1024)
    if args.all:
        files = sorted(p for p in logs.glob("*.log") if p.stat().st_size <= limit)
    else:
        files = [logs / name for name in DEFAULT if (logs / name).is_file()]
    if not files:
        print("nothing to copy in " + str(logs), file=sys.stderr)
        return 2

    stamp = dt.datetime.fromtimestamp(max(p.stat().st_mtime for p in files)).strftime("%Y-%m-%d-%H%M")
    dest = Path(args.out) / ("%s-%s" % (stamp, args.tag))
    dest.mkdir(parents=True, exist_ok=True)
    print("log folder %s" % logs)
    for path in files:
        target = dest / path.name
        shutil.copy2(path, target)
        digest = hashlib.md5(target.read_bytes()).hexdigest()
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M:%S")
        print("  %-28s %10d B  %s  md5 %s" % (path.name, target.stat().st_size, mtime, digest))
    print("archived -> %s" % dest)

    # What was NOT archived, said out loud.  This tool's whole failure mode has been silence: its default
    # set was missing KitVerify.log for two days and `ArmorStatProbe.log` until 2026-10-15, and in both
    # cases the answer to "did you archive the run?" was "yes" while the log was still being destroyed by
    # the next launch.  A hardcoded list will fall behind again - a new probe is a new log name - so the
    # tool now reports the logs it left behind instead of hoping the list stays complete.
    left = sorted(p for p in logs.glob("*.log") if p not in files)
    if left:
        print("  NOT archived (not in the known set; add to DEFAULT or pass --all):")
        for path in left:
            mtime = dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%m-%d %H:%M")
            print("    %-34s %10d B  %s" % (path.name, path.stat().st_size, mtime))

    import re
    for pattern in args.grep:
        rx = re.compile(pattern)
        print("\n=== %s ===" % pattern)
        for path in files:
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    print("%s:%d: %s" % (path.name, number, line))
    return 0


if __name__ == "__main__":
    sys.exit(main())
