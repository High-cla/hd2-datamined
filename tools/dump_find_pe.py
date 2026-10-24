#!/usr/bin/env python3
"""Find PE images inside a (multi-GB) full minidump, without loading the dump.

Why this exists
    Reading anything out of a dump needs the image base, and the dump's
    ModuleListStream is not always a trustworthy source for it:

      * a manually / reflectively mapped image is not registered at all;
      * Windows keeps *copies of PE headers* in heap for some modules -- those
        are unregistered too, and if you only look at "is it in the module list"
        you will mistake them for manual maps;
      * tools that print the module list often truncate it (`dump_read_rva.py`
        prints only the first 40 of 166), which makes real modules look absent.

    So this tool ignores the module list for *finding* images: it walks every
    captured memory range, validates `MZ` .. `PE\\0\\0` + COFF/optional headers
    and reports each image with SizeOfImage / TimeDateStamp / section perms, plus
    a `kind` classification (module vs heap header copy vs unregistered orphan).

    Measured on the build-25480438 crash dumps in E:\\hd2-dumps\\kept: game.dll
    *is* a registered module there (base 0x7ffe17410000, SizeOfImage 74,727,424),
    and the only unregistered >=20 MB PEs are heap header copies of
    nvngx_dlss.dll / steamclient64.dll.  Treat `kind` as the answer, not the
    module list.

    Dumps are 10+ GB, so this streams 4 MB chunks with a 4 KB tail overlap (a PE
    header cannot straddle a chunk boundary unnoticed) and never holds more than
    one chunk in RAM.

Usage
    python dump_find_pe.py <dump>                       # scan, print ranked table
    python dump_find_pe.py <dump> --json-out out.json   # also save machine-readable
    python dump_find_pe.py <dump> --min-size 0x1400000  # only (default: 1 MB)
    python dump_find_pe.py <dump> --list-ranges         # just the memory map

Notes
    - `MZ` is searched with bytes.find (memchr), so the whole 10 GB scan is I/O bound.
    - An image nested inside another image (embedded PE, e.g. a packed payload) is
      reported with `nested_in` set to the containing image's base.
    - Protection comes from the optional MemoryInfoListStream when the dump has one.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_read_rva import Dump  # noqa: E402  (same Memory64List parsing)

MEMINFO = 16
CHUNK = 4 << 20
OVERLAP = 0x1000
MIN_E_LFANEW = 0x40
MAX_E_LFANEW = 0xFE0

MACHINES = {
    0x014C: "i386", 0x8664: "amd64", 0xAA64: "arm64",
    0x01C0: "arm", 0x01C4: "armnt", 0x0200: "ia64",
}
PROTECT = {
    0x01: "NOACCESS", 0x02: "R", 0x04: "RW", 0x08: "WC",
    0x10: "X", 0x20: "RX", 0x40: "RWX", 0x80: "WCX",
}
STATE = {0x1000: "COMMIT", 0x2000: "RESERVE", 0x10000: "FREE"}
MEMS = {0x20000: "PRIVATE", 0x40000: "MAPPED", 0x1000000: "IMAGE"}


# --------------------------------------------------------------------- helpers
def parse_pe(buf: bytes, va: int, dump: Dump | None = None) -> dict | None:
    """Validate a PE header at buf[0] (whose virtual address is `va`)."""
    if len(buf) < 0x200 or buf[:2] != b"MZ":
        return None
    (e_lfanew,) = struct.unpack_from("<I", buf, 0x3C)
    if not (MIN_E_LFANEW <= e_lfanew <= MAX_E_LFANEW) or e_lfanew + 0x40 > len(buf):
        return None
    if buf[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return None
    machine, nsect, tds = struct.unpack_from("<HHI", buf, e_lfanew + 4)
    if machine not in MACHINES or not (1 <= nsect <= 96):
        return None
    opt_size, chars = struct.unpack_from("<HH", buf, e_lfanew + 20)
    opt = e_lfanew + 24
    if opt_size < 0x60 or opt + 0x40 > len(buf):
        return None
    (magic,) = struct.unpack_from("<H", buf, opt)
    if magic == 0x20B:                      # PE32+
        (image_base,) = struct.unpack_from("<Q", buf, opt + 24)
        (size_image,) = struct.unpack_from("<I", buf, opt + 56)
        (size_heads,) = struct.unpack_from("<I", buf, opt + 60)
        (subsystem,) = struct.unpack_from("<H", buf, opt + 68)
    elif magic == 0x10B:                    # PE32
        (image_base,) = struct.unpack_from("<I", buf, opt + 28)
        (size_image,) = struct.unpack_from("<I", buf, opt + 56)
        (size_heads,) = struct.unpack_from("<I", buf, opt + 60)
        (subsystem,) = struct.unpack_from("<H", buf, opt + 68)
    else:
        return None
    if size_image <= 0 or size_image > 0x80000000 or size_image % 0x1000:
        return None
    if size_heads <= 0 or size_heads > size_image:
        return None
    # sections: name + RVA + size + IMAGE_SCN_* permission bits
    sect = []
    sbase = opt + opt_size
    if sbase + nsect * 40 <= len(buf):
        for i in range(nsect):
            off = sbase + i * 40
            raw = buf[off:off + 8].split(b"\0", 1)[0].decode("latin-1", "replace")
            vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", buf, off + 8)
            (chars,) = struct.unpack_from("<I", buf, off + 36)
            sect.append((raw, vaddr, vsize, raddr, rsize, chars))
    return {
        "va": va,
        "e_lfanew": e_lfanew,
        "machine": MACHINES[machine],
        "nsect": nsect,
        "tds": tds,
        "size_image": size_image,
        "image_base_pref": image_base,
        "size_headers": size_heads,
        "subsystem": subsystem,
        "chars": chars,
        "sections": sect,
        "aslr_ok": image_base == va,
    }


def meminfo(dump: Dump) -> list[tuple[int, int, int, int, int]]:
    """[(base, size, state, protect, type)] from MemoryInfoListStream, else []."""
    if MEMINFO not in dump.streams:
        return []
    _, rva = dump.streams[MEMINFO]
    head = dump._read_at(rva, 16)
    if len(head) < 16:
        return []
    hdr_size, ent_size, count = struct.unpack("<IIQ", head)
    if ent_size < 48 or count > 4_000_000:
        return []
    blob = dump._read_at(rva + hdr_size, ent_size * count)
    out = []
    for i in range(count):
        o = i * ent_size
        if o + 48 > len(blob):
            break
        base, _abase, _aprot, _a1, size, state, protect, typ = struct.unpack_from(
            "<QQIIQIII", blob, o)
        out.append((base, size, state, protect, typ))
    out.sort()
    return out


def meminfo_lookup(table, addr: int):
    import bisect
    if not table:
        return None
    starts = [t[0] for t in table]           # cheap enough: table is ~1e5 entries
    i = bisect.bisect_right(starts, addr) - 1
    if i < 0:
        return None
    base, size, state, protect, typ = table[i]
    if addr >= base + size:
        return None
    return {"base": base, "size": size, "state": STATE.get(state, hex(state)),
            "protect": PROTECT.get(protect & 0xFF, hex(protect & 0xFF)),
            "type": MEMS.get(typ, hex(typ))}


def perms(chars: int) -> str:
    """IMAGE_SCN_MEM_* -> rwx, plus an 'x' for executable."""
    out = ""
    out += "r" if chars & 0x40000000 else "-"
    out += "w" if chars & 0x80000000 else "-"
    out += "x" if chars & 0x20000000 else "-"
    out += "c" if chars & 0x00000020 else "-"   # CNT_CODE
    return out


def ts(tds: int) -> str:
    if not tds:
        return "-"
    try:
        return datetime.datetime.fromtimestamp(tds, datetime.timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return f"0x{tds:08x}"


def readable(n: int) -> str:
    if n >= 1 << 30:
        return f"{n / (1 << 30):.2f}G"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f}M"
    if n >= 1 << 10:
        return f"{n / (1 << 10):.1f}K"
    return str(n)


# ------------------------------------------------------------------------ scan
def scan(dump: Dump, chunk: int, progress=20.0) -> tuple[list[dict], dict]:
    images: dict[int, dict] = {}
    stats = {"ranges": 0, "bytes": 0, "mz_hits": 0, "pe_hits": 0,
             "chunks": 0, "t0": time.time(), "coverage": {}}
    total = sum(r[1] for r in dump.ranges)
    done = 0
    next_mark = progress
    t_last = time.time()
    for start, size, off in dump.ranges:
        stats["ranges"] += 1
        pos = 0
        while pos < size:
            take = min(chunk, size - pos)
            take = min(take, chunk)
            dump.f.seek(off + pos)
            buf = dump.f.read(min(take + OVERLAP, size - pos))
            if not buf:
                break
            stats["bytes"] += take
            stats["chunks"] += 1
            limit = min(take, len(buf))
            p = 0
            while True:
                q = buf.find(b"MZ", p)
                if q < 0 or q >= limit:
                    break
                p = q + 1
                stats["mz_hits"] += 1
                info = parse_pe(buf[q:q + MAX_E_LFANEW + 0x200], start + pos + q, dump)
                if not info:
                    continue
                stats["pe_hits"] += 1
                prev = images.get(info["va"])
                if prev is None:
                    images[info["va"]] = info
            pos += take
            done += take
            now = time.time()
            if now - t_last > 2.0:
                t_last = now
                pct = 100.0 * done / total if total else 100.0
                if pct >= next_mark:
                    print(f"  ... {pct:5.1f}%  {readable(done)}/{readable(total)}  "
                          f"{stats['mz_hits']:,} MZ  {stats['pe_hits']:,} PE  "
                          f"({now - stats['t0']:.0f}s)", file=sys.stderr, flush=True)
                    next_mark += progress
    stats["elapsed"] = time.time() - stats["t0"]
    return sorted(images.values(), key=lambda d: -d["size_image"]), stats


# ------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump")
    ap.add_argument("--chunk", type=lambda s: int(s, 0), default=CHUNK)
    ap.add_argument("--min-size", type=lambda s: int(s, 0), default=1 << 20)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--json-out")
    ap.add_argument("--list-ranges", action="store_true")
    ap.add_argument("--no-meminfo", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    dump = Dump(args.dump)
    print(f"{args.dump}")
    print(f"  file {os.path.getsize(args.dump):,} B | {len(dump.ranges):,} memory ranges | "
          f"{len(dump.modules)} PEB modules | parsed in {time.time() - t0:.2f}s")
    total = sum(r[1] for r in dump.ranges)
    print(f"  captured virtual bytes: {total:,} ({readable(total)})")
    if args.list_ranges:
        for start, size, off in dump.ranges[:args.top]:
            print(f"  {start:#018x} +{size:>12,}  @file+{off:#x}")
        return 0

    minfo = [] if args.no_meminfo else meminfo(dump)
    print(f"  MemoryInfoListStream: {len(minfo):,} regions"
          if minfo else "  MemoryInfoListStream: absent (protection unknown)")

    if not args.quiet:
        print("\nscanning ...", file=sys.stderr)
    images, stats = scan(dump, args.chunk)

    mod_by_base = {base: (name, size) for name, base, size in dump.modules}
    # fingerprint of every *registered* module -> lets us recognise heap copies of
    # the PE headers (Windows keeps header copies; they are unaligned & unregistered)
    mod_fingerprint = {}
    for name, base, size in dump.modules:
        hdr = dump.read_virtual(base, 0x1000)
        if not hdr:
            continue
        info = parse_pe(bytes(hdr), base)
        if info:
            mod_fingerprint.setdefault((info["size_image"], info["tds"]), []).append(name)
    # nesting: an image whose base sits inside another image's SizeOfImage window
    for img in images:
        img["nested_in"] = None
        for other in images:
            if other is img:
                continue
            if other["va"] < img["va"] < other["va"] + other["size_image"]:
                img["nested_in"] = other["va"]
                break
    # coverage of the image window by captured ranges
    rstart = [r[0] for r in dump.ranges]
    import bisect
    for img in images:
        lo, hi = img["va"], img["va"] + img["size_image"]
        captured = 0
        i = max(0, bisect.bisect_right(rstart, lo) - 1)
        while i < len(dump.ranges) and dump.ranges[i][0] < hi:
            s, sz, _ = dump.ranges[i]
            captured += max(0, min(s + sz, hi) - max(s, lo))
            i += 1
        img["captured"] = captured
        img["covered_pct"] = 100.0 * captured / img["size_image"] if img["size_image"] else 0
        mod = mod_by_base.get(img["va"])
        img["module"] = mod[0] if mod else None
        img["module_size"] = mod[1] if mod else None
        img["protect"] = meminfo_lookup(minfo, img["va"])
        img["aligned"] = (img["va"] % 0x1000) == 0
        # classify: registered module / heap header copy / genuine manual map
        if img["module"]:
            img["kind"] = "module"
        else:
            twins = mod_fingerprint.get((img["size_image"], img["tds"]), [])
            if twins:
                img["kind"] = "header-copy"
                img["twin"] = twins[0]
            elif not img["aligned"]:
                img["kind"] = "header-copy?"
            else:
                img["kind"] = "orphan"

    

    big = [im for im in images if im["size_image"] >= args.min_size]
    print(f"\nscan stats: {stats['ranges']:,} ranges | {stats['bytes']:,} B read "
          f"({readable(stats['bytes'])}) | {stats['chunks']:,} chunks | "
          f"{stats['mz_hits']:,} 'MZ' | {stats['pe_hits']:,} validated PE | "
          f"{len(images):,} unique images | {stats['elapsed']:.1f}s")
    print(f"images >= {args.min_size:,} B: {len(big)}   "
          f"unregistered: {sum(1 for im in big if not im['module'])} "
          f"(header-copies of registered modules are not manual maps)\n")

    hdr = (f"{'#':>3} {'base':>18} {'SizeOfImage':>12} {'TSD':>10} {'machine':>7} "
           f"{'sect':>4} {'cap':>7} {'prot':>6}  {'image_base_ok':>4}  module / note")
    print(hdr)
    print("-" * len(hdr))
    for i, im in enumerate(big, 1):
        prot = (im["protect"] or {}).get("protect", "?")
        if im.get("kind") == "header-copy":
            mod = f"** header-copy of {im['twin'].split(chr(92))[-1]} (unregistered) **"
        elif im.get("kind") == "orphan":
            mod = "** ORPHAN — not in PEB module list (manual map?) **"
        else:
            mod = im["module"] or "** header-copy? (unaligned) **"
        if len(mod) > 74:
            mod = mod[:24] + "..." + mod[-46:]
        extra = ""
        if im["nested_in"]:
            extra += f" nested_in={im['nested_in']:#x}"
        print(f"{i:>3} {im['va']:#018x} {im['size_image']:>12,} {ts(im['tds']):>10} "
              f"{im['machine']:>7} {im['nsect']:>4} {im['covered_pct']:>6.1f}% "
              f"{prot:>6}  {str(im['aslr_ok']):>4}  {mod}{extra}")

    # section table of the orphan(s) -- that is the interesting part
    orphans = [im for im in big if not im["module"]]
    for im in orphans:
        print(f"\nsections of orphan {im['va']:#x} (SizeOfImage {im['size_image']:,}):")
        for name, va, vs, ra, rs, ch in im["sections"]:
            print(f"  {name:>8}  RVA {va:#010x}  vsize {vs:>10,}  raw {rs:>10,}"
                  f"  {perms(ch)}")

    if args.json_out:
        slim = []
        for im in big:
            j = {k: v for k, v in im.items() if k != "sections"}
            j["sections"] = [{"name": n, "rva": va, "vsize": vs,
                              "perms": perms(ch)}
                             for n, va, vs, _ra, _rs, ch in im["sections"]]
            j["tds_iso"] = ts(im["tds"])
            slim.append(j)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"dump": args.dump, "stats": {k: v for k, v in stats.items()
                                                    if k != "t0"},
                       "images": slim}, f, indent=1)
        print(f"\njson -> {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
