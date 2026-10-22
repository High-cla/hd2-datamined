#!/usr/bin/env python3
"""MurmurHash64A exactly as the HD2 engine checks it, plus the inverse solve used to
keep a modified ``.dl_bin`` plaintext at the *original* content hash.

CLI FRONT-END; THE LIBRARY IS ``murmur64.py``
    Both files implement the same function and their selftest cross-checks them against each other.
    Import ``murmur64`` when you need the hash in code (``murmur64.padding_word_for_hash``); use this
    file when you want the answer from a shell.

Why this exists
    A sealed ``.dl_bin`` has two independent gates (docs/DLBIN-SEALED-BOX.md):

      1. the libsodium sealed box authenticates the bytes  -> ``dlbin_seal.py``
      2. the engine compares ``MurmurHash64A(plaintext)`` with an expected value baked into
         the game                                          -> this file

    Gate 2 is why a *correctly sealed* file with modified content still fails to load: ``0xC000000D``.
    MurmurHash64A is invertible (the multiplier is odd, and ``x ^ (x >> 47)`` is its own inverse on 64
    bits because ``2 * 47 >= 64``), so one free aligned 8-byte word can be solved to hold the total
    hash at the original value.

Algorithm (MurmurHash2 / MurmurHash64A)
    seed 0xDEADBEEFABAD1DEA, m 0xC6A4A7935BD1E995, r 47, little-endian words.

THE 2026-10-22 REPAIR - THREE INDEPENDENT DEFECTS, ALL IN THE INVERSE
    The solver in the first version could not round-trip anything; its own ``selftest`` said so (20/20
    failures) and was the reason this file never got published.  Each defect was measured separately:

    D1  ``_unxorshift47`` applied ``x ^= x >> 47`` TWICE.  That is the identity on 64 bits
        (2*47 >= 64), so the finalisation inverse silently undid only the middle multiply:
        ``hash_before_finalisation(h)`` was ``h * M_INV``, with both xor-shifts left in place.
        Fix: one application (``unshift``).
    D2  the solved value was ``mix(word)``, not ``word``: the last step never applied ``unmix``.
        Fix: an explicit ``unmix`` (two multiplies by ``M_INV`` around one xor-shift).
    D3  the tail step was never reversed.  For ``len(data) % 8 != 0`` the hash ends with
        ``h ^= tail_pattern ; h *= M`` after the last full block, and the backward walk started from
        the post-tail state.  Fix: undo the tail before walking backwards.

    Guard against all three: the selftest now checks solve→identity (solving for the file's own hash
    must return the file's own word), tail and no-tail round-trips, ``unmix(mix(x)) == x``, and a
    cross-check against ``murmur64.py`` when it is importable.

Usage
    python murmur64a.py hash <file>
    python murmur64a.py solve <in> --word N --target HEX --out <file> [--keep-low-byte HEX]
    python murmur64a.py selftest
"""
from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys

SEED = 0xDEADBEEFABAD1DEA
M = 0xC6A4A7935BD1E995
R = 47
MASK64 = (1 << 64) - 1
M_INV = pow(M, -1, 1 << 64)          # odd multiplier -> invertible mod 2**64


def _mix(k: int) -> int:
    k = (k * M) & MASK64
    k ^= k >> R
    k = (k * M) & MASK64
    return k


def unshift(value: int) -> int:
    """``x ^ (x >> 47)``, which is its OWN inverse on 64 bits: 2 * 47 >= 64 leaves no third term.

    Applying it twice therefore returns the input - that was defect D1.
    """
    return (value ^ (value >> R)) & MASK64


def unmix(value: int) -> int:
    """Invert ``_mix``: undo the second multiply, then the xor-shift, then the first multiply."""
    return (unshift((value * M_INV) & MASK64) * M_INV) & MASK64


def murmur64a(data: bytes) -> int:
    """MurmurHash64A (MurmurHash2, 64-bit) with the engine's seed."""
    h = (SEED ^ ((len(data) * M) & MASK64)) & MASK64
    offset = 0
    while offset + 8 <= len(data):
        h ^= _mix(struct.unpack_from("<Q", data, offset)[0])
        h = (h * M) & MASK64
        offset += 8
    tail = data[offset:]
    if tail:
        for index, byte in enumerate(tail):
            h ^= byte << (8 * index)
        h = (h * M) & MASK64
    h ^= h >> R
    h = (h * M) & MASK64
    h ^= h >> R
    return h & MASK64


def hash_before_finalisation(h: int) -> int:
    """Invert the two-step finalisation; returns the hash as it stood after the last word."""
    return unshift((unshift(h) * M_INV) & MASK64)


