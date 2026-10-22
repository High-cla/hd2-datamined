#!/usr/bin/env python3
"""Hunt for the X25519 key that opens the game's sealed `.dl_bin` files.

Why this can work at all
    A sealed ``.dl_bin`` is a libsodium ``crypto_box_seal`` blob:
        epk(32) || tag(16) || ciphertext
        nonce   = BLAKE2b-24(epk || recipient_pk)
        shared  = X25519(recipient_sk, epk)
        subkey  = HSalsa20(shared, nonce[:16]);  key stream = Salsa20(subkey, nonce[16:])
        tag     = Poly1305(ciphertext, stream[:32])        <- verified on open

    Given a candidate 32-byte *private* key we can rebuild all of that and let
    PyNaCl verify the tag: the real key yields exactly one plaintext, every wrong
    key raises BadSignatureTag.  That is a 2^-128 oracle, and it validates the
    whole model (nonce derivation included) on a file whose plaintext we know is
    an LDLD container.

Cost
    ~2 X25519 + one BLAKE2b + one secretbox open per candidate.  Run it over the
    32-byte aligned windows of a binary first (data/rodata sections are small);
    unaligned and seed-derived passes are opt-in.

Usage
    python dlbin_keyhunt.py <candidate binary> --blob <sealed .dl_bin> [--step 32]
                            [--start OFFSET] [--end OFFSET] [--limit N] [--seed]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import serialization
import nacl.bindings

BASE = b"\x09" + b"\x00" * 31


def public_of(sk: bytes) -> bytes:
    return X25519PrivateKey.from_private_bytes(sk).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def opens(sk: bytes, sealed: bytes) -> bool:
    """True if `sk` is the recipient private key of this sealed blob.

    The box key is NOT the raw X25519 shared point: ``crypto_box_beforenm`` runs it
    through HSalsa20 with a zero nonce first, and the 24-byte message nonce is
    BLAKE2b(epk || recipient_pk).  Getting either wrong makes the oracle reject the
    true key, so it is validated against a self-made ``SealedBox`` in the selftest.
    """
    if len(sk) != 32:
        return False
    epk, rest = sealed[:32], sealed[32:]
    try:
        pk = public_of(sk)
        box_key = nacl.bindings.crypto_box_beforenm(epk, sk)
    except Exception:                                        # noqa: BLE001
        return False
    nonce = hashlib.blake2b(epk + pk, digest_size=24).digest()
    try:
        nacl.bindings.crypto_secretbox_open(rest, nonce, box_key)
        return True
    except Exception:                                        # noqa: BLE001 - BadSignatureTag
        return False


def selftest() -> bool:
    from nacl.public import PrivateKey, SealedBox
    key = PrivateKey.generate()
    blob = SealedBox(key.public_key).encrypt(b"LDLD" * 100)
    good = opens(bytes(key), blob)
    bad = opens(bytes(PrivateKey.generate()), blob)
    print(f"  oracle selftest: real key -> {good}, wrong key -> {bad}")
    return good and not bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("--blob", help="a sealed .dl_bin (any valid one works as the oracle)")
    ap.add_argument("--step", type=int, default=32)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=0, help="0 = end of file")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--selftest", action="store_true", help="validate the oracle, then exit")
    ap.add_argument("--seed", action="store_true",
                    help="also try sk = clamp(BLAKE2b-32(window)) (seed_keypair layout)")
    args = ap.parse_args()

    if args.selftest:
        return 0 if selftest() else 1
    if not args.blob:
        print("--blob is required for a scan"); return 1
    sealed = open(args.blob, "rb").read()
    if sealed[:4] in (b"LDLD", b"LTLD"):
        print("blob looks like plaintext, not a sealed box"); return 1
    data = open(args.binary, "rb").read()
    end = args.end or len(data)
    end = min(end, len(data))
    offsets = range(args.start, end - 32, args.step)
    print(f"{args.binary}: scanning {len(range(args.start, end - 32, args.step)):,} window(s) "
          f"step={args.step} seed_pass={args.seed}")
    print(f"oracle: {args.blob} ({len(sealed):,} B)")

    started = time.time()
    hits = []
    for n, off in enumerate(offsets, 1):
        window = data[off:off + 32]
        if window == b"\x00" * 32 or len(set(window)) < 8:
            continue
        candidates = [window]
        if args.seed:
            digest = hashlib.blake2b(window, digest_size=64).digest()[:32]
            candidates.append(bytes([digest[0] & 248]) + digest[1:31]
                              + bytes([(digest[31] & 127) | 64]))
        for sk in candidates:
            if opens(sk, sealed):
                hits.append((off, sk))
                print(f"  HIT offset 0x{off:08X}: sk={sk.hex()}")
        if args.limit and n >= args.limit:
            print("limit reached"); break
        if n % 5000 == 0:
            rate = n / (time.time() - started)
            print(f"  {n:,} windows  {rate:,.0f}/s  elapsed {time.time() - started:,.0f}s")

    if not hits:
        print("no key found in this pass")
        return 1
    for off, sk in hits:
        _, pk = shared_and_pk(sk, sealed[:32])
        print(f"  offset 0x{off:08X}\n    sk={sk.hex()}\n    pk={pk.hex()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
