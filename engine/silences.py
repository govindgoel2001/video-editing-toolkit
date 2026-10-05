"""Find dead air from the waveform, not from the transcript.

faster-whisper's word timings drift by a few hundred ms and it happily reports
a 42-second phrase with no internal pause, so transcript gaps alone miss most
of the dead air. ffmpeg's silencedetect reads the actual samples and finds the
real ones — 244 of them in the screen recording where the transcript found 35.

    python edit/silences.py "edit/audio/vid1 screenrec.wav"
    python edit/silences.py "edit/audio/vid1 screenrec.wav" --keep 0.18
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from config import EDIT
CACHE = EDIT / "silences.json"

START_RE = re.compile(r"silence_start:\s*(-?[0-9.]+)")
END_RE = re.compile(r"silence_end:\s*(-?[0-9.]+)")


def detect(audio: Path, noise_db: int = -30, min_dur: float = 0.35) -> list[tuple[float, float]]:
    """Every (start, end) window quieter than `noise_db` for at least `min_dur`."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio),
         "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"],
        capture_output=True, text=True, errors="replace",
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr[-2000:])
    log = proc.stderr

    spans: list[tuple[float, float]] = []
    pending: float | None = None
    for line in log.splitlines():
        if (m := START_RE.search(line)):
            pending = max(0.0, float(m.group(1)))
        elif (m := END_RE.search(line)) and pending is not None:
            spans.append((pending, float(m.group(1))))
            pending = None
    return spans


def keep_ranges(
    spans: list[tuple[float, float]],
    total: float,
    keep: float = 0.16,
    start: float = 0.0,
    end: float | None = None,
) -> list[tuple[float, float]]:
    """Invert the silences into the ranges worth keeping.

    `keep` is how much of each silence survives — a hard butt-join on the
    waveform sounds rushed, so we leave a breath. Split evenly either side of
    the cut so neither the outgoing nor incoming word loses its edge.
    """
    end = total if end is None else end
    half = keep / 2.0

    cuts = [(a, b) for a, b in spans if b > start and a < end and (b - a) > keep]
    ranges: list[tuple[float, float]] = []
    cursor = start

    for a, b in cuts:
        seg_end = min(end, a + half)
        if seg_end - cursor > 0.20:
            ranges.append((round(cursor, 3), round(seg_end, 3)))
        cursor = max(cursor, min(end, b - half))

    if end - cursor > 0.20:
        ranges.append((round(cursor, 3), round(end, 3)))

    return ranges


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio", type=Path)
    ap.add_argument("--noise", type=int, default=-30)
    ap.add_argument("--min-dur", type=float, default=0.35)
    ap.add_argument("--keep", type=float, default=0.16)
    args = ap.parse_args()

    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(args.audio)],
        capture_output=True, text=True).stdout.strip())

    spans = detect(args.audio, args.noise, args.min_dur)
    dead = sum(b - a for a, b in spans)
    ranges = keep_ranges(spans, dur, args.keep)
    kept = sum(b - a for a, b in ranges)

    print(f"{args.audio.name}: {dur / 60:.2f} min")
    print(f"  {len(spans)} silences >= {args.min_dur}s at {args.noise}dB "
          f"= {dead / 60:.2f} min dead ({dead / dur * 100:.0f}%)")
    print(f"  -> {len(ranges)} keep-ranges, {kept / 60:.2f} min "
          f"({kept / dur * 100:.0f}% of source)")

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    cache[args.audio.stem] = {"spans": spans, "duration": dur}
    CACHE.write_text(json.dumps(cache, indent=1))
    print(f"  cached -> {CACHE.name}")


if __name__ == "__main__":
    main()
