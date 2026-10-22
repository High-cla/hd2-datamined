#!/usr/bin/env python3
"""Turn a "lit lens + dark reticle" texture into an emissive reticle mask.

Why
    Some scope mods ship the optic as one picture: a bright lens disc with the
    crosshair *cut out* in black (ApexScope does exactly this).  HD2 draws the
    reticle additively - the shader multiplies the texture by ReticleColor *
    ReticleColorIntensity - so the slot needs the opposite polarity: bright
    lines on black.  10x Scope's own reticle texture is white-on-black.

What "invert" has to mean here
    A plain ``255 - v`` turns the black page *outside* the lens into a white
    field (the whole reticle quad would glow).  What we actually want is the
    ink, not the background.  For a thin dark stroke lying on a bright lens:

        top-hat(v) = max_local(A) - A

    which is the standard white top-hat of the inverted image (opening removes
    anything narrower than the structuring element).  Its properties:

      * a stroke pixel                -> local max  = lens brightness  -> bright
      * flat lens interior / outside  -> local max == A              -> 0
      * the broad lens falloff        -> opening tracks a monotonic ramp -> ~0

    So only the strokes survive, and a stroke's amplitude follows the local
    lens brightness - i.e. the reticle fades out at the optic rim instead of
    being cut by a hard circle.

Usage
    python lensmask_to_reticle.py <source.png> -o <reticle.png> [--radius 9]
                                  [--black 0] [--report]
"""
from __future__ import annotations

import argparse
import sys

from PIL import Image, ImageChops, ImageFilter


def extract(path: str, radius: int = 9) -> Image.Image:
    """Return an L-mode reticle mask (bright strokes on black)."""
    if radius % 2 == 0:
        radius += 1                      # PIL morph filters need an odd size
    lens = Image.open(path).convert("L")
    inverted = ImageChops.invert(lens)
    # grayscale opening = erosion then dilation; removes every bright feature
    # thinner than the structuring element (i.e. keeps the broad lens shape)
    opened = inverted.filter(ImageFilter.MinFilter(radius))
    opened = opened.filter(ImageFilter.MaxFilter(radius))
    return ImageChops.subtract(inverted, opened)


def apply_black_level(image: Image.Image, black: int) -> Image.Image:
    """Fade the sub-black tail (the analytic leftover of the lens gradient)."""
    if black <= 0:
        return image
    scale = 255.0 / (255.0 - black)
    return image.point(lambda v: max(0, min(255, int(round((v - black) * scale)))))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--radius", type=int, default=9,
                    help="structuring element; must exceed the thickest stroke")
    ap.add_argument("--black", type=int, default=0,
                    help="black level to subtract (0 keeps the analytic tail)")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    mask = apply_black_level(extract(args.image, args.radius), args.black)
    mask.save(args.out)

    if args.report:
        hist = mask.histogram()
        total = sum(hist)
        nonzero = sum(hist[1:])
        print(f"wrote {args.out}  {mask.size[0]}x{mask.size[1]}  L")
        print(f"  nonzero {nonzero} px ({100.0 * nonzero / total:.2f}%)  "
              f"max {max(i for i, n in enumerate(hist) if n)}")
        for low in range(0, 256, 32):
            band = sum(hist[low:low + 32])
            if band:
                print(f"  {low:3d}-{low + 31:3d}: {band:6d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
