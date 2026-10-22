#!/usr/bin/env python3
"""stratagem_join.py -- join stratagem_settings rows to HD2Runtime's named catalog.

WHY
    The rows are now named by their own +16 pointer, so the external cross-check no longer needs
    value clustering - it can be done per name.  That turns "our cooldown value set overlaps the
    wiki's" into "for these named stratagems the cooldown matches exactly".

WHY THE MATCH IS FUZZY
    The game's internal display names and the catalog's names are written by different people:
        ours     "TEAM WEAPONS. MACHINEGUN"      catalog  "MG-43 Machine Gun"
        ours     "ORBITAL. 120MM HE STRIKE"      catalog  "Orbital 120mm HE Barrage"
        ours     "EAGLE. AIRSTRIKE SMOKE"        catalog  "Eagle Smoke Strike"
    so an exact join finds only a fraction.  Instead each row is matched to the most similar
    catalog name *within the same family*, and the similarity score is reported.

WHY A WRONG PAIRING SHOWS UP
    Cooldowns are not uniform: orbital alone spans 70/75/80/100/180/240/300.  A mispaired row will
    almost always disagree on cooldown, so "similarity high AND cooldown equal" is much stronger
    evidence than either alone.  Eagle is the exception - every eagle stratagem is 15 s, so that
    family carries no discriminating power on cooldown and is only useful as a sanity check.

USAGE
    python tools/stratagem_join.py --sk refs/dlbin/keys/recipient.sk \\
        --sdk refs/hd2runtime/HD2Runtime-0.28.1-sdk.zip
"""
from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import struct
import sys
import zipfile
from collections import Counter, defaultdict

HEADER = 48
DESCRIPTOR = 16
STRIDE = 400
NAME_PTR, MAX_USES, COOLDOWN, CELL = 16, 80, 104, 392

FAMILY = {"orbital": "ORBITAL", "eagle": "EAGLE", "support": "TEAM WEAPONS",
          "backpack": "BACKPACK", "sentry": "SENTRYS", "vehicle": "VEHICLES",
          "mine": "EMPLACEMENTS", "emplacement": "EMPLACEMENTS", "mission": "MISSIONS"}


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
            out.append({"at": at, "type_id": type_id, "payload": payload, "payload_at": at + 24})


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


def norm(text: str) -> str:
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sk", required=True)
    ap.add_argument("--sdk", default="refs/hd2runtime/HD2Runtime-0.28.1-sdk.zip")
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--threshold", type=float, default=0.80)
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))
    plain = unseal((game / "generated_stratagem_settings.dl_bin").read_bytes(), box)

    rows = []
    for gi, g in enumerate(groups(plain)):
        p0 = g["payload_at"]
        marker, count = struct.unpack_from("<QQ", plain, p0)
        if marker != DESCRIPTOR or count <= 0 or count * STRIDE > g["payload"]:
            continue
        rows_at = p0 + DESCRIPTOR
        pool = plain[p0:]
        for index in range(count):
            base = rows_at + index * STRIDE
            display = read_cstr(pool, struct.unpack_from("<Q", plain, base + NAME_PTR)[0])
            head, _, tail = display.partition(".")
            rows.append({
                "group": gi, "row": index, "display": display,
                "prefix": head.strip(), "short": (tail or display).strip(),
                "cooldown": round(struct.unpack_from("<f", plain, base + COOLDOWN)[0], 3),
                "max_uses": struct.unpack_from("<I", plain, base + MAX_USES)[0],
                "cell": struct.unpack_from("<I", plain, base + CELL)[0],
            })

    with zipfile.ZipFile(a.sdk) as fh:
        catalog = json.loads(fh.read("StratagemAuthoringCapabilities.json"))["stratagems"]
    print(f"rows {len(rows)}   catalog {len(catalog)}")
    for s in catalog:
        s.setdefault("cooldown", None)

    by_family: dict[str, list] = defaultdict(list)
    for s in catalog:
        by_family[FAMILY.get(s["family"], s["family"].upper())].append(s)

    # ---- fuzzy match inside the family ---------------------------------------------------------
    matched, unmatched = [], []
    for r in rows:
        family = r["prefix"]
        candidates = by_family.get(family, [])
        if not candidates:
            unmatched.append((r, 0.0, ""))
            continue
        want = norm(r["short"])
        best, score = None, 0.0
        for s in candidates:
            got = norm(s["name"])
            # compare against the catalog name both whole and with the family word removed
            alt = norm(s["name"].replace(FAMILY.get(s["family"], ""), "", 1))
            sc = max(difflib.SequenceMatcher(None, want, got).ratio(),
                     difflib.SequenceMatcher(None, want, alt).ratio())
            if sc > score:
                best, score = s, sc
        if best is not None and score >= a.threshold:
            matched.append((r, best, score))
        else:
            unmatched.append((r, score, best["name"] if best else ""))

    print(f"\nfuzzy match within family, threshold {a.threshold}: {len(matched)}/{len(rows)}")

    # ---- cooldown agreement validates the pairing ----------------------------------------------
    comparable = [(r, s, sc) for r, s, sc in matched if s["cooldown"] is not None]
    agree = [(r, s, sc) for r, s, sc in comparable if abs(r["cooldown"] - s["cooldown"]) < 0.01]
    print(f"catalog entries carrying a cooldown: {len(comparable)}")
    print(f"  +104 agrees: {len(agree)}    disagrees: {len(comparable) - len(agree)}")
    if comparable:
        print(f"  agreement rate: {len(agree) / len(comparable):.1%}")

    print("\n== per-family agreement ==")
    fam_tab = defaultdict(lambda: [0, 0])
    for r, s, sc in comparable:
        fam_tab[s["family"]][0 if abs(r["cooldown"] - s["cooldown"]) < 0.01 else 1] += 1
    for fam in sorted(fam_tab):
        good, bad = fam_tab[fam]
        print(f"  {fam:<12} agree {good:>2}  disagree {bad:>2}")

    print("\n== disagreements (a mismatch means either the pairing or the field is wrong) ==")
    for r, s, sc in comparable:
        if abs(r["cooldown"] - s["cooldown"]) >= 0.01:
            print(f"  {r['display']!r:<46} ours={r['cooldown']:<7} "
                  f"catalog={s['cooldown']:<5} sim={sc:.3f} <- {s['name']!r}")

    print("\n== +392 cell vs catalog family ==")
    tab = defaultdict(Counter)
    for r, s, sc in matched:
        tab[s["family"]][r["cell"]] += 1
    for fam in sorted(tab, key=lambda f: min(tab[f])):
        cells = sorted(tab[fam])
        print(f"  {fam:<12} cell {cells[0]:>2}..{cells[-1]:<2}  "
              f"{dict(sorted(tab[fam].items()))}")

    print("\n== +80 max_uses vs catalog maxUses ==")
    for r, s, sc in matched[:10]:
        print(f"  {r['display']:<42} ours=0x{r['max_uses']:08X} "
              f"catalog={s.get('maxUses', {}).get('value')}")

    print(f"\n== unmatched rows ({len(unmatched)}) ==")
    for r, sc, cand in unmatched:
        print(f"  [{r['group']:>2}] cell={r['cell']:<3} cd={r['cooldown']:<7} "
              f"{r['display']!r:<48} best={sc:.2f} {cand!r}")

    hit = {id(s) for _, s, _ in matched}
    missing = [s for s in catalog if id(s) not in hit]
    print(f"\n== catalog entries with no row ({len(missing)}/{len(catalog)}) ==")
    for s in missing:
        print(f"  {s['family']:<12} {s['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
