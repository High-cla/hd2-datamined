#!/usr/bin/env python3
"""crash_watch.py — catch the crash the second it happens, WITHOUT a debugger.

WHY THIS EXISTS (2026-10-17, user: "有什么既能抓崩溃转储又不会触发 GameGuard 的方法吗")

    Three facts measured that day, in order:

      * procdump -e / -w / -ma <pid> are DEBUGGERS.  Helldivers 2 runs nProtect GameGuard,
        which detects one and kills the process silently; the resulting dump describes the
        execution, not the crash.  (HISTORY §3.16.60)
      * WER LocalDumps is NOT a debugger and its configuration works: a test program with
        the same key (DumpType=0, CustomDumpFlags=0x21b64) produced a complete 39 MB dump
        with an ExceptionStream (tools/crashtest.exe, 2026-10-17 15:55).  On this game it
        still never completes — each repeated fault restarts the multi-GB write, so the file
        stays at 0 bytes (16 minutes of a 9 s loop).  (HISTORY §3.16.61)
      * The game's own crash reporter (CRS, in-process) writes a real dump at the instant of
        the exception — engine dump 6.2 MB with ExceptionStream, 106 thread stacks.  That is
        the only capture that is at the right moment AND immune to GameGuard.  But CRS
        deletes crash_data/.temp minutes later, and by the time a human notices, the process
        has already lost its threads: the engine capture at t+0 had 106 threads, our manual
        dump 8 minutes later had 1.

WHAT IS PUBLISHED AND WHAT IS NOT
    ``tools/dumper.ps1`` is NOT in this repository.  The external full dump it drives is dead on this
    build (EAC strips PROCESS_VM_READ), and can_read_memory() refuses before that file is ever called.
    The part that still works needs no dump code at all: rescuing the game's OWN crash capture from
    CRS's folder before CRT deletes it.

WHAT THIS DOES (no debugger anywhere):

    1. polls the two engine dump locations every --interval seconds (default 0.25);
    2. the moment a new engine dump appears, copies every CRS artifact (dump, screenshot,
       report, attach.txt) into D:\\hd2-dumps\\kept\\crash-<stamp>\\ and records hashes;
    3. runs tools/dumper.ps1 (MiniDumpWriteDump = an ordinary reader, NOT a debugger)
       against the process while its threads are still warm, for a full-memory dump;
       ★ 2026-10-20: on build 25988413 this leg is DEAD - EAC grants the handle and strips
       PROCESS_VM_READ, so MiniDumpWriteDump returns 0x80070005.  full_dump() now asks
       can_read_memory() first and says so instead of burning 900 s on a 0-byte file.
       The rescue (1/2) is unaffected and is now the whole point of this tool on this build;
    4. appends KEPT.tsv and prints "you may now kill the game".

    It NEVER kills anything.  Killing is what makes WER delete a partial dump.

USAGE
    python tools/crash_watch.py                 # watch until Ctrl-C
    python tools/crash_watch.py --once          # one pass (for a smoke test)
    python tools/crash_watch.py --no-dump       # only rescue the engine artifacts
    python tools/crash_watch.py --selftest      # exercise the rescue path on a fake crash
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time

APP = os.path.expandvars(r"%APPDATA%\Arrowhead\Helldivers2")
CRS_TEMP = os.path.join(APP, "crash_data", ".temp")
CRS_ATTACH = os.path.join(APP, "crash_data", "attachments")
CRS_DUMPS = os.path.join(APP, "dumps")
# ★ 2026-10-20: reports/ 一直是漏掉的第四个位置 —— crashpad 把**它自己抓的转储**放在
#   crash_data/reports/<uuid>.dmp（实测 4.2–6.5 MB，比 dumps/ 那批 950 KB 的引擎小转储信息更多），
#   而旧的 rescue() 只走 .temp / attachments / dumps。本 build 上外部抓取已废（见 full_dump），
#   这一份就是能留下的最好的东西。
CRS_REPORTS = os.path.join(APP, "crash_data", "reports")
DUMPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dumper.ps1")
# ★ 2026-10-17 20:0x: the archive moved to E:\hd2-dumps (D: only had ~15 GB left and one full
#   MiniDumpWriteDump of this game is 9-11 GB).  --root (or HD2_DUMP_ROOT) keeps the tool usable on
#   whichever volume has room without editing it again.
OUT_ROOT = os.environ.get("HD2_DUMP_ROOT") or "hd2-dumps"
KEEP_ROOT = os.path.join(OUT_ROOT, "kept")
LOG = os.path.join(OUT_ROOT, "crash_watch.log")
GAME_EXE = "helldivers2.exe"


def apply_root(root: str) -> None:
    """Point the archive (and its log) at another volume before the loop starts."""
    global OUT_ROOT, KEEP_ROOT, LOG
    OUT_ROOT = os.path.abspath(root)
    KEEP_ROOT = os.path.join(OUT_ROOT, "kept")
    LOG = os.path.join(OUT_ROOT, "crash_watch.log")
    os.makedirs(KEEP_ROOT, exist_ok=True)


def log(line: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    text = f"{stamp} {line}"
    print(text, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except OSError:
        pass


def md5(path: str) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_game_pid() -> int | None:
    """PID of the running game (None if it is already gone).  tasklist: no third-party deps."""
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {GAME_EXE}", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower().endswith(GAME_EXE):
            try:
                return int(parts[1])
            except ValueError:
                return None
    return None


def engine_dumps():
    """Current engine dump files: (path, size, mtime)."""
    found = []
    for root in (CRS_TEMP, CRS_REPORTS, CRS_DUMPS):
        if not os.path.isdir(root):
            continue
        for base, _dirs, files in os.walk(root):
            for name in files:
                if name.lower().endswith(".dmp"):
                    path = os.path.join(base, name)
                    try:
                        st = os.stat(path)
                    except OSError:
                        continue
                    found.append((path, st.st_size, st.st_mtime))
    return sorted(found, key=lambda item: item[2])


def rescue(path: str, stamp: str, record: bool = True) -> str:
    """Copy the engine artifacts for THIS crash into kept/crash-<stamp>/ and return the dir."""
    target = os.path.join(KEEP_ROOT, f"crash-{stamp}")
    os.makedirs(target, exist_ok=True)
    copied = []
    parent = os.path.basename(os.path.dirname(path))
    # .temp/<id>/<id>.dmp -> <id> ; reports/<uuid>.dmp -> <uuid>（attachments 用同一个 uuid 命名）
    crash_id = os.path.splitext(os.path.basename(path))[0] if parent == "reports" else parent
    wanted = [(path, os.path.basename(path))]
    for side in (os.path.join(CRS_TEMP, crash_id), os.path.join(CRS_ATTACH, crash_id),
                 CRS_REPORTS, CRS_DUMPS):
        if not os.path.isdir(side):
            continue
        for base, _dirs, files in os.walk(side):
            for name in files:
                if name.lower().endswith((".dmp", ".jpg", ".txt")):
                    src = os.path.join(base, name)
                    # only this crash's artifacts: keep the dumps folder to the last minute
                    if side in (CRS_DUMPS, CRS_REPORTS) and time.time() - os.path.getmtime(src) > 90:
                        continue
                    wanted.append((src, name))
    seen_src, seen_name = set(), set()
    for src, name in wanted:
        key = os.path.normcase(os.path.abspath(src))
        if key in seen_src:                                  # the same file reached us twice
            continue
        seen_src.add(key)
        base = name if name not in seen_name else f"{int(time.time() * 1000)}_{name}"
        seen_name.add(name)
        dst = os.path.join(target, base)
        try:
            shutil.copy2(src, dst)
            copied.append((dst, md5(dst), os.path.getsize(dst)))
        except OSError as exc:
            log(f"  ! copy failed {src}: {exc}")
    for dst, digest, size in copied:
        log(f"  saved {os.path.basename(dst)}  {size:,} B  md5 {digest}")
    if record:
        with open(os.path.join(KEEP_ROOT, "KEPT.tsv"), "a", encoding="utf-8") as fh:
            for dst, digest, size in copied:
                fh.write("%s\t%s\t%d\t%s\tCOPIED by crash_watch.py\tcomplete\n"
                         % (time.strftime("%Y-%m-%d %H:%M:%S"), os.path.relpath(dst, KEEP_ROOT),
                            size, digest))
    return target


def can_read_memory(pid: int) -> "tuple[bool, str]":
    """README-级的一问：这个句柄到底能不能读到目标的一个字节。

    ★ 2026-10-20 实测：build 25988413 的 EAC **不拒绝句柄**，它在句柄创建时把
    PROCESS_VM_READ 剥掉 —— 三档 OpenProcess 全部成功，而 ReadProcessMemory 在已提交的
    MEM_IMAGE 区上仍然 err=5，MiniDumpWriteDump 返回 0x80070005。
    所以旧版"直接调 dumper.ps1"在没有权限时会白等 900 秒再留一个 0 字节文件；
    这里先花 20 毫秒问一句，答案是否就当场说清楚。
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import eac_access_test                       # 同目录的那个 5 秒只读测试
    except Exception as exc:                          # noqa: BLE001 - 只是少了一层保护
        return True, f"preflight unavailable ({exc}); trying the dumper anyway"
    ops = eac_access_test.probe_ops(pid)
    if not ops["handle"]:
        return False, f"OpenProcess(0x0410) failed err={ops['open_err']}"
    if ops["read"]:
        return True, "handle can read the target"
    return False, (f"handle granted but ReadProcessMemory err={ops['read_err']} "
                   "(PROCESS_VM_READ stripped by the anti-cheat)")


