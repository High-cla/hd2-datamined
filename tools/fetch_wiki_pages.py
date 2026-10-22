#!/usr/bin/env python3
"""fetch_wiki_pages.py -- cache the wiki's stratagem/weapon page source locally.

WHY NOT HTML
    The rendered tables on a stratagem page are produced by a Lua module from a JSON data module
    (`{{Attack_Data_Stratagem|KEY}}` -> Module:Getdata-Attacks -> Module:Decodedata-Attacks/*.json).
    Scraping the HTML would re-parse a derived view and lose the keys.  The page SOURCE carries the
    numbers as plain template parameters:

        {{Infobox Stratagem | permit_type = Offensive | base_cooldown = 240s | ... }}
        {{Stratagem Stats Table | call_time = 8.45 | uses = Unlimited | cooldown = 240 }}
        {{Attack_Data_Stratagem|ORBITAL 380MM HE BARRAGE}}

    so page source + the JSON modules together are the database, and HTML is not needed at all.

SOURCE ETIQUETTE
    helldivers.wiki.gg/robots.txt is `User-agent: * / Allow: /`, with explicit blocks only for
    named AI-training crawlers.  This script therefore:
      * batches 50 titles per request through the MediaWiki API instead of one request per page,
      * sleeps between batches,
      * caches under refs/wiki/ for local research only -- the content is CC BY-SA wiki content
        and is NOT redistributed by this repository.
    Re-running is cheap: pages already cached are skipped unless --force.

USAGE
    python tools/fetch_wiki_pages.py --category Stratagems
    python tools/fetch_wiki_pages.py --category Weapons --category Stratagems --force
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
import urllib.parse
import urllib.request

API = "https://helldivers.wiki.gg/api.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
SKIP_PREFIXES = ("User:", "Talk:", "File:", "Template:", "Category:", "Help:", "Module:")
SKIP_TITLES = {"Stratagems", "Weapons", "Damage Comparison"}
TITLE_MAP = "_titles.json"          # filename stem -> the real page title


def safe_stem(title: str) -> str:
    """A Windows-safe filename stem; the real title is kept in TITLE_MAP."""
    out = title.replace("/", "_").replace("\\", "_").replace(":", "_")
    return out.replace("#", "_").replace("?", "_").replace("*", "_").replace("|", "_").strip()


def api(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=HEADERS)
    return json.loads(urllib.request.urlopen(request, timeout=60).read().decode("utf-8"))


def category_members(name: str) -> list[str]:
    out, cont = [], {}
    while True:
        reply = api({"action": "query", "list": "categorymembers",
                     "cmtitle": f"Category:{name}", "cmlimit": 500, "format": "json", **cont})
        out.extend(m["title"] for m in reply.get("query", {}).get("categorymembers", []))
        cont = reply.get("continue") or {}
        if not cont:
            return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", action="append", required=True)
    ap.add_argument("--out", default="refs/wiki/pages")
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    titles: list[str] = []
    for category in a.category:
        members = category_members(category)
        kept = [t for t in members
                if t not in SKIP_TITLES and not t.startswith(SKIP_PREFIXES)]
        print(f"Category:{category}: {len(members)} members, {len(kept)} kept")
        titles.extend(kept)

    titles = list(dict.fromkeys(titles))
    # merge with any map already on disk so a partial re-run never loses titles
    map_path = out / TITLE_MAP
    title_map: dict[str, str] = {}
    if map_path.is_file():
        try:
            title_map = json.loads(map_path.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            title_map = {}
    for title in titles:
        title_map[safe_stem(title)] = title
    todo = [t for t in titles if a.force or not (out / f"{safe_stem(t)}.wikitext").exists()]
    print(f"{len(titles)} unique titles, {len(todo)} to fetch")

    fetched = 0
    for start in range(0, len(todo), a.batch):
        chunk = todo[start:start + a.batch]
        reply = api({"action": "query", "prop": "revisions", "rvslots": "main",
                     "rvprop": "content|timestamp", "format": "json",
                     "titles": "|".join(chunk)})
        pages = reply.get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", "")
            revisions = page.get("revisions") or []
            if not revisions:
                print(f"  MISSING {title}")
                continue
            slot = revisions[0].get("slots", {}).get("main", {})
            content = slot.get("*") or slot.get("content") or ""
            path = out / f"{safe_stem(title)}.wikitext"
            path.write_text(content, encoding="utf-8")
            fetched += 1
        print(f"  batch {start // a.batch + 1}: {len(chunk)} requested, {fetched} written so far")
        time.sleep(a.sleep)

    map_path.write_text(json.dumps(title_map, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"done: {fetched} pages in {out}; title map {len(title_map)} entries -> {TITLE_MAP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
