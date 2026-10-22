#!/usr/bin/env python3
"""build_stratagem_alias.py -- map our stratagem rows to wiki page titles without using names.

THE PROBLEM
    Our decrypted rows carry an internal display name ("BACKPACK. SUPPLY BACKPACK"); the wiki page is
    titled "B-1 Supply Pack".  Only the orbital/eagle families happen to agree, so name matching
    covers 15 of 237 pages.

THE BRIDGE USED HERE
    Each row also carries a LOCALISATION KEY (the `+24` pointer), which is an internal slug:

        BACKPACK. SUPPLY BACKPACK   -> nui_stratagem_backpack_ammo_name      -> backpack_ammo
        SENTRYS. MACHINEGUN         -> nui_stratagem_turret_machinegun_gpmg_name
                                                                  -> turret_machinegun_gpmg

    HD2Runtime's catalog names the same object in `uiIcon.nativeType` (CamelCase, e.g. `AmmoBackpack`,
    `TurretMachinegunGPMG`), and that field equals the wiki's `ref`.  So:

        row +24 key  ->  slug  ~=  catalog uiIcon.nativeType  ->  catalog stratagem name == page title

    Two match grades, both requiring a UNIQUE catalog counterpart:
        nativeType-exact   slug and nativeType are equal after lowercasing  (34 rows)
        token-set          equal after camelCase split + set compare, which also catches the
                           reordered cases: backpack_ammo <-> AmmoBackpack  (4 rows)

WHY IT STOPS THERE
    The catalog only maps 96 stratagems and only 128 of our 153 rows carry a key, so ~38 is close to
    the ceiling of this particular bridge.  Anything beyond it would need a different identifier, and
    guessing would poison the alias table -- a wrong alias makes every later `--sk` comparison wrong.

OUTPUT
    refs/stratagem-alias.json: [{display, key, slug, wiki_title, catalog_name, native_type, method,
    type_value, cooldown, uses, callin, cell}]

USAGE
    python tools/build_stratagem_alias.py --sk refs/dlbin/keys/recipient.sk
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys
import zipfile

HEADER = 48
DESCRIPTOR = 16
STRIDE = 400
NAME_PTR, KEY_PTR = 16, 24


def unseal(blob: bytes, box) -> bytes:
    return box.decrypt(blob) if len(blob) > HEADER else blob


def read_cstr(buf: bytes, at: int, limit: int = 250) -> str:
    if at <= 0 or at >= len(buf):
        return ""
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end <= at:
        return ""
    raw = buf[at:end]
    return "" if any(b < 32 or b > 126 for b in raw) else raw.decode("ascii")


def camel(text: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)


def tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in re.split(r"[^a-z0-9]+", camel(text).lower()) if t)


def joined(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", camel(text).lower())


def slug_of(key: str) -> str:
    trimmed = re.sub(r"^nui_(n_)?stratagem_", "", key)
    return re.sub(r"(?:_name|_desc)$", "", trimmed)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--sdk", default="refs/hd2runtime/HD2Runtime-0.28.1-sdk.zip")
    ap.add_argument("--out", default="refs/stratagem-alias.json")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))
    plain = unseal((game / "generated_stratagem_settings.dl_bin").read_bytes(), box)

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
            rows.append({
                "display": read_cstr(pool, struct.unpack_from("<Q", plain, row + NAME_PTR)[0]),
                "key": read_cstr(pool, struct.unpack_from("<Q", plain, row + KEY_PTR)[0]),
                "type_value": struct.unpack_from("<I", plain, row)[0],
                "uses": struct.unpack_from("<I", plain, row + 80)[0],
                "callin": round(struct.unpack_from("<f", plain, row + 84)[0], 3),
                "cooldown": round(struct.unpack_from("<f", plain, row + 104)[0], 3),
                "cell": struct.unpack_from("<I", plain, row + 392)[0],
            })

    with zipfile.ZipFile(a.sdk) as fh:
        catalog = json.loads(fh.read("StratagemAuthoringCapabilities.json"))["stratagems"]

    by_joined: dict[str, list] = {}
    by_tokens: dict[frozenset, list] = {}
    for entry in catalog:
        icon = entry.get("uiIcon") or {}
        native = icon.get("nativeType")
        if not native:
            continue
        by_joined.setdefault(joined(native), []).append(entry)
        by_tokens.setdefault(tokens(native), []).append(entry)

    alias = []
    stats = {"nativeType-exact": 0, "token-set": 0, "ambiguous": 0, "no-key": 0, "unmatched": 0}
    for row in rows:
        if not row["key"]:
            stats["no-key"] += 1
            continue
        slug = slug_of(row["key"])
        hits = by_joined.get(joined(slug), [])
        method = "nativeType-exact"
        if not hits:
            hits = by_tokens.get(tokens(slug), [])
            method = "token-set"
        if not hits:
            stats["unmatched"] += 1
            continue
        if len(hits) > 1:
            stats["ambiguous"] += 1
            continue
        entry = hits[0]
        stats[method] += 1
        alias.append({**row, "slug": slug, "wiki_title": entry["name"],
                      "catalog_name": entry["name"],
                      "native_type": (entry.get("uiIcon") or {}).get("nativeType"),
                      "method": method})

    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"count": len(alias), "stats": stats, "alias": alias},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"rows {len(rows)}   aliases {len(alias)}   {out} ({out.stat().st_size:,} B)")
    for k, v in stats.items():
        print(f"  {k:<18}{v:>4}")
    print("\nsample:")
    for item in alias[:10]:
        print(f"  {item['display']:<38} -> {item['wiki_title']:<34} "
              f"[{item['method']}] {item['slug']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