def full_dump(stamp: str) -> str | None:
    """Full-memory dump of the still-warm process via dumper.ps1 (MiniDumpWriteDump, NOT a debugger)."""
    pid = find_game_pid()
    if not pid:
        log("  ! the game process is already gone - engine artifacts saved, no memory dump")
        return None
    readable, why = can_read_memory(pid)
    if not readable:
        log(f"  ! external full dump unavailable on this build: {why}")
        log("    (EAC grants the handle and strips PROCESS_VM_READ - measured 2026-10-20,")
        log("     docs/MEMORY-ACCESS-25988413.md; the in-process artifacts are what we keep)")
        return None
    out = os.path.join(KEEP_ROOT, f"crash-{stamp}-pid{pid}-full.dmp")
    log(f"  dumping pid {pid} -> {out}  (MiniDumpWriteMp, no debugger)")
    started = time.time()
    try:
        proc = subprocess.run(["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass",
                               "-File", DUMPER, "-TargetPid", str(pid), "-Out", out],
                              capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"  ! dumper failed to start: {exc}")
        return None
    for line in (proc.stdout or "").splitlines():
        log("    " + line.strip())
    if proc.returncode != 0 or not os.path.exists(out):
        log(f"  ! dump did not complete (rc={proc.returncode})")
        return None
    size = os.path.getsize(out)
    log(f"  FULL DUMP {size:,} B in {time.time() - started:.1f}s")
    with open(os.path.join(KEEP_ROOT, "KEPT.tsv"), "a", encoding="utf-8") as fh:
        fh.write("%s\t%s\t%d\t%s\tFULL DUMP by crash_watch.py\tcomplete\n"
                 % (time.strftime("%Y-%m-%d %H:%M:%S"), os.path.basename(out), size, md5(out)))
    return out


