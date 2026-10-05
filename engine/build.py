"""Assemble the cut from edl.json.

Pipeline, in the order video-use's hard rules demand:

    per-segment extract (style + silence cut + grade + 30ms audio fades)
      -> lossless concat
      -> one composite encode: overlays, then graphics, then subtitles LAST
         inside the same filter graph, so a burned caption is never covered
         and the whole cut is only encoded once more
      -> loudnorm

Segment extraction is where this differs from stock render.py: the screen
recording needs a multi-input filter_complex (backdrop + rounded mask) that a
single -vf chain can't express, so extraction branches on the range's `style`.

    python edit/build.py edit/edl.json -o edit/final.mp4
    python edit/build.py edit/edl.json -o edit/preview.mp4 --draft
"""

from __future__ import annotations

import argparse
import hashlib
import os
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from silences import keep_ranges  # noqa: E402
from styles import (OUT_H, OUT_W, PIP_W, PIP_X, cam_filter,  # noqa: E402
                    pip_filtergraph,
                    screen_full_filtergraph, src_to_out)

from config import EDIT
ASSETS = EDIT / "assets"

from config import font_path, filter_path, load_edl
FONT_TITLE = filter_path(font_path(True))
FONT_BODY = filter_path(font_path(True))

ACCENT = "0xE0A94A"          # the site's amber
INK = "0xF2F6F3"

FPS = 30
SAMPLE_RATE = 48000


def run(cmd: list[str], what: str) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-12:]
        raise SystemExit(f"\nffmpeg failed during {what}:\n  " + "\n  ".join(tail))


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def esc(text: str) -> str:
    """Escape a string for use inside a drawtext= option value."""
    return (text.replace("\\", "\\\\").replace(":", "\\:")
                .replace("'", "’").replace("%", "\\%")
                .replace(",", "\\,").replace("[", "\\[").replace("]", "\\]"))


# -------- Segment extraction -------------------------------------------------


def audio_fades(duration: float) -> str:
    """30ms fades at both edges so cuts never pop (video-use hard rule 3)."""
    out_start = max(0.0, duration - 0.03)
    return f"afade=t=in:st=0:d=0.03,afade=t=out:st={out_start:.3f}:d=0.03"


LEVEL_TARGET = -20.0       # LUFS every segment is matched to before loudnorm
LEVEL_PEAK_CEIL = -1.5     # dBTP headroom kept when applying the gain
# The GoPro is further from his mouth and duller than the screen mic, and a
# dull distant voice reads quieter than a close one at the same LUFS. The cold
# open is aimed here instead, which is the same number plus a nudge.
LEVEL_TARGET_GOPRO = -18.6
LEVEL_CACHE = EDIT / "levels.json"


def _levels() -> dict:
    if LEVEL_CACHE.exists():
        return json.loads(LEVEL_CACHE.read_text(encoding="utf-8"))
    return {}


def match_gain(src: Path, start: float, dur: float, asel: str,
               speed: float = 1.0, pre: str = "",
               target: float | None = None) -> str:
    """A static `volume=` filter bringing this range to LEVEL_TARGET.

    The camera and the screen recording use different mics and sit about 7 dB
    apart, so every angle change stepped in level. A single loudnorm at the end
    cannot fix that, it normalises the whole file. Measured once per range with
    ebur128 and applied as a fixed gain, which moves the level without touching
    the dynamics the way a per-segment loudnorm would.

    `pre` is anything that runs ahead of this gain in the real chain, and it
    has to be measured through, not around. The intro's repair chain is a
    de-noiser, a corrective EQ that is negative across most of the speech
    band, a compressor and a limiter. Measuring the raw file and then applying
    the difference leaves everything that chain took out still missing, which
    is how the cold open ended up a good two dB under the rest of the video
    while the numbers said it matched.
    """
    digest = hashlib.md5((asel + "|" + pre).encode()).hexdigest()[:8]
    key = f"{src.resolve()}|{src.stat().st_mtime_ns}|{src.stat().st_size}|{start:.3f}|{dur:.3f}|{speed}|{digest}"
    cache = _levels()
    if key not in cache:
        chain = [f for f in (asel, f"atempo={speed}" if speed != 1.0 else "",
                             pre.rstrip(",")) if f]
        chain.append("ebur128=peak=true")
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-v", "info",
             "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
             "-vn", "-af", ",".join(chain), "-f", "null", "-"],
            capture_output=True, text=True,
        )
        log = proc.stderr
        tail = log[log.rfind("Summary:"):] if "Summary:" in log else log
        def grab(label: str) -> float | None:
            m = re.search(rf"{label}:\s*(-?\d+(?:\.\d+)?)", tail)
            return float(m.group(1)) if m else None
        integrated, peak = grab("I"), grab("Peak")
        if integrated is None:
            print(f"  level: no reading for {src.name} @{start:.1f}, left alone")
            integrated, peak = LEVEL_TARGET, LEVEL_PEAK_CEIL
        cache[key] = {"i": integrated, "peak": peak if peak is not None else 0.0}
        LEVEL_CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    m = cache[key]
    gain = (LEVEL_TARGET if target is None else target) - m["i"]
    gain = max(-12.0, min(12.0, gain))
    room = LEVEL_PEAK_CEIL - m["peak"]
    if gain > room:
        gain = room
    if abs(gain) < 0.2:
        return ""
    print(f"  level: {src.name} @{start:.1f} is {m['i']:.1f} LUFS, {gain:+.1f} dB")
    return f"volume={gain:.2f}dB,"


PLAUSIBLE_WORD = 0.45   # above this the transcript timing is not real

_WORDS_CACHE: dict[str, list[tuple[float, float]]] = {}


def spoken_words(source_key: str) -> list[tuple[float, float]]:
    """(start, end) of every word in a source, from its transcript."""
    if source_key not in _WORDS_CACHE:
        tr = EDIT / "transcripts" / f"{source_key}.json"
        if not tr.exists():
            _WORDS_CACHE[source_key] = []
        else:
            data = json.loads(tr.read_text(encoding="utf-8"))
            _WORDS_CACHE[source_key] = [
                (float(w["start"]), float(w["end"])) for w in data["words"]
                if w.get("type") == "word"
            ]
    return _WORDS_CACHE[source_key]


def cuttable(spans: list[tuple[float, float]],
             words: list[tuple[float, float]],
             guard: float = 0.05) -> list[tuple[float, float]]:
    """Silence that is safe to remove: the waveform's gaps minus every word.

    The waveform silence map and the transcript disagree by a few tens of
    milliseconds, and cutting on the waveform alone takes the head or tail off
    a word, which is what being talked over sounds like. Subtracting the words
    outright means a cut can never land inside one; it is not a tolerance that
    has to be tuned.
    """
    # faster-whisper inflates word durations badly here: the median "word"
    # runs 740 ms and the 95th percentile 2.4 s, so a single word often spans a
    # real pause. Subtracting those would put the dead air straight back.
    # Only plausibly-short words, whose bounds are trustworthy, are protected.
    words = [(a, b) for a, b in words if b - a <= PLAUSIBLE_WORD]
    if not words:
        return spans

    out: list[tuple[float, float]] = []
    for a0, b0 in spans:
        pieces = [(a0, b0)]
        for ws, we in words:
            if we <= a0 or ws >= b0:
                continue
            ws, we = ws - guard, we + guard
            nxt = []
            for x, y in pieces:
                if we <= x or ws >= y:
                    nxt.append((x, y))
                    continue
                if ws > x:
                    nxt.append((x, min(ws, y)))
                if we < y:
                    nxt.append((max(we, x), y))
            pieces = nxt
        out.extend((x, y) for x, y in pieces if y > x)
    return sorted(out)


