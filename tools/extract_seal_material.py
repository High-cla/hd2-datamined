#!/usr/bin/env python3
"""Extract the precomputed sealed-box material out of a mod's ``boot.lua``.

SCOPE AND WHAT MUST NEVER BE PUBLISHED
    Some community mods ship a **fixed-ephemeral** sealed-box material so that pure Lua can rewrite
    ``data/game/generated_*.dl_bin`` at runtime: with the ephemeral secret baked in, the XSalsa20
    keystream is a constant, so "sealing" degenerates to

        epk || Poly1305(cipher, poly) || cipher,   cipher = plaintext XOR keystream[32:]

    This tool only *reads* that material out of a mod file you already have locally, so that our own
    re-sealing code can speak the same format as that mod.  It contains no key material itself, and
    this repository ships none.

    The files it writes ARE key material (a Poly1305 key and a usable keystream).  Do not commit them,
    do not paste them into an issue, do not attach them to a mod you publish.  When you need to show
    someone what a run produced, use ``--share-safe``: the same report with every secret replaced by a
    ``<redacted: N B>`` placeholder, so the structure is reviewable and the material is not.

HOW THE MATERIAL APPEARS IN THE LUA
    It lives in the source as a table built by a self-invoking function:

        local material = (function()
            ...
            return { keystream = "\\NNN\\NNN...", epk = "...", poly = "...", max_len = 65536 }
        end)()

    We do **not** trust a hand-rolled parser for that: the strings are full of decimal escapes, so we
    hand the extracted expression to a real Lua 5.1 (lupa) and read the resulting table.

USAGE
    python extract_seal_material.py <mod>/boot.lua -o <dir>
        # writes keystream.bin, epk.bin, poly.bin, material.json   <- key material, keep local
    python extract_seal_material.py <mod>/boot.lua -o <dir> --share-safe
        # same analysis, secrets replaced by placeholders in material.json (nothing secret in the .bin
        # files either: they are not written in this mode)

    --share-safe prints and keeps only lengths, hashes and the structural claims below; the .bin files
    are skipped on purpose, because "just don't commit them" has failed for everyone who ever tried.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

from lupa import lua51

OPENERS = ("local material = (function()", "material = (function()")

REDACTED = "<redacted: {} B>"


def extract_expression(source: str) -> str:
    start = -1
    for opener in OPENERS:
        start = source.find(opener)
        if start >= 0:
            body_start = start + opener.index("(function()")
            break
    if start < 0:
        raise SystemExit("extract: no `material = (function()` found - wrong file?")
    end = source.find("\nend)()", body_start)
    if end < 0:
        raise SystemExit("extract: no closing `end)()` after the material function")
    return source[body_start:end + len("\nend)()")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lua")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--share-safe", action="store_true",
                    help="write no .bin files and redact every secret in material.json")
    args = ap.parse_args()

    source = open(args.lua, encoding="utf-8", errors="surrogateescape").read()
    expression = extract_expression(source)
    print(f"{args.lua}: material expression {len(expression):,} chars")

    # encoding=None: the fields are raw binary, a UTF-8 decoding runtime would choke on them
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True, encoding=None)
    chunk = runtime.execute(b"return function(src) return loadstring('return ' .. src)() end")
    try:
        table = chunk(expression.encode("ascii", "surrogateescape"))
    except Exception as exc:                                  # noqa: BLE001
        raise SystemExit(f"extract: material did not evaluate: {exc}")

    fields = {}
    for key in (b"keystream", b"epk", b"poly"):
        try:
            value = table[key]
        except Exception:                                     # noqa: BLE001
            raise SystemExit(f"extract: material has no `{key.decode()}` field")
        if not isinstance(value, bytes):
            raise SystemExit(f"extract: material.{key.decode()} is {type(value).__name__}, "
                             f"expected a binary string")
        fields[key.decode()] = value
    max_len = None
    try:
        max_len = table[b"max_len"]
    except Exception:                                         # noqa: BLE001
        pass

    os.makedirs(args.out, exist_ok=True)
    for key, blob in fields.items():
        if args.share_safe:
            print(f"  {key:9s} {len(blob):>6,} B  sha256 {hashlib.sha256(blob).hexdigest()[:16]}  "
                  f"(not written)")
            continue
        path = os.path.join(args.out, f"{key}.bin")
        with open(path, "wb") as handle:
            handle.write(blob)
        print(f"  {key:9s} {len(blob):>6,} B  sha256 {hashlib.sha256(blob).hexdigest()[:16]}  {path}")

    # the two structural claims that make this material usable at all
    poly_matches = fields["poly"] == fields["keystream"][:32]
    print(f"  poly == keystream[:32] : {poly_matches}")
    print(f"  usable plaintext       : {len(fields['keystream']) - 32:,} B "
          f"(max_len field says {max_len})")

    meta = {
        "source": os.path.basename(args.lua),
        "keystream_len": len(fields["keystream"]),
        "epk": REDACTED.format(len(fields["epk"])) if args.share_safe else fields["epk"].hex(),
        "poly": REDACTED.format(len(fields["poly"])) if args.share_safe else fields["poly"].hex(),
        "poly_equals_keystream_prefix": poly_matches,
        "max_len_field": max_len,
        "usable_plaintext": len(fields["keystream"]) - 32,
        "sha256": {k: hashlib.sha256(v).hexdigest() for k, v in fields.items()},
    }
    with open(os.path.join(args.out, "material.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"wrote {os.path.join(args.out, 'material.json')}")
    if not args.share_safe:
        print("\n!! the files just written are KEY MATERIAL. do not commit, paste or publish them.")
        print("   re-run with --share-safe if you need a report you can show someone.")
    return 0 if poly_matches else 1


if __name__ == "__main__":
    sys.exit(main())
