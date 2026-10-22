"""Cross-table references to DamageSettings rows (read-only).

Parses the LDLD containers of the plaintext tables and reports, for every
DamageInfo row (type id = primary key), which projectile / explosion records
refer to it.  Rows nobody refers to are candidates to host a hash-correction
word, because nothing ever applies their status effects.

usage:
  python tools/dmg_refs.py --dir refs/dlbin/plaintext-all [--json out.json] [--top 20]
"""
import argparse
import json
import struct
import sys
from pathlib import Path

DAMAGE_TYPE = 0xE0A72CF0
PROJECTILE_TYPE = 0xBD4042C2
EXPLOSION_TYPE = 0x2AEA2592

# record layouts (offsets verified against work/filediver/*.go, stride checked at parse time)
DAMAGE_STRIDE = 76
DAMAGE_TYPE_AT = 0
DAMAGE_DMG_AT = 4
DAMAGE_DURABLE_AT = 8
DAMAGE_STATUS_AT = 44          # 4 x {u32 type, f32 value}

PROJECTILE_STRIDE = 272
PROJECTILE_DAMAGE_REF_AT = 60  # enum.DamageInfoType
PROJECTILE_ON_IMPACT_AT = 144  # enum.ExplosionType
PROJECTILE_ON_EXPIRE_AT = 156

EXPLOSION_STRIDE = 152
EXPLOSION_DAMAGE_REF_AT = 4    # enum.DamageInfoType


def parse_ldld(data):
    """[(index, type_hash, payload_offset, payload_size, header_offset)]"""
    count = struct.unpack_from('<I', data, 0)[0]
    out, off = [], 4
    for i in range(count):
        magic = data[off:off + 4]
        if magic != b'LDLD':
            raise ValueError(f'group {i}: bad magic {magic!r} at 0x{off:X}')
        type_hash, payload_size = struct.unpack_from('<II', data, off + 8)
        wide = data[off + 16]
        out.append((i, type_hash, off + 24, payload_size, off, wide))
        off += 24 + payload_size
    return out, off


def array_at(data, payload_offset):
    """LDLD array descriptor: (u64 array_offset, u32 count, u32 pad), then the array."""
    aoff, count, pad = struct.unpack_from('<QII', data, payload_offset)
    if pad != 0 or aoff > 0x1000:
        raise ValueError(f'unexpected array descriptor {aoff},{count},{pad} at 0x{payload_offset:X}')
    return payload_offset + aoff, count


def load_table(path, type_hash, stride):
    data = path.read_bytes()
    groups, end = parse_ldld(data)
    for idx, th, poff, psz, hoff, wide in groups:
        if th == type_hash:
            base, count = array_at(data, poff)
            end = (base - poff) + count * stride
            if end > psz:
                raise ValueError(f'{path.name}: {count} x {stride} overruns payload ({end} > {psz})')
            return data, base, count, groups
    raise ValueError(f'{path.name}: group 0x{type_hash:08X} not found')


def damage_rows(path):
    data, base, count, groups = load_table(path, DAMAGE_TYPE, DAMAGE_STRIDE)
    rows = []
    for i in range(count):
        off = base + i * DAMAGE_STRIDE
        t, dmg, dur = struct.unpack_from('<Iii', data, off)
        status = [struct.unpack_from('<If', data, off + DAMAGE_STATUS_AT + 8 * k) for k in range(4)]
        rows.append({'index': i, 'offset': off, 'type': t, 'damage': dmg, 'durable': dur,
                     'status': status})
    return data, rows


def collect(path, type_hash, stride, ref_at, label):
    data, base, count, groups = load_table(path, type_hash, stride)
    refs = {}
    for i in range(count):
        off = base + i * stride
        ref = struct.unpack_from('<I', data, off + ref_at)[0]
        refs.setdefault(ref, []).append(i)
    print(f'{path.name:52s} records={count:4d}  distinct {label} refs={len(refs):4d}')
    return refs, data, base, count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='refs/dlbin/plaintext-all', type=Path)
    ap.add_argument('--json', type=Path)
    ap.add_argument('--top', type=int, default=15)
    args = ap.parse_args()

    d, rows = damage_rows(args.dir / 'generated_damage_settings.dl_bin')
    print(f'damage_settings: {len(rows)} rows, file {len(d):,} B')
    by_type = {r['type']: r for r in rows}
    if len(by_type) != len(rows):
        print('  WARNING: duplicate type ids')

    proj_refs, *_ = collect(args.dir / 'generated_projectile_settings.dl_bin',
                            PROJECTILE_TYPE, PROJECTILE_STRIDE,
                            PROJECTILE_DAMAGE_REF_AT, 'damage')
    expl_refs, *_ = collect(args.dir / 'generated_explosion_settings.dl_bin',
                            EXPLOSION_TYPE, EXPLOSION_STRIDE,
                            EXPLOSION_DAMAGE_REF_AT, 'damage')

    referenced = set(proj_refs) | set(expl_refs)
    bad = sorted(t for t in referenced if t not in by_type)
    print(f'\nreferenced damage types: {len(referenced)}'
          f'  (projectile {len(proj_refs)}, explosion {len(expl_refs)}, both {len(set(proj_refs) & set(expl_refs))})')
    if bad:
        print(f'  OUT OF RANGE refs (not a row in this table): {bad[:20]}'
              f'{" ..." if len(bad) > 20 else ""}')

    orphans = [r for r in rows if r['type'] not in referenced]
    print(f'orphan rows (no projectile/explosion reference): {len(orphans)}')

    # aligned empty status slots inside a row: usable as hash-correction words
    def usable(row):
        out = []
        start = row['offset']
        for k in range(4):
            pos = start + DAMAGE_STATUS_AT + 8 * k
            t, v = row['status'][k]
            if t == 0 and v == 0.0 and pos % 8 == 0:
                out.append(pos)
        return out

    orphan_hosts = [r for r in orphans if usable(r)]
    print(f'orphans with an 8-byte aligned empty status slot: {len(orphan_hosts)}')
    for r in orphan_hosts[:args.top]:
        print(f'  row {r["index"]:3d} type {r["type"]:3d} dmg {r["damage"]:5d} '
              f'word 0x{usable(r)[0]:05X} ({len(usable(r))} slots)')
    if orphan_hosts:
        first = usable(orphan_hosts[0])[0]
        print(f'\n  first usable correction word: 0x{first:X} ({first} = {first % 8} mod 8)')

    # reference histogram for the most used rows
    hist = sorted(((len(v), t) for t, v in proj_refs.items()), reverse=True)[:args.top]
    print('\nmost referenced damage rows (by projectiles):')
    for n, t in hist:
        r = by_type.get(t)
        print(f'  type {t:3d}: {n:3d} projectiles  dmg={r["damage"] if r else "?"}')

    if args.json:
        payload = {
            'damage': [{'type': r['type'], 'index': r['index'], 'damage': r['damage'],
                        'durable': r['durable'], 'offset': r['offset'],
                        'status': [[t, v] for t, v in r['status']],
                        'usable_words': usable(r),
                        'referenced_by_projectile': proj_refs.get(r['type'], []),
                        'referenced_by_explosion': expl_refs.get(r['type'], [])} for r in rows],
            'orphans': [r['type'] for r in orphans],
            'orphan_hosts': [{'type': r['type'], 'words': usable(r)} for r in orphan_hosts],
        }
        args.json.write_text(json.dumps(payload, indent=1), encoding='utf-8')
        print(f'\nwrote {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