def subtract_drops(ranges: list[tuple[float, float]], drops, start: float,
                   end: float) -> list[tuple[float, float]]:
    """Take stutters and false starts out of a range's keep list.

    `drops` are (from, to) in source time, the timebase read off the
    transcript; `ranges` are relative to `start`, as silence_cuts returns them.
    With no silence map the whole range is the one keep span.
    """
    if not drops:
        return ranges
    out = list(ranges) or [(0.0, end - start)]
    for a, b in drops:
        a, b = float(a) - start, float(b) - start
        nxt = []
        for x, y in out:
            if b <= x or a >= y:
                nxt.append((x, y))
                continue
            if a > x:
                nxt.append((x, a))
            if b < y:
                nxt.append((b, y))
        out = nxt
    # a sliver shorter than two frames is a click, not speech
    out = [(x, y) for x, y in out if y - x >= 0.07]
    if not out:
        raise ValueError('Drops remove the entire range; remove that range from the EDL instead.')
    return out


def silence_cuts(source_key: str, start: float, end: float,
                 keep: float = 0.16, drops=None) -> list[tuple[float, float]]:
    """Keep-ranges inside [start, end), relative to `start`, with dead air gone.

    Uses the cached waveform silence map, so this is the real dead air rather
    than gaps guessed from word timings.
    """
    cache_path = EDIT / "silences.json"
    if not cache_path.exists():
        return subtract_drops([], drops, start, end)
    cache = json.loads(cache_path.read_text())
    entry = cache.get(source_key)
    if not entry:
        return subtract_drops([], drops, start, end)

    spans = [(float(a), float(b)) for a, b in entry["spans"]]
    spans = cuttable(spans, spoken_words(source_key))
    ranges = keep_ranges(spans, float(entry["duration"]), keep, start, end)
    ranges = [(max(a, start), min(b, end)) for a, b in ranges if b > start and a < end]
    ranges = [(a - start, b - start) for a, b in ranges if b > a]
    return subtract_drops(ranges, drops, start, end)


def select_filters(cuts: list[tuple[float, float]]) -> tuple[str, str]:
    """(video select, audio select) filters keeping only `cuts`.

    One encode for the whole section instead of one per surviving fragment.
    Every cut lands inside a silence with a breath left on each side, so the
    joins are inaudible without per-fragment fades.
    """
    n = SAMPLE_RATE // FPS
    grid = (f"asetpts=PTS-STARTPTS,aresample={SAMPLE_RATE},"
            f"asetnsamples=n={n}:p=1")
    if not cuts:
        return "", f"{grid},asetpts=N/SR/TB"

    # Select by frame INDEX, not by timestamp.
    #
    # `select` and `aselect` each decide per frame, and after an input seek the
    # two streams do not start at exactly the same instant, so a boundary that
    # falls near a frame edge can round one way for video and the other way for
    # audio. Every such disagreement costs one frame, they accumulate over
    # hundreds of cuts, and the result is audio that runs progressively short
    # against the picture and tears at the joins.
    #
    # Upstream of this the video is forced to a constant FPS and the audio is
    # cut into frames of exactly SAMPLE_RATE/FPS samples, so frame n means the
    # same instant in both. Selecting the same integer n on both streams keeps
    # exactly the same set, and the output is always FPS frames of video per
    # SAMPLE_RATE samples of audio.
    spans = []
    for a_t, b_t in cuts:
        i0 = int(round(a_t * FPS))
        i1 = int(round(b_t * FPS)) - 1
        if i1 >= i0 >= 0:
            spans.append((i0, i1))
    if not spans:
        return "", ""

    expr = "+".join(f"between(n,{i0},{i1})" for i0, i1 in spans)
    return (f"setpts=PTS-STARTPTS,select='{expr}',setpts=N/FRAME_RATE/TB",
            f"{grid},aselect='{expr}',asetpts=N/SR/TB")


def frame_count(cuts: list[tuple[float, float]], dur: float,
                speed: float = 1.0) -> int:
    """How many output frames this segment must hold.

    Pinned with -frames:v so the picture cannot come out one frame longer than
    the sound. Mirrors exactly what select_filters keeps.
    """
    if cuts:
        n = sum(int(round(b * FPS)) - int(round(a * FPS)) for a, b in cuts)
    else:
        n = int(dur * FPS)
    return max(1, int(round(n / speed)))


def aligned_audio(chain: str, frames: int) -> str:
    """Finish even atempo output on the same integer frame/sample grid."""
    samples = frames * (SAMPLE_RATE // FPS)
    return (f"{chain},apad,atrim=end_sample={samples},"
            f"asetnsamples=n={SAMPLE_RATE // FPS}:p=0,asetpts=N/SR/TB")


def quality(draft: bool) -> list[str]:
    if draft:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "19"]


# The GoPro mic is 20 dB noisier than the screen mic and loses ~25 dB above
# 8 kHz, so a straight cut between them sounds like a different room. Where the
# screen recording covers the moment we borrow its audio instead; this chain is
# only for the intro, which it never covered.
#
# The curve is measured rather than guessed. Both mics were banded on the same
# speech, normalised to 640-1200 Hz, and the difference between them is what
# `GOPRO_CURVE` inverts: cut the 80-320 Hz box, leave the 2-4 kHz alone instead
# of boosting it, and rebuild the top two octaves. It stops at 16 kHz on
# purpose. Past that there is nothing on the tape but hiss, and lifting it
# just makes the hiss louder. Result is within 2.6 dB of the screen mic from
# 80 Hz to 11 kHz, with a noise floor 1.4 dB below the old chain.
GOPRO_CURVE = (
    # Video three, measured on 300 s of the same speech on both mics
    # (screen 100-400 against GX010247 94.1-394.1), banded and normalised to
    # 640-1200 Hz. The GoPro is 8 dB boomy under 140 Hz and loses 10 to 20 dB
    # from 3.6 kHz up, with nothing at all past 14 kHz, so the lift stops there.
    # The first pass lifted 4.3 kHz by 7 dB and landed 6 dB hotter than the
    # screen mic in that band, which is where harshness lives; it is now +2.
    "entry(0,-12);entry(60,-10);entry(95,-8);entry(134,-7);entry(190,-5);entry(269,-3);entry(381,-2);entry(538,0);entry(761,0);entry(1076,-1);entry(1522,0);entry(2152,1.5);entry(3044,2);entry(4305,2);entry(6089,5);entry(8611,10);entry(12000,8);entry(15000,0);entry(24000,-8)"
)
GOPRO_REPAIR = (
    "highpass=f=80,"
    "afftdn=nr=12:nf=-50:tn=1,"
    f"firequalizer=gain_entry='{GOPRO_CURVE}':gain='gain_interpolate(f)',"
    "deesser=i=0.3,"
    "acompressor=threshold=-24dB:ratio=3:attack=6:release=170,"
    "alimiter=limit=0.94"
)