def solve_word(data: bytes, word_index: int, target: int) -> int:
    """Value the 8-byte word at ``word_index`` must hold for the whole file to hash to ``target``.

    The word must be a full 8-byte block (it may not overlap the tail), and every other byte stays as
    it is in ``data``.
    """
    full = len(data) & ~7
    offset = word_index * 8
    if word_index < 0 or offset + 8 > full:
        raise ValueError(f"word_index {word_index} is not a full 8-byte block of a {len(data)} B file")

    h = (SEED ^ ((len(data) * M) & MASK64)) & MASK64
    for index in range(word_index):
        h ^= _mix(struct.unpack_from("<Q", data, index * 8)[0])
        h = (h * M) & MASK64

    # walk backwards: finalisation -> tail -> the blocks after ours -> our word
    wanted = hash_before_finalisation(target)
    tail = data[full:]
    if tail:
        wanted = ((wanted * M_INV) & MASK64) ^ int.from_bytes(tail, "little")
    for index in range(full // 8 - 1, word_index, -1):
        wanted = ((wanted * M_INV) & MASK64) ^ _mix(struct.unpack_from("<Q", data, index * 8)[0])
    return unmix(((wanted * M_INV) & MASK64) ^ h)


def _reference():
    """The library implementation, if this checkout carries it next to us."""
    try:
        import murmur64                                   # noqa: PLC0415 - optional, same directory
    except Exception:                                     # noqa: BLE001
        return None
    return murmur64


def selftest() -> int:
    failures = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"  {name:<52} {'PASS' if ok else 'FAIL'}{('  ' + detail) if detail else ''}")
        failures += 0 if ok else 1

    # 1) empty input == pure finalisation of the seed
    h = murmur64a(b"")
    expect = SEED
    expect ^= expect >> R
    expect = (expect * M) & MASK64
    expect ^= expect >> R
    check("empty input equals finalised seed", h == expect, f"0x{h:016X}")

    # 2) D1/D2 as unit facts: the inverse helpers must actually invert
    check("unshift is its own inverse", all(unshift(unshift(x)) == x
                                            for x in (0, 1, 0x123456789ABCDEF0, MASK64)))
    sample = [int.from_bytes(os.urandom(8), "little") for _ in range(64)]
    check("unmix(mix(x)) == x  (64 samples)",
          all(unmix(_mix(x)) == x for x in sample))

    # 3) the inverse finalisation must undo the finalisation
    def finalise(h0: int) -> int:
        h1 = h0 ^ (h0 >> R)
        h2 = (h1 * M) & MASK64
        return h2 ^ (h2 >> R)
    check("hash_before_finalisation(finalise(x)) == x  (64 samples)",
          all(hash_before_finalisation(finalise(x)) == x for x in sample))

    # 4) solve -> identity: asking for the file's CURRENT hash must give back its CURRENT word
    ok_identity = True
    for length in (8, 16, 48, 51, 63, 64, 100):
        for word_index in range(length // 8):
            data = bytes(os.urandom(length))
            original = struct.unpack_from("<Q", data, word_index * 8)[0]
            solved = solve_word(data, word_index, murmur64a(data))
            if solved != original:
                ok_identity = False
                print(f"    identity mismatch len={length} word={word_index}: "
                      f"0x{solved:016X} != 0x{original:016X}")
    check("solve(target = current hash) returns the current word", ok_identity,
          "7 lengths x every block, tail and no tail")

    # 5) real round-trip: change the file elsewhere, keep the ORIGINAL hash in one word
    ok_round = True
    for length in (16, 48, 51, 63, 100):
        for word_index in (0, length // 8 - 1):
            data = bytearray(os.urandom(length))
            target = murmur64a(bytes(data))
            data[length // 2] ^= 0xFF                      # a real edit, somewhere else
            struct.pack_into("<Q", data, word_index * 8,
                             solve_word(bytes(data), word_index, target))
            if murmur64a(bytes(data)) != target:
                ok_round = False
                print(f"    round-trip mismatch len={length} word={word_index}")
    check("edit elsewhere + solve one word keeps the hash", ok_round)

    # 6) cross-check against the library implementation when present
    ref = _reference()
    if ref is None:
        print("  murmur64.py not importable next to this file     SKIP (cross-check unavailable)")
    else:
        check("agrees with murmur64.py on 200 random inputs",
              all(ref.murmur64(blob) == murmur64a(blob)
                  for blob in (os.urandom(n) for n in range(200))),
              f"seed 0x{ref.SEED:016X}")

    print(f"selftest: {failures} failure(s)")
    return 1 if failures else 0


def cmd_solve(args) -> int:
    data = bytearray(open(args.file, "rb").read())
    target = int(args.target, 16)
    word = solve_word(bytes(data), args.word, target)
    if args.keep_low_byte:
        wanted_byte = int(args.keep_low_byte, 16)
        if word & 0xFF != wanted_byte:
            print(f"low byte of the solved word is 0x{word & 0xFF:02X}, "
                  f"needs 0x{wanted_byte:02X} - vary an earlier free byte and re-solve")
            return 1
    struct.pack_into("<Q", data, args.word * 8, word)
    got = murmur64a(bytes(data))
    print(f"word {args.word} = 0x{word:016X}  ->  hash 0x{got:016X} "
          f"({'MATCH' if got == target else 'MISMATCH'})")
    if got != target:
        return 1
    with open(args.out, "wb") as handle:
        handle.write(bytes(data))
    print(f"wrote {args.out} ({len(data):,} B, sha256 {hashlib.sha256(bytes(data)).hexdigest()[:16]})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("hash", help="print the content hash")
    p.add_argument("file")
    p.set_defaults(func=lambda a: print(f"{a.file}: {murmur64a(open(a.file,'rb').read()):016X}")
                  or 0)

    p = sub.add_parser("solve", help="put one 8-byte word so the whole file keeps a target hash")
    p.add_argument("file")
    p.add_argument("--word", type=int, required=True, help="8-byte block index")
    p.add_argument("--target", required=True, help="wanted hash, hex")
    p.add_argument("--out", required=True)
    p.add_argument("--keep-low-byte", default="",
                   help="reject the solve unless the word's low byte equals this hex byte")
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("selftest")
    p.set_defaults(func=lambda a: selftest())
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
