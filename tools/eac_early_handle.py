#!/usr/bin/env python3
"""eac_early_handle.py — race the anti-cheat: grab a VM_READ handle the instant the game appears.

WHY THIS EXISTS (2026-10-20)

    EAC grants every handle we ask for and strips PROCESS_VM_READ at creation
    (docs/MEMORY-ACCESS-25988413.md).  A handle's access mask is fixed when it is
    created, so the only way to hold a readable handle is to create it BEFORE the
    protection applies to the process.

    There are two moments that could be that window:

      * between process creation and the EAC driver's process-notify callback, and
      * (more realistically) never - the game is started by the EAC service, which
        knows the pid at creation time.

    This tool measures which it is, instead of guessing: it polls the process list
    every 10 ms, opens 0x0410 on first sight, keeps the handle, and asks it to read
    one byte at several later moments.  A handle that can read at t+0 and still
    reads at t+30 s is a dump path; one that is refused at t+0 is the answer "no".

    It is read-only: one 8-byte read at a committed MEM_IMAGE address per sample.
    It never writes, never injects, and never kills anything.

WHAT IT PROVED (2026-10-20) - A FAILED ATTEMPT, PUBLISHED ON PURPOSE
    The t+0 read was already refused (err=5) on a handle created 10.6 ms after the pid appeared, so
    the access mask is fixed at creation and there is no pre-protection window.  This tool never
    obtained a readable handle.  Its value is that it closes the question with a measurement instead
    of an assumption.

USAGE
    python tools/eac_early_handle.py            # run this FIRST, then start the game
    python tools/eac_early_handle.py --timeout 180 --out eac-early-handle.log
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)


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
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.OpenProcess.restype = wt.HANDLE
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = wt.BOOL
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
k32.GetProcessTimes.restype = wt.BOOL

GAME = b"helldivers2.exe"


def log_lines(path: str):
    def emit(line: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        text = f"{stamp} {line}"
        print(text, flush=True)
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
    return emit


def find_pid() -> int | None:
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    if snap == wt.HANDLE(-1).value:
        return None
    entry = PE32()
    entry.dwSize = ctypes.sizeof(entry)
    found = None
    try:
        ok = k32.Process32First(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == GAME:
                found = int(entry.th32ProcessID)
                break
            ok = k32.Process32Next(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return found


def first_image_region(h) -> int | None:
    addr, mbi, n = 0x10000, MBI(), 0
    while addr < 0x7FFFFFFFFFFF and n < 300000:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            return None
        if mbi.State == 0x1000 and mbi.Type == 0x1000000:
            return int(mbi.BaseAddress)
        nxt = int(mbi.BaseAddress) + int(mbi.RegionSize)
        if nxt <= addr:
            return None
        addr, n = nxt, n + 1
    return None


def read_check(h, region: int) -> tuple[bool, int]:
    buf = ctypes.create_string_buffer(8)
    got = ctypes.c_size_t(0)
    ctypes.set_last_error(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(region), buf, 8, ctypes.byref(got))
    return bool(ok) and got.value == 8, ctypes.get_last_error()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=180.0, help="seconds to wait for the game")
    ap.add_argument("--interval", type=float, default=0.01, help="poll interval in seconds")
    ap.add_argument("--out", default="eac-early-handle.log")
    ap.add_argument("--samples", default="0,1,5,15,30,60", help="seconds after acquisition to re-read")
    a = ap.parse_args()
    emit = log_lines(a.out)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    emit(f"watching for {GAME.decode()} every {a.interval*1000:.0f} ms, timeout {a.timeout:.0f}s")

    pid = find_pid()
    if pid:
        emit(f"the game is ALREADY running (pid {pid}) - this test needs it to START while we watch")
        return 2

    started = time.time()
    handle = None
    seen_at = 0.0
    while time.time() - started < a.timeout:
        pid = find_pid()
        if pid:
            seen_at = time.time()
            break
        time.sleep(a.interval)
    if not pid:
        emit(f"no {GAME.decode()} appeared within {a.timeout:.0f}s")
        return 1

    # the whole race: how fast can a 0x0410 handle be created after the pid becomes visible
    ctypes.set_last_error(0)
    handle = k32.OpenProcess(0x0410, False, pid)
    acquired = time.time()
    lag_ms = (acquired - seen_at) * 1000.0
    emit(f"pid {pid} seen; OpenProcess(0x0410) -> "
         f"{'handle' if handle else 'FAILED err=%d' % ctypes.get_last_error()} "
         f"after {lag_ms:.1f} ms of polling")

    created = wt.FILETIME()
    zero = wt.FILETIME()
    if handle and k32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(zero),
                                      ctypes.byref(zero), ctypes.byref(zero)):
        ft = (created.dwHighDateTime << 32) | created.dwLowDateTime
        created_unix = ft / 1e7 - 11644473600
        emit(f"process creation -> handle: {(acquired - created_unix) * 1000.0:.1f} ms")

    if not handle:
        emit("VERDICT: BLOCKED  even the very first OpenProcess was refused")
        return 0

    region = first_image_region(handle)
    if region is None:
        emit("VERDICT: BLOCKED  no committed MEM_IMAGE region visible through this handle")
        k32.CloseHandle(handle)
        return 0
    emit(f"first committed MEM_IMAGE region: {region:#x}")

    ok, err = read_check(handle, region)
    emit(f"t+0     ReadProcessMemory -> {'OK' if ok else 'DENIED err=%d' % err}")
    if not ok:
        emit("VERDICT: FILTERED  the handle was stripped at creation; there is no early window")
        k32.CloseHandle(handle)
        return 0

    for delay in [float(x) for x in a.samples.split(",") if x.strip()]:
        time.sleep(max(0.0, delay - (time.time() - acquired)))
        ok, err = read_check(handle, region)
        emit(f"t+{delay:<5.0f} ReadProcessMemory -> {'OK' if ok else 'DENIED err=%d' % err}")
        if not ok:
            emit("VERDICT: HANDLE REVOKED  it read once, then stopped")
            k32.CloseHandle(handle)
            return 0
    emit("VERDICT: READABLE  an early handle survives - a crash-time full dump is possible")
    k32.CloseHandle(handle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