def graph_arg(graph: str, tag: str) -> list[str]:
    """Pass the filtergraph as a file, not as an argument.

    The zoom tracks are piecewise ffmpeg expressions, and a segment carrying
    several of them builds a graph tens of thousands of characters long. That
    is past the Windows command-line limit, and the failure surfaces as
    WinError 206 from CreateProcess rather than anything ffmpeg says.
    """
    path = EDIT / f"_graph_{tag}.txt"
    path.write_text(graph, encoding="utf-8")
    return ["-filter_complex_script", str(path)]


def redact_chain(boxes: list[dict], seg_start: float) -> str:
    """Solid boxes over regions that must not be published, in source time.

    Prepended ahead of the silence select so `t` is the segment's own source
    timeline — the timebase the box was measured in — rather than output time,
    which the cuts would have shifted. A filled box, not a blur: a blur of
    large on-screen text can still be read back, and these are credentials.
    """
    parts = []
    for b in boxes:
        a = float(b["from"]) - seg_start
        z = float(b["to"]) - seg_start
        parts.append(
            f"drawbox=x={int(b['x'])}:y={int(b['y'])}:"
            f"w={int(b['w'])}:h={int(b['h'])}:"
            f"color={b.get('color', 'black')}:t=fill:"
            f"enable='between(t,{a:.3f},{z:.3f})'"
        )
    return ",".join(parts) + "," if parts else ""


def mute_chain(windows: list[list[float]] | None, seg_start: float) -> str:
    """Silence spans of the source, for a word that gets bleeped.

    Runs ahead of the silence select, so `t` is the segment's own source
    timeline, the same timebase `redact_chain` uses.
    """
    parts = [f"volume=0:enable='between(t,{float(a) - seg_start:.3f},{float(b) - seg_start:.3f})'"
             for a, b in (windows or [])]
    return ",".join(parts) + "," if parts else ""


def extract_pip(screen: Path, cam: Path, start: float, cam_start: float,
                dur: float, zooms: list[dict], cam_key: str, out: Path,
                draft: bool, cuts: list[tuple[float, float]] | None = None,
                seg_start: float = 0.0, redact: list[dict] | None = None,
                mute: list | None = None) -> None:
    """Screen full bleed with the face box in the corner, both angles locked.

    The same select expression runs on both streams. They are two views of one
    synchronised take, so identical cuts keep them frame-locked through the
    silence removal; audio always comes from the screen recording.
    """
    vsel, asel = select_filters(cuts or [])
    out_dur = sum(b - a for a, b in cuts) if cuts else dur
    zooms = [{**z, "at": src_to_out(max(0.0, float(z["at"]) - seg_start), cuts or [])}
             for z in zooms]

    pre = f"{vsel}," if vsel else ""
    graph = pip_filtergraph(zooms, out_dur, cam_key, fps=FPS,
                            pre_screen=redact_chain(redact or [], seg_start) + pre,
                            pre_cam=pre)
    af = mute_chain(mute, seg_start) + (f"{asel}," if asel else "")
    af = aligned_audio(f"{af}{match_gain(screen, start, dur, asel)}{audio_fades(out_dur)}",
                       frame_count(cuts or [], dur))

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(screen),
        "-ss", f"{cam_start:.3f}", "-t", f"{dur:.3f}", "-i", str(cam),
        "-i", str(ASSETS / "pip_mask.png"),
        "-i", str(ASSETS / "pip_plate.png"),
        *graph_arg(graph, out.stem),
        "-map", "[v]", "-map", "0:a:0",
        "-af", af,
        *quality(draft),
        "-frames:v", str(frame_count(cuts or [], dur)),
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        # PCM, not AAC: an AAC clip carries encoder priming at its head,
        # and seventeen of those stacked through the concat walk the sound
        # off the picture. PCM concatenates sample for sample.
        "-c:a", "pcm_s16le", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-movflags", "+faststart", str(out),
    ]
    run(cmd, f"pip segment {out.name}")


def extract_screen(src: Path, start: float, dur: float, zooms: list[dict],
                   out: Path, draft: bool,
                   cuts: list[tuple[float, float]] | None = None,
                   seg_start: float = 0.0, redact: list[dict] | None = None,
                   mute: list | None = None) -> None:
    """Screen recording with no face box, for the stretch the camera missed."""
    vsel, asel = select_filters(cuts or [])
    out_dur = sum(b - a for a, b in cuts) if cuts else dur
    zooms = [{**z, "at": src_to_out(max(0.0, float(z["at"]) - seg_start), cuts or [])}
             for z in zooms]

    graph = screen_full_filtergraph(
        zooms, out_dur, fps=FPS,
        pre=redact_chain(redact or [], seg_start) + (f"{vsel}," if vsel else ""))
    af = mute_chain(mute, seg_start) + (f"{asel}," if asel else "")
    af = aligned_audio(f"{af}{match_gain(src, start, dur, asel)}{audio_fades(out_dur)}",
                       frame_count(cuts or [], dur))
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
        *graph_arg(graph, out.stem),
        "-map", "[v]", "-map", "0:a:0",
        "-af", af,
        *quality(draft),
        "-frames:v", str(frame_count(cuts or [], dur)),
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        # PCM, not AAC: an AAC clip carries encoder priming at its head,
        # and seventeen of those stacked through the concat walk the sound
        # off the picture. PCM concatenates sample for sample.
        "-c:a", "pcm_s16le", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-movflags", "+faststart", str(out),
    ]
    run(cmd, f"screen segment {out.name}")


