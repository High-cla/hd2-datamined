#!/usr/bin/env python3
"""Probe: in what numeric form does a stratagem row carry its projectile type?

The wiki's Module:Decodedata-Attacks/stratagemdata.json decodes each stratagem's settings and
exposes a `projectile_type` *name* (e.g. "Orbital_Precision_Strike").  If our row stores the same
thing, it must be one of a few numeric encodings.  For each matched (our row, wiki entry) pair this
prints which encoding actually occurs in that row, and at which offset.
"""
import json
import pathlib
import re
import struct
import sys

sys.path.insert(0, "tools")
from nacl.public import PrivateKey, SealedBox            # noqa: E402
import table_xref_scan as X                              # noqa: E402
import typelib                                           # noqa: E402

GAME = pathlib.Path(r"D:\SteamLibrary\steamapps\common\Helldivers 2\data\game")
SK = pathlib.Path("refs/dlbin/keys/recipient.sk")

box = SealedBox(PrivateKey(SK.read_bytes().ljust(32, b"\0")[:32]))
types = typelib.TypeLib(X.unseal((GAME / "dl_library.dl_typelib").read_bytes(), box))


def stride_of(t):
    members = types.members(t)
    if len(members) == 1 and (members[0]["size64"] or 0) > 8:
        return types.free_runs(members[0]["type_id"], 1)[0]
    return types.free_runs(t, 1)[0]


proj = X.dominant(X.rows_of(X.unseal((GAME / "generated_projectile_settings.dl_bin").read_bytes(),
                                    box), stride_of))
fd = {it["type"]: it for it in json.loads(
    pathlib.Path("refs/helldiversdata/generated_projectile_settings.json")
    .read_text(encoding="utf-8"))[0]["ProjectileSettings"]["items"]}
ptype_list = json.loads(pathlib.Path("refs/helldiversdata/enums_ProjectileType.json")
                        .read_text(encoding="utf-8"))["ProjectileType"]
ename = {n: i for i, n in enumerate(ptype_list)}


def proj_encodings(name):
    full = "ProjectileType_" + name
    item = fd.get(full)
    if not item:
        return None
    upper = item["name_upper"]
    matches = [(i, r) for i, r in enumerate(proj) if struct.unpack_from("<I", r, 4)[0] == upper]
    out = {"name": full, "name_upper": upper, "enum_index": ename.get(full)}
    if matches:
        index, row = matches[0]
        out["file_index"] = index
        out["type_id"] = struct.unpack_from("<I", row, 0)[0]
        out["copies"] = len(matches)
    return out


wiki = json.loads(pathlib.Path("refs/wiki/stratagemdata.json")
                  .read_text(encoding="utf-8"))["weapon"]


def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


plain = box.decrypt((GAME / "generated_stratagem_settings.dl_bin").read_bytes())


def groups(payload):
    out, start = [], 0
    while True:
        at = payload.find(b"LDLD", start)
        if at < 0:
            return out
        start = at + 4
        if at + 24 > len(payload):
            continue
        version, type_id, size, wide = struct.unpack_from("<IIII", payload, at + 4)
        if version in (1, 2) and 0 < size and at + 24 + size <= len(payload):
            out.append((size, at + 24))


def cstr(buf, at, limit=250):
    if at <= 0 or at >= len(buf):
        return ""
    end = buf.find(b"\0", at, min(len(buf), at + limit))
    if end <= at:
        return ""
    raw = buf[at:end]
    return "" if any(b < 32 or b > 126 for b in raw) else raw.decode("ascii")


rows = []
for size, p0 in groups(plain):
    marker, count = struct.unpack_from("<QQ", plain, p0)
    if marker != 16 or count * 400 > size:
        continue
    base, pool = p0 + 16, plain[p0:]
    for i in range(count):
        row = base + i * 400
        rows.append((cstr(pool, struct.unpack_from("<Q", plain, row + 16)[0]),
                     plain[row:row + 400]))

by_name = {norm(k): v for k, v in wiki.items()}
print(f"{'our row':<38}{'wiki projectile_type':<34}encodings found in the row")
print("-" * 118)
for display, raw in rows:
    entry = by_name.get(norm(display.replace(".", " ")))
    if not entry or not entry.get("projectile_type"):
        continue
    enc = proj_encodings(entry["projectile_type"])
    if enc is None:
        print(f"  {display:<36}{entry['projectile_type']:<34}(not in filediver dump)")
        continue
    values = [struct.unpack_from("<I", raw, s)[0] for s in range(0, 396, 4)]
    hits = []
    for key in ("name_upper", "type_id", "file_index", "enum_index"):
        want = enc.get(key)
        if want is None:
            continue
        slots = [f"+{s}" for s, v in enumerate(values) if v == want]
        if slots:
            hits.append(f"{key}={want} at {','.join(slots)}")
    print(f"  {display:<36}{entry['projectile_type']:<34}" + (" | ".join(hits) or "none"))
