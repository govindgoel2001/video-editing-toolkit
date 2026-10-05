"""Per-segment look: the filter chains and the eased zoom program.

Three styles, because the three kinds of footage want different treatment:

  screen  the 1080p60 screen recording, dropped into the Screen Studio frame
          (rounded corners, rim light, drop shadow, gradient backdrop) with a
          scripted cursor-follow zoom on top
  cam     the 4K GoPro talking head, scaled to 1080p with a warm grade
  broll   the juggling clip — same scale, cooler/punchier grade, optional speed

Zoom is driven by keyframes rather than cursor tracking: the editor picks the
moments from the transcript, which lands on intent rather than on every stray
mouse twitch.
"""

from __future__ import annotations

# Frame geometry — must match make_frame_assets.py
OUT_W, OUT_H = 1920, 1080
CONTENT_W, CONTENT_H = 1568, 882
CONTENT_X, CONTENT_Y = 176, 116

# Corner face box, modelled on the second reference video: the camera lives in
# the bottom-left over the screen for the whole tutorial, and the edit cuts to
# full frame only when he turns and talks to the lens.
PIP_W, PIP_H = 460, 414
PIP_X, PIP_Y = 48, 610
PIP_R = 22
PIP_PAD = 40              # must match make_pip_assets.PAD

# Where his head sits in each 4K angle, as a crop box that lands head and
# shoulders in the face box. Same 1440x1296 size everywhere so the box never
# changes scale between angles; only the position differs.
FACE_CROPS = {}  # EDL face_crops: {source_key: [x, y, width, height]}

# Grades. The GoPro footage is shot in a dim room under warm tungsten, so the
# cam grade lifts shadows and adds contrast rather than adding more warmth.
#
# The grain gets taken out in time, not in space. `hqdn3d`'s last two numbers
# are the temporal ones: they average a pixel against where it was on the
# frames either side, which is exactly what sensor grain is and exactly what
# a face is not. The spatial numbers stay low. A spatial blur strong enough to
# even out skin also takes the beard, the cap weave and the catchlights with
# it, and the picture reads as a smudged lens rather than a clean one.
GRADE_CAM = (
    "hqdn3d=1.5:1.2:8:7,"
    "unsharp=5:5:0.30:5:5:0.0,"
    "eq=contrast=1.07:brightness=0.02:saturation=1.06,"
    "curves=r='0/0.012 0.5/0.52 1/1':b='0/0.0 0.5/0.48 1/0.985'"
)
GRADE_BROLL = (
    "eq=contrast=1.14:brightness=0.03:saturation=1.12,"
    "unsharp=5:5:0.6:5:5:0.0"
)
GRADE_SCREEN = "eq=contrast=1.04:saturation=1.03"


def _ease(p: str) -> str:
    """Cubic ease-in-out on a normalised progress expression `p` in [0,1].

    Linear easing reads as robotic on a zoom; cubic is the one thing that makes
    a scripted move feel like a camera operator rather than a keyframe.
    """
    return f"if(lt({p},0.5),4*pow({p},3),1-pow(-2*({p})+2,3)/2)"


def piecewise(keys: list[tuple[float, float]]) -> str:
    """ffmpeg expression interpolating `keys` [(t, value), ...] with cubic ease.

    Holds the first value before the first key and the last value after the
    last key. Keys must be sorted by t.
    """
    if not keys:
        return "1"
    if len(keys) == 1:
        return f"{keys[0][1]:.6f}"

    expr = f"{keys[-1][1]:.6f}"          # value after the final key
    for (t0, v0), (t1, v1) in reversed(list(zip(keys, keys[1:]))):
        span = max(t1 - t0, 1e-6)
        p = f"((t-{t0:.4f})/{span:.6f})"
        seg = f"({v0:.6f}+({v1 - v0:.6f})*({_ease(p)}))"
        expr = f"if(lt(t,{t1:.4f}),{seg},{expr})"
    expr = f"if(lt(t,{keys[0][0]:.4f}),{keys[0][1]:.6f},{expr})"
    return expr