def extract_cam(src: Path, start: float, dur: float, style: str,
                out: Path, draft: bool, speed: float = 1.0,
                cuts: list[tuple[float, float]] | None = None,
                audio: tuple[Path, float] | None = None,
                crop: tuple | list | None = None) -> None:
    """Full-frame camera. `audio` borrows the screen mic for the same moment."""
    vsel, asel = select_filters(cuts or [])
    out_dur = (sum(b - a for a, b in cuts) if cuts else dur) / speed

    vf = cam_filter(fps=FPS, style=style,
                    pre=f"{vsel}," if vsel else "", crop=crop)
    if speed != 1.0:
        # Select source frames before retiming, then restore constant output fps.
        vf += f",setpts=PTS/{speed},fps={FPS}"

    ains = []
    if audio is not None:
        apath, astart = audio
        ains = ["-ss", f"{astart:.3f}", "-t", f"{dur:.3f}", "-i", str(apath)]
        amap, gain_src, gain_start = "1:a:0", apath, astart
        repair = ""
    else:
        amap, gain_src, gain_start = "0:a:0", src, start
        repair = f"{GOPRO_REPAIR}," if os.environ.get("VIDEO_GOPRO_REPAIR") == "1" else ""

    af = f"{asel}," if asel else ""
    if speed != 1.0:
        af = f"{af}atempo={speed},"
    af = (f"{af}{repair}"
          f"{match_gain(gain_src, gain_start, dur, asel, speed, pre=repair, target=(LEVEL_TARGET_GOPRO if repair else None))}"
          f"{audio_fades(out_dur)}")
    af = aligned_audio(af, frame_count(cuts or [], dur, speed))

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
        *ains,
        "-map", "0:v:0", "-map", amap,
        "-vf", vf, "-af", af,
        *quality(draft),
        "-frames:v", str(frame_count(cuts or [], dur, speed)),
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        # PCM, not AAC: an AAC clip carries encoder priming at its head,
        # and seventeen of those stacked through the concat walk the sound
        # off the picture. PCM concatenates sample for sample.
        "-c:a", "pcm_s16le", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-movflags", "+faststart", str(out),
    ]
    run(cmd, f"{style} segment {out.name}")


def segment_audio(r: dict, sync: dict, screen: Path,
                  screen_dur: float) -> tuple[str, float, tuple | None]:
    """Decide which microphone a range uses.

    Every angle is one synchronised take, so a camera shot that falls inside
    the screen recording's span can borrow the good mic. Returns the audio
    source key, its start time in that source, and the (path, start) to feed
    ffmpeg as a second input when the audio is borrowed.
    """
    style = r.get("style", "cam")
    start = float(r["start"])
    dur = float(r["end"]) - start
    key = screen.stem                      # caches are keyed by file stem
    if style == "screen":
        return key, start, None
    offset = sync.get(r["source"])
    if style != "broll" and offset is not None:
        screen_t = start + offset
        if screen_t >= 0 and screen_t + dur <= screen_dur:
            return key, screen_t, (screen, screen_t)
    return r.get("audio_key", r["source"]), start, None

def range_cuts(r: dict, audio_key: str, audio_start: float) -> list[tuple[float, float]]:
    """Keep source-time drops in sync when borrowing another microphone."""
    start, end = float(r['start']), float(r['end'])
    shift = audio_start - start
    drops = [[float(a)+shift, float(b)+shift] for a,b in r.get('drops', [])]
    if r.get('cut_silence', r.get('style', 'cam') != 'broll'):
        return silence_cuts(audio_key, audio_start, audio_start+end-start,
                            keep=float(r.get('keep_silence', .16)), drops=drops)
    return subtract_drops([], drops, audio_start, audio_start+end-start)


def probe_dur(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return float(out.strip() or 0.0)


def usable(path: Path, want: float, tol: float = 0.5) -> bool:
    """A clip counts as done only if ffprobe can read it and it is the right
    length. Existence is not enough: a run killed mid-write leaves a file with
    no moov atom, and the concat demuxer stops dead at it and silently drops
    every segment that follows."""
    if not path.exists():
        return False
    try:
        return abs(probe_dur(path) - want) <= tol
    except (ValueError, OSError):
        return False


def extract_all(edl: dict, draft: bool) -> tuple[list[Path], list[float], list]:
    """Extract every range; return the segment paths and their output offsets."""
    clips = EDIT / ("clips_draft" if draft else "clips")
    clips.mkdir(parents=True, exist_ok=True)

    from styles import FACE_CROPS
    FACE_CROPS.clear()
    FACE_CROPS.update(edl.get("face_crops", {}))
    sync = edl.get("sync", {})
    screen = Path(edl["sources"]["screen"])
    screen_dur = probe_dur(screen)

    paths: list[Path] = []
    offsets: list[float] = []
    seg_cuts: list = []
    t = 0.0

    for i, r in enumerate(edl["ranges"]):
        src = Path(edl["sources"][r["source"]])
        start, end = float(r["start"]), float(r["end"])
        dur = end - start
        style = r.get("style", "cam")
        speed = float(r.get("speed", 1.0))
        out = clips / f"seg_{i:03d}.mov"

        # Which microphone this shot will actually use. Every angle is the same
        # take, so a camera shot inside the screen recording's span can borrow
        # the good mic; only the intro, juggling and outro cannot.
        audio_key, audio_start, borrow = segment_audio(
            r, sync, screen, screen_dur)

        cuts = range_cuts(r, audio_key, audio_start)

        out_dur = frame_count(cuts, dur, speed) / FPS
        face = r.get("face")
        label = "pip" if (style == "screen" and face) else style
        mic = "screen-mic" if audio_key == screen.stem else "gopro-mic"
        saved = f"  -{dur - out_dur:.1f}s" if cuts else ""
        print(f"  [{i:03d}] {label:6s} {r['source']:14s} "
              f"{start:7.2f}->{end:7.2f}  {out_dur:5.2f}s{saved:8s} "
              f"{mic:10s} {r.get('beat', '')}")

        signature_data = [edl, r, cuts, draft,
                          [(v, Path(v).stat().st_size, Path(v).stat().st_mtime_ns)
                           for v in edl['sources'].values()],
                          Path(__file__).read_text(),
                          (Path(__file__).parent/'styles.py').read_text(),
                          os.environ.get('VIDEO_GOPRO_REPAIR','0')]
        signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
        receipt = out.with_suffix('.cache.json')
        fresh = receipt.exists() and receipt.read_text() == signature
        if not fresh or not usable(out, out_dur):
            out.unlink(missing_ok=True)
            if style == "screen" and face:
                extract_pip(screen, Path(edl["sources"][face]), start,
                            start - sync[face], dur, r.get("zooms", []),
                            face, out, draft, cuts, seg_start=start,
                            redact=r.get("redact"), mute=r.get("mute"))
            elif style == "screen":
                extract_screen(src, start, dur, r.get("zooms", []), out,
                               draft, cuts, seg_start=start,
                               redact=r.get("redact"), mute=r.get("mute"))
            else:
                extract_cam(src, start, dur, style, out, draft, speed, cuts,
                            audio=borrow, crop=r.get("crop"))
            if not usable(out, out_dur):
                raise SystemExit(
                    f"\nsegment {i:03d} came out at {probe_dur(out):.2f}s, "
                    f"expected {out_dur:.2f}s")

            receipt.write_text(signature)

        paths.append(out)
        offsets.append(t)
        seg_cuts.append((start, cuts))
        t += out_dur

    return paths, offsets, seg_cuts


def concat(paths: list[Path], out: Path) -> None:
    listing = EDIT / "_concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in paths))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(out)],
        "concat")
    listing.unlink(missing_ok=True)
    want = sum(probe_dur(p) for p in paths)
    got = probe_dur(out)
    if abs(got - want) > 1.0:
        raise SystemExit(
            f"\nconcat lost footage: {got:.1f}s out of {want:.1f}s of clips. "
            "The demuxer stops at the first unreadable file and says nothing.")


