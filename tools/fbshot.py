#!/usr/bin/env python3
"""fbshot — dump the Linux framebuffer (/dev/fb0, RGB565) to a PNG.

Usage:  fbshot.py [out.png|-]      ('-' or omitted = write PNG to stdout)

Lets a remote (no-display) operator SEE exactly what's painted on the SPI
panel. Over SSH:  ssh pi 'python3 .../fbshot.py -' > shot.png
"""
import os
import sys

import numpy as np
from PIL import Image

FB = os.environ.get("PISYNTH_FB", "/dev/fb0")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "-"
    node = os.path.basename(os.path.realpath(FB))
    with open(f"/sys/class/graphics/{node}/virtual_size") as f:
        w, h = (int(v) for v in f.read().strip().split(","))
    with open(FB, "rb") as f:
        raw = f.read(w * h * 2)
    px = np.frombuffer(raw, dtype="<u2").astype(np.uint32)
    r = ((px >> 11) & 0x1F) << 3
    g = ((px >> 5) & 0x3F) << 2
    b = (px & 0x1F) << 3
    rgb = np.dstack([r, g, b]).astype(np.uint8).reshape(h, w, 3)
    img = Image.fromarray(rgb, "RGB")
    if out == "-":
        img.save(sys.stdout.buffer, "PNG")
    else:
        img.save(out, "PNG")
        print(f"saved {out} ({w}x{h})")


if __name__ == "__main__":
    main()
