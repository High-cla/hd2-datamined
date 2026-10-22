#!/usr/bin/env python3
"""Replace one texture inside a ``.patch_N`` mod with a PNG, and repack it.

Conventions this tool enforces
    * the DDS header of the original texture is kept **byte for byte** - only
      the pixel blob is regenerated, so the engine sees the same format, size,
      mip count and flags it already accepted;
    * the regenerated blob must have exactly the original byte length, which
      keeps every TOC offset in the package valid;
    * every other resource in the patch must come out with an identical
      ``sha256`` in the rebuilt package (asserted before the result is used).

Usage
    python swap_texture.py <patch> --id 8CECE9664922DAED --image new.png \
        -o <outdir> [--name 9ba626afa44a3aa3.patch_3] [--preview png]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

from PIL import Image

SDK_CANDIDATES = [os.environ.get("HD2SDK", ""), os.path.expanduser(os.path.join("~", "HD2SDK-CommunityEdition"))]

# DXGI format -> Pillow DXT encoder + bytes per 4x4 block
ENCODERS = {
    70: ("DXT1", 8),   # BC1_TYPELESS
    71: ("DXT1", 8),   # BC1_UNORM
    72: ("DXT1", 8),   # BC1_UNORM_SRGB
    77: ("DXT5", 16),  # BC3_UNORM
    78: ("DXT5", 16),  # BC3_UNORM_SRGB
}
DXGI_NAMES = {70: "BC1_TYPELESS", 71: "BC1_UNORM", 72: "BC1_UNORM_SRGB",
              77: "BC3_UNORM", 78: "BC3_UNORM_SRGB"}


def find_sdk() -> str:
    for root in SDK_CANDIDATES:
        if root and os.path.isfile(os.path.join(root, "srkit", "__init__.py")):
            return root
    raise SystemExit("swap_texture: cannot find the HD2SDK checkout (set HD2SDK=<path>)")


def srkit(sdk: str, argv: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=sdk)
    return subprocess.run([sys.executable, "-m", "srkit", *argv],
                          capture_output=True, text=True, env=env, cwd=sdk)


def dds_info(head: bytes) -> dict:
    if len(head) < 148 or head[:4] != b"DDS ":
        raise SystemExit("swap_texture: payload is not a DDS with the 4-byte magic")
    height = struct.unpack_from("<I", head, 12)[0]
    width = struct.unpack_from("<I", head, 16)[0]
    mip_count = struct.unpack_from("<I", head, 28)[0] or 1
    if head[84:88] != b"DX10":
        raise SystemExit("swap_texture: original DDS has no DX10 extended header")
    dxgi = struct.unpack_from("<I", head, 128)[0]
    return {"width": width, "height": height, "mips": mip_count, "dxgi": dxgi}


def mip_sizes(width: int, height: int, count: int) -> list[tuple[int, int]]:
    out = []
    w, h = width, height
    for _ in range(count):
        out.append((max(1, w), max(1, h)))
        w //= 2
        h //= 2
    return out


def build_dds(header: bytes, image, info: dict) -> tuple[bytes, list[int]]:
    pixel_format = ENCODERS[info["dxgi"]][0]
    blocks = []
    sizes = []
    for w, h in mip_sizes(info["width"], info["height"], info["mips"]):
        level = image if (w, h) == image.size else image.resize((w, h), Image.Resampling.BOX)
        padded_w, padded_h = (w + 3) // 4 * 4, (h + 3) // 4 * 4
        if (padded_w, padded_h) != (w, h):
            canvas = level.copy()
            canvas = canvas.crop((0, 0, padded_w, padded_h))
            level = canvas
        buf = io.BytesIO()
        level.convert("RGB").save(buf, "DDS", pixel_format=pixel_format)
        data = buf.getvalue()[128:]
        blocks.append(data)
        sizes.append(len(data))
    return header + b"".join(blocks), sizes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("patch")
    ap.add_argument("--id", required=True, help="texture file id, hex (as in INDEX.md)")
    ap.add_argument("--image", required=True, help="replacement PNG")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--name", default="", help="output package name (default: keep original)")
    ap.add_argument("--preview", default="", help="write mip0 of the new texture here (PNG)")
    ap.add_argument("--keep", action="store_true", help="keep the scratch workspace")
    args = ap.parse_args()

    sdk = find_sdk()
    from PIL import Image

    patch = os.path.abspath(args.patch)
    target_id = int(args.id, 16) if not args.id.lower().startswith("0x") else int(args.id, 16)
    scratch = tempfile.mkdtemp(prefix="swap_tex_")
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    try:
        res = srkit(sdk, ["unpack", patch, "-o", scratch, "--quiet"])
        if res.returncode != 0:
            print(res.stdout[-500:], res.stderr[-1500:], sep="\n", file=sys.stderr)
            return 1

        package_dirs = [d for d in os.listdir(scratch) if os.path.isdir(os.path.join(scratch, d))]
        if len(package_dirs) != 1:
            raise SystemExit(f"swap_texture: unexpected workspace layout {package_dirs}")
        pkg_dir = os.path.join(scratch, package_dirs[0])
        old_pkg = json.load(open(os.path.join(pkg_dir, "package.json"), encoding="utf-8"))

        entry = next((e for e in old_pkg["entries"]
                      if int(e["file_id"], 10) == target_id), None)
        if entry is None:
            raise SystemExit(f"swap_texture: no entry with file id {args.id}")
        if entry["type_name"] != "texture":
            raise SystemExit(f"swap_texture: {args.id} is a {entry['type_name']}, not a texture")

        dds_path = os.path.join(pkg_dir, entry["resource_dir"], "texture.dds")
        original = open(dds_path, "rb").read()
        header, old_pixels = original[:148], original[148:]
        info = dds_info(header)
        if info["dxgi"] not in ENCODERS:
            raise SystemExit(f"swap_texture: DXGI {info['dxgi']} "
                             f"({DXGI_NAMES.get(info['dxgi'], '?')}) is not encodable here")
        print(f"target  {args.id}  {info['width']}x{info['height']}  "
              f"{info['mips']} mip(s)  {DXGI_NAMES[info['dxgi']]}  "
              f"{len(old_pixels)} pixel bytes")

        image = Image.open(args.image).convert("RGB")
        if image.size != (info["width"], info["height"]):
            print(f"note    resizing {image.size} -> {(info['width'], info['height'])}")
            image = image.resize((info["width"], info["height"]), Image.Resampling.LANCZOS)

        new_dds, mip_bytes = build_dds(header, image, info)
        new_pixels = new_dds[148:]
        print("mips    " + " ".join(str(b) for b in mip_bytes[:4]) + " ...")
        if len(new_pixels) != len(old_pixels):
            raise SystemExit(f"swap_texture: pixel blob size changed "
                             f"{len(old_pixels)} -> {len(new_pixels)}; refusing to repack")
        print(f"pixels  {len(new_pixels)} bytes (identical to original)")

        open(dds_path, "wb").write(new_dds)

        name = args.name or old_pkg["name"]
        res = srkit(sdk, ["pack", scratch, "-o", out_dir, "--name", name, "--quiet"])
        if res.returncode != 0:
            print(res.stdout[-800:], res.stderr[-2000:], sep="\n", file=sys.stderr)
            return 1
        new_patch = os.path.join(out_dir, name)
        print(f"packed  {new_patch}  ({os.path.getsize(new_patch)} bytes)")

        # ---- verification: every other resource must be byte identical ----
        verify_dir = tempfile.mkdtemp(prefix="swap_verify_")
        try:
            res = srkit(sdk, ["unpack", new_patch, "-o", verify_dir, "--quiet"])
            if res.returncode != 0:
                print(res.stdout[-500:], res.stderr[-1500:], sep="\n", file=sys.stderr)
                return 1
            vpkg = os.path.join(verify_dir, os.listdir(verify_dir)[0])
            new_pkg = json.load(open(os.path.join(vpkg, "package.json"), encoding="utf-8"))
            bad = 0
            for old_entry in old_pkg["entries"]:
                new_entry = next((e for e in new_pkg["entries"]
                                  if e["file_id"] == old_entry["file_id"]
                                  and e["type_name"] == old_entry["type_name"]), None)
                if new_entry is None:
                    print(f"  MISSING {old_entry['type_name']} {old_entry['file_id']}")
                    bad += 1
                    continue
                changed = [k for k in ("toc", "gpu", "stream")
                           if old_entry["blobs"][k]["sha256"] != new_entry["blobs"][k]["sha256"]]
                if int(old_entry["file_id"], 10) == target_id:
                    expected = {"gpu"} if old_entry["gpu_resource_offset"] >= 0 else {"gpu"}
                    print(f"  target  {old_entry['type_name']:<9} {old_entry['file_id']:<22} "
                          f"changed blobs: {changed or 'none'}")
                    if changed != sorted(expected):
                        print("  ! target texture changed an unexpected blob")
                        bad += 1
                    continue
                if changed:
                    print(f"  DRIFT   {old_entry['type_name']:<9} {old_entry['file_id']:<22} {changed}")
                    bad += 1
            print(f"verify  {bad} problem(s)" if bad else "verify  all other resources byte identical")

            if args.preview:
                from PIL import Image as _Image
                vdds = os.path.join(vpkg, entry["resource_dir"], "texture.dds")
                _Image.open(vdds).convert("RGB").save(args.preview, "PNG")
                print(f"preview {args.preview}")
            return 1 if bad else 0
        finally:
            shutil.rmtree(verify_dir, ignore_errors=True)
    finally:
        if not args.keep:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