# -------- Graphics -----------------------------------------------------------


def fade_alpha(t0: float, t1: float, fade: float = 0.25) -> str:
    """Alpha expression that fades a graphic in and out at its edges."""
    return (f"if(lt(t,{t0 + fade:.3f}),(t-{t0:.3f})/{fade},"
            f"if(lt(t,{t1 - fade:.3f}),1,({t1:.3f}-t)/{fade}))")


def title_filters(card: dict) -> list[str]:
    """A beat title: big condensed caps with a rule and an optional subtitle."""
    t0 = float(card["at"])
    t1 = t0 + float(card.get("dur", 2.6))
    en = f"between(t,{t0:.3f},{t1:.3f})"
    a = fade_alpha(t0, t1)
    # Sits above where the captions land, so the two never stack.
    y = int(card.get("y", 690))
    size = int(card.get("size", 64))
    slide = f"+{int(card.get('slide', 14))}*(1-min((t-{t0:.3f})/0.35,1))"

    # The screen recording underneath is busy text, so each line gets its own
    # dark box. Without it the subtitle line disappears into the page behind.
    scrim = "box=1:boxcolor=0x0A1410@0.62:boxborderw=14"

    # Clears the face box in the bottom-left and reads as a lower third beside
    # him rather than a caption floating over the page.
    bar_x = int(card.get("x", PIP_X + PIP_W + 48))
    txt_x = bar_x + 32

    parts = [
        f"drawbox=x={bar_x}:y={y - 18}:w=8:h={size + 14}:color={ACCENT}@0.95:t=fill:enable='{en}'",
        (f"drawtext=fontfile='{FONT_TITLE}':text='{esc(card['text'].upper())}'"
         f":fontcolor={INK}:fontsize={size}:x={txt_x}:y='{y}{slide}'"
         f":{scrim}:alpha='{a}':enable='{en}'"),
    ]
    if card.get("sub"):
        parts.append(
            f"drawtext=fontfile='{FONT_BODY}':text='{esc(card['sub'])}'"
            f":fontcolor={ACCENT}:fontsize={int(size * 0.42)}:x={txt_x + 2}"
            f":y='{y + size + 20}{slide}':{scrim}:alpha='{a}':enable='{en}'"
        )
    return parts


def callout_filters(card: dict) -> list[str]:
    """A box + label pinned over something on screen, in frame coordinates."""
    t0 = float(card["at"])
    t1 = t0 + float(card.get("dur", 2.5))
    en = f"between(t,{t0:.3f},{t1:.3f})"
    a = fade_alpha(t0, t1, 0.2)
    x, y = int(card["x"]), int(card["y"])
    w, h = int(card["w"]), int(card["h"])

    parts = [
        f"drawbox=x={x}:y={y}:w={w}:h={h}:color={ACCENT}@0.9:t=3:enable='{en}'",
    ]
    if card.get("label"):
        lh = 40
        ly = y - lh - 8 if y > 150 else y + h + 8
        parts += [
            f"drawbox=x={x}:y={ly}:w={min(len(card['label']) * 15 + 28, 620)}"
            f":h={lh}:color={ACCENT}@0.95:t=fill:enable='{en}'",
            (f"drawtext=fontfile='{FONT_BODY}':text='{esc(card['label'].upper())}'"
             f":fontcolor=0x10201A:fontsize=22:x={x + 14}:y={ly + 9}"
             f":alpha='{a}':enable='{en}'"),
        ]
    return parts


def prompt_filters(card: dict) -> list[str]:
    """A direct-address card — the 'tell me in the comments' beat."""
    t0 = float(card["at"])
    t1 = t0 + float(card.get("dur", 3.4))
    en = f"between(t,{t0:.3f},{t1:.3f})"
    a = fade_alpha(t0, t1, 0.3)
    slide = f"+{20}*(1-min((t-{t0:.3f})/0.4,1))"

    w, h = 760, 132
    x, y = OUT_W - w - 90, 120
    return [
        # The box is static and only the text slides. drawbox resolves its
        # geometry once, at configure time with t=0, so an expression in `y`
        # froze at a value hundreds of pixels off and the card never drew.
        f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0x0C1A14@0.90"
        f":t=fill:enable='{en}'",
        f"drawbox=x={x}:y={y}:w=7:h={h}:color={ACCENT}:t=fill:enable='{en}'",
        (f"drawtext=fontfile='{FONT_TITLE}':text='{esc(card['question'].upper())}'"
         f":fontcolor={INK}:fontsize=36:x={x + 30}:y='{y + 24}{slide}'"
         f":alpha='{a}':enable='{en}'"),
        (f"drawtext=fontfile='{FONT_BODY}':text='{esc(card.get('hint', 'drop it in the comments'))}'"
         f":fontcolor={ACCENT}:fontsize=24:x={x + 30}:y='{y + 80}{slide}'"
         f":alpha='{a}':enable='{en}'"),
    ]


def progress_bar(total: float) -> list[str]:
    """The unlit rail the progress line runs along.

    Only the rail is a drawbox. drawbox resolves x/y/w/h once, when the graph
    is configured and t is zero, so a growing width evaluates to zero and the
    line never appears. The lit part is an overlay instead, built by
    `progress_overlay`, because overlay does re-evaluate its position per
    frame.
    """
    return [
        f"drawbox=x=0:y={OUT_H - 5}:w={OUT_W}:h=5:color=0xFFFFFF@0.10:t=fill",
    ]


def progress_overlay(total: float) -> tuple[list[str], str]:
    """A full-width amber bar slid in from the left, revealing as it goes.

    The bar itself never changes size. It starts one screen width to the left
    and walks right, so the part of it inside the frame is exactly the part of
    the video already watched, and everything still to come is off the left
    edge where the frame clips it.
    """
    src = ["-f", "lavfi", "-i",
           f"color=c={ACCENT}@0.85:s={OUT_W}x5:r={FPS}:d={total + 1:.3f}"]
    x = f"{OUT_W}*(t/{total:.3f}-1)"
    # shortest=1, or overlay keeps emitting repeated frames of the last
    # picture until the colour source runs out and the cut grows a second.
    return src, f"overlay=x='{x}':y={OUT_H - 5}:format=auto:shortest=1"


