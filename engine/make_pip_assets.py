"""Assets for the corner face box: a rounded mask and the plate it sits on.

The plate is drawn once as RGBA and overlaid under the face, so the drop
shadow and rim light cost nothing per frame. Run after changing PIP geometry.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from styles import PIP_H, PIP_R, PIP_W

from config import EDIT
ASSETS = EDIT / "assets"
PAD = 40          # room around the box for the shadow
RIM = 3           # rim light thickness in px


def rounded(w: int, h: int, r: int, ss: int = 4) -> Image.Image:
    """Antialiased rounded-rect mask, drawn oversized then downsampled."""
    big = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        [0, 0, w * ss - 1, h * ss - 1], radius=r * ss, fill=255)
    return big.resize((w, h), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    mask = rounded(PIP_W, PIP_H, PIP_R)
    mask.save(ASSETS / "pip_mask.png")

    pw, ph = PIP_W + PAD * 2, PIP_H + PAD * 2
    plate = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))

    # Shadow: the box silhouette, blurred, offset down a little.
    shadow = Image.new("L", (pw, ph), 0)
    shadow.paste(rounded(PIP_W + 8, PIP_H + 8, PIP_R + 4), (PAD - 4, PAD + 4))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    sh = np.asarray(shadow, np.float32) / 255.0 * 0.55
    plate_arr = np.zeros((ph, pw, 4), np.float32)
    plate_arr[..., 3] = sh * 255.0

    # Rim light: a thin bright ring right on the edge, so the box reads
    # against dark screen content the way it does against light.
    outer = np.asarray(rounded(PIP_W + RIM * 2, PIP_H + RIM * 2,
                               PIP_R + RIM), np.float32) / 255.0
    inner = np.zeros_like(outer)
    m = np.asarray(mask, np.float32) / 255.0
    inner[RIM:RIM + PIP_H, RIM:RIM + PIP_W] = m
    ring = np.clip(outer - inner, 0, 1)
    ry, rx = PAD - RIM, PAD - RIM
    region = plate_arr[ry:ry + PIP_H + RIM * 2, rx:rx + PIP_W + RIM * 2]
    a = ring * 0.85
    region[..., 0] = np.maximum(region[..., 0], 242 * a)
    region[..., 1] = np.maximum(region[..., 1], 246 * a)
    region[..., 2] = np.maximum(region[..., 2], 244 * a)
    region[..., 3] = np.maximum(region[..., 3], a * 255.0)

    Image.fromarray(plate_arr.clip(0, 255).astype(np.uint8), "RGBA").save(
        ASSETS / "pip_plate.png")
    print(f"pip_mask.png {PIP_W}x{PIP_H} r={PIP_R}")
    print(f"pip_plate.png {pw}x{ph} pad={PAD}")


if __name__ == "__main__":
    main()
