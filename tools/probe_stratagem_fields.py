#!/usr/bin/env python3
"""Probe every numeric field of both wiki stratagem views against our stratagem rows.

The two wiki views:
  * stratagems data.json  -- "settings" view: num_bombs / num_salvos / area_size / fire_height ...
  * stratagemdata.json    -- "item resource" view: cap / calltime / bomb_interval / salvos / uses ...

Eagle entries have no num_bombs in the settings view, but the item-resource view calls the same
concept `cap` (Capacity on the wiki page).  So testing only one view's field names misses it.
"""
import json
import pathlib
import re
import struct
import sys

sys.path.insert(0, "tools")
from nacl.public import PrivateKey, SealedBox            # noqa: E402

GAME = pathlib.Path(r"D:\SteamLibrary\steamapps\common\Helldivers 2\data\game")
box = SealedBox(PrivateKey(pathlib.Path("refs/dlbin/keys/recipient.sk")
                           .read_bytes().ljust(32, b"\0")[:32]))
plain = box.decrypt((GAME / "generated_stratagem_settings.dl_bin").read_bytes())


def groups(buf):
    out, start = [], 0
    while True:
        at = buf.find(b"LDLD", start)
        if at < 0:
            return out
        start = at + 4
        if at + 24 > len(buf):
            continue
        version, type_id, payload, wide = struct.unpack_from("<IIII", buf, at + 4)
        if version in (1, 2) and 0 < payload and at + 24 + payload <= len(buf):
            out.append((payload, at + 24, type_id))


def cstr(buf, at, limit=250):
    if at <= 0 or at >= len(buf):
        return ""
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end <= at:
        return ""
    raw = buf[at:end]
    return "" if any(b < 32 or b > 126 for b in raw) else raw.decode("ascii")


rows = {}
for size, p0, _tid in groups(plain):
    marker, count = struct.unpack_from("<QQ", plain, p0)
    if marker != 16 or count * 400 > size:
        continue
    base, pool = p0 + 16, plain[p0:]
    for i in range(count):
        at = base + i * 400
        rows[cstr(pool, struct.unpack_from("<Q", plain, at + 16)[0])] = plain[at:at + 400]


def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


by_norm = {norm(k.replace(".", " ")): v for k, v in rows.items()}

sources = {
    "settings": ("refs/wiki/modules/Decodedata-Attacks__stratagems_data.json.raw", "stratagems"),
    "itemres": ("refs/wiki/stratagemdata.json", "weapon"),
}

for label, (path, root) in sources.items():
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))[root]
    pairs = []
    for key, entry in data.items():
        raw = by_norm.get(norm(key))
        if raw is not None:
            pairs.append((key, raw, entry))
    print(f"\n=== {label}: {len(pairs)} pairs")

    fields = []
    for _, _, entry in pairs:
        for k, v in entry.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in fields:
                fields.append(k)

    found = []
    for field in fields:
        values = [e.get(field) for _, _, e in pairs]
        present = [v for v in values if v is not None]
        if len(set(present)) < 2:
            continue
        best = None
        for slot in range(0, 396, 4):
            col_u = [struct.unpack_from("<I", r, slot)[0] for _, r, _ in pairs]
            col_f = [struct.unpack_from("<f", r, slot)[0] for _, r, _ in pairs]
            for kind, col in (("u32", col_u), ("f32", col_f)):
                ok = tot = 0
                for got, want in zip(col, values):
                    if want is None:
                        continue
                    tot += 1
                    if kind == "u32":
                        good = got == want
                    else:
                        good = abs(got - want) <= 1e-3 * max(1.0, abs(want))
                    if good:
                        ok += 1
                if tot and ok / tot >= 0.99 and (best is None or ok / tot > best[1]):
                    best = (slot, ok / tot, kind, tot)
        if best:
            found.append((field, best[0], best[1], best[2], best[3], len(set(present))))
    print(f"  {'field':<22}{'offset':>7} {'kind':<4}{'rate':>6}{'/pairs':>8}{'distinct':>9}")
    for field, slot, rate, kind, tot, distinct in sorted(found, key=lambda r: r[1]):
        print(f"  {field:<22}{'+' + str(slot):>7} {kind:<4}{rate:>6.2f}{tot:>8}{distinct:>9}")
    if not found:
        print("  (nothing matched)")
    missed = [f for f in fields if f not in {x[0] for x in found}]
    print(f"  not located: {', '.join(missed)}")