def resolve_cards(cards: list[dict], offsets: list[float],
                  durations: list[float],
                  seg_cuts: list[tuple[float, list]] | None = None) -> list[dict]:
    """Turn segment-anchored cards into absolute output times.

    Two anchors are supported, and which one you want depends on the card:

      {"seg": 3, "offset": 0.4}  0.4s into segment 3, for beat titles that
                                 should land the moment the beat starts
      {"seg": 3, "src": 99.2}    at source time 99.2 inside segment 3, for
                                 anything cued to a spoken word — the time you
                                 read straight off the transcript

    Both beat absolute output times, which silence removal would otherwise
    invalidate on every retune.
    """
    seg_cuts = seg_cuts or []
    out: list[dict] = []
    for c in cards:
        c = dict(c)
        if "seg" not in c:
            out.append(c)
            continue

        i = int(c.pop("seg"))
        if not 0 <= i < len(offsets):
            continue

        if "src" in c:
            seg_start, cuts = (seg_cuts[i] if i < len(seg_cuts) else (0.0, []))
            local = src_to_out(max(0.0, float(c.pop("src")) - seg_start), cuts)
            c["at"] = offsets[i] + local
        else:
            c["at"] = offsets[i] + float(c.pop("offset", 0.4))

        seg_end = offsets[i] + durations[i]
        if c["at"] >= seg_end - 0.3:
            continue
        c["dur"] = min(float(c.get("dur", 2.6)), max(seg_end - c["at"], 0.6))
        out.append(c)
    return out


def chip_filters(card: dict) -> list[str]:
    """A labelled pill in the top-left of the framed content.

    Fixed position on purpose. A box drawn around a named UI element has to be
    re-measured every time a cut moves, and a box framing the wrong thing is
    worse than no box; a pill that names what he just said cannot misalign.
    """
    t0 = float(card["at"])
    t1 = t0 + float(card.get("dur", 3.0))
    en = f"between(t,{t0:.3f},{t1:.3f})"
    a = fade_alpha(t0, t1, 0.22)
    text = card["text"]

    x = int(card.get("x", 232))
    y = int(card.get("y", 168))
    slide = f"+{16}*(1-min((t-{t0:.3f})/0.3,1))"

    return [
        (f"drawtext=fontfile='{FONT_BODY}':text='{esc(text.upper())}'"
         f":fontcolor=0x0C1A14:fontsize=26:x='{x}{slide}':y={y}"
         f":box=1:boxcolor={ACCENT}@0.94:boxborderw=13"
         f":alpha='{a}':enable='{en}'"),
    ]


def countdown_filters(card: dict) -> list[str]:
    """A ten second clock in the top right, counting into the tutorial.

    `at` is the moment it hits zero, not the moment it appears, because the
    thing it is promising is the cut to the screen recording. It runs on the
    output clock, so a retune that moves that cut moves the clock with it.

    The number is an ffmpeg expansion rather than ten drawn cards: `ceil` of
    the time left reads 10 on the first frame and 1 on the last, which is how
    a clock counts, and it never drifts if the cut moves by a frame.
    """
    t1 = float(card["at"])
    t0 = t1 - float(card.get("len", 10.0))
    en = f"between(t,{t0:.3f},{t1:.3f})"
    a = fade_alpha(t0, t1, 0.3)

    w, h = 300, 118
    x, y = OUT_W - w - 56, 54
    inner = w - 48
    steps = max(1, int(round(t1 - t0)))

    left = f"{t1:.3f}-t"                     # seconds still to run
    num = f"%{{eif\\:ceil({left})\\:d}}"

    return [
        f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0x0C1A14@0.88:t=fill:enable='{en}'",
        f"drawbox=x={x}:y={y}:w=7:h={h}:color={ACCENT}:t=fill:enable='{en}'",
        (f"drawtext=fontfile='{FONT_BODY}'"
         f":text='{esc(card.get('label', 'tutorial starts in').upper())}'"
         f":fontcolor={ACCENT}:fontsize=21:x={x + 26}:y={y + 18}"
         f":alpha='{a}':enable='{en}'"),
        (f"drawtext=fontfile='{FONT_TITLE}':text='{num}'"
         f":fontcolor={INK}:fontsize=52:x={x + 26}:y={y + 46}"
         f":alpha='{a}':enable='{en}'"),
        # The bar empties as the clock runs, so the last two seconds read
        # without anyone having to find the digit. One box per second rather
        # than one box with a shrinking width: drawbox resolves its width once
        # at configure time, so an expression there would freeze on frame one.
        # Stepping also matches the digit, which counts whole seconds too.
        f"drawbox=x={x + 26}:y={y + h - 16}:w={inner}:h=4"
        f":color=0xFFFFFF@0.16:t=fill:enable='{en}'",
    ] + [
        f"drawbox=x={x + 26}:y={y + h - 16}:w={int(inner * i / steps)}:h=4"
        f":color={ACCENT}@0.9:t=fill"
        f":enable='between(t,{t1 - i:.3f},{t1 - i + 1:.3f})'"
        for i in range(1, steps + 1)
    ]


def graphics_pass(base: Path, edl: dict, total: float, out: Path,
                  draft: bool, offsets: list[float] | None = None,
                  durations: list[float] | None = None,
                  seg_cuts: list | None = None) -> None:
    offsets = offsets or []
    durations = durations or []
    seg_cuts = seg_cuts or []
    filters: list[str] = []
    for card in resolve_cards(edl.get("titles", []), offsets, durations, seg_cuts):
        filters += title_filters(card)
    for card in resolve_cards(edl.get("callouts", []), offsets, durations, seg_cuts):
        filters += callout_filters(card)
    for card in resolve_cards(edl.get("prompts", []), offsets, durations, seg_cuts):
        filters += prompt_filters(card)
    for card in resolve_cards(edl.get("chips", []), offsets, durations, seg_cuts):
        filters += chip_filters(card)
    for card in resolve_cards(edl.get("countdown", []), offsets, durations, seg_cuts):
        filters += countdown_filters(card)
    if edl.get("progress_bar", True):
        # Rail only. The moving part needs a second input, which this
        # single-input path cannot carry; `composite` is the one that ships.
        filters += progress_bar(total)

    if not filters:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(base), "-c", "copy", str(out)],
            "graphics passthrough")
        return

    run(["ffmpeg", "-y", "-v", "error", "-i", str(base),
         "-vf", ",".join(filters),
         *quality(draft), "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", str(out)],
        "graphics")


def overlay_pass(base: Path, overlays: list[dict], out: Path,
                 draft: bool) -> None:
    """Composite rendered animation clips over the cut.

    Runs before subtitles so a burned caption is never hidden behind an
    overlay (video-use hard rule 1). Each clip is PTS-shifted to its output
    time rather than trimmed, so its own easing stays intact.
    """
    if not overlays:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(base), "-c", "copy", str(out)],
            "overlay passthrough")
        return

    inputs: list[str] = ["-i", str(base)]
    for ov in overlays:
        inputs += ["-i", str(EDIT.parent / ov["file"]) if not Path(ov["file"]).is_absolute()
                   else ov["file"]]

    parts: list[str] = []
    for i, ov in enumerate(overlays, start=1):
        t = float(ov["at"])
        parts.append(f"[{i}:v]format=rgba,setpts=PTS-STARTPTS+{t:.3f}/TB[o{i}]")

    cur = "[0:v]"
    for i, ov in enumerate(overlays, start=1):
        t = float(ov["at"])
        end = t + float(ov.get("dur", 5.0))
        nxt = f"[v{i}]"
        parts.append(f"{cur}[o{i}]overlay=0:0:eof_action=pass"
                     f":enable='between(t,{t:.3f},{end:.3f})'{nxt}")
        cur = nxt

    run(["ffmpeg", "-y", "-v", "error", *inputs,
         "-filter_complex", ";".join(parts),
         "-map", cur, "-map", "0:a",
         *quality(draft), "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", str(out)],
        "overlays")


