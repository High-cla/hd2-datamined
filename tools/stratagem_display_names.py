#!/usr/bin/env python3
"""stratagem_display_names.py -- recover the real in-game display name of every stratagem row.

WHY THIS WORKS (and why the alias table only got 38)
    The row does not store the display name as a string; it stores a LOCALISATION ID.  Three
    neighbouring slots hold three different renderings of the same object:

        +40  u32  -> "SUPPLY PACK"        (upper-case name)
        +44  u32  -> "Supply Pack"        (the in-game display name)
        +48  u32  -> description

    Those IDs index the engine's `.strings` resources, whose format is

        magic "\xae\xf3\x85>" (4 B) | version u32 | count u32 | language ThinHash u32
        count x u32  id
        count x u32  offset   (into this same blob)
        ... NUL-terminated UTF-8 strings ...

    and whose language field is `ThinHash("us")` = 0x03F97B57 for the English copy, where
    `ThinHash(x)` is the high 32 bits of MurmurHash64A(x, seed 0) -- the same function as
    `stingray.Sum(x).Thin()` in filediver.  That equality is what confirmed the format.

    Consequence: the in-game display name of EVERY row is recoverable, and that name is what the
    wiki uses for its page titles ("Ballistic Shield Backpack" -> page "SH-20 Ballistic Shield
    Backpack").  No hash-to-name guessing and no external mapping table needed.

INPUT
    A directory of `.strings` blobs.  Produce it with srkit:

        python -m srkit unpack "<game>/data/bundles.00.nxa" -o <dir> --type strings \\
            --no-gpu --no-stream

    One bundle already resolves ~88% of the rows; the rest live in other bundles, so point this at
    as many unpacked bundles as you have.

USAGE
    python tools/stratagem_display_names.py --sk <recipient.sk> --strings <dir> \\
        --out refs/stratagem-display-names.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

HEADER = 48
DESCRIPTOR = 16
STRIDE = 400
UPPER_PTR, NAME_ID, DESC_ID = 40, 44, 48
MAGIC = b"\xae\xf3\x85>"


def murmur64a(key: bytes) -> int:
    """MurmurHash64A with seed 0 -- verified against the `language` field of real .strings blobs."""
    mix = 0xC6A4A7935BD1E995
    mask = (1 << 64) - 1
    h = (len(key) * mix) & mask
    i = 0
    while i + 8 <= len(key):
        k = struct.unpack_from("<Q", key, i)[0]
        i += 8
        k = (k * mix) & mask
        k ^= k >> 47
        k = (k * mix) & mask
        h ^= k
        h = (h * mix) & mask
    tail = key[i:]
    if tail:
        keep = {1: 0xFF, 2: 0xFFFF, 3: 0xFFFFFF, 4: 0xFFFFFFFF,
                5: 0xFFFFFFFFFF, 6: 0xFFFFFFFFFFFF, 7: 0xFFFFFFFFFFFFFF}
        h ^= int.from_bytes(tail, "little") & keep[len(tail)]
        h = (h * mix) & mask
    h ^= h >> 47
    h = (h * mix) & mask
    h ^= h >> 47
    return h


def thin(text: str) -> int:
    return (murmur64a(text.encode()) >> 32) & 0xFFFFFFFF


def load_strings(directory: pathlib.Path, language: str) -> dict[int, str]:
    """id -> text for one language, over every .strings blob found under `directory`."""
    want = thin(language)
    table: dict[int, str] = {}
    blobs = scanned = 0
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) < 16 or data[:4] != MAGIC:
            continue
        scanned += 1
        _, _version, count, lang = struct.unpack_from("<4sIII", data, 0)
        if lang != want or count <= 0 or len(data) < 16 + 8 * count:
            continue
        blobs += 1
        for index in range(count):
            ident = struct.unpack_from("<I", data, 16 + 4 * index)[0]
            offset = struct.unpack_from("<I", data, 16 + 4 * count + 4 * index)[0]
            if offset >= len(data):
                continue
            end = data.find(b"\0", offset)
            if end < 0:
                continue
            try:
                text = data[offset:end].decode("utf-8")
            except UnicodeDecodeError:
                continue
            table.setdefault(ident, text)
    print(f"strings: scanned {scanned} blobs, {blobs} are {language!r} "
          f"(ThinHash {want:#010x}), {len(table)} ids")
    return table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--strings", required=True, help="directory of unpacked .strings blobs")
    ap.add_argument("--language", default="us")
    ap.add_argument("--out", default="refs/stratagem-display-names.json")
    ap.add_argument("--wiki-db", default="refs/wiki/wiki.sqlite",
                    help="optional: attach the matching wiki page title to each row")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    table = load_strings(pathlib.Path(a.strings), a.language)

    game = pathlib.Path(a.game) / "data" / "game"
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))
    plain = box.decrypt((game / "generated_stratagem_settings.dl_bin").read_bytes())

    rows = []
    start = 0
    while True:
        at = plain.find(b"LDLD", start)
        if at < 0:
            break
        start = at + 4
        if at + 24 > len(plain):
            continue
        version, _tid, payload, _wide = struct.unpack_from("<IIII", plain, at + 4)
        if version not in (1, 2) or payload <= 0 or at + 24 + payload > len(plain):
            continue
        p0 = at + 24
        marker, count = struct.unpack_from("<QQ", plain, p0)
        if marker != DESCRIPTOR or count * STRIDE > payload:
            continue
        base, pool = p0 + DESCRIPTOR, plain[p0:]
        for i in range(count):
            row = base + i * STRIDE
            target = struct.unpack_from("<Q", plain, row + 16)[0]
            display = ""
            if 0 < target < payload:
                at_text = p0 + target          # pool is plain[p0:], so target is pool-relative
                end = plain.find(b"\0", at_text, at_text + 250)
                if end > at_text:
                    raw = plain[at_text:end]
                    if all(32 <= b <= 126 for b in raw):
                        display = raw.decode("ascii")
            upper_id = struct.unpack_from("<I", plain, row + UPPER_PTR)[0]
            name_id = struct.unpack_from("<I", plain, row + NAME_ID)[0]
            desc_id = struct.unpack_from("<I", plain, row + DESC_ID)[0]
            rows.append({
                "internal_name": display,
                "name_id": name_id,
                "upper_id": upper_id,
                "desc_id": desc_id,
                "upper": table.get(upper_id, ""),
                "display_name": table.get(name_id, ""),
                "description": table.get(desc_id, ""),
                "cells": {"type_value": struct.unpack_from("<I", plain, row)[0],
                          "uses": struct.unpack_from("<I", plain, row + 80)[0],
                          "callin": round(struct.unpack_from("<f", plain, row + 84)[0], 3),
                          "cooldown": round(struct.unpack_from("<f", plain, row + 104)[0], 3),
                          "cell": struct.unpack_from("<I", plain, row + 392)[0]},
            })

    db_path = pathlib.Path(a.wiki_db)
    if db_path.is_file():
        import re
        import sqlite3
        conn = sqlite3.connect(db_path)
        pages = [r[0] for r in conn.execute("SELECT title FROM page")]

        def flat(text):
            return re.sub(r"[^a-z0-9]", "", text.lower())

        by_flat = {flat(p): p for p in pages}
        matched = 0
        for row in rows:
            name = row["display_name"]
            if not name:
                continue
            key = flat(name)
            title, how = by_flat.get(key), "exact"
            if title is None:
                # wiki titles carry the manufacturer prefix ("SH-20 Ballistic Shield Backpack")
                cands = [p for p in pages if flat(p).endswith(key) and len(key) >= 6]
                title, how = (cands[0], "suffix") if len(cands) == 1 else (None, None)
            if title:
                row["wiki_title"] = title
                row["wiki_match"] = how
                matched += 1
        print(f"wiki pages matched: {matched}/{len([r for r in rows if r['display_name']])} "
              f"(from {len(pages)} pages)")

    named = [r for r in rows if r["display_name"]]
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"count": len(rows), "named": len(named), "rows": rows},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"rows {len(rows)}   display name recovered {len(named)}/{len(rows)}   -> {out}")
    print("\nsample:")
    for r in rows[:12]:
        print(f"  {r['internal_name']:<40} -> {r['display_name']!r:<30} "
              f"(upper {r['upper']!r})")
    missing = [r["internal_name"] for r in rows if not r["display_name"]]
    if missing:
        print(f"\nnot resolved ({len(missing)}) — ids live in bundles not unpacked yet:")
        print("  " + ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
