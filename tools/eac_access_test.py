#!/usr/bin/env python3
"""eac_access_test.py — decide whether the anti-cheat still lets an outside process
READ the game, by testing OPERATIONS, not handles.

WHY THIS EXISTS (2026-10-20)

    The old full-dump pipeline was:

        tools/crash_watch.py  ->  tools/dumper.ps1  ->  MiniDumpWriteDump(handle)
                                   (dbghelp, NOT a debugger)

    It worked under nProtect GameGuard and produced five 10-11 GB
    MiniDumpWithFullMemory files in E:\\hd2-dumps\\kept\\.

    Build 25988413 replaced GameGuard with Easy Anti-Cheat (EOS): a kernel driver
    (EasyAntiCheat_EOSSys) is loaded and running.  Whether that driver filters our
    access cannot be answered offline - the driver is encrypted (40-byte import
    directory, not one API name visible).

★★★ 2026-10-20 20:4x - THE FIRST VERSION OF THIS TOOL WAS WRONG, AND THIS IS WHY.
    It judged by OpenProcess alone: all three masks came back GRANTED, so it
    printed "READABLE  external MiniDumpWriteDump should still work".  That was a
    **false positive**.  EAC's ObRegisterCallbacks does not refuse the handle - it
    strips the requested rights at creation and hands back a weaker handle.  So
    OpenProcess, which is exactly what the old dumper.ps1 tried first, succeeds on
    a handle that cannot read a single byte.

    Measured on pid 6552 with a 0x0410 handle that OpenProcess said "ok" to:
        VirtualQueryEx        ok   (PROCESS_QUERY_INFORMATION survived)
        GetProcessTimes       ok
        QueryFullProcessImageNameW ok
        EnumProcessModules    FAIL err=5   (it reads the PEB -> needs VM_READ)
        ReadProcessMemory     FAIL err=5   (tested at a committed MEM_IMAGE region)
        MiniDumpWriteDump(0)  FAIL 0x80070005 E_ACCESSDENIED

    Lesson (the one this project already wrote down once): a check that only asks
    "did the call return a handle" cannot fail, so it is not a check.  This version
    asks "can you read one byte of the target", which can.

WHAT IT MEASURES NOW

    stage A  OpenProcess 0x1000 / 0x0410 / 0x1F0FFF      informational
    stage B  VirtualQueryEx                              QUERY_INFORMATION alive?
    stage C  ReadProcessMemory at a committed MEM_IMAGE  ** the real question **
    stage D  --dump-normal: one MiniDumpNormal           the whole dump path

    Verdict is taken from stage C only.  A granted-but-stripped handle is named as
    such instead of being reported as success.

WHAT IT PROVED (2026-10-20, build 25988413) - A FAILED ATTEMPT, PUBLISHED ON PURPOSE
    Stage C never succeeded: ReadProcessMemory returned err=5 on a committed MEM_IMAGE region, and
    MiniDumpWriteDump returned 0x80070005.  Nothing in this file circumvents anything - it measures,
    and the measurement says no.  It is here because "we tried and it failed" is worth more than
    silence: docs/MEMORY-ACCESS-25988413.md sections 2-8 are this tool's own output.

USAGE
    python tools/eac_access_test.py --selftest
    python tools/eac_access_test.py                 # auto-find helldivers2.exe
    python tools/eac_access_test.py --pid 6552 --dump-normal out\\eac-normal.dmp
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.OpenProcess.restype = wt.HANDLE
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.CloseHandle.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = wt.BOOL
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("Reserved", wt.WORD),
                ("RegionSize", ctypes.c_size_t), ("State", wt.DWORD),
                ("Protect", wt.DWORD), ("Type", wt.DWORD)]


MEM_COMMIT, MEM_IMAGE = 0x1000, 0x1000000
STAGES = [
    ("QUERY_LIMITED_INFORMATION", 0x1000, "harmless identity read"),
    ("QUERY_INFORMATION|VM_READ", 0x0410, "what MiniDumpWriteDump needs"),
    ("PROCESS_ALL_ACCESS", 0x1F0FFF, "what dumper.ps1 asks for first"),
]


def try_open(pid: int, access: int) -> tuple[bool, int]:
    h = k32.OpenProcess(access, False, pid)
    if not h:
        return False, ctypes.get_last_error()
    k32.CloseHandle(h)
    return True, 0


def first_image_region(h) -> int | None:
    """Walk VirtualQueryEx (needs only QUERY_INFORMATION) to a committed MEM_IMAGE."""
    addr, mbi, n = 0x10000, MBI(), 0
    while addr < 0x7FFFFFFFFFFF and n < 300000:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            return None
        if mbi.State == MEM_COMMIT and mbi.Type == MEM_IMAGE:
            return int(mbi.BaseAddress)
        nxt = int(mbi.BaseAddress) + int(mbi.RegionSize)
        if nxt <= addr:
            return None
        addr = nxt
        n += 1
    return None


def probe_ops(pid: int, mask: int = 0x0410) -> dict:
    """The only question that matters: can this handle read one byte of the target?"""
    out = {"handle": False, "open_err": 0, "vq": None, "region": None,
           "read": None, "read_err": 0, "read_bytes": 0}
    ctypes.set_last_error(0)
    h = k32.OpenProcess(mask, False, pid)
    if not h:
        out["open_err"] = ctypes.get_last_error()
        return out
    out["handle"] = True
    try:
        base = first_image_region(h)
        out["vq"] = base is not None
        if base is None:
            return out
        out["region"] = base
        buf, got = ctypes.create_string_buffer(8), ctypes.c_size_t(0)
        ctypes.set_last_error(0)
        ok = k32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, 8, ctypes.byref(got))
        out["read"] = bool(ok) and got.value == 8
        out["read_err"] = ctypes.get_last_error()
        out["read_bytes"] = got.value
    finally:
        k32.CloseHandle(h)
    return out


def dump_normal(pid: int, path: str) -> str:
    dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)
    dbghelp.MiniDumpWriteDump.argtypes = [wt.HANDLE, wt.DWORD, wt.HANDLE, wt.DWORD,
                                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    dbghelp.MiniDumpWriteDump.restype = wt.BOOL
    h = k32.OpenProcess(0x0410, False, pid)
    if not h:
        return "OPEN_FAILED err=%d" % ctypes.get_last_error()
    try:
        ctypes.set_last_error(0)
        with open(path, "wb") as f:
            ok = dbghelp.MiniDumpWriteDump(h, pid, f.fileno(), 0, None, None, None)
        err = ctypes.get_last_error()
        return "OK size=%d" % os.path.getsize(path) if ok else \
               "DUMP_FAILED err=%d (0x%08x) size=%d" % (err, err & 0xFFFFFFFF, os.path.getsize(path))
    finally:
        k32.CloseHandle(h)


def report(pid: int, dump_path: str | None, mask: int = 0x0410) -> dict:
    try:
        elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        elevated = False
    print("target pid %d   (elevated=%s)" % (pid, elevated))
    print("  -- stage A: OpenProcess (informational; EAC grants these and strips rights) --")
    for label, access, why in STAGES:
        ok, err = try_open(pid, access)
        print("     %-30s %#08x  %-16s  (%s)"
              % (label, access, "GRANTED" if ok else "DENIED err=%d" % err, why))
    print("  -- stage B/C: can the handle actually touch memory --")
    ops = probe_ops(pid, mask)
    if not ops["handle"]:
        print("     OpenProcess(%#x) FAILED err=%d" % (mask, ops["open_err"]))
        print("VERDICT: BLOCKED  (no handle at all)")
        return ops
    print("     VirtualQueryEx  -> %s" % ("ok" if ops["vq"] else "FAILED"))
    if ops["region"] is None:
        print("     ReadProcessMemory -> not attempted (no committed MEM_IMAGE region found)")
        print("VERDICT: BLOCKED  (address space not explorable)")
        return ops
    print("     target address  -> %#x (committed MEM_IMAGE)" % ops["region"])
    if ops["read"]:
        print("     ReadProcessMemory -> OK (%d B)" % ops["read_bytes"])
        print("VERDICT: READABLE  an outside process can still read this process")
    else:
        print("     ReadProcessMemory -> DENIED err=%d" % ops["read_err"])
        print("VERDICT: FILTERED  handle granted, PROCESS_VM_READ stripped "
              "-> external dump is DEAD")
    if dump_path:
        print("     MiniDumpNormal -> %s" % (dump_normal(pid, dump_path) if ops["read"]
                                             else "skipped (no VM_READ)"))
    return ops


def find_game_pids() -> list[int]:
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq helldivers2.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, errors="replace",
    ).stdout
    pids = []
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.strip().split('","')]
        if len(parts) >= 2 and parts[1].isdigit():
            pids.append(int(parts[1]))
    return pids


def _pids_of(image: str) -> list[str]:
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq %s" % image, "/FO", "CSV", "/NH"],
        capture_output=True, text=True, errors="replace",
    ).stdout
    pids = []
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.strip().split('","')]
        if len(parts) >= 2 and parts[1].isdigit():
            pids.append(parts[1])
    return pids


def selftest() -> int:
    print("== selftest: child process of our own, full rights ==")
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        time.sleep(1.5)
        print("\n-- positive control: 0x0410 --")
        good = probe_ops(child.pid, 0x0410)
        print("   handle=%s vq=%s read=%s" % (good["handle"], good["vq"], good["read"]))
        print("\n-- MUTATION: a handle deliberately opened WITHOUT VM_READ (0x0400) --")
        print("   (this is the shape EAC hands back, and the read test must catch it)")
        bad = probe_ops(child.pid, 0x0400)
        print("   handle=%s vq=%s region=%s read=%s err=%d"
              % (bad["handle"], bad["vq"], bad["region"] is not None, bad["read"], bad["read_err"]))
        print("\n== negative controls ==")
        ghost_ok, ghost_err = try_open(0x0FFFFFF0, 0x0410)
        print("   bogus pid -> %s" % ("GRANTED (!!)" if ghost_ok else "DENIED err=%d" % ghost_err))
        ppl_denied = False
        for p in _pids_of("csrss.exe"):
            ok, err = try_open(int(p), 0x0410)
            print("   csrss pid %-6s -> %s" % (p, "GRANTED (!!)" if ok else "DENIED err=%d" % err))
            if not ok and err == 5:
                ppl_denied = True
        checks = [
            ("own child: handle + vq + read all work", good["handle"] and good["vq"] and good["read"]),
            ("rights-limited handle: read is REFUSED", bad["handle"] and not bad["read"]),
            ("rights-limited handle: read reports err=5", bad["read_err"] == 5),
            ("bogus pid denied", not ghost_ok),
            ("PPL process denied with err=5", ppl_denied),
        ]
        print()
        for name, ok in checks:
            print("  %-46s %s" % (name, "PASS" if ok else "FAIL"))
        bad_n = sum(1 for _, ok in checks if not ok)
        print("%d PASS / %d FAIL" % (len(checks) - bad_n, bad_n))
        return 0 if bad_n == 0 else 1
    finally:
        if child.poll() is None:
            child.kill()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--dump-normal", default="", help="also take one MiniDumpNormal here")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    pids = [a.pid] if a.pid else find_game_pids()
    if not pids:
        print("no helldivers2.exe running (pass --pid to target something else)")
        return 2
    for pid in pids:
        report(pid, a.dump_normal or None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