def subtitle_filter(srt: Path) -> str:
    style = ("FontName=Segoe UI,FontSize=17,Bold=1,"
             "PrimaryColour=&H00F3F6F2,OutlineColour=&H00101A14,"
             "BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV=12")
    path = srt.resolve().as_posix().replace(":", "\\:")
    return f"subtitles='{path}':force_style='{style}'"


# One sound per thing that moves, and nothing anywhere else. A whoosh under
# every card that flies in, a pop under every pill, a rise into the cut that
# starts the tutorial, and a single stinger on the portfolio reveal. Levels are
# Quiet and short. The first pass measured "correct" at about 12 dB under
# speech and he heard it as too loud and too long, so the whoosh lost half its
# length and everything came down another six. An effect you notice is an
# effect that is too loud; these are meant to be felt on the cut and forgotten.
SFX_FOR_OVERLAY = {"opener": ("whoosh", -20.0), "ch_result": ("stinger", -17.0),
                   "st_crash": ("whoosh_down", -18.0)}
# By name prefix, for the families that video four added: a face punch-in
# lands on a hit, a stat card pops, a stock cutaway swishes in.
SFX_FOR_PREFIX = {"punch_": ("impact", -17.0), "stat_": ("pop", -20.0),
                  "st_": ("whoosh", -21.0)}


def sfx_cues(edl: dict, offsets: list[float], durations: list[float],
             seg_cuts: list) -> list[tuple[float, str, float]]:
    """(output time, sample name, gain in dB) for every effect in the cut."""
    cues: list[tuple[float, str, float]] = []

    for ov in resolve_cards(edl.get("overlays", []), offsets, durations, seg_cuts):
        stem = Path(ov["file"]).stem
        name, gain = SFX_FOR_OVERLAY.get(stem) or next(
            (v for k, v in SFX_FOR_PREFIX.items() if stem.startswith(k)),
            ("whoosh", -20.0))
        # A whoosh reads as pushing the card on, so it starts just before it.
        lead = 0.10 if name == "whoosh" else 0.0
        cues.append((max(0.0, float(ov["at"]) - lead), name, gain))

    for chip in resolve_cards(edl.get("chips", []), offsets, durations, seg_cuts):
        cues.append((float(chip["at"]), "pop", -22.0))

    for cd in resolve_cards(edl.get("countdown", []), offsets, durations, seg_cuts):
        zero = float(cd["at"])
        cues.append((max(0.0, zero - 2.2), "riser", -22.0))   # riser is 2.2s
        cues.append((zero, "impact", -16.0))
        for n in (3, 2, 1):
            cues.append((zero - n, "click", -27.0))

    # Extra effects take the same seg/src anchors as cards, so a bleep stays
    # on its word however the silence cuts move.
    for extra in resolve_cards(edl.get("sfx", []), offsets, durations, seg_cuts):
        cues.append((float(extra["at"]), extra["name"],
                     float(extra.get("gain_db", -20.0))))

    return sorted(c for c in cues if c[0] >= 0.0)


def render_sfx_bed(cues: list[tuple[float, str, float]], total: float,
                   out: Path) -> bool:
    """Sum every effect into one stereo bed the length of the cut.

    One bed mixed once beats one ffmpeg input per effect: twenty-five extra
    inputs and an amix with twenty-six legs is slow to build and impossible to
    read when something lands in the wrong place.
    """
    if not cues:
        return False

    import numpy as np

    n = int(total * SAMPLE_RATE) + SAMPLE_RATE
    bed = np.zeros((n, 2), dtype=np.float32)
    cache: dict[str, "np.ndarray"] = {}

    for at, name, gain_db in cues:
        if name not in cache:
            path = EDIT / "sfx" / f"{name}.wav"
            if not path.exists():
                raise SystemExit(f"no sfx sample named {name} in {path.parent}")
            with wave.open(str(path)) as w:
                raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
                cache[name] = raw.reshape(-1, w.getnchannels())[:, :2].astype(
                    np.float32) / 32768.0
        clip = cache[name] * (10.0 ** (gain_db / 20.0))
        i = int(at * SAMPLE_RATE)
        j = min(i + len(clip), n)
        if j > i:
            bed[i:j] += clip[: j - i]

    peak = float(np.max(np.abs(bed)))
    if peak > 0.99:                       # only if two effects land together
        bed *= 0.99 / peak
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((bed * 32767.0).astype("<i2").tobytes())
    return True


def render_music_bed(edl: dict, total: float, offsets: list[float],
                     durations: list[float], seg_cuts: list, out: Path) -> bool:
    """One stereo music track the length of the cut, switching by section.

    Each cue in `music` starts a track at its anchor and runs until the next
    cue, with a crossfade across the change so a switch reads as a decision
    rather than a dropout. Ducking under the voice happens at the mix, keyed
    on the speech itself, so the bed only has to get the levels roughly right.
    """
    cues = resolve_cards(edl.get("music", []), offsets, durations, seg_cuts)
    if not cues:
        return False
    import numpy as np

    cues = sorted(cues, key=lambda c: float(c["at"]))
    n = int(total * SAMPLE_RATE) + SAMPLE_RATE
    bed = np.zeros((n, 2), dtype=np.float32)
    xf = 0.9
    for i, c in enumerate(cues):
        t0 = max(0.0, float(c["at"]) - (xf / 2 if i else 0.0))
        t1 = (float(cues[i + 1]["at"]) + xf / 2) if i + 1 < len(cues) else total
        length = t1 - t0
        f = Path(c["file"])
        f = f if f.is_absolute() else EDIT / f
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-stream_loop", "-1",
             "-ss", f"{float(c.get('from', 0.0)):.3f}", "-i", str(f),
             "-t", f"{length:.3f}", "-f", "f32le", "-ac", "2",
             "-ar", str(SAMPLE_RATE), "-"], capture_output=True).stdout
        x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()
        x *= 10.0 ** (float(c.get("gain_db", -24.0)) / 20.0)
        k = min(len(x), int(xf * SAMPLE_RATE))
        ramp = np.linspace(0.0, 1.0, k, dtype=np.float32)[:, None]
        if i:
            x[:k] *= ramp
        if i + 1 < len(cues) or True:
            x[-k:] *= ramp[::-1]
        a = int(t0 * SAMPLE_RATE)
        b = min(a + len(x), n)
        bed[a:b] += x[: b - a]
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((np.clip(bed, -1, 1) * 32767.0).astype("<i2").tobytes())
    return True


