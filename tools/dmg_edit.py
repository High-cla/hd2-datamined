"""Hash-preserving edit of one DamageSettings row (offline .dl_bin route).

The content hash gate is MurmurHash64A over the whole plaintext container, so any
edit has to be paid for by one 8-byte aligned "correction word" whose value makes
the total hash land back on the original.  damage_settings has no record padding,
so the correction is paid in an empty status slot of a row nothing references
(a "host" row): the solve writes one random 8-byte word there.

usage:
  python tools/dmg_edit.py --type 114 --damage 600 --host-type 537
  python tools/dmg_edit.py --type 114 --damage 600 --host-type 537 --seal
"""
import argparse
import os
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from murmur64 import murmur64, padding_word_for_hash, SEED  # noqa: E402

DAMAGE_TYPE = 0xE0A72CF0
STRIDE = 76
TYPE_AT, DMG_AT, DUR_AT, STATUS_AT = 0, 4, 8, 44


def parse_ldld(data):
    count = struct.unpack_from('<I', data, 0)[0]
    off, groups = 4, []
    for i in range(count):
        if data[off:off + 4] != b'LDLD':
            raise ValueError(f'group {i}: bad magic at 0x{off:X}')
        th, psz = struct.unpack_from('<II', data, off + 8)
        groups.append({'index': i, 'type': th, 'payload': off + 24, 'size': psz, 'header': off})
        off += 24 + psz
    if off != len(data):
        raise ValueError(f'container ends at 0x{off:X}, file is {len(data):,} B')
    return groups


def damage_array(data):
    for g in parse_ldld(data):
        if g['type'] == DAMAGE_TYPE:
            aoff, count, pad = struct.unpack_from('<QII', data, g['payload'])
            if pad != 0:
                raise ValueError('unexpected array descriptor padding')
            base = g['payload'] + aoff
            if base + count * STRIDE > g['payload'] + g['size']:
                raise ValueError('array overruns its group payload')
            return base, count
    raise ValueError('damage settings group not found')


def rows(data):
    base, count = damage_array(data)
    out = []
    for i in range(count):
        off = base + i * STRIDE
        t, dmg, dur = struct.unpack_from('<Iii', data, off)
        status = [struct.unpack_from('<If', data, off + STATUS_AT + 8 * k) for k in range(4)]
        out.append({'index': i, 'offset': off, 'type': t, 'damage': dmg, 'durable': dur,
                    'status': status})
    return out


def empty_aligned_words(row):
    words = []
    for k in range(4):
        pos = row['offset'] + STATUS_AT + 8 * k
        t, v = row['status'][k]
        if t == 0 and v == 0.0 and pos % 8 == 0:
            words.append({'offset': pos, 'slot': k})
    return words


