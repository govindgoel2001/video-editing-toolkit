"""Turn a coarse time range into tight sub-ranges with the dead air removed.

Reads the word-level transcript, finds every gap longer than a threshold, and
returns ranges that keep the speech and a small breath either side. Cutting on
word boundaries rather than on an audio-energy threshold means we never clip a
consonant off the front of a word.

Usage as a library:
    from autocut import tighten, load_words
    ranges = tighten(load_words("edit/transcripts/GX010237.json"), 12.0, 48.0)

Usage from the shell (inspect what a range would become):
    python edit/autocut.py edit/transcripts/GX010237.json 12 48
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# A pause shorter than this is rhetorical and worth keeping.
DEFAULT_MAX_GAP = 0.55
# How much of the silence to leave at each side of a cut, so speech never
# starts hard on the first syllable.
LEAD_IN = 0.12
LEAD_OUT = 0.22
# Ranges shorter than this aren't worth a cut point.
MIN_RANGE = 0.45


def load_words(transcript: str | Path) -> list[dict]:
    data = json.loads(Path(transcript).read_text(encoding="utf-8"))
    return [w for w in data["words"] if w.get("type") == "word"]


def tighten(
    words: list[dict],
    start: float,
    end: float,
    max_gap: float = DEFAULT_MAX_GAP,
    lead_in: float = LEAD_IN,
    lead_out: float = LEAD_OUT,
    drop: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    """Sub-ranges covering the speech between `start` and `end`.

    `drop` is an optional list of (start, end) windows to remove outright —
    fluffed lines, restarts, a phone ringing.
    """
    inside = [w for w in words if w["end"] > start and w["start"] < end]
    if not inside:
        return []

    if drop:
        inside = [
            w for w in inside
            if not any(w["start"] < d_end and w["end"] > d_start
                       for d_start, d_end in drop)
        ]
        if not inside:
            return []

    ranges: list[list[float]] = []
    cur_start = max(start, inside[0]["start"] - lead_in)
    prev_end = inside[0]["end"]

    for w in inside[1:]:
        if w["start"] - prev_end > max_gap:
            ranges.append([cur_start, min(end, prev_end + lead_out)])
            cur_start = max(start, w["start"] - lead_in)
        prev_end = w["end"]

    ranges.append([cur_start, min(end, prev_end + lead_out)])

    # merge anything that ended up adjacent after padding, drop slivers
    merged: list[list[float]] = []
    for r in ranges:
        if r[1] - r[0] < MIN_RANGE:
            continue
        if merged and r[0] - merged[-1][1] < 0.08:
            merged[-1][1] = r[1]
        else:
            merged.append(r)

    return [(round(a, 3), round(b, 3)) for a, b in merged]


def _main() -> None:
    transcript, start, end = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    max_gap = float(sys.argv[4]) if len(sys.argv) > 4 else DEFAULT_MAX_GAP
    words = load_words(transcript)
    out = tighten(words, start, end, max_gap=max_gap)
    kept = sum(b - a for a, b in out)
    print(f"{len(out)} ranges, {kept:.1f}s kept of {end - start:.1f}s "
          f"({kept / max(end - start, 1e-6) * 100:.0f}%)")
    for a, b in out:
        print(f"  {a:8.3f} -> {b:8.3f}  ({b - a:5.2f}s)")


if __name__ == "__main__":
    _main()
