#!/usr/bin/env python3
"""Export every texture inside a ``.patch_N`` add-on as one editable DDS per file.

Why a wrapper
    ``srkit unpack --type texture`` already decodes the header and reassembles the
    pixel data from the ``.gpu_resources`` companion, but it writes
    ``<patch>/resources/texture_<ID>/texture.dds`` -- one folder per texture and no
    clue what is inside.  For "swap the texture" work you want a flat, sortable
    listing plus the format/size in the name, and usually a PNG preview to look at.

What it does
    1. runs ``srkit unpack <patch> --type texture`` into a scratch dir
    2. reads each ``texture.dds`` header (width, height, mip count, DXGI format)
    3. copies them to ``<out>/<label>/<ID>_<W>x<H>_<FORMAT>.dds``
    4. optionally converts each to PNG with the SDK's ``deps/texconv.exe``
    5. writes ``INDEX.md`` + ``index.json`` next to the files

Usage
    python export_textures.py <patch> -o <dir> [--label NAME] [--no-preview]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

SDK_CANDIDATES = [os.environ.get("HD2SDK", ""), os.path.expanduser(os.path.join("~", "HD2SDK-CommunityEdition"))]
TEXCONV_REL = os.path.join("deps", "texconv.exe")

# DDS header offsets
DWIDTH, DHEIGHT, DMIPS, FPFOURCC = 16, 12, 28, 84
# DXGI_FORMAT (dxgiformat.h).  The earlier table here was shifted by one because
# it omitted the *_TYPELESS entries, so 71 (BC1_UNORM) was labelled
# BC1_UNORM_SRGB and 98 (BC7_UNORM) BC7_UNORM_SRGB.  Files already exported keep
# their old names; a fresh export now gets the true format.
DXGI_FORMATS = {
    0: "UNKNOWN", 1: "R32G32B32A32_TYPELESS", 2: "R32G32B32A32_FLOAT",
    3: "R32G32B32A32_UINT", 10: "R16G16B16A16_FLOAT", 11: "R16G16B16A16_UNORM",
    28: "R8G8B8A8_UNORM", 29: "R8G8B8A8_UNORM_SRGB", 31: "R8G8B8A8_SNORM",
    41: "R32_FLOAT", 49: "R8G8_UNORM", 61: "R8_UNORM",
    70: "BC1_TYPELESS", 71: "BC1_UNORM", 72: "BC1_UNORM_SRGB",
    73: "BC2_TYPELESS", 74: "BC2_UNORM", 75: "BC2_UNORM_SRGB",
    76: "BC3_TYPELESS", 77: "BC3_UNORM", 78: "BC3_UNORM_SRGB",
    79: "BC4_TYPELESS", 80: "BC4_UNORM", 81: "BC4_SNORM",
    82: "BC5_TYPELESS", 83: "BC5_UNORM", 84: "BC5_SNORM",
    85: "B5G6R5_UNORM", 86: "B5G5R5A1_UNORM",
    87: "B8G8R8A8_UNORM", 88: "B8G8R8A8_UNORM_SRGB",
    94: "BC6H_TYPELESS", 95: "BC6H_UF16", 96: "BC6H_SF16",
    97: "BC7_TYPELESS", 98: "BC7_UNORM", 99: "BC7_UNORM_SRGB",
}


def find_sdk() -> str:
    for root in SDK_CANDIDATES:
        if root and os.path.isfile(os.path.join(root, "srkit", "__init__.py")):
            return root
    raise SystemExit("export_textures: cannot find the HD2SDK checkout (set HD2SDK=<path>)")


def parse_dds(path: str) -> dict:
    with open(path, "rb") as handle:
        head = handle.read(148)
    if len(head) < 148 or head[:4] != b"DDS ":
        raise SystemExit(f"{path}: not a DDS file")
    height = struct.unpack_from("<I", head, DHEIGHT)[0]
    width = struct.unpack_from("<I", head, DWIDTH)[0]
    mips = struct.unpack_from("<I", head, DMIPS)[0] or 1
    fourcc = head[FPFOURCC:FPFOURCC + 4]
    fmt = None
    if fourcc == b"DX10":
        dxgi = struct.unpack_from("<I", head, 128)[0]
        fmt = DXGI_FORMATS.get(dxgi, f"DXGI_{dxgi}")
    else:
        fmt = fourcc.decode("ascii", "replace").strip("\x00") or "legacy"
    return {"width": width, "height": height, "mips": mips, "format": fmt,
            "bytes": os.path.getsize(path)}


def texture_dirs(scratch: str) -> list[tuple[str, str]]:
    """Return ``[(file_id_hex, dds_path)]`` from an srkit unpack tree."""
    found = []
    for base, dirs, files in os.walk(scratch):
        if "texture.dds" not in files:
            continue
        resource_json = os.path.join(base, "resource.json")
        file_id = os.path.basename(base)
        if os.path.isfile(resource_json):
            try:
                meta = json.load(open(resource_json, encoding="utf-8"))
                file_id = "%016X" % int(meta.get("file_id", "0"))
            except (OSError, ValueError):
                pass
        found.append((file_id, os.path.join(base, "texture.dds")))
    found.sort()
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("patch")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--no-preview", action="store_true")
    args = ap.parse_args()

    sdk = find_sdk()
    patch = os.path.abspath(args.patch)
    label = args.label or os.path.basename(os.path.dirname(patch)) or "patch"
    out_dir = os.path.join(os.path.abspath(args.out), label)
    dds_dir = os.path.join(out_dir, "dds")
    os.makedirs(dds_dir, exist_ok=True)

    scratch = tempfile.mkdtemp(prefix="srkit_tex_")
    env = dict(os.environ, PYTHONPATH=sdk)
    try:
        command = [sys.executable, "-m", "srkit", "unpack", patch, "-o", scratch, "--type", "texture"]
        result = subprocess.run(command, capture_output=True, text=True, env=env, cwd=sdk)
        tail = (result.stdout or "").strip().splitlines()[-1:] or [""]
        print(f"srkit: {tail[0]}")
        if result.returncode != 0:
            print(result.stderr[-800:], file=sys.stderr)
            return 1

        rows = []
        for file_id, dds in texture_dirs(scratch):
            info = parse_dds(dds)
            name = "%s_%dx%d_%s.dds" % (file_id, info["width"], info["height"], info["format"])
            target = os.path.join(dds_dir, name)
            shutil.copy2(dds, target)
            rows.append({"file_id": file_id, **info, "file": name})
            print("  %-40s %5dx%-5d mips=%-2d %-18s %8.1f KiB"
                  % (file_id, info["width"], info["height"], info["mips"],
                     info["format"], info["bytes"] / 1024))

        previews = []
        if not args.no_preview and rows:
            try:
                from PIL import Image
            except ImportError:
                Image = None
                print("Pillow not available; skipping previews")
            if Image is not None:
                png_dir = os.path.join(out_dir, "png")
                os.makedirs(png_dir, exist_ok=True)
                for row in rows:
                    source = os.path.join(dds_dir, row["file"])
                    try:
                        image = Image.open(source)
                        if image.mode not in ("RGB", "RGBA"):
                            image = image.convert("RGBA")
                        target = os.path.join(png_dir, os.path.splitext(row["file"])[0] + ".png")
                        image.save(target, "PNG")
                        previews.append(os.path.basename(target))
                    except Exception as exc:            # noqa: BLE001 - 单张失败不影响其它
                        print("  ! preview failed for %s: %s" % (row["file"], exc))
                print(f"previews: {len(previews)}/{len(rows)} in {png_dir}")

        with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as handle:
            json.dump({"patch": patch, "label": label, "textures": rows,
                       "previews": previews}, handle, indent=2)
        with open(os.path.join(out_dir, "INDEX.md"), "w", encoding="utf-8") as handle:
            handle.write(f"# {label} — 贴图清单\n\n来源：`{patch}`\n\n")
            handle.write("| file_id | 尺寸 | mip | 格式 | 大小 | 文件 |\n|---|---:|---:|---|---:|---|\n")
            for row in rows:
                handle.write("| `%s` | %dx%d | %d | %s | %.1f KiB | `dds/%s` |\n"
                             % (row["file_id"], row["width"], row["height"], row["mips"],
                                row["format"], row["bytes"] / 1024, row["file"]))
            if previews:
                handle.write("\n预览：`png/` 下同名 PNG。\n")
        print(f"wrote {len(rows)} texture(s) into {dds_dir}")
        return 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