def diff_ranges(a, b, limit=40):
    out, start = [], None
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y and start is None:
            start = i
        elif x == y and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(a)))
    return out[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plain', type=Path,
                    default=ROOT / 'tables/generated_damage_settings.dl_bin')
    ap.add_argument('--type', type=int, required=True, help='DamageInfoType row to edit')
    ap.add_argument('--damage', type=int, required=True, help='new Damage value')
    ap.add_argument('--durable', type=int, help='new DurableDamage value (default: keep)')
    ap.add_argument('--host-type', type=int, required=True,
                    help='unreferenced row that pays the hash correction')
    ap.add_argument('--out-dir', type=Path, default=Path('dmg-edit-out'))
    ap.add_argument('--material', type=Path, help='seal material file (needed with --seal)')
    ap.add_argument('--key', type=Path, help='recipient secret key for the round-trip check (needed with --seal)')
    ap.add_argument('--seal', action='store_true', help='also produce the sealed .dl_bin')
    args = ap.parse_args()

    original = args.plain.read_bytes()
    h0 = murmur64(original)
    print(f'plaintext {args.plain.name}: {len(original):,} B  hash {h0:016X}')

    table = rows(original)
    by_type = {r['type']: r for r in table}
    target = by_type.get(args.type)
    if target is None:
        print(f'ERROR: no row with DamageInfoType {args.type}')
        return 2
    host = by_type.get(args.host_type)
    if host is None:
        print(f'ERROR: no row with DamageInfoType {args.host_type}')
        return 2
    if target['index'] == host['index']:
        print('ERROR: host row must differ from the edited row')
        return 2
    words = empty_aligned_words(host)
    if not words:
        print(f'ERROR: host row {args.host_type} has no empty 8-byte aligned status word')
        return 2

    new_durable = target['durable'] if args.durable is None else args.durable
    edited = bytearray(original)
    struct.pack_into('<i', edited, target['offset'] + DMG_AT, args.damage)
    struct.pack_into('<i', edited, target['offset'] + DUR_AT, new_durable)
    print(f'target row   : type {args.type} (record {target["index"]}, offset 0x{target["offset"]:X})')
    print(f'  Damage    {target["damage"]} -> {args.damage}')
    print(f'  Durable   {target["durable"]} -> {new_durable}'
          + ('  (unchanged)' if new_durable == target['durable'] else ''))
    print(f'host row     : type {args.host_type} (record {host["index"]}, '
          f'{len(words)} empty slots, damage {host["damage"]})')
    print(f'correction   : word at 0x{words[0]["offset"]:X} (slot {words[0]["slot"]}, '
          f'{words[0]["offset"] % 8} mod 8)')

    h_edit = murmur64(bytes(edited))
    print(f'after the semantic edit: hash {h_edit:016X} ({"differs" if h_edit != h0 else "UNCHANGED"})')

    word = padding_word_for_hash(bytes(edited), words[0]['offset'], h0, SEED)
    struct.pack_into('<Q', edited, words[0]['offset'], struct.unpack('<Q', word)[0])
    h_solved = murmur64(bytes(edited))
    print(f'correction word value  : 0x{struct.unpack("<Q", word)[0]:016X}')
    print(f'final hash             : {h_solved:016X}  '
          f'{"== original  PASS" if h_solved == h0 else "!= original  FAIL"}')
    if h_solved != h0:
        return 3

    ranges = diff_ranges(original, bytes(edited))
    print(f'\nchanged byte ranges ({len(ranges)}):')
    for a, b in ranges:
        print(f'  0x{a:05X}..0x{b:05X}  ({b - a} B)  '
              f'{original[a:b].hex()} -> {edited[a:b].hex()}')

    args.out_dir.mkdir(parents=True, exist_ok=True)
    plain_out = args.out_dir / 'generated_damage_settings.edited.plain.dl_bin'
    plain_out.write_bytes(bytes(edited))
    print(f'\nwrote {plain_out}')

    report = {
        'source': str(args.plain),
        'original_hash': f'{h0:016X}',
        'final_hash': f'{h_solved:016X}',
        'hash_preserved': h_solved == h0,
        'edit': {'type': args.type, 'record': target['index'],
                 'offset': f'0x{target["offset"]:X}',
                 'damage': [target['damage'], args.damage],
                 'durable': [target['durable'], new_durable]},
        'correction': {'host_type': args.host_type, 'record': host['index'],
                       'offset': f'0x{words[0]["offset"]:X}', 'slot': words[0]['slot'],
                       'value': f'0x{struct.unpack("<Q", word)[0]:016X}'},
        'changed_ranges': [[f'0x{a:X}', f'0x{b:X}'] for a, b in diff_ranges(original, bytes(edited))],
    }

    if args.seal:
        if not args.material or not args.key:
            print('ERROR: --seal needs --material and --key')
            return 2
        sealed_out = args.out_dir / 'generated_damage_settings.sealed.dl_bin'
        cmd = [sys.executable, str(HERE / 'dlbin_seal.py'), 'seal-material', str(plain_out),
               '--material', str(args.material), '--out', str(sealed_out)]
        print('\nsealing:', ' '.join(cmd[1:]))
        done = subprocess.run(cmd, capture_output=True, text=True)
        sys.stdout.write(done.stdout)
        sys.stderr.write(done.stderr)
        if done.returncode != 0:
            print(f'seal failed with exit {done.returncode}')
            return 4
        blob = sealed_out.read_bytes()
        print(f'  sealed {len(blob):,} B = plaintext {len(original):,} + 48')
        # round trip: open with the recipient key and compare
        back = args.out_dir / 'roundtrip.plain.dl_bin'
        cmd2 = [sys.executable, str(HERE / 'dlbin_seal.py'), 'open-key', str(sealed_out),
                '--key', str(args.key), '--out', str(back)]
        done2 = subprocess.run(cmd2, capture_output=True, text=True)
        sys.stdout.write(done2.stdout)
        sys.stderr.write(done2.stderr)
        if done2.returncode != 0:
            print(f'open-key failed with exit {done2.returncode}')
            return 5
        same = back.read_bytes() == bytes(edited)
        print(f'  round trip identical: {same}  hash {murmur64(back.read_bytes()):016X}')
        report['sealed'] = {'path': str(sealed_out), 'size': len(blob),
                            'md5': __import__('hashlib').md5(blob).hexdigest(),
                            'roundtrip_identical': same}

    (args.out_dir / 'edit-report.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(f'wrote {args.out_dir / "edit-report.json"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