def composite(base: Path, edl: dict, total: float, srt: Path | None,
              out: Path, draft: bool, offsets: list[float],
              durations: list[float], seg_cuts: list) -> None:
    """Overlays, graphics and subtitles in one encode.

    Running these as three passes meant three generations of h.264 over the
    whole cut and three times the encode time. Order inside the graph still
    obeys video-use hard rule 1: overlays first, subtitles last, so a burned
    caption is never covered.
    """
    overlays = resolve_cards(edl.get("overlays", []), offsets, durations, seg_cuts)

    inputs: list[str] = ["-i", str(base)]
    for ov in overlays:
        f = Path(ov["file"])
        inputs += ["-i", str(f if f.is_absolute() else EDIT.parent / f)]

    parts: list[str] = []
    for i, ov in enumerate(overlays, start=1):
        parts.append(f"[{i}:v]format=rgba,"
                     f"setpts=PTS-STARTPTS+{float(ov['at']):.3f}/TB[o{i}]")

    cur = "[0:v]"
    for i, ov in enumerate(overlays, start=1):
        t = float(ov["at"])
        end = t + float(ov.get("dur", 5.0))
        nxt = f"[v{i}]"
        parts.append(f"{cur}[o{i}]overlay=0:0:eof_action=pass"
                     f":enable='between(t,{t:.3f},{end:.3f})'{nxt}")
        cur = nxt

    chain: list[str] = []
    for card in resolve_cards(edl.get("titles", []), offsets, durations, seg_cuts):
        chain += title_filters(card)
    for card in resolve_cards(edl.get("callouts", []), offsets, durations, seg_cuts):
        chain += callout_filters(card)
    for card in resolve_cards(edl.get("prompts", []), offsets, durations, seg_cuts):
        chain += prompt_filters(card)
    for card in resolve_cards(edl.get("chips", []), offsets, durations, seg_cuts):
        chain += chip_filters(card)
    for card in resolve_cards(edl.get("countdown", []), offsets, durations, seg_cuts):
        chain += countdown_filters(card)
    want_bar = edl.get("progress_bar", True)
    if want_bar:
        chain += progress_bar(total)

    if chain:
        parts.append(f"{cur}{','.join(chain)}[vg]")
        cur = "[vg]"

    if want_bar:
        # After the cards, so the line is never buried, and before the
        # subtitles, which always go last.
        src, filt = progress_overlay(total)
        idx = len([a for a in inputs if a == "-i"])
        inputs += src
        parts.append(f"{cur}[{idx}:v]{filt}[vb]")
        cur = "[vb]"

    if srt is not None and srt.exists():
        parts.append(f"{cur}{subtitle_filter(srt)}[vout]")
        cur = "[vout]"

    if not parts:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(base), "-c", "copy", str(out)],
            "composite passthrough")
        return

    run(["ffmpeg", "-y", "-v", "error", *inputs,
         *graph_arg(";".join(parts), "composite"),
         "-map", cur, "-map", "0:a",
         *quality(draft), "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", str(out)],
        "composite")


# -------- Entry point --------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("edl", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--draft", action="store_true",
                    help="fast, lower-quality pass for checking cut points")
    ap.add_argument("--no-subs", action="store_true")
    args = ap.parse_args()

    edl = load_edl(args.edl)
    work = EDIT / "work"
    work.mkdir(parents=True, exist_ok=True)

    print("extracting segments")
    paths, offsets, seg_cuts = extract_all(edl, args.draft)
    durations = [probe_duration(p) for p in paths]
    total = offsets[-1] + durations[-1] if paths else 0.0
    print(f"  {len(paths)} segments, {total / 60:.2f} min")

    base = work / "base.mov"
    print("concat")
    concat(paths, base)

    srt = None if args.no_subs else (EDIT / "master.srt")
    if srt is not None and not srt.exists():
        print(f"  no {srt.name}; rendering without captions")
        srt = None

    print("composite (overlays + graphics + subtitles, one pass)")
    staged = work / "composite.mov"
    composite(base, edl, total, srt, staged, args.draft,
              offsets, durations, seg_cuts)

    bed = work / "sfx.wav"
    cues = sfx_cues(edl, offsets, durations, seg_cuts)
    has_sfx = render_sfx_bed(cues, total, bed)
    print(f"sfx bed: {len(cues)} cues" if has_sfx else "sfx bed: none")

    print("loudnorm (two pass)")
    # Two pass, not one. Single pass loudnorm is a dynamic normaliser: riding
    # six dB of makeup across the whole cut, it would slowly undo the
    # per-segment matching done at extraction. Measuring first and applying
    # linear=true makes the final move one fixed gain.
    spec = "I=-14:TP=-1.5:LRA=11"
    # The effects are mixed in ahead of the measurement, not after it, so the
    # -14 LUFS and the -1.5 dBTP ceiling apply to what the viewer hears rather
    # than to the speech alone.
    music = work / "music.wav"
    has_music = render_music_bed(edl, total, offsets, durations, seg_cuts, music)
    print(f"music bed: {len(edl.get('music', []))} cues" if has_music else "music bed: none")
    ins = (["-i", str(staged)] + (["-i", str(bed)] if has_sfx else [])
           + (["-i", str(music)] if has_music else []))
    legs = ["[sp]"] + (["[1:a]"] if has_sfx else [])
    graph = "[0:a]asplit=2[sp][key];" if has_music else "[0:a]anull[sp];"
    if has_music:
        # The bed ducks under the voice, keyed on the speech itself, so it
        # swells in the pauses and gets out of the way when he talks.
        m = 2 if has_sfx else 1
        graph += (f"[{m}:a][key]sidechaincompress=threshold=0.02:ratio=5"
                  ":attack=20:release=450:makeup=1[duck];")
        legs.append("[duck]")
    graph += (f"{''.join(legs)}amix=inputs={len(legs)}:duration=first:normalize=0[mx];"
              if len(legs) > 1 else f"{legs[0]}anull[mx];")
    pre = graph + "[mx]"
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", *ins, "-vn",
         "-filter_complex", f"{pre}loudnorm={spec}:print_format=json[a]",
         "-map", "[a]", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    af = f"loudnorm={spec}"
    try:
        m = json.loads(probe[probe.rindex("{"): probe.rindex("}") + 1])
        af = (f"loudnorm={spec}:measured_I={m['input_i']}"
              f":measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
              f":measured_thresh={m['input_thresh']}"
              f":offset={m['target_offset']}:linear=true:print_format=summary")
        print(f"  measured {m['input_i']} LUFS, peak {m['input_tp']} dBTP")
    except (ValueError, KeyError):
        print("  measure pass gave no json, falling back to dynamic")

    run(["ffmpeg", "-y", "-v", "error", *ins,
         "-filter_complex", f"{pre}{af}[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(args.output)],
        "loudnorm")

    stem = args.output.with_name(args.output.stem + "_mix.wav")
    print(f"mix stem -> {stem.name}")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(args.output), "-vn",
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(stem)],
        "speech stem")

    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(args.output)],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"\n{args.output}  {float(dur) / 60:.2f} min")


if __name__ == "__main__":
    main()
