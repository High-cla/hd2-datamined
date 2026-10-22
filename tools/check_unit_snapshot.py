#!/usr/bin/env python3
"""Fail a Lua probe that iterates a ``World.units()`` snapshot and calls Unit getters per item.

Why
    ``world:units()`` / ``World.units(world)`` returns a **snapshot**; in a live mission world
    individual handles go stale and any getter on them reads past the end of a fixed-size record
    (recorded fault: ``movsd xmm0, qword ptr [rdi + rbx + 0x30]`` with ``rdi = index<<6``).
    That is a process-level crash --- ``pcall`` cannot catch it.

    The rule has been written down since 2026-10-20 and was still violated on 2026-10-21 by
    ``exp_hud 0.7.0`` (full scan of 3554 units -> instant crash on world load). Writing it in prose
    is not enough, so this is the executable version.

What it flags
    A ``for`` loop whose *iteration variable* is passed to a ``Unit.*`` / ``UNIT.*`` function, in a
    file that also calls ``units(...)`` on a world.  Deliberately conservative: it reports the file
    and line so a human decides, and it only fires when the loop variable actually reaches a getter.

Usage
    python check_unit_snapshot.py <file.lua> [...]
    python check_unit_snapshot.py --selftest        # prove the check bites
"""
from __future__ import annotations

import re
import sys

UNITS_CALL = re.compile(r"(?:World\s*\.\s*units\s*\(|[:.]units\s*\()")
FOR_LOOP = re.compile(r"^\s*for\s+([A-Za-z_]\w*)\s*(?:=[^d]|in\b)")

# ``for k, v in pairs(...)`` style loops have two names; only the value matters for our call shape
MULTI = re.compile(r"^\s*for\s+([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*(?:=[^d]|in\b)")


def strip_comment(line: str) -> str:
    """Drop a trailing ``--`` comment that is not inside a string (good enough for probes)."""
    out, quote = [], None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            if ch == quote and line[i - 1] != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "-" and line[i:i + 2] == "--":
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def scan(path: str) -> list[tuple[int, str, str]]:
    """Return ``[(line_no, loop_var, getter)]`` for every getter reached from a units() loop."""
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError as exc:
        print(f"  ! {path}: {exc}")
        return []

    text = "\n".join(strip_comment(line) for line in lines)
    if not UNITS_CALL.search(text):
        return []

    findings: list[tuple[int, str, str]] = []
    active: list[tuple[str, int]] = []          # (loop var, indent of the `for` line)
    for number, raw in enumerate(lines, 1):
        line = strip_comment(raw)
        indent = len(line) - len(line.lstrip())

        # a bare `end` closes every loop opened at the same or deeper indentation
        if re.match(r"^\s*end\b", line):
            active = [(v, i) for v, i in active if i < indent]

        # any getter call on this line, reached while a units() loop is open?
        getter = re.search(r"\b(?:UNIT|Unit)\s*\.\s*(\w+)\s*\(", line)
        if getter:
            for var, _ in active:
                # the handle usually arrives as `list[i]` / `units[i]`, so match the loop
                # variable as a whole word anywhere on the line, not only as first argument
                if re.search(r"\b%s\b" % re.escape(var), line):
                    findings.append((number, var, "Unit." + getter.group(1)))
                    break

        multi = MULTI.match(line)
        single = FOR_LOOP.match(line) if not multi else None
        if multi:
            active.append((multi.group(2), indent))      # for k, v in ... -> v is the item
        elif single:
            active.append((single.group(1), indent))
    return findings


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    if not argv:
        print(__doc__)
        return 2
    bad = 0
    for path in argv:
        findings = scan(path)
        if findings:
            bad += 1
            print(f"FAIL {path}: iterates a units() snapshot and calls getters per item")
            for line_no, var, getter in findings:
                print(f"       line {line_no}: loop var '{var}' -> {getter}")
        else:
            print(f"ok   {path}")
    if bad:
        print(f"\n{bad} file(s) would crash on a stale handle -- see "
              f"docs/STINGRAY-API-25988413.md (units() handles expire)")
    return 1 if bad else 0


def selftest() -> int:
    """A positive and a negative case, so the check is known to bite."""
    positive = """
local list = World.units(world)
for i = 1, #list do
    local name = UNIT.resource_name(list[i])
    local p = UNIT.world_position(list[i])
end
"""
    negative = """
local n = WORLD.num_units(world)
local t = WORLD.time(world)
"""
    cases = [("positive", positive, True), ("negative", negative, False)]
    failed = 0
    for name, source, expect_hit in cases:
        path = f"_selftest_{name}.lua"
        open(path, "w", encoding="utf-8").write(source)
        hits = scan(path)
        ok = bool(hits) == expect_hit
        print(f"{'PASS' if ok else 'FAIL'}  {name}: expect_hit={expect_hit} hits={len(hits)}")
        if not ok:
            failed += 1
        import os
        os.remove(path)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
