#!/usr/bin/env python3
"""Search a loaded PE image inside a (multi-GB) minidump for a float constant table.

Why this exists
    We have a *derived* model of Helldivers 2's armor-class table (offline math +
    in-game readback):

        RATING = 50 + 50*A     SPEED = 500*S     STAMINA = 100*(2 - F)
        light  A=0.0 S=1.1 F=0.75   ->  50 / 550 / 125
        medium A=1.0 S=1.0 F=1.0    -> 100 / 500 / 100
        heavy  A=2.0 S=0.9 F=1.5    -> 150 / 450 / 50

    and a damage curve A = -1/0/1/2/3 -> x1.66 / x1.25 / x1.00 / x0.75 / x0.65.

    The *in-memory* encoding is unknown: it may be [A,S,F] rows (AoS), three parallel
    arrays (SoA), percentages (110/100/90) or the displayed integers (550/500/450).
    So instead of one exact byte pattern we

      1. seed-scan the image for rare float/int constants (memchr on the 4-byte
         encoding -- fast enough for 70 MB of .text),
      2. cluster seeds that sit within a small radius of each other,
      3. match a catalogue of candidate *layouts* at every cluster,
      4. dump hex + float windows + protection + nearby strings for each hit.

    Nothing is written; the dump is opened read-only.

Usage
    python dump_find_class_table.py <dump> --module game.dll
    python dump_find_class_table.py <dump> --base 0x7ffe17410000 --size 0x4744000
    python dump_find_class_table.py <dump> --base ... --window 0x263c000:0x2000000
    python dump_find_class_table.py <dump> --base ... --at 0x2664240 --len 256
    python dump_find_class_table.py <dump> --base ... --grep "light|medium|heavy"
    python dump_find_class_table.py <dump> --base ... --json-out hits.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dump_read_rva import Dump                      # noqa: E402
from dump_find_pe import parse_pe, meminfo, meminfo_lookup, ts  # noqa: E402

CHUNK = 4 << 20
SEED_CAP = 400_000          # per-seed hit cap (protects RAM on common values)


# ------------------------------------------------------------------ seed values
# (label, python float) -- encoded as little-endian f32 (and selectively f64).
F32_SEEDS = [
    ("1.1", 1.1), ("0.9", 0.9), ("0.75", 0.75), ("1.5", 1.5),
    ("1.66", 1.66), ("1.65", 1.65), ("0.65", 0.65), ("1.25", 1.25),
    ("550", 550.0), ("450", 450.0), ("125", 125.0), ("150", 150.0),
    ("110", 110.0), ("90", 90.0),
    ("-1/3", -1.0 / 3.0), ("1/3", 1.0 / 3.0), ("2/3", 2.0 / 3.0),
]
F64_SEEDS = [("1.1d", 1.1), ("0.9d", 0.9), ("0.75d", 0.75), ("1.5d", 1.5)]
I32_SEEDS = [("110i", 110), ("90i", 90), ("550i", 550), ("450i", 450),
             ("125i", 125), ("150i", 150)]

SMALL = 0.001               # "is this float ~equal" tolerance for pattern slots


def enc_seeds() -> list[tuple[str, bytes]]:
    out = []
    for lab, v in F32_SEEDS:
        out.append(("f32:" + lab, struct.pack("<f", v), 4))
    for lab, v in F64_SEEDS:
        out.append(("f64:" + lab, struct.pack("<d", v), 8))
    for lab, v in I32_SEEDS:
        out.append(("i32:" + lab, struct.pack("<i", v), 4))
    return out


# ------------------------------------------------------------------- patterns
ANY = None


def F(v):
    return ("f32", v, SMALL)


def Fi(v):
    return ("i32", v, 0)


def Fx(v):
    """Exact-ish f32 token: 1.1f stored in memory is 1.1000000238, not the f64 1.1,
    so compare with a tolerance that is far below the spacing of our constants
    (>=0.05) but far above one f32 ulp."""
    return ("f32", v, 1e-5 * max(1.0, abs(v)))


PATTERNS = [
    # ---- armor class, AoS [A,S,F] rows (the model as stated)
    ("AoS_ASF", 4, [Fx(0.0), Fx(1.1), Fx(0.75), Fx(1.0), Fx(1.0), Fx(1.0),
                    Fx(2.0), Fx(0.9), Fx(1.5)]),
    ("AoS_SF", 4, [Fx(1.1), Fx(0.75), Fx(1.0), Fx(1.0), Fx(2.0), Fx(0.9), Fx(1.5)]),
    ("AoS_SFA", 4, [Fx(1.1), Fx(0.75), Fx(0.0), Fx(1.0), Fx(1.0), Fx(1.0),
                    Fx(0.9), Fx(1.5), Fx(2.0)]),
    ("AoS_FSA", 4, [Fx(0.75), Fx(1.1), Fx(0.0), Fx(1.0), Fx(1.0), Fx(1.0),
                    Fx(1.5), Fx(0.9), Fx(2.0)]),
    # ---- armor class, SoA columns
    ("SoA_S", 4, [Fx(1.1), Fx(1.0), Fx(0.9)]),
    ("SoA_F", 4, [Fx(0.75), Fx(1.0), Fx(1.5)]),
    ("SoA_A", 4, [Fx(0.0), Fx(1.0), Fx(2.0)]),
    ("SoA_S_pctAoS", 4, [Fx(1.1), ANY, Fx(1.0), ANY, Fx(0.9)]),
    ("SoA_F_pctAoS", 4, [Fx(0.75), ANY, Fx(1.0), ANY, Fx(1.5)]),
    # ---- displayed values, if the table stores what the UI shows
    ("disp_rating", 4, [Fx(50.0), Fx(100.0), Fx(150.0)]),
    ("disp_speed", 4, [Fx(550.0), Fx(500.0), Fx(450.0)]),
    ("disp_stamina", 4, [Fx(125.0), Fx(100.0), Fx(50.0)]),
    ("disp_i_rating", 4, [Fi(50), Fi(100), Fi(150)]),
    ("disp_i_speed", 4, [Fi(550), Fi(500), Fi(450)]),
    ("disp_i_stamina", 4, [Fi(125), Fi(100), Fi(50)]),
    # ---- percentages instead of multipliers
    ("pct_speed_i", 4, [Fi(110), Fi(100), Fi(90)]),
    ("pct_stam_i", 4, [Fi(75), Fi(100), Fi(150)]),
    ("pct_speed_f", 4, [Fx(110.0), Fx(100.0), Fx(90.0)]),
    ("pct_stam_f", 4, [Fx(75.0), Fx(100.0), Fx(150.0)]),
    # ---- damage curve
    ("dmg_mult_a", 4, [Fx(1.66), Fx(1.25), Fx(1.0), Fx(0.75), Fx(0.65)]),
    ("dmg_mult_b", 4, [Fx(1.65), Fx(1.25), Fx(1.0), Fx(0.75), Fx(0.65)]),
    ("dmg_mult_c", 4, [Fx(1.66), Fx(1.25), Fx(1.0), Fx(0.75), Fx(0.6)]),
    ("SoA_dmg_A", 4, [Fx(-1.0), Fx(0.0), Fx(1.0), Fx(2.0), Fx(3.0)]),
    ("AoS_dmg", 4, [Fx(-1.0), Fx(1.66), Fx(0.0), Fx(1.25), Fx(1.0), Fx(1.0),
                    Fx(2.0), Fx(0.75), Fx(3.0), Fx(0.65)]),
    ("AoS_dmg_b", 4, [Fx(-1.0), Fx(1.65), Fx(0.0), Fx(1.25), Fx(1.0), Fx(1.0),
                      Fx(2.0), Fx(0.75), Fx(3.0), Fx(0.65)]),
    # ---- VERIFIED layout in build 25480438: {f32 A; f32 mult} rows, stride 8,
    #      stored descending in A (3,2,1,0,-1).  Found at RVA 0x21ceff0.
    ("AoS_dmg_desc", 4, [Fx(3.0), Fx(0.65), Fx(2.0), Fx(0.75), Fx(1.0), Fx(1.0),
                         Fx(0.0), Fx(1.25), Fx(-1.0), Fx(1.66)]),
    ("AoS_dmg_desc_b", 4, [Fx(3.0), Fx(0.6), Fx(2.0), Fx(0.75), Fx(1.0), Fx(1.0),
                           Fx(0.0), Fx(1.25), Fx(-1.0), Fx(1.65)]),
    # ---- same tables but stored in descending class order (the damage curve we
    #      actually recovered at RVA 0x21ceff0 is stored heavy-first, so try it)
    ("AoS_ASF_rev", 4, [Fx(2.0), Fx(0.9), Fx(1.5), Fx(1.0), Fx(1.0), Fx(1.0),
                        Fx(0.0), Fx(1.1), Fx(0.75)]),
    ("AoS_SFA_rev", 4, [Fx(0.9), Fx(1.5), Fx(2.0), Fx(1.0), Fx(1.0), Fx(1.0),
                        Fx(1.1), Fx(0.75), Fx(0.0)]),
    ("AoS_FSA_rev", 4, [Fx(1.5), Fx(0.9), Fx(2.0), Fx(1.0), Fx(1.0), Fx(1.0),
                        Fx(0.75), Fx(1.1), Fx(0.0)]),
    ("SoA_S_rev", 4, [Fx(0.9), Fx(1.0), Fx(1.1)]),
    ("SoA_F_rev", 4, [Fx(1.5), Fx(1.0), Fx(0.75)]),
    ("SoA_A_rev", 4, [Fx(2.0), Fx(1.0), Fx(0.0)]),
    ("AoS_ASF_s8", 8, [Fx(0.0), Fx(1.1), Fx(0.75), Fx(1.0), Fx(1.0), Fx(1.0),
                       Fx(2.0), Fx(0.9), Fx(1.5)]),
    ("AoS_ASF_s8_rev", 8, [Fx(2.0), Fx(0.9), Fx(1.5), Fx(1.0), Fx(1.0), Fx(1.0),
                           Fx(0.0), Fx(1.1), Fx(0.75)]),
    ("AoS_ASF_pad4", 4, [Fx(0.0), Fx(1.1), Fx(0.75), ANY, Fx(1.0), Fx(1.0),
                         Fx(1.0), ANY, Fx(2.0), Fx(0.9), Fx(1.5), ANY]),
    ("AoS_ASF_pad4_rev", 4, [Fx(2.0), Fx(0.9), Fx(1.5), ANY, Fx(1.0), Fx(1.0),
                             Fx(1.0), ANY, Fx(0.0), Fx(1.1), Fx(0.75), ANY]),
    # ---- rating-first rows: {rating, speed_mult, stamina_mult}
    ("AoS_rating_SF", 4, [Fx(50.0), Fx(1.1), Fx(0.75), Fx(100.0), Fx(1.0),
                          Fx(1.0), Fx(150.0), Fx(0.9), Fx(1.5)]),
    ("AoS_disp_full", 4, [Fx(50.0), Fx(550.0), Fx(125.0), Fx(100.0), Fx(500.0),
                          Fx(100.0), Fx(150.0), Fx(450.0), Fx(50.0)]),
    ("AoS_disp_full_rev", 4, [Fx(150.0), Fx(450.0), Fx(50.0), Fx(100.0), Fx(500.0),
                              Fx(100.0), Fx(50.0), Fx(550.0), Fx(125.0)]),
]
F32 = "<f"
I32 = "<i"


# ------------------------------------------------------------------- utilities
def read_span(dump: Dump, va: int, length: int) -> tuple[bytearray, int]:
    """Read [va, va+length) stitching ranges; missing pages read as zeros."""
    buf = bytearray(length)
    hi = va + length
    covered = 0
    for start, size, off in dump.ranges:
        if start + size <= va or start >= hi:
            continue
        lo = max(start, va)
        hi2 = min(start + size, hi)
        dump.f.seek(off + (lo - start))
        chunk = dump.f.read(hi2 - lo)
        buf[lo - va: lo - va + len(chunk)] = chunk
        covered += len(chunk)
    return buf, covered


def _perms(chars: int) -> str:
    return (("r" if chars & 0x40000000 else "-") +
            ("w" if chars & 0x80000000 else "-") +
            ("x" if chars & 0x20000000 else "-"))


def section_of(sections, rva: int) -> str:
    """Section index + scrubbed name + IMAGE_SCN_* perms (MemInfoList is absent)."""
    for idx, sec in enumerate(sections):
        name, sva, svs = sec[0], sec[1], sec[2]
        chars = sec[5] if len(sec) > 5 else 0
        if sva <= rva < sva + max(svs, 0x1000):
            return f"S{idx} {name.strip() or '<scrubbed>'} {_perms(chars)}"
    return "<outside image sections>"


def fmt_floats(blob: bytes, rva0: int, off: int, n: int = 24) -> list[str]:
    """Render n f32 starting at blob[off] as 6-per-line rows labelled by RVA."""
    lines = []
    for row in range(0, n, 6):
        vals = []
        for i in range(row, min(row + 6, n)):
            o = off + i * 4
            if o < 0 or o + 4 > len(blob):
                vals.append(" " * 12)
                continue
            (v,) = struct.unpack_from("<f", blob, o)
            vals.append(f"{v:+.6g}")
        lines.append(f"     [0x{rva0 + off + row * 4:08x}] "
                     + " ".join(f"{v:>12}" for v in vals))
    return lines


def hexdump(blob: bytes, base_rva: int, off: int, n: int = 96) -> list[str]:
    out = []
    lo = max(0, off - n // 2)
    hi = min(len(blob), off + n // 2)
    lo -= lo % 16
    for o in range(lo, hi, 16):
        row = blob[o:o + 16]
        hexs = " ".join(f"{b:02x}" for b in row)
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        out.append(f"     0x{base_rva + o:08x}  {hexs:<47}  {txt}")
    return out


def nearby_strings(dump: Dump, va: int, span: int = 0x2000,
                   needles=(b"light", b"medium", b"heavy", b"Light", b"Medium",
                            b"Heavy", b"armor", b"Armor", b"stamina", b"Stamina",
                            b"speed", b"Speed", b"rating", b"Rating")) -> dict:
    blob, _ = read_span(dump, va - span, span * 2)
    found = {}
    for n in needles:
        idx = blob.find(n)
        while idx >= 0:
            key = n.decode()
            found.setdefault(key, []).append(va - span + idx)
            idx = blob.find(n, idx + 1)
    # UTF-16LE variants
    for n in (b"light", b"medium", b"heavy"):
        u = b"".join(bytes([c, 0]) for c in n)
        if u in blob:
            found.setdefault(n.decode() + "(u16)", []).append(va - span + blob.find(u))
    return found


def match_patterns(blob: bytes, rva0: int, off_lo: int,
                   off_hi: int) -> list[tuple[str, int]]:
    """Try every 4-byte-aligned (in RVA space) start in [off_lo,off_hi)."""
    hits = []
    for name, stride, toks in PATTERNS:
        need = len(toks) * stride
        lo = max(0, off_lo)
        lo += (-(rva0 + lo)) % 4                  # first start whose RVA % 4 == 0
        for start in range(lo, min(len(blob) - need, off_hi), 4):
            ok = True
            for i, tok in enumerate(toks):
                if tok is ANY:
                    continue
                kind, val, tol = tok
                o = start + i * stride
                if kind == "f32":
                    (cur,) = struct.unpack_from("<f", blob, o)
                elif kind == "i32":
                    (cur,) = struct.unpack_from("<i", blob, o)
                else:
                    ok = False
                    break
                if not (abs(cur - val) <= tol):   # NaN-safe: NaN never matches
                    ok = False
                    break
            if ok:
                hits.append((name, start))
    return hits


# ------------------------------------------------------------------------ scan
def scan_image(dump: Dump, lo: int, hi: int, base: int, seeds, chunk: int,
               verbose: bool, align: int = 4) -> tuple[list[tuple[int, str]], dict]:
    hits: list[tuple[int, str]] = []
    counts: dict[str, int] = {lab: 0 for lab, _p, _s in seeds}
    truncated: set[str] = set()
    t0 = time.time()
    bytes_read = 0
    for start, size, off in dump.ranges:
        if start + size <= lo or start >= hi:
            continue
        pos = max(lo, start)
        end = min(hi, start + size)
        while pos < end:
            take = min(chunk, end - pos)
            dump.f.seek(off + (pos - start))
            buf = dump.f.read(take)
            if not buf:
                break
            bytes_read += len(buf)
            for lab, pat, step in seeds:
                idx = buf.find(pat)
                while idx >= 0:
                    # A float seed that is not naturally aligned is almost always
                    # the tail of an 8-byte pointer (ptr+6 / ptr+2) faking a
                    # small-magnitude float -- drop those.
                    if ((pos + idx - base) % step) == 0:
                        counts[lab] += 1
                        if counts[lab] <= SEED_CAP:
                            hits.append((pos + idx, lab))
                        elif lab not in truncated:
                            truncated.add(lab)
                    idx = buf.find(pat, idx + 1)
            pos += take
    if verbose:
        print(f"  scanned {bytes_read:,} B in {time.time() - t0:.1f}s; "
              f"{len(hits):,} seed hits", file=sys.stderr)
        for lab, c in sorted(counts.items(), key=lambda kv: -kv[1]):
            if c:
                print(f"    {lab:<10} {c:>9,}{'  (capped)' if lab in truncated else ''}",
                      file=sys.stderr)
    return hits, {"counts": counts, "truncated": sorted(truncated),
                  "bytes": bytes_read, "seconds": round(time.time() - t0, 2)}


def cluster(hits, radius: int) -> list[dict]:
    if not hits:
        return []
    hits.sort()
    out = []
    cur = [hits[0]]
    for va, lab in hits[1:]:
        if va - cur[0][0] <= radius:
            cur.append((va, lab))
        else:
            out.append(cur)
            cur = [(va, lab)]
    out.append(cur)
    clusters = []
    for grp in out:
        labs = {lab for _va, lab in grp}
        clusters.append({"lo": grp[0][0], "hi": grp[-1][0],
                         "seeds": sorted(labs), "score": len(labs),
                         "values": sorted({lab.split(":")[1] for lab in labs})})
    clusters.sort(key=lambda c: (-c["score"], c["lo"]))
    return clusters


# ------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump")
    ap.add_argument("--module", help="module name to look up in the PEB ModuleList")
    ap.add_argument("--base", type=lambda s: int(s, 0), help="image base VA")
    ap.add_argument("--size", type=lambda s: int(s, 0), help="SizeOfImage override")
    ap.add_argument("--window", help="RVA:len sub-window inside the image (hex)")
    ap.add_argument("--at", type=lambda s: int(s, 0), help="RVA to hex/float dump")
    ap.add_argument("--len", type=int, default=256)
    ap.add_argument("--grep", help="regex over ASCII+UTF16 strings in the image")
    ap.add_argument("--radius", type=int, default=128, help="cluster radius (bytes)")
    ap.add_argument("--align", type=int, default=4,
                    help="natural alignment required for a seed hit (bytes)")
    ap.add_argument("--min-score", type=int, default=2, help="cluster distinct-seed floor")
    ap.add_argument("--show", type=int, default=25, help="clusters to print")
    ap.add_argument("--chunk", type=lambda s: int(s, 0), default=CHUNK)
    ap.add_argument("--json-out")
    ap.add_argument("--max-strings", type=int, default=200)
    args = ap.parse_args()

    dump = Dump(args.dump)
    if args.base:
        base = args.base
    else:
        found = dump.find_module(args.module or "game.dll")
        if not found:
            print(f"module {args.module} not in ModuleList; use --base", file=sys.stderr)
            return 1
        _name, base, size = found
        args.size = args.size or size
        print(f"module {_name}\n  base {base:#x}  SizeOfImage {size:#x} ({size:,})")
    if not args.size:
        hdr, cov = read_span(dump, base, 0x1000)
        info = parse_pe(bytes(hdr[:0x1000]), base)
        if not info:
            print("no PE header at that base; pass --size", file=sys.stderr)
            return 1
        args.size = info["size_image"]
    hdr, _ = read_span(dump, base, 0x1000)
    info = parse_pe(bytes(hdr[:0x1000]), base) or {}
    sections = info.get("sections", [])
    print(f"  SizeOfImage {args.size:,}  TSD {ts(info.get('tds', 0))}  "
          f"sections {len(sections)}")

    if args.grep:
        return do_grep(dump, base, args)
    if args.at is not None:
        return do_at(dump, base, args, sections)

    lo, hi = base, base + args.size
    if args.window:
        a, b = args.window.split(":")
        lo = base + int(a, 0)
        hi = min(hi, base + int(b, 0))
    print(f"  scan window {lo:#x}..{hi:#x} ({(hi - lo) / 2**20:.1f} MB)")

    seeds = enc_seeds()
    print(f"  {len(seeds)} seed patterns", file=sys.stderr)
    hits, stats = scan_image(dump, lo, hi, base, seeds, args.chunk,
                             verbose=True, align=args.align)
    cl = cluster(hits, args.radius)
    good = [c for c in cl if c["score"] >= args.min_score]
    print(f"\n{len(hits):,} hits -> {len(cl):,} clusters, {len(good):,} with "
          f">= {args.min_score} distinct rare seeds (radius {args.radius} B)\n")

    minfo = meminfo(dump)
    shown = 0
    results = []
    for c in good:
        rva = c["lo"] - base
        win_lo = max(0, c["lo"] - base - 32)
        win_hi = min(args.size, c["hi"] - base + 64)
        blob, cov = read_span(dump, base + win_lo, win_hi - win_lo)
        pat = match_patterns(blob, win_lo, max(0, c["lo"] - base - win_lo - 8),
                             min(len(blob), c["hi"] - base - win_lo + 8))
        rec = {
            "rva": rva, "va": c["lo"], "hi_va": c["hi"], "seeds": c["values"],
            "score": c["score"],
            "section": section_of(sections, rva),
            "protect": meminfo_lookup(minfo, c["lo"]),
            "patterns": [{"name": n, "rva": win_lo + s} for n, s in pat],
        }
        rec["nearby_strings"] = nearby_strings(dump, c["lo"])
        results.append(rec)
        if shown >= args.show:
            continue
        shown += 1
        print(f"--- #{shown}  RVA 0x{rva:08x} (VA 0x{c['lo']:x})  "
              f"section {rec['section']}  seeds={','.join(c['values'])}")
        prot = rec["protect"]
        if prot:
            print(f"    page: protect={prot['protect']} type={prot['type']} "
                  f"region={prot['base']:#x}+{prot['size']:,}")
        else:
            print("    page: MemoryInfoListStream absent -> ownership from PE "
                  "section field only")
        if pat:
            for n, s in pat:
                print(f"    *** PATTERN {n} @ RVA 0x{win_lo + s:08x}")
        if rec["nearby_strings"]:
            print(f"    strings: " + ", ".join(
                f"{k}@{v[0]:#x}" for k, v in list(rec["nearby_strings"].items())[:8]))
        off = c["lo"] - base - win_lo
        for line in fmt_floats(blob, win_lo, off, 20):
            print(line)
        for line in hexdump(blob, win_lo, off, 96):
            print(line)
        print()

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"dump": args.dump, "base": base, "size": args.size,
                       "seed_stats": stats, "clusters": len(cl),
                       "hits": len(hits), "results": results}, f, indent=1)
        print(f"json -> {args.json_out}")
    return 0


def do_at(dump: Dump, base: int, args, sections) -> int:
    va = base + args.at
    blob, cov = read_span(dump, va, args.len)
    print(f"VA 0x{va:x} (RVA 0x{args.at:x}) section "
          f"{section_of(sections, args.at)}  covered {cov}/{args.len}")
    for line in fmt_floats(blob, args.at, 0, args.len // 4):
        print(line)
    print()
    for o in range(0, len(blob), 16):
        row = blob[o:o + 16]
        hexs = " ".join(f"{b:02x}" for b in row)
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        print(f"  0x{args.at + o:08x}  {hexs:<47}  {txt}")
    return 0


def do_grep(dump: Dump, base: int, args) -> int:
    """Regex over ASCII + UTF-16LE strings inside the image window."""
    # accept \xNN escapes as well as plain text, so binary-ish needles work
    needle = (args.grep.encode().decode("unicode_escape").encode("latin-1")
              if "\\x" in args.grep else args.grep.encode())
    rx = re.compile(needle)
    lo, hi = base, base + args.size
    n = 0
    step = 8 << 20
    for start, size, off in dump.ranges:
        if start + size <= lo or start >= hi:
            continue
        pos = max(lo, start)
        end = min(hi, start + size)
        while pos < end:
            take = min(step, end - pos)
            dump.f.seek(off + (pos - start))
            blob = dump.f.read(take)
            if not blob:
                break
            for m in rx.finditer(blob):
                rva = pos - base + m.start()
                ctx = blob[max(0, m.start() - 32):m.start() + 56]
                print(f"  0x{rva:08x}  {len(m.group())}B  {m.group()[:32]!r}  ctx={ctx!r}")
                n += 1
                if n >= args.max_strings:
                    print(f"  ... capped at {args.max_strings}")
                    return 0
            pos += take
    print(f"  {n} matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
