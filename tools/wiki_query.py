#!/usr/bin/env python3
"""wiki_query.py -- read the local wiki database without touching the wiki.

Examples
    # everything we know about one stratagem, including the resolved attack chain
    python tools/wiki_query.py --stratagem "Orbital 380mm HE Barrage"

    # the same, plus a diff against our decrypted stratagem_settings row
    python tools/wiki_query.py --stratagem "Orbital Airburst Strike" --sk refs/dlbin/keys/recipient.sk

    # every stratagem with a given page parameter
    python tools/wiki_query.py --field permit_type

    # which stratagems have a given attack entity, and what it holds
    python tools/wiki_query.py --entity S_P15_IE

    # ad-hoc SQL
    python tools/wiki_query.py --sql "SELECT title, value FROM param WHERE key='cooldown' ORDER BY num"
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import struct
import sys


def connect(path: pathlib.Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"!! no database at {path}; run tools/wiki_build_db.py first")
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def page_params(db, title: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {"infobox": {}, "stats": {}}
    for row in db.execute("SELECT section, key, value FROM param WHERE title=?", (title,)):
        out.setdefault(row["section"], {})[row["key"]] = row["value"]
    return out


def merged_entry(db, attack_key: str):
    """The merged module row for a page's attack key.

    Stratagems live in the `stratagem` table and weapons in `weapon`; the two sets of modules
    capitalise their keys differently (`AR-23 Liberator` vs `40-K MELTAGUN`), and the page
    parameter may be a third capitalisation, so the lookup is case-insensitive.
    """
    for table in ("stratagem", "weapon"):
        row = db.execute(f"SELECT key, json FROM {table} WHERE key=?", (attack_key,)).fetchone()
        if row is None:
            row = db.execute(f"SELECT key, json FROM {table} WHERE LOWER(key)=?",
                             (attack_key.lower(),)).fetchone()
        if row is not None:
            return table, row["key"], json.loads(row["json"])
    return None, None, None


def resolve_chain(db, attack_key: str) -> list[tuple[str, str, dict]]:
    """Follow the merged `attacks` list of a page through the module entities."""
    _table, _key, entry = merged_entry(db, attack_key)
    if entry is None:
        return []
    out = []
    for attack in entry.get("attacks", []):
        kind, name = attack.get("type"), attack.get("name")
        section = {"projectile": "projectile", "explosion": "explosion",
                   "damage": "damage", "status": None, "beam": "beam", "arc": "arc",
                   "weapon": None, "spray": "spray"}.get(kind, kind)
        found = {}
        if section:
            for hit in db.execute("SELECT json FROM entity WHERE section=? AND key=?",
                                  (section, name)):
                found = json.loads(hit["json"])
                break
            if not found:                      # try any section, names are unique enough
                for hit in db.execute("SELECT section, json FROM entity WHERE key=?", (name,)):
                    found = json.loads(hit["json"])
                    break
            if not found and kind in ("weapon", "weapons"):
                # nested weapon attacks (a sentry's gun) live in the merged weapon table
                for hit in db.execute("SELECT json FROM weapon WHERE LOWER(key)=LOWER(?)",
                                      (name,)):
                    found = json.loads(hit["json"])
                    break
        out.append((kind, name, found))
    return out


def our_row(sk: str, game: str, title: str):
    """Fetch the matching row out of our decrypted stratagem_settings table."""
    from nacl.public import PrivateKey, SealedBox

    gamedir = pathlib.Path(game) / "data" / "game"
    box = SealedBox(PrivateKey(pathlib.Path(sk).read_bytes().ljust(32, b"\0")[:32]))
    plain = box.decrypt((gamedir / "generated_stratagem_settings.dl_bin").read_bytes())
    want = norm(title)
    start = 0
    while True:
        at = plain.find(b"LDLD", start)
        if at < 0:
            return None
        start = at + 4
        if at + 24 > len(plain):
            continue
        version, _tid, payload, _wide = struct.unpack_from("<IIII", plain, at + 4)
        if version not in (1, 2) or payload <= 0 or at + 24 + payload > len(plain):
            continue
        p0 = at + 24
        marker, count = struct.unpack_from("<QQ", plain, p0)
        if marker != 16 or count * 400 > payload:
            continue
        base, pool = p0 + 16, plain[p0:]
        for i in range(count):
            row = base + i * 400
            target = struct.unpack_from("<Q", plain, row + 16)[0]
            if not (0 < target < payload):
                continue
            end = plain.find(b"\0", p0 + target, p0 + target + 250)
            if end < 0:
                continue
            display = plain[p0 + target:end].decode("ascii", errors="replace")
            if norm(display) != want:
                continue
            return {
                "display": display,
                "type": struct.unpack_from("<I", plain, row)[0],
                "max_uses": struct.unpack_from("<I", plain, row + 80)[0],
                "callin": struct.unpack_from("<f", plain, row + 84)[0],
                "cooldown": struct.unpack_from("<f", plain, row + 104)[0],
                "cell": struct.unpack_from("<I", plain, row + 392)[0],
            }
    return None


def show_stratagem(db, title: str, sk: str, game: str) -> None:
    page = db.execute("SELECT * FROM page WHERE title=?", (title,)).fetchone()
    if page is None:
        matches = [r["title"] for r in db.execute("SELECT title FROM page").fetchall()
                   if norm(title) in norm(r["title"])]
        print(f"no page named {title!r}" + (f"; did you mean {matches[:5]}?" if matches else ""))
        return
    params = page_params(db, title)
    print(f"\n=== {title} ===")
    if page["last_updated"]:
        print(f"  wiki last updated: {page['last_updated']}")
    for section in ("infobox", "stats"):
        if not params.get(section):
            continue
        print(f"  [{section}]")
        width = max((len(k) for k in params[section]), default=0)
        for key, value in params[section].items():
            print(f"    {key:<{width}} = {value}")
    key = page["attack_key"]
    if not key:
        return
    table, matched, entry = merged_entry(db, key)
    print(f"  [attack data key] {key}" +
          (f"   -> {table} table key {matched!r}" if matched and matched != key else ""))
    if entry:
        scalars = {k: v for k, v in entry.items()
                   if isinstance(v, (int, float, str)) and k not in ("name",)
                   and not isinstance(v, bool)}
        if scalars:
            shown = ", ".join(f"{k}={v}" for k, v in list(scalars.items())[:10])
            print(f"    [merged] {shown}")
    chain = resolve_chain(db, key)
    if not chain:
        print("    (no merged attack rows for this key in the cached modules)")
        return
    for kind, name, data in chain:
        preview = ""
        if data:
            numeric = {k: v for k, v in data.items()
                       if isinstance(v, (int, float)) and k not in ("name",)}
            preview = ", ".join(f"{k}={v}" for k, v in list(numeric.items())[:7])
        print(f"    {kind:<10} {name:<24} {preview}")
    if sk:
        row = our_row(sk, game, title)
        if row is None:
            print("  [our table] no matching row")
        else:
            print(f"  [our table] {row['display']!r}  type={row['type']}  "
                  f"cooldown={row['cooldown']:g}  call-in={row['callin']:g}  "
                  f"uses={row['max_uses'] if row['max_uses'] != 0xFFFFFFFF else 'inf'}  "
                  f"cell={row['cell']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="refs/wiki/wiki.sqlite")
    ap.add_argument("--stratagem", "--page", dest="stratagem", default="",
                    help="page title (works for stratagems and weapons alike)")
    ap.add_argument("--field", default="")
    ap.add_argument("--entity", default="")
    ap.add_argument("--sql", default="")
    ap.add_argument("--sk", default="")
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    a = ap.parse_args()

    db = connect(pathlib.Path(a.db))

    if a.sql:
        for row in db.execute(a.sql):
            print(dict(row))
        return 0

    if a.entity:
        rows = db.execute("SELECT section, key, json FROM entity WHERE key=?", (a.entity,)).fetchall()
        if not rows:
            print(f"no entity named {a.entity!r}")
            return 1
        for row in rows:
            print(f"\n=== [{row['section']}] {row['key']} ===")
            print(json.dumps(json.loads(row["json"]), ensure_ascii=False, indent=1))
        return 0

    if a.field:
        rows = db.execute(
            "SELECT title, value FROM param WHERE key=? ORDER BY num IS NULL, num",
            (a.field,)).fetchall()
        print(f"{len(rows)} page(s) with param {a.field!r}")
        width = max((len(r["title"]) for r in rows), default=0)
        for row in rows:
            print(f"  {row['title']:<{width}}  {row['value']}")
        return 0

    if a.stratagem:
        show_stratagem(db, a.stratagem, a.sk, a.game)
        return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
