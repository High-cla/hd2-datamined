#!/usr/bin/env python3
"""wiki_build_db.py -- build a local SQLite database from the cached wiki pages + data modules.

WHAT GOES IN
    * page source (refs/wiki/pages/*.wikitext) -> the template parameters that carry the numbers:
          {{Infobox Stratagem | permit_type= | unlock_level= | base_cooldown= | ... }}
          {{Infobox Weapon | damage={{Damage|Ballistic|90}} | capacity=45 | fire_rate=640 rpm }}
          {{Stratagem Stats Table | call_time= | uses= | cooldown= | cooldown_upgraded= }}
          {{Attack_Data_Stratagem|KEY}} / {{Attack_Data_Weapon|KEY}}   <- key for the detail table
          {{Last Updated|1.007.000}}
    * the JSON data modules (refs/wiki/modules/*.raw) -> the detailed attack data keyed by entity:
          Decodedata-Attacks/stratagems data.json   stratagems / projectile / explosion / ...
          Decodedata-Attacks/stratagemdata.json     item-resource view
          Decodedata-Attacks/data.json              damage / projectile / explosion / beam / arc

WHY THIS SHAPE
    The rendered HTML table is a JOIN of those two layers performed by a Lua module.  Storing the two
    layers separately keeps the join re-doable, lets a value be looked up without the wiki, and lets
    the same DB be cross-checked against the decrypted game tables.

VALUES THAT ARE THEMSELVES TEMPLATES
    `{{Damage|Ballistic|90}}` and `{{Currency|Requisition|7500}}` are kept verbatim in `param.value`,
    and `param.num` additionally carries the last numeric argument, so "90" and "7500" are queryable
    without losing what kind of number they were.

TABLES
    page(title, kind, last_updated, attack_key, n_params)
    param(section, title, key, value, num)   -- section = infobox / stats / weapon / throwable
    entity(section, key, json)               -- module dumps, one row per entity
    stratagem(key, json)                     -- the merged 'stratagems' section

USAGE
    python tools/fetch_wiki_pages.py --category Stratagems --category Weapons
    python tools/wiki_build_db.py --out refs/wiki/wiki.sqlite
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3

# section -> template names that fill it (spelling variants appear in the source)
TEMPLATES = {
    "infobox": ("Infobox Stratagem", "Infobox Weapon", "Infobox_Weapon",
                "Infobox Support Weapon", "Infobox Throwable", "Infobox Any"),
    "stats": ("Stratagem Stats Table",),
}
ATTACK_KEY = re.compile(r"\{\{\s*Attack[_ ]Data[_ ]?(?:Stratagem|Weapon)\s*\|\s*([^}|]+)")
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def find_template(text: str, name: str) -> str | None:
    """Return the full {{name ...}} block, matching nested braces."""
    start = text.find("{{" + name)
    if start < 0:
        return None
    depth, i = 0, start
    while i < len(text) - 1:
        pair = text[i:i + 2]
        if pair == "{{":
            depth += 1
            i += 2
            continue
        if pair == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return text[start:i]
            continue
        i += 1
    return None


def split_params(block: str) -> dict[str, str]:
    """Split a template body on top-level '|', then key=value."""
    body = block[2:-2]
    parts, depth, current = [], 0, []
    i = 0
    while i < len(body):
        pair = body[i:i + 2]
        if pair == "{{":
            depth += 1
            current.append(pair)
            i += 2
            continue
        if pair == "}}":
            depth -= 1
            current.append(pair)
            i += 2
            continue
        if body[i] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            i += 1
            continue
        current.append(body[i])
        i += 1
    parts.append("".join(current))

    out = {}
    for part in parts[1:]:                      # parts[0] is the template name
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        out[key.strip()] = value.strip()
    return out


def numeric(value: str):
    """A number from '240s' / '8.45' / '640 rpm', or from the last numeric arg of a template.

    Keeps `{{Damage|Ballistic|90}}` -> 90 and `{{Currency|Requisition|7500}}` -> 7500 queryable
    without discarding the original string.
    """
    if value is None:
        return None
    stripped = value.strip()
    if stripped.startswith("{{"):
        args = [p.strip() for p in stripped[2:-2].split("|")]
        for arg in reversed(args):
            hit = NUMBER.search(arg)
            if hit:
                return float(hit.group(0))
        return None
    hit = re.match(r"^\s*(-?\d+(?:\.\d+)?)", stripped)
    return float(hit.group(1)) if hit else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default="refs/wiki/pages")
    ap.add_argument("--modules", default="refs/wiki/modules")
    ap.add_argument("--out", default="refs/wiki/wiki.sqlite")
    a = ap.parse_args()

    pages_dir, modules_dir = pathlib.Path(a.pages), pathlib.Path(a.modules)
    if not pages_dir.is_dir():
        print(f"!! no pages at {pages_dir}; run tools/fetch_wiki_pages.py first")
        return 2

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    db = sqlite3.connect(out)
    db.executescript("""
        CREATE TABLE page(title TEXT PRIMARY KEY, kind TEXT, last_updated TEXT,
                          attack_key TEXT, n_params INT);
        CREATE TABLE param(section TEXT, title TEXT, key TEXT, value TEXT, num REAL);
        CREATE TABLE entity(section TEXT, key TEXT, json TEXT);
        CREATE TABLE stratagem(key TEXT PRIMARY KEY, json TEXT);
        CREATE TABLE weapon(key TEXT PRIMARY KEY, json TEXT);
        CREATE INDEX idx_param_title ON param(title);
        CREATE INDEX idx_param_key ON param(key);
        CREATE INDEX idx_entity_key ON entity(key);
    """)

    title_map = {}
    map_path = pages_dir / "_titles.json"
    if map_path.is_file():
        try:
            title_map = json.loads(map_path.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            title_map = {}

    page_count = param_count = 0
    kinds = {"stratagem": 0, "weapon": 0}
    for path in sorted(pages_dir.glob("*.wikitext")):
        text = path.read_text(encoding="utf-8", errors="replace")
        title = title_map.get(path.stem, path.stem.replace("_", " "))
        updated = find_template(text, "Last Updated")
        last_updated = None
        if updated:
            hit = NUMBER.search(updated)
            last_updated = hit.group(0) if hit else None

        key_hit = ATTACK_KEY.search(text)
        attack_key = key_hit.group(1).strip() if key_hit else None

        kind = None
        n_params = 0
        for section, names in TEMPLATES.items():
            block = None
            for name in names:
                block = find_template(text, name)
                if block:
                    if kind is None:
                        kind = "stratagem" if name.endswith("Stratagem") else "weapon"
                    break
            if not block:
                continue
            for param, value in split_params(block).items():
                db.execute("INSERT INTO param VALUES (?,?,?,?,?)",
                           (section, title, param, value, numeric(value)))
                param_count += 1
                n_params += 1
        if kind:
            kinds[kind] = kinds.get(kind, 0) + 1
        db.execute("INSERT OR REPLACE INTO page VALUES (?,?,?,?,?)",
                   (title, kind, last_updated, attack_key, n_params))
        page_count += 1

    entity_count = 0
    merged = 0
    merged_weapon = [0]
    for path in sorted(modules_dir.glob("*.raw")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:                                       # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        for section, value in data.items():
            if section == "stratagems" and isinstance(value, dict):
                for key, entry in value.items():
                    db.execute("INSERT OR REPLACE INTO stratagem VALUES (?,?)",
                               (key, json.dumps(entry, ensure_ascii=False)))
                    merged += 1
                continue
            # weapon data: several modules carry a `weapon`/`weapons` section under different
            # capitalisations, so keep the entry with the most fields for each folded key.
            if section in ("weapon", "weapons") and isinstance(value, dict):
                for key, entry in value.items():
                    if not isinstance(entry, dict):
                        continue
                    folded = key.lower()
                    previous = db.execute(
                        "SELECT key, json FROM weapon WHERE LOWER(key)=?", (folded,)).fetchone()
                    if previous is not None:
                        if len(json.loads(previous[1])) >= len(entry):
                            continue
                        db.execute("DELETE FROM weapon WHERE key=?", (previous[0],))
                    db.execute("INSERT INTO weapon VALUES (?,?)",
                               (key, json.dumps(entry, ensure_ascii=False)))
                    merged_weapon[0] += 1
                continue
            if not isinstance(value, dict):
                continue
            for key, entry in value.items():
                if not isinstance(entry, dict):
                    continue
                db.execute("INSERT INTO entity VALUES (?,?,?)",
                           (section, key, json.dumps(entry, ensure_ascii=False)))
                entity_count += 1

    db.commit()
    for table in ("page", "param", "entity", "stratagem", "weapon"):
        n = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<10} {n:>6} rows")
    print(f"db -> {out}  ({out.stat().st_size:,} B)")
    print(f"   pages {page_count} ({kinds}), params {param_count}, "
          f"entities {entity_count}, merged stratagem rows {merged}, "
          f"merged weapon rows {merged_weapon[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
