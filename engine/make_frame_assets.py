"""Generate the static Screen Studio-style frame assets.

The screen recording is near-black (#040905 page background), so the surround
has to be lighter than the content or the rounded corners vanish. We use a
deep forest/teal gradient pulled from the site's own palette, plus a soft
amber glow behind the top-left where the content is brightest.

Outputs into edit/assets/:
  bg.png     1920x1080 gradient backdrop with the drop shadow already baked in
  mask.png   CONTENT_W x CONTENT_H rounded-rect luma mask (white = opaque)
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT_W, OUT_H = 1920, 1080
CONTENT_W, CONTENT_H = 1568, 882          # 81.6% of frame, 16:9
CONTENT_X = (OUT_W - CONTENT_W) // 2      # 176
CONTENT_Y = 116                           # sits slightly high, room for captions below
CORNER_R = 18

SHADOW_BLUR = 34
SHADOW_OFFSET_Y = 22
SHADOW_ALPHA = 0.55

from config import EDIT
ASSETS = EDIT / "assets"


def gradient_bg() -> Image.Image:
    """Diagonal deep-forest -> teal-charcoal gradient with an amber corner glow."""
    ys, xs = np.mgrid[0:OUT_H, 0:OUT_W].astype(np.float32)
    # diagonal ramp, 0 at top-left -> 1 at bottom-right
    t = (xs / OUT_W * 0.55 + ys / OUT_H * 0.45)
    t = np.clip(t, 0.0, 1.0)

    top = np.array([58, 96, 78], np.float32)      # deep forest
    bot = np.array([24, 40, 48], np.float32)      # teal charcoal
    rgb = top[None, None, :] * (1 - t)[..., None] + bot[None, None, :] * t[..., None]

    # amber glow behind the upper-left third, echoing the site's accent
    gx, gy = OUT_W * 0.22, OUT_H * 0.18
    d = np.sqrt((xs - gx) ** 2 + (ys - gy) ** 2) / (OUT_W * 0.62)
    glow = np.clip(1.0 - d, 0.0, 1.0) ** 2.2
    amber = np.array([196, 142, 62], np.float32)
    rgb += amber[None, None, :] * glow[..., None] * 0.55

    # vignette so the corners fall off and the eye stays centre-frame
    vx = (xs - OUT_W / 2) / (OUT_W / 2)
    vy = (ys - OUT_H / 2) / (OUT_H / 2)
    vig = np.clip(1.0 - 0.38 * (vx ** 2 + vy ** 2), 0.0, 1.0)
    rgb *= vig[..., None]

    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


def rounded_mask(w: int, h: int, r: int, supersample: int = 4) -> Image.Image:
    """Antialiased rounded-rect luma mask."""
    big = Image.new("L", (w * supersample, h * supersample), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, w * supersample - 1, h * supersample - 1),
        radius=r * supersample, fill=255,
    )
    return big.resize((w, h), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    bg = gradient_bg()
    mask = rounded_mask(CONTENT_W, CONTENT_H, CORNER_R)

    # bake the drop shadow into the backdrop
    shadow_layer = Image.new("L", (OUT_W, OUT_H), 0)
    shadow_layer.paste(mask, (CONTENT_X, CONTENT_Y + SHADOW_OFFSET_Y))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))

    shadow_arr = np.asarray(shadow_layer, np.float32) / 255.0 * SHADOW_ALPHA
    bg_arr = np.asarray(bg, np.float32)
    bg_arr *= (1.0 - shadow_arr)[..., None]

    # 2px light rim just outside the content edge — separates near-black content
    # from the backdrop the way Screen Studio's bezel does
    rim_pad = 2
    rim = rounded_mask(CONTENT_W + rim_pad * 2, CONTENT_H + rim_pad * 2,
                       CORNER_R + rim_pad)
    rim_layer = Image.new("L", (OUT_W, OUT_H), 0)
    rim_layer.paste(rim, (CONTENT_X - rim_pad, CONTENT_Y - rim_pad))
    rim_arr = np.asarray(rim_layer, np.float32) / 255.0
    rim_colour = np.array([236, 244, 240], np.float32)
    bg_arr = bg_arr * (1 - rim_arr * 0.30)[..., None] + \
        rim_colour[None, None, :] * (rim_arr * 0.30)[..., None]

    bg = Image.fromarray(np.clip(bg_arr, 0, 255).astype(np.uint8), "RGB")

    bg.save(ASSETS / "bg.png")
    mask.save(ASSETS / "mask.png")

    print(f"bg.png    {bg.size}")
    print(f"mask.png  {mask.size}  corner_r={CORNER_R}")
    print(f"content   {CONTENT_W}x{CONTENT_H} at ({CONTENT_X},{CONTENT_Y})")


if __name__ == "__main__":
    main()
