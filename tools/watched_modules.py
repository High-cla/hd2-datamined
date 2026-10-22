#!/usr/bin/env python3
r"""watched_modules.py -- watch which DLLs a starting process actually maps, from outside.

WHY
    The loadlib matrix can only report what a Lua call returns, and the plugin-swap runs die
    *before* the Lua VM boots, so they produce no reading at all.  But "did the image get mapped"
    does not need anything inside the process: VirtualQueryEx walks the address space with
    PROCESS_QUERY_INFORMATION only, and GetMappedFileNameW turns each region into a file name.
    Both are proven to work under this build's anti-cheat (docs/MEMORY-ACCESS-25988413.md section 8:
    18,170 regions, 170 mapped files, all read-only metadata).

WHAT IT SETTLES
    Put a different *validly signed* DLL at an engine plugin's own name.  Two readings remain:

        gate 2 keyed by NAME (+ gate 1 signature)      -> the image IS mapped, then init dies
        gate 2 keyed by NAME + CONTENT / tamper check  -> the image is NEVER mapped

    The normal state is the baseline: the plugin's name must show up there, or the instrument
    itself is not working.

USAGE
    python tools/watched_modules.py --watch level_generation --timeout 120
        # starts polling immediately; waits for helldivers2.exe, then reports the first moment the
        # substring appears in the mapped-file list (and the total mapped-file count per sample)
"""
from __future__ import annotations

import argparse
import subprocess
import ctypes
import ctypes.wintypes as wt
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)   # GetMappedFileNameW lives here
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.OpenProcess.restype = wt.HANDLE
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
psapi.GetMappedFileNameW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]
psapi.GetMappedFileNameW.restype = wt.DWORD

MEM_COMMIT = 0x1000
IMAGE = 0x1000000
QUERY_INFORMATION = 0x0400
GAME_IMAGE = "helldivers2.exe"


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("Reserved", wt.WORD),
                ("RegionSize", ctypes.c_size_t), ("State", wt.DWORD),
                ("Protect", wt.DWORD), ("Type", wt.DWORD)]


class PE32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.Process32First.argtypes = [wt.HANDLE, ctypes.POINTER(PE32)]
k32.Process32Next.argtypes = [wt.HANDLE, ctypes.POINTER(PE32)]


def find_pid() -> int | None:
    """Toolhelp snapshot - no subprocess, so nothing to go wrong inside a sandboxed job."""
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    if snap == wt.HANDLE(-1).value:
        return None
    entry = PE32()
    entry.dwSize = ctypes.sizeof(entry)
    found = None
    try:
        ok = k32.Process32First(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == GAME_IMAGE.encode():
                found = int(entry.th32ProcessID)
                break
            ok = k32.Process32Next(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return found


def launch_game() -> None:
    """`cmd /c start steam://...` - ShellExecuteW on that URL is silently dropped by this Steam."""
    subprocess.Popen(["cmd", "/c", "start", "", "steam://rungameid/553850"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def mapped_files(handle) -> list[str]:
    """Every mapped file name in the target, or [] if the handle went stale (process died)."""
    names: list[str] = []
    addr, mbi = 0x10000, MBI()
    buf = ctypes.create_unicode_buffer(1024)
    while addr < 0x7FFFFFFFFFFF:
        if not k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(mbi),
                                  ctypes.sizeof(mbi)):
            break
        if mbi.State == MEM_COMMIT and mbi.Type == IMAGE:
            got = psapi.GetMappedFileNameW(handle, ctypes.c_void_p(int(mbi.BaseAddress)), buf, 1024)
            if got:
                names.append(buf.value)
        nxt = int(mbi.BaseAddress) + int(mbi.RegionSize)
        if nxt <= addr:
            break
        addr = nxt
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", required=True, help="substring of the mapped file name to look for")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--poll", type=float, default=0.15, help="seconds between samples")
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--launch", action="store_true", help="launch the game through steam:// first")
    a = ap.parse_args()

    needle = a.watch.lower()
    started = time.time()
    print(f"watching for '{a.watch}' in the mapped-file list, timeout {a.timeout:.0f}s")

    if a.launch:
        launch_game()
        print("  steam:// launch issued")
    pid = a.pid
    last_try = time.time()
    while pid == 0 and time.time() - started < a.timeout:
        pid = find_pid()
        if pid:
            print(f"  {GAME_IMAGE} appeared (pid {pid}) at t+{time.time()-started:.1f}s")
            break
        if a.launch and time.time() - last_try > 20:
            launch_game()
            last_try = time.time()
            print(f"  relaunch issued at t+{time.time()-started:.1f}s")
        time.sleep(0.1)
    if not pid:
        print("VERDICT: the game never started")
        return 2

    handle = None
    first_seen: float | None = None
    samples = 0
    peak = 0
    while time.time() - started < a.timeout:
        if handle is None:
            handle = k32.OpenProcess(QUERY_INFORMATION, False, pid)
            if not handle:
                print("!! could not open the process for QUERY_INFORMATION")
                return 3
        names = mapped_files(handle)
        now = time.time() - started
        if not names:
            print(f"VERDICT: address space unreadable at t+{now:.1f}s (process gone)")
            break
        samples += 1
        peak = max(peak, len(names))
        hit = [n for n in names if needle in n.lower()]
        if hit and first_seen is None:
            first_seen = now
            print(f"  FIRST SEEN at t+{now:.1f}s  ({len(names)} mapped file(s)): {hit[0]}")
            k32.CloseHandle(handle)
            handle = None
            break
        time.sleep(a.poll)

    if handle:
        k32.CloseHandle(handle)
    print()
    if first_seen is not None:
        print(f"RESULT: MAPPED  — '{a.watch}' appeared in the address space at t+{first_seen:.1f}s "
              f"(samples {samples}, peak mapped files {peak})")
        return 0
    print(f"RESULT: NEVER MAPPED — '{a.watch}' did not appear in {samples} sample(s), "
          f"peak mapped files {peak}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
