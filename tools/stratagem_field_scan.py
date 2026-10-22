#!/usr/bin/env python3
"""stratagem_field_scan.py -- which row/group field carries the stratagem panel category?

METHOD
    The rows now have trustworthy labels: each of the 12 groups is a family (BACKPACK, EAGLE,
    ORBITAL, SENTRYS, TEAM WEAPONS, VEHICLES, MISSIONS, ...), recovered from the display name that
    the row's own +16 pointer resolves to.

    The wiki's four stratagem-panel categories are families of those families:
        Offensive (red)   = Orbital + Eagle
        Supply    (blue)  = Support Weapons (TEAM WEAPONS) + Backpacks + Vehicles
        Defensive (green) = Sentries + Emplacements
        Mission   (yellow)= Missions + Resupply (CONSUMABLES) + event rewards
    So the category field must put every row of a category on a value *not used by any other
    category*.  This tool tests exactly that:

        for each slot: V_off, V_sup, V_def, V_mis  = value set per wiki category
        disjoint = number of the 6 category pairs whose value sets do not intersect
        6/6 means "this slot alone separates the four panel categories"

    Purity (constant inside a family) is reported too, but a slot can separate the categories
    without being family-constant - a family may legitimately span two values.

    Group headers are dumped as well: the LDLD header is 24 bytes but only 20 are accounted for
    ('LDLD', version, type_id, payload, wide), leaving 4 bytes at +20 that nothing has read yet.

USAGE
    python tools/stratagem_field_scan.py --sk refs/dlbin/keys/recipient.sk
"""
from __future__ import annotations

import argparse
import itertools
import pathlib
import struct
import sys
from collections import Counter, defaultdict

HEADER = 48
DESCRIPTOR = 16
STRIDE = 400
NAME_PTR = 16
MAX_CATEGORY_DOMAIN = 40      # above this a field is an id, not a category

WIKI = {
    "OFFENSIVE": {"ORBITAL", "EAGLE"},
    "SUPPLY": {"TEAM WEAPONS", "BACKPACK", "VEHICLES", "TANK"},
    "DEFENSIVE": {"SENTRYS", "SENTRIES", "EMPLACEMENTS"},
    "MISSION": {"MISSIONS", "MISSIONS CLAN STATION", "CONSUMABLES", "PRESIDENT REWARDS"},
}


def unseal(blob: bytes, box) -> bytes:
    return box.decrypt(blob) if len(blob) > HEADER else blob


def groups(plain: bytes) -> list[dict]:
    out, start = [], 0
    while True:
        at = plain.find(b"LDLD", start)
        if at < 0:
            return out
        start = at + 4
        if at + 24 > len(plain):
            continue
        version, type_id, payload, wide = struct.unpack_from("<IIII", plain, at + 4)
        if version in (1, 2) and 0 < payload and at + 24 + payload <= len(plain):
            out.append({"at": at, "type_id": type_id, "version": version,
                        "payload": payload, "wide": wide, "payload_at": at + 24})


def read_cstr(buf: bytes, at: int, limit: int = 250) -> str:
    if at <= 0 or at >= len(buf):
        return ""
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end <= at:
        return ""
    raw = buf[at:end]
    if any(b < 32 or b > 126 for b in raw):
        return ""
    return raw.decode("ascii")


def wiki_of(family: str) -> str:
    for name, fams in WIKI.items():
        if family in fams:
            return name
    return "UNKNOWN"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))
    plain = unseal((game / "generated_stratagem_settings.dl_bin").read_bytes(), box)

    found = groups(plain)
    print("== group headers (24 bytes; +20 is unaccounted) ==")
    for i, g in enumerate(found):
        at = g["at"]
        print(f"  [{i:>2}] {plain[at:at + 24].hex(' ')}   at={at:#08x} v{g['version']} "
              f"type=0x{g['type_id']:08X} payload={g['payload']} wide={g['wide']}")

    rows: list[tuple[str, bytes, int]] = []
    for gi, g in enumerate(found):
        p0 = g["payload_at"]
        marker, count = struct.unpack_from("<QQ", plain, p0)
        if marker != DESCRIPTOR or count <= 0 or count * STRIDE > g["payload"]:
            continue
        rows_at = p0 + DESCRIPTOR
        pool = plain[p0:]
        for index in range(count):
            base = rows_at + index * STRIDE
            name = read_cstr(pool, struct.unpack_from("<Q", plain, base + NAME_PTR)[0])
            family = name.split(".")[0].strip() if "." in name else "(none)"
            rows.append((family, plain[base:base + STRIDE], gi))

    known = [(f, raw) for f, raw, _ in rows if wiki_of(f) != "UNKNOWN"]
    print(f"\nrows {len(rows)}   of which wiki-classifiable {len(known)}")

    scored = []
    for slot in range(0, STRIDE - 3, 4):
        per = {k: set() for k in WIKI}
        by_family: dict[str, Counter] = defaultdict(Counter)
        for family, raw, _ in rows:
            value = struct.unpack_from("<I", raw, slot)[0]
            by_family[family][value] += 1
            cat = wiki_of(family)
            if cat != "UNKNOWN":
                per[cat].add(value)
        if any(not per[k] for k in WIKI):
            continue
        pairs = list(itertools.combinations(WIKI, 2))
        disj = sum(1 for x, y in pairs if not (per[x] & per[y]))
        purity = sum(c.most_common(1)[0][1] for c in by_family.values()) / len(rows)
        distinct = len({v for s in per.values() for v in s})
        # A field that is unique per row trivially has disjoint value sets across categories and
        # scores 6/6 without meaning anything.  Only small-domain fields can be a category.
        if distinct > MAX_CATEGORY_DOMAIN:
            continue
        scored.append((disj, slot, per, purity, distinct))

    print("\n== slots ranked by how well they separate the 4 wiki categories "
          "(6 = perfectly) ==")
    best = max(s[0] for s in scored)
    print(f"   {len(scored)} slot(s) with <= {MAX_CATEGORY_DOMAIN} values; "
          f"best disjointness = {best}/6")
    for disj, slot, per, purity, distinct in sorted(scored, key=lambda s: (-s[0], s[4]))[:12]:
        print(f"  +{slot:<4} disjoint={disj}/6 distinct={distinct:<3} purity={purity:.3f}")
        for k in WIKI:
            vals = sorted(per[k])
            shown = ", ".join(f"0x{v:08X}" for v in vals[:6]) + (" ..." if len(vals) > 6 else "")
            print(f"        {k:<10} {len(vals):>3} values  {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