def zoom_keys(zooms: list[dict], seg_dur: float) -> tuple[list, list, list]:
    """Turn a segment's zoom list into (z, fx, fy) keyframe tracks.

    Each zoom is {"at": t, "to": z, "fx": 0..1, "fy": 0..1, "dur": ramp,
    "hold": seconds at target}. fx/fy are the focus point in normalised source
    coordinates: the point that stays put as the frame tightens around it.
    Between zooms the frame eases back to full view.
    """
    z_keys: list[tuple[float, float]] = [(0.0, 1.0)]
    fx_keys: list[tuple[float, float]] = [(0.0, 0.5)]
    fy_keys: list[tuple[float, float]] = [(0.0, 0.5)]

    for zm in sorted(zooms, key=lambda d: d["at"]):
        at = float(zm["at"])
        ramp = float(zm.get("dur", 1.0))
        hold = float(zm.get("hold", 2.0))
        z = float(zm.get("to", 1.4))
        fx = float(zm.get("fx", 0.5))
        fy = float(zm.get("fy", 0.5))

        # pan the focus point during the ramp, not before it
        fx_keys.append((at, fx_keys[-1][1]))
        fy_keys.append((at, fy_keys[-1][1]))

        z_keys.append((at, z_keys[-1][1]))
        z_keys.append((at + ramp, z))
        fx_keys.append((at + ramp, fx))
        fy_keys.append((at + ramp, fy))

        out_at = at + ramp + hold
        if out_at + 0.6 < seg_dur:
            z_keys.append((out_at, z))
            z_keys.append((out_at + 0.6, 1.0))
            fx_keys.append((out_at, fx))
            fx_keys.append((out_at + 0.6, 0.5))
            fy_keys.append((out_at, fy))
            fy_keys.append((out_at + 0.6, 0.5))

    return z_keys, fx_keys, fy_keys


FPS = 30


def src_to_out(t_src: float, cuts: list[tuple[float, float]]) -> float:
    """Map a time in the source segment to its time after the silences are cut.

    Lets the EDL name zoom moments in source time — the timebase you actually
    read off the transcript — while the filter graph runs in output time.
    """
    if not cuts:
        return t_src
    # Whole frames, matching build.select_filters exactly. Summing the spans as
    # floats drifts against the render: each span is rounded to a frame boundary
    # there, and across a dozen spans that reached 95 ms by the end of the repos
    # section, which is enough to walk a chip off the word it belongs to.
    n = 0
    for a, b in cuts:
        i0 = int(round(a * FPS))
        i1 = int(round(b * FPS)) - 1
        if t_src < b:
            return (n + max(0, int(round(t_src * FPS)) - i0)) / FPS
        n += i1 - i0 + 1
    return n / FPS


def screen_filtergraph(zooms: list[dict], seg_dur: float, fps: int = 30,
                       pre: str = "") -> str:
    """Full filter_complex for one framed screen-recording segment.

    Inputs must be wired as: [0]=source segment, [1]=bg.png, [2]=mask.png.
    `pre` is prepended to the video chain (the silence select, if any), so
    every downstream `t` is output time.
    Output label is [v].
    """
    z_keys, fx_keys, fy_keys = zoom_keys(zooms, seg_dur)
    z = piecewise(z_keys)
    fx = piecewise(fx_keys)
    fy = piecewise(fy_keys)

    # round the scaled size to even pixels so the crop doesn't jitter by a line
    sw = f"round({OUT_W}*({z})/2)*2"
    sh = f"round({OUT_H}*({z})/2)*2"

    return (
        f"[0:v]{pre}fps={fps},{GRADE_SCREEN},format=rgba,"
        f"scale=w='{sw}':h='{sh}':eval=frame:flags=bicubic,"
        f"crop={OUT_W}:{OUT_H}:x='(iw-{OUT_W})*({fx})':y='(ih-{OUT_H})*({fy})',"
        f"scale={CONTENT_W}:{CONTENT_H}:flags=lanczos[content];"
        f"[content][2:v]alphamerge[rounded];"
        f"[1:v][rounded]overlay={CONTENT_X}:{CONTENT_Y}:format=auto,"
        f"format=yuv420p[v]"
    )


