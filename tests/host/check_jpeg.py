#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
"""Decode the JPEGs written by test_jpeg with an independent decoder.

test_jpeg writes <name>.jpg next to <name>.rgb (packed RGB24 source pixels).
The file name encodes pattern, size and quality: <pattern>_<W>x<H>_q<Q>.jpg.

Each JPEG must decode cleanly with libjpeg (via Pillow), without warnings,
and be a baseline 4:2:0 image of the right size.  Fidelity is judged against
libjpeg's own encoder: the same source, quality and subsampling, with the same
standard Huffman tables.  Ours must be within a fraction of a dB of its PSNR
and not meaningfully larger.  This is independent of the content, so there are
no hand-tuned per-image thresholds; a corrupt bitstream decodes to garbage
and fails by tens of dB.
"""
import io
import math
import pathlib
import re
import sys
import warnings

import numpy as np
from PIL import Image, ImageFile, JpegImagePlugin

ImageFile.LOAD_TRUNCATED_IMAGES = False

MAX_PSNR_DEFICIT_DB = 0.5   # vs libjpeg at the same settings
MAX_SIZE_RATIO = 1.10       # vs libjpeg at the same settings
SAMPLING_420 = 2            # Pillow's code for 4:2:0

NAME_RE = re.compile(r"(?P<pat>\w+?)_(?P<w>\d+)x(?P<h>\d+)_q(?P<q>\d+)\.jpg$")


def psnr(a, b):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if mse == 0 else 10 * math.log10(255.0 ** 2 / mse)


def decode(data):
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # libjpeg warnings become failures
        img = Image.open(io.BytesIO(data))
        img.load()
    return img


def check(path):
    m = NAME_RE.match(path.name)
    if not m:
        return f"unexpected file name {path.name}"
    w, h, q = int(m["w"]), int(m["h"]), int(m["q"])

    ours = path.read_bytes()
    img = decode(ours)
    if img.size != (w, h) or img.mode != "RGB":
        return f"{path.name}: {img.size} {img.mode}, expected {(w, h)} RGB"
    if JpegImagePlugin.get_sampling(img) != SAMPLING_420:
        return f"{path.name}: not 4:2:0"
    if "progressive" in img.info or "progression" in img.info:
        return f"{path.name}: not baseline"

    src = np.frombuffer(path.with_suffix(".rgb").read_bytes(), np.uint8)
    src = src.reshape(h, w, 3)

    buf = io.BytesIO()
    Image.fromarray(src).save(buf, "JPEG", quality=q, subsampling=SAMPLING_420)
    ref = buf.getvalue()

    ours_db = psnr(src, np.asarray(img))
    ref_db = psnr(src, np.asarray(decode(ref)))
    if ours_db < ref_db - MAX_PSNR_DEFICIT_DB:
        return f"{path.name}: PSNR {ours_db:.2f} dB vs libjpeg {ref_db:.2f} dB"
    if len(ours) > len(ref) * MAX_SIZE_RATIO + 64:
        return f"{path.name}: {len(ours)} bytes vs libjpeg {len(ref)}"
    return None


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <dir>")
    files = sorted(pathlib.Path(sys.argv[1]).glob("*.jpg"))
    if not files:
        sys.exit("no JPEG files to check")
    errors = [e for e in map(check, files) if e]
    for e in errors:
        print("FAIL", e)
    print(f"check_jpeg: {len(files) - len(errors)}/{len(files)} images OK")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
