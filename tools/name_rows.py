"""Recover row names for beam / arc / explosion tables by cross-build fingerprints.

The current build renumbered every settings row, so the public old-build JSON dumps
(shalzuth/HelldiversData) cannot be joined by row index.  The *contents* survived
though: a row whose numeric fields are byte-identical in both builds is the same
logical row.  Fingerprint the old records, fingerprint the current binary records,
and keep only one-to-one matches.

usage:
  python tools/name_rows.py                # all three tables
  python tools/name_rows.py --table arc    # one table
"""
import argparse
import json
import struct
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAIN = ROOT / 'refs/dlbin/plaintext-all'
WEB = ROOT / 'refs/web'


def f32(value):
    """Round a JSON number to the float32 the binary stores."""
    return struct.unpack('<f', struct.pack('<f', float(value)))[0]


def array_of(path):
    """(base offset, count, stride) of the single DLArray inside a settings group."""
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 0)[0]
    if count != 1:
        raise ValueError(f'{path.name}: expected 1 group, got {count}')
    off = 4                                   # skip the group count
    type_hash, size = struct.unpack_from('<II', data, off + 8)
    payload = off + 24
    aoff, n, pad = struct.unpack_from('<QII', data, payload)
    return data, payload + aoff, n, type_hash


def as_float(v):
    return struct.unpack('<f', struct.pack('<I', v))[0]


# ---------------------------------------------------------------- per table rules
def explosion_fp(rec, base):
    """five float32 radii/cone in a row, plus the audio event id as a tiebreaker."""
    vals = [round(v, 5) for v in struct.unpack_from('<5f', rec, base + 16)]
    vals.append(struct.unpack_from('<I', rec, base + 64)[0])
    return tuple(vals)


def explosion_old(item):
    vals = [round(f32(item[k]), 5) for k in
            ('inner_radius', 'outer_radius', 'stagger_radius', 'cone_angle', 'camera_shake_radius')]
    vals.append(int(item['audio_event']))
    return tuple(vals)


def arc_fp(rec, base):
    # 6 floats (speed .. max_angle_spread_first_shot) then 2 u32 chain values
    vals = [round(v, 5) for v in struct.unpack_from('<6f', rec, base + 4)]
    vals += list(struct.unpack_from('<2I', rec, base + 28))
    return tuple(vals)


def arc_old(item):
    vals = [round(f32(item[k]), 5) for k in
            ('speed', 'distance', 'distance_at_max_angle_spread',
             'distance_at_max_angle_spread_first_shot', 'max_angle_spread',
             'max_angle_spread_first_shot')]
    vals += [int(item['max_chain_length']), int(item['max_chain_split'])]
    return tuple(vals)


def beam_fp(rec, base):
    """radius, length, decal size, and the damage row the beam applies."""
    radius, length = struct.unpack_from('<2f', rec, base + 4)
    decal = struct.unpack_from('<f', rec, base + 40)[0]
    dmg = struct.unpack_from('<I', rec, base + 12)[0]
    return (round(radius, 5), round(length, 5), round(decal, 5), dmg)


def beam_old(item):
    return (round(f32(item['radius']), 5), round(f32(item['length']), 5),
            round(f32(item['decal_size']), 5), DMG_NAME_TO_ID.get(item['damage_info_type'], -1))


def damage_name_to_id():
    """old-build DamageInfoType name -> current-build row id.

    Relaxed rule: a name is mapped when its old row's six numeric fields match exactly
    one current row.  Several old names may share a fingerprint (rebalances aside), but
    the *id* is still determined.
    """
    old_raw = json.load(open(WEB / 'generated_damage_settings.json', encoding='utf-8'))
    old = [x for x in old_raw if 'DamageSettings' in x][0]['DamageSettings']['items']
    data = (PLAIN / 'generated_damage_settings.dl_bin').read_bytes()
    base = 0x64
    count = (len(data) - base) // 76
    current = defaultdict(list)
    for i in range(count):
        off = base + i * 76
        t, dmg, dur = struct.unpack_from('<Iii', data, off)
        ap = tuple(struct.unpack_from('<4I', data, off + 12))
        demo, stag, push = struct.unpack_from('<3I', data, off + 28)
        current[(dmg, dur, ap, demo, stag, push)].append(t)
    out = {}
    for item in old:
        fp = (item['damage'][0], item['damage'][1], tuple(item['armor_penetration_per_angle']),
              item['demolition_strength'], item['force_strength'], item['force_impulse'])
        ids = current.get(fp, [])
        if len(ids) == 1:
            out[item['type']] = ids[0]
    return out


DMG_NAME_TO_ID = damage_name_to_id()

TABLES = {
    'explosion': {'file': 'generated_explosion_settings.dl_bin', 'json': 'generated_explosion_settings.json',
                  'stride': 152, 'key': 'ExplosionSettings', 'fp': explosion_fp, 'old': explosion_old,
                  'label': 'ExplosionType'},
    'arc': {'file': 'generated_arc_settings.dl_bin', 'json': 'generated_arc_settings.json',
            'stride': 104, 'key': 'ArcSettings', 'fp': arc_fp, 'old': arc_old, 'label': 'ArcType'},
    'beam': {'file': 'generated_beam_settings.dl_bin', 'json': 'generated_beam_settings.json',
             'stride': 112, 'key': 'BeamSettings', 'fp': beam_fp, 'old': beam_old, 'label': 'BeamType'},
}


def run(name):
    spec = TABLES[name]
    data, base, count, type_hash = array_of(PLAIN / spec['file'])
    stride = spec['stride']
    if base + count * stride > len(data):
        raise ValueError(f'{name}: array does not fit')

    raw = json.load(open(WEB / spec['json'], encoding='utf-8'))
    old = raw[0][spec['key']]['items']

    old_by_fp = defaultdict(list)
    for item in old:
        old_by_fp[spec['old'](item)].append(item['type'])

    matched, ambiguous, new_only = {}, 0, 0
    for i in range(count):
        rec = data
        fp = spec['fp'](rec, base + i * stride)
        hits = old_by_fp.get(fp, [])
        if len(hits) == 1:
            matched[i] = hits[0]
        elif hits:
            ambiguous += 1
        else:
            new_only += 1

    named = {name_ for name_ in matched.values()}
    print(f'\n=== {name}: current {count} rows, old dump {len(old)} rows, stride {stride}, group 0x{type_hash:08X}')
    print(f'    one-to-one matches: {len(matched)}  (ambiguous {ambiguous}, only-in-new {new_only})')
    print(f'    distinct old names recovered: {len(named)} / {len(old)}')

    table = []
    for i in range(count):
        row_type = struct.unpack_from('<I', data, base + i * stride)[0]
        table.append({'index': i, 'type': row_type, 'name': matched.get(i),
                      'offset': base + i * stride})
    out = WEB / f'name_map_{name}.json'
    out.write_text(json.dumps({'table': name, 'group_type': f'0x{type_hash:08X}',
                               'rows': table}, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'    wrote {out.relative_to(ROOT)}')
    for i in list(matched)[:8]:
        row_type = struct.unpack_from('<I', data, base + i * stride)[0]
        print(f'      row {i:3d} type {row_type:4d}  {matched[i]}')
    return len(matched), len(old)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--table', choices=sorted(TABLES), action='append')
    args = ap.parse_args()
    names = args.table or sorted(TABLES)
    total_m = total_o = 0
    for n in names:
        m, o = run(n)
        total_m += m
        total_o += o
    print(f'\nTOTAL: {total_m} rows named from {total_o} old-dump rows')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