def banner(lines: list[str]) -> None:
    print("", flush=True)
    print("*" * 78, flush=True)
    for line in lines:
        print("* " + line, flush=True)
    print("*" * 78, flush=True)
    print("", flush=True)


def watch(interval: float, do_dump: bool, once: bool) -> int:
    log(f"watching {CRS_TEMP} and {CRS_DUMPS}")
    seen = {path for path, _s, _m in engine_dumps()}
    log(f"baseline: {len(seen)} engine dump(s) already present")
    handled = set()
    while True:
        current = engine_dumps()
        for path, size, mtime in current:
            if path in seen or path in handled:
                continue
            handled.add(path)
            stamp = time.strftime("%H%M%S")
            log(f"CRASH DETECTED  {path}  {size:,} B")
            begin = time.time()
            target = rescue(path, stamp)
            log(f"  engine artifacts rescued in {(time.time() - begin) * 1000:.0f} ms -> {target}")
            dumped = full_dump(stamp) if do_dump else None
            banner([f"KEPT {target}",
                    f"full dump: {dumped or 'not taken'}",
                    "",
                    "you may now kill the game - both files are out of CRS's folder",
                    "this tool never attaches a debugger and never kills anything"])
        if once:
            log(f"one pass: {len(handled)} new crash(es)")
            return 0 if handled else 1
        time.sleep(interval)


def selftest() -> int:
    """Create a fake CRS capture and prove the rescue path copies it + hashes it + logs it."""
    import tempfile
    stamp = "selftest"
    fake_id = "00000000-0000-0000-0000-000000000000"
    made = []
    try:
        src_dir = os.path.join(CRS_TEMP, fake_id)
        os.makedirs(src_dir, exist_ok=True)
        fake = os.path.join(src_dir, fake_id + ".dmp")
        with open(fake, "wb") as fh:
            fh.write(b"MDMP" + b"\0" * 60)
        made.append(fake)
        attach = os.path.join(CRS_ATTACH, fake_id)
        os.makedirs(attach, exist_ok=True)
        report = os.path.join(attach, "crash-report.txt")
        with open(report, "w", encoding="utf-8") as fh:
            fh.write("selftest\n")
        made.append(report)
        target = rescue(fake, "selftest", record=False)
        ok = os.path.isdir(target) and os.path.exists(os.path.join(target, fake_id + ".dmp"))
        print("SELFTEST", "PASS" if ok else "FAIL", "->", target)
        return 0 if ok else 1
    finally:
        for path in made:
            try:
                os.remove(path)
            except OSError:
                pass
        for d in (os.path.join(CRS_ATTACH, fake_id), os.path.join(CRS_TEMP, fake_id)):
            try:
                os.rmdir(d)
            except OSError:
                pass
        shutil.rmtree(os.path.join(KEEP_ROOT, "crash-selftest"), ignore_errors=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="rescue the game's own crash dump the moment it appears")
    ap.add_argument("--interval", type=float, default=0.25)
    ap.add_argument("--root", default=os.environ.get("HD2_DUMP_ROOT") or OUT_ROOT,
                    help="archive root (default: E:\\hd2-dumps or HD2_DUMP_ROOT)")
    ap.add_argument("--watch", action="store_true", help="watch continuously (the default)")
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--no-dump", action="store_true", help="only rescue the engine artifacts")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    apply_root(args.root)
    if args.selftest:
        return selftest()
    return watch(args.interval, do_dump=not args.no_dump, once=args.once)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
