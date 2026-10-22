#!/usr/bin/env python3
"""fetch_wiki_modules.py -- pull the wiki's decoded-data modules on demand.

The wiki's `Module:` namespace holds the community's decoded dumps of the game's settings tables
(`Decodedata-Attacks/data.json` and friends).  They are useful as a FIELD-NAME DICTIONARY and as a
structural reference -- see docs/WIKI-DATA-MODULES.md -- but their numbers come from various builds
and disagree with ours in places, and they are the wiki's content, so they are not vendored here.

Requires a browser-looking User-Agent: the wiki answers 403 to Python's default.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import urllib.request

MODULES = [
    "Module:Decodedata-Attacks/data.json",
    "Module:Decodedata-Attacks-2/data.json",
    "Module:Decodedata-Attacks/enemydata.json",
    "Module:Decodedata-Attacks/status data.json",
    "Module:Decodedata-Attacks/stratagems data.json",
    "Module:Decodedata-Attacks/stratagemdata.json",
    "Module:Decodedata-Attacks/weapons data.json",
    "Module:Decodedata-Attacks/new gear.json",
    "Module:Decodedata-Weapons/data.json",
    "Module:Weapon Attach/data.json",
    "Module:Weapon Attach/data weapons.json",
    "Module:Weapon Attach/attachments.json",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="refs/wiki/modules")
    ap.add_argument("--module", action="append", default=[],
                    help="fetch only this Module: page (repeatable)")
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    wanted = a.module or MODULES
    failures = 0
    for page in wanted:
        slug = page.replace("Module:", "").replace("/", "__").replace(" ", "_")
        url = ("https://helldivers.wiki.gg/wiki/"
               + page.replace(" ", "_") + "?action=raw")
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            data = urllib.request.urlopen(request, timeout=60).read()
        except Exception as exc:                                 # noqa: BLE001
            print(f"  FAIL {page}: {exc}")
            failures += 1
            continue
        path = out / f"{slug}.raw"
        path.write_bytes(data)
        print(f"  {len(data):>8,} B  {page} -> {path.name}")
    print(f"{len(wanted) - failures}/{len(wanted)} fetched into {out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
