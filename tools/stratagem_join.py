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

# (our display name, catalog cooldown) pairs that disagree because the catalog snapshot predates
# a published patch.  Without this the tool reports a known-good value as a mismatch forever.
#   wiki, patch 1.007.200 (2026-10-20): "Decreased cooldown from 100 seconds to 90 seconds"
#   build 25988413 was installed 2026-10-20 and reads 90; see
#   docs/STRATAGEM-SETTINGS-DECODED.md section 4.
PATCHED = {
    ("ORBITAL. AIRBURST STRIKE", 100): "patch 1.007.200 (2026-10-20): cooldown 100 -> 90",
}

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

    # ---- fuzzy match inside the family, one catalog entry per row -------------------------------
    # A per-row "best candidate" lets two rows claim the same catalog entry: our
    # "EXPENDABLE ANTI-TANK" and "EXPENDABLE ANTI-TANK (Booster)" both want EAT-17, and the second
    # one then looks like a cooldown mismatch when it is really a pairing collision.  Assigning
    # greedily by descending similarity makes the pairing one-to-one, which is also the conservative
    # choice for a verification tool: a row that has no free partner is reported as unmatched
    # instead of being forced onto someone else's entry.
    options = []
    for r in rows:
        candidates = by_family.get(r["prefix"], [])
        if not candidates:
            continue
        want = norm(r["short"])
        for s in candidates:
            got = norm(s["name"])
            # compare against the catalog name whole and with the family word removed
            alt = norm(s["name"].replace(FAMILY.get(s["family"], ""), "", 1))
            sc = max(difflib.SequenceMatcher(None, want, got).ratio(),
                     difflib.SequenceMatcher(None, want, alt).ratio())
            if sc >= a.threshold:
                options.append((sc, r, s))
    options.sort(key=lambda t: -t[0])

    matched, unmatched = [], []
    taken_rows, taken_catalog = set(), set()
    for sc, r, s in options:
        if id(r) in taken_rows or id(s) in taken_catalog:
            continue
        taken_rows.add(id(r))
        taken_catalog.add(id(s))
        matched.append((r, s, sc))
    for r in rows:
        if id(r) not in taken_rows:
            unmatched.append((r, 0.0, ""))

    print(f"\nfuzzy match within family, threshold {a.threshold}: {len(matched)}/{len(rows)}")

    # ---- cooldown agreement validates the pairing ----------------------------------------------
    comparable = [(r, s, sc) for r, s, sc in matched if s["cooldown"] is not None]
    agree, moved, bad = [], [], []
    for pair in comparable:
        close = abs(pair[0]["cooldown"] - pair[1]["cooldown"]) < 0.01
        if close:
            agree.append(pair)
        elif (pair[0]["display"], pair[1]["cooldown"]) in PATCHED:
            moved.append(pair)
        else:
            bad.append(pair)
    print(f"catalog entries carrying a cooldown: {len(comparable)}")
    print(f"  agrees {len(agree)}   patched since the snapshot {len(moved)}"
          f"   unexplained {len(bad)}")
    if comparable:
        print(f"  agreement rate (agrees + patched): "
              f"{(len(agree) + len(moved)) / len(comparable):.1%}")
    for pair in moved:
        key = (pair[0]["display"], pair[1]["cooldown"])
        print(f"  PATCHED {key[0]!r}: ours={pair[0]['cooldown']} catalog={key[1]}"
              f" -> {PATCHED[key]}")

    print("\n== per-family agreement (patched values count as agreeing) ==")
    fam_ok: dict[str, int] = defaultdict(int)
    fam_bad: dict[str, int] = defaultdict(int)
    for pair in agree + moved:
        fam_ok[pair[1]["family"]] += 1
    for pair in bad:
        fam_bad[pair[1]["family"]] += 1
    for fam in sorted(set(fam_ok) | set(fam_bad)):
        print(f"  {fam:<12} agree {fam_ok[fam]:>2}  disagree {fam_bad[fam]:>2}")

    print("\n== unexplained disagreements (either the pairing or the field is wrong) ==")
    if not bad:
        print("  none")
    for r, s, sc in bad:
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
