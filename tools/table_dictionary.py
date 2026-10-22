#!/usr/bin/env python3
"""table_dictionary.py -- read-only dictionary of every `.dl_bin` table in this build.

WHAT IT PRODUCES
    For all ``data/game/generated_*.dl_bin`` (plus the typelib that describes them):

        1. the container geometry   how many groups, which type each group holds,
                                    the row record size, how many rows fit, and how many
                                    bytes are left over after the last whole row
        2. the field tree           every member of every type, with byte offset / size /
                                    element type, resolved recursively through the typelib
        3. the names                type names come from a public hash->name list (filediver's
                                    ``dl_type_names.txt``); the typelib itself is stripped and
                                    carries no strings at all

    Two outputs: ``--json`` (machine readable, everything) and ``--md`` (human readable summary).

WHAT IT DOES NOT DO
    It never writes to the game, never launches it, and never touches process memory.  It only reads
    the sealed files, decrypts them with a recipient key you supply, and parses the bytes.  Read-only
    by construction - the only outputs are the two report files.

WHY THE KEY IS AN ARGUMENT, NOT A CONSTANT
    The sealed-box recipient private key is not published (see docs/DLBIN-SEALED-BOX.md).  Point
    ``--sk`` at your own copy; the tool refuses to run without it, so no key material can end up in
    this repository.

GEOMETRY, AND WHERE IT IS APPROXIMATE
    A group's payload is ``44-byte header + N * record_size`` for the tables measured so far
    (projectile: 44 + 355*272 = 96,604 exactly).  Some tables carry a second, smaller block after the
    rows - explosion has 3,664 bytes after 424*152 - so the tool reports the leftover instead of
    pretending the row count is exact.  ``rows_exact`` is true only when the leftover is zero.

USAGE
    python tools/table_dictionary.py --sk <recipient.sk> --game "<...>/Helldivers 2" \\
        --names refs/dl-type-names.json --json out/dictionary.json --md out/DICTIONARY.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import typelib                                                    # noqa: E402

HEADER = 48          # sealed box: epk(32) + tag(16)
GROUP_HEADER = 24    # 'LDLD' + version + type id + payload size + wide
DESCRIPTOR = 16      # payload prefix: u64 0x10, u64 row count  (verified: projectile 355, explosion 424)


def load_names(path: pathlib.Path | None) -> dict[int, str]:
    """Either the public name list (one name per line) or a precomputed id->name json."""
    if path is None or not path.is_file():
        return {}
    if path.suffix.lower() == ".txt":
        out = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            name = line.strip()
            if not name or name.startswith("//"):
                continue
            out[typelib.type_hash(name)] = name
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for item in data.get("fields", []):
        try:
            out[int(item["id_hex"], 16)] = item["name"]
        except (KeyError, ValueError, TypeError):
            continue
    return out


def unseal(blob: bytes, box) -> bytes:
    return box.decrypt(blob) if len(blob) > HEADER else blob


def scan_groups(plain: bytes) -> list[dict]:
    """Every plausible 'LDLD' group; validated by version and payload bounds."""
    groups, start = [], 0
    while True:
        at = plain.find(b"LDLD", start)
        if at < 0:
            break
        start = at + 4
        if at + GROUP_HEADER > len(plain):
            continue
        version, type_id, payload, wide = struct.unpack_from("<IIII", plain, at + 4)
        if version not in (1, 2) or not 0 < payload or at + GROUP_HEADER + payload > len(plain):
            continue
        groups.append({"at": at, "version": version, "type_id": type_id,
                       "payload": payload, "wide": wide, "payload_at": at + GROUP_HEADER})
    return groups


class Dictionary:
    def __init__(self, typelib_bytes: bytes, names: dict[int, str]):
        self.lib = typelib.TypeLib(typelib_bytes)
        self.names = names
        self._record: dict[int, int | None] = {}
        self._members: dict[int, list[dict]] = {}

    # ---- type layer -------------------------------------------------------
    def name(self, tid: int) -> str:
        return self.names.get(tid) or f"0x{tid:08X}"

    def record_size(self, tid: int) -> int | None:
        if tid not in self._record:
            try:
                self._record[tid] = self.lib.free_runs(tid, 1)[0]
            except Exception:                                     # noqa: BLE001
                self._record[tid] = None
        return self._record[tid]

    def members(self, tid: int) -> list[dict]:
        if tid in self._members:
            return self._members[tid]
        out = []
        try:
            raw = self.lib.members(tid)
        except Exception:                                         # noqa: BLE001
            raw = []
        for m in raw:
            child = m["type_id"]
            out.append({
                "offset": m["offset64"],
                "size": m["size64"],
                "type_id": child,
                "type": self.name(child),
                "record_size": self.record_size(child),
            })
        self._members[tid] = out
        return out

    def element_of(self, tid: int) -> tuple[int, int | None]:
        """A ``*Settings`` container wraps one member whose type is the row record."""
        members = self.members(tid)
        if len(members) == 1 and (members[0]["record_size"] or 0) > (self.record_size(tid) or 0):
            return members[0]["type_id"], members[0]["record_size"]
        return tid, self.record_size(tid)

    def tree(self, tid: int, depth: int = 0, seen: frozenset = frozenset()) -> dict:
        node = {"type_id": tid, "name": self.name(tid), "record_size": self.record_size(tid),
                "members": []}
        if depth >= 3 or tid in seen:
            return node
        for m in self.members(tid):
            child = dict(m)
            if depth + 1 < 3 and m["type_id"] not in seen:
                child["children"] = self.tree(m["type_id"], depth + 1, seen | {tid})["members"]
            node["members"].append(child)
        return node


def geometry(plain: bytes, payload_at: int, payload: int, stride: int | None) -> dict:
    """Classify one group payload.

    The common shape is ``u64 0x10 + u64 count`` followed by ``count`` records, i.e. exactly
    ``payload == 16 + count*stride``.  When bytes remain they are a second block in the same group -
    for explosion that is the 3,664-byte tail after row 424; when the count is a power of two the
    remainder is usually a hashmap slot array sitting between the descriptor and the rows.
    """
    if stride and payload >= DESCRIPTOR + stride:
        marker, count = struct.unpack_from("<QQ", plain, payload_at)
        if marker == DESCRIPTOR and 0 < count < 100_000_000:
            used = count * stride
            if DESCRIPTOR + used <= payload:
                tail = payload - DESCRIPTOR - used
                power2 = count & (count - 1) == 0
                layout = "array" if tail == 0 else ("hashmap+rows" if power2 else "array+tail")
                return {"rows": count, "tail": tail, "layout": layout, "stride": stride}
    if stride and payload >= stride:
        return {"rows": payload // stride, "tail": payload % stride,
                "layout": "raw" if payload % stride else "raw-array", "stride": stride}
    return {"rows": None, "tail": None, "layout": "unknown", "stride": stride}


def analyse_table(name: str, plain: bytes, dic: Dictionary) -> dict:
    groups = scan_groups(plain)
    rows_total, leftover_total, clean = 0, 0, 0
    details, seen_types = [], {}
    for g in groups:
        elem_tid, stride = dic.element_of(g["type_id"])
        geo = geometry(plain, g["payload_at"], g["payload"], stride)
        rows, leftover = geo["rows"], geo["tail"]
        if rows is not None:
            rows_total += rows
            leftover_total += leftover
            clean += 1 if leftover == 0 else 0
        key = (g["type_id"], elem_tid)
        slot = seen_types.setdefault(key, {"container": dic.name(g["type_id"]),
                                           "element": dic.name(elem_tid),
                                           "element_type_id": elem_tid,
                                           "stride": stride, "groups": 0, "rows": 0,
                                           "leftover": 0})
        slot["groups"] += 1
        slot["rows"] += rows or 0
        slot["leftover"] += leftover or 0
        details.append({"at": g["at"], "type_id": g["type_id"], "version": g["version"],
                        "wide": g["wide"], "payload": g["payload"], **geo})
    return {
        "table": name,
        "plain_size": len(plain),
        "groups": len(groups),
        "rows": rows_total,
        "rows_exact": bool(groups) and leftover_total == 0,
        "layouts": sorted({d["layout"] for d in details}),
        "leftover_bytes": leftover_total,
        "types": list(seen_types.values()),
        "group_detail": details,
    }


def write_markdown(tables: list[dict], dic: Dictionary, path: pathlib.Path) -> None:
    lines = ["# Table dictionary — build 25988413 (read-only)", "",
             "`count` is read from each group's payload header (`u64 0x10, u64 count`); for a group",
             "whose layout is `hashmap+rows` it is the **hashmap slot count**, not the number of rows.",
             "", "layout legend:", "",
             "| layout | meaning |", "|---|---|",
             "| `array` | `16 + count*stride == payload`, exactly. Rows are clean and contiguous. |",
             "| `array+tail` | same, plus a second unmapped block after the rows (explosion: 3,664 B). |",
             "| `hashmap+rows` | count is a power of two: a hashmap slot array sits between the descriptor and the rows. |",
             "| `raw` | no `0x10` descriptor; the payload is rows directly. |", "",
             "| table | plain B | groups | count | layout | element type(s) |",
             "|---|---:|---:|---:|---|---|"]
    for t in sorted(tables, key=lambda x: -x["plain_size"]):
        kinds = ", ".join(f"{ty['element']}×{ty['stride']}B" for ty in t["types"][:3])
        layouts = "+".join(t.get("layouts", []))
        lines.append(f"| `{t['table']}` | {t['plain_size']:,} | {t['groups']} | "
                     f"{t['rows']:,} | {layouts} | {kinds} |")
    lines.append("")
    lines.append("## Field layouts")
    lines.append("")
    for t in sorted(tables, key=lambda x: x["table"]):
        for ty in t["types"]:
            tid = ty["element_type_id"]
            lines.append(f"### {ty['element']}  (`{t['table']}`, stride {ty['stride']} B, "
                         f"rows {ty['rows']:,})")
            lines.append("")
            lines.append("| offset | size | type | note |")
            lines.append("|---:|---:|---|---|")
            for m in dic.members(tid):
                lines.append(f"| {m['offset']} | {m['size']} | {m['type']} "
                             f"(`0x{m['type_id']:08X}`) | |")
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=r"D:\SteamLibrary\steamapps\common\Helldivers 2")
    ap.add_argument("--sk", required=True, help="recipient.sk (32 B) - not shipped with this repo")
    ap.add_argument("--names", default="", help="hash->name json (filediver dl_type_names derived)")
    ap.add_argument("--json", default="", help="write the full dictionary here")
    ap.add_argument("--md", default="", help="write the human-readable summary here")
    a = ap.parse_args()

    from nacl.public import PrivateKey, SealedBox

    game = pathlib.Path(a.game) / "data" / "game"
    if not game.is_dir():
        print(f"!! not a game data dir: {game}")
        return 2
    box = SealedBox(PrivateKey(pathlib.Path(a.sk).read_bytes().ljust(32, b"\0")[:32]))

    typelib_path = game / "dl_library.dl_typelib"
    typelib_plain = unseal(typelib_path.read_bytes(), box)
    dic = Dictionary(typelib_plain, load_names(pathlib.Path(a.names) if a.names else None))
    print(f"typelib: {dic.lib.nt} types, {dic.lib.nm} members, {len(dic.names)} name(s)")

    tables = []
    for path in sorted(game.glob("*.dl_bin")):
        tables.append(analyse_table(path.name, unseal(path.read_bytes(), box), dic))

    clean = sum(1 for t in tables if t["rows_exact"])
    print(f"tables: {len(tables)}   rows exact: {clean}   leftover: {len(tables) - clean}")
    print(f"{'table':<48}{'groups':>7}{'rows':>9}{'leftover':>10}  exact  element")
    for t in sorted(tables, key=lambda x: -x["plain_size"]):
        ty = t["types"][0] if t["types"] else {"element": "-", "stride": "-"}
        print(f"{t['table']:<48}{t['groups']:>7}{t['rows']:>9}{t['leftover_bytes']:>10}  "
              f"{'yes' if t['rows_exact'] else ' no'}   {ty['element']}")

    if a.json:
        pathlib.Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        payload = {"build": "25988413", "tables": tables,
                   "types": {f"0x{tid:08X}": dic.tree(tid)
                             for tid in {ty["element_type_id"] for t in tables for ty in t["types"]}}}
        pathlib.Path(a.json).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"json -> {a.json}  ({pathlib.Path(a.json).stat().st_size:,} B)")
    if a.md:
        pathlib.Path(a.md).parent.mkdir(parents=True, exist_ok=True)
        write_markdown(tables, dic, pathlib.Path(a.md))
        print(f"md   -> {a.md}  ({pathlib.Path(a.md).stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
