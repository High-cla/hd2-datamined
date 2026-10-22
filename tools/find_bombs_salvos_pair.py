#!/usr/bin/env python3
"""Find the (num_bombs, salvos) slot PAIR in stratagem_settings.

A single-field scan found neither `num_bombs` nor `num_salvos` anywhere in the 400-byte row.  But
they describe one thing together -- warheads fired at once, times the number of volleys -- so the
likely layout is two slots side by side.  A joint scan over slot pairs is far more discriminating
than two independent scans: 8 orbital rows with num_bombs = 1/1/1/1/60/3/3/5 pin down a pair almost
uniquely, whereas either column alone matches many slots by chance.
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
            out.append((payload, at + 24))


def cstr(buf, at, limit=250):
    if at <= 0 or at >= len(buf):
        return ""
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end <= at:
        return ""
    raw = buf[at:end]
    return "" if any(b < 32 or b > 126 for b in raw) else raw.decode("ascii")


rows = {}
for size, p0 in groups(plain):
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
data = json.loads(pathlib.Path("refs/wiki/modules/Decodedata-Attacks__stratagems_data.json.raw")
                  .read_text(encoding="utf-8"))["stratagems"]

targets = []
for key, entry in data.items():
    raw = by_norm.get(norm(key))
    if raw is None:
        continue
    if entry.get("num_bombs") is None or entry.get("num_salvos") is None:
        continue
    targets.append((key, raw, entry["num_bombs"], entry["num_salvos"]))

print(f"joint targets: {len(targets)}")
print(f"  {'stratagem':<32}{'num_bombs':>10}{'salvos':>8}{'product':>9}")
for key, _raw, bombs, salvos in targets:
    print(f"  {key:<32}{bombs:>10}{salvos:>8}{bombs * salvos:>9}")

print("\n== slot pairs (a, b) where row[a]==num_bombs and row[b]==num_salvos ==")
hits = []
for a in range(0, 396, 4):
    for b in range(0, 396, 4):
        if a == b:
            continue
        ok = 0
        for _key, raw, bombs, salvos in targets:
            ua = struct.unpack_from("<I", raw, a)[0]
            ub = struct.unpack_from("<I", raw, b)[0]
            fa = struct.unpack_from("<f", raw, a)[0]
            fb = struct.unpack_from("<f", raw, b)[0]
            if (ua == bombs or abs(fa - bombs) < 1e-6) and (ub == salvos or abs(fb - salvos) < 1e-6):
                ok += 1
        if ok >= len(targets) - 1:
            hits.append((ok, a, b))
hits.sort(reverse=True)
if not hits:
    print("  none (tried every ordered pair, allowing one mismatch)")
for ok, a, b in hits[:10]:
    print(f"  +{a:<4},+{b:<4} {ok}/{len(targets)}")
    for key, raw, bombs, salvos in targets:
        va = struct.unpack_from("<I", raw, a)[0]
        vb = struct.unpack_from("<I", raw, b)[0]
        mark = "" if (va == bombs and vb == salvos) else "  <-- diff"
        print(f"      {key:<32} ours=({va},{vb})  wiki=({bombs},{salvos}){mark}")

print("\n== is the PRODUCT stored instead? ==")
for slot in range(0, 396, 4):
    ok = 0
    for _key, raw, bombs, salvos in targets:
        u = struct.unpack_from("<I", raw, slot)[0]
        f = struct.unpack_from("<f", raw, slot)[0]
        if u == bombs * salvos or abs(f - bombs * salvos) < 1e-6:
            ok += 1
    if ok >= len(targets) - 1:
        print(f"  +{slot:<4} {ok}/{len(targets)}  holds num_bombs*num_salvos")