def cam_filter(fps: int = 30, style: str = "cam", pre: str = "",
               crop: tuple | list | None = None) -> str:
    """Single -vf chain for a 4K GoPro segment scaled to 1080p.

    `crop` is an optional (x, y, w, h) in source pixels, applied before the
    downscale. The GoPro is very wide and he sits left of centre, so a
    full-frame cut without one puts him small in a lot of empty ceiling.
    """
    grade = GRADE_BROLL if style == "broll" else GRADE_CAM
    cut = f"crop={int(crop[2])}:{int(crop[3])}:{int(crop[0])}:{int(crop[1])}," if crop else ""
    return (f"fps={fps},{pre}{cut}scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase:flags=lanczos,crop={OUT_W}:{OUT_H},"
            f"{grade},format=yuv420p")

def zoom_chain(zooms: list[dict], seg_dur: float, fps: int, pre: str) -> str:
    """Screen chain at full frame: grade, then the eased punch-in."""
    z_keys, fx_keys, fy_keys = zoom_keys(zooms, seg_dur)
    z, fx, fy = piecewise(z_keys), piecewise(fx_keys), piecewise(fy_keys)
    sw = f"round({OUT_W}*({z})/2)*2"
    sh = f"round({OUT_H}*({z})/2)*2"
    # The offsets are written out of the same scale expression rather than
    # from crop's `iw`/`ih`. crop resolves those once, when the graph is
    # configured and the zoom is still 1.0, so `(iw-OUT_W)` is frozen at zero
    # and every focus point silently collapses to the top-left corner. The
    # picture still zooms, which is why it looks like it works.
    return (
        f"[0:v]fps={fps},{pre}{GRADE_SCREEN},"
        f"scale=w='{sw}':h='{sh}':eval=frame:flags=bicubic,"
        f"crop={OUT_W}:{OUT_H}:x='({sw}-{OUT_W})*({fx})':y='({sh}-{OUT_H})*({fy})'"
    )


def screen_full_filtergraph(zooms: list[dict], seg_dur: float, fps: int = 30,
                            pre: str = "") -> str:
    """Screen recording full bleed, no face box. Input [0]=screen. Output [v]."""
    return f"{zoom_chain(zooms, seg_dur, fps, pre)},format=yuv420p[v]"


def pip_filtergraph(zooms: list[dict], seg_dur: float, cam_key: str,
                    fps: int = 30, pre_screen: str = "",
                    pre_cam: str = "") -> str:
    """Screen full bleed with the camera in the corner.

    Inputs: [0]=screen segment, [1]=camera segment, [2]=pip_mask.png,
    [3]=pip_plate.png. Both media inputs get the same silence select, so the
    two angles stay locked to each other. Output label is [v].
    """
    box = FACE_CROPS.get(cam_key)
    if box:
        cx, cy, cw, ch = box
        face_crop = f"crop={cw}:{ch}:{cx}:{cy}"
    else:
        face_crop = f"crop=w='floor(min(iw,ih*{PIP_W}/{PIP_H})/2)*2':h='floor(min(ih,iw*{PIP_H}/{PIP_W})/2)*2'"
    px, py = PIP_X - PIP_PAD, PIP_Y - PIP_PAD
    return (
        f"{zoom_chain(zooms, seg_dur, fps, pre_screen)}[scr];"
        f"[1:v]fps={fps},{pre_cam}{face_crop},"
        f"scale={PIP_W}:{PIP_H}:flags=lanczos,{GRADE_CAM},format=rgba[face];"
        f"[face][2:v]alphamerge[faceR];"
        f"[scr][3:v]overlay={px}:{py}:format=auto[plated];"
        f"[plated][faceR]overlay={PIP_X}:{PIP_Y}:format=auto,"
        f"format=yuv420p[v]"
    )
