"""Build the burned-caption SRT on the output timeline.

video-use's own SRT builder assumes each range plays straight through, so it
would drift by however much dead air we removed — up to half a minute by the
end. This version maps every word through the same silence cuts the video used,
so the captions stay on the word.

Two-word uppercase chunks, breaking on punctuation.

    python edit/captions.py edit/edl.json -o edit/master.srt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import (probe_dur, probe_duration, segment_audio,  # noqa: E402
                   silence_cuts, range_cuts)
from styles import src_to_out  # noqa: E402

from config import EDIT
PUNCT = set(".,!?;:")
MAX_WORDS = 2
UPPERCASE = True
MIN_SHOW = 0.30


def ts(seconds: float) -> str:
    total = round(max(0.0, seconds) * 1000)
    h, total = divmod(total, 3600000)
    m, total = divmod(total, 60000)
    s, ms = divmod(total, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def chunk(words: list[dict]) -> list[list[dict]]:
    out: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        text = (w.get("text") or "").strip()
        if not text:
            continue
        cur.append(w)
        if len(cur) >= MAX_WORDS or text[-1] in PUNCT:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def build(edl: dict, clips_dir: Path) -> list[tuple[float, float, str]]:
    entries: list[tuple[float, float, str]] = []
    offset = 0.0

    sync = edl.get("sync", {})
    screen = Path(edl["sources"]["screen"])
    screen_dur = probe_dur(screen)

    for i, r in enumerate(edl["ranges"]):
        start, end = float(r["start"]), float(r["end"])
        speed = float(r.get("speed", 1.0))
        style = r.get("style", "cam")

        # Caption the microphone we actually hear, not the camera we see: a
        # shot that borrows the screen mic must read the screen transcript, at
        # screen times, or every word lands on the wrong frame.
        key, key_start, _ = segment_audio(r, sync, screen, screen_dur)
        end = key_start + (end - start)
        start = key_start

        cuts = range_cuts(r, key, key_start)

        seg_path = clips_dir / f"seg_{i:03d}.mov"
        seg_dur = probe_duration(seg_path) if seg_path.exists() else (
            (sum(b - a for a, b in cuts) if cuts else end - start) / speed)

        if not r.get("captions", True):
            offset += seg_dur
            continue

        tr = EDIT / "transcripts" / f"{key}.json"
        if not tr.exists():
            offset += seg_dur
            continue

        words = [w for w in json.loads(tr.read_text(encoding="utf-8"))["words"]
                 if w.get("type") == "word"
                 and w["end"] > start and w["start"] < end
                 # a word cut as a stutter must not be captioned
                 and not any(float(x) <= w["start"] < float(y)
                             for x, y in r.get("drops", []))]

        for group in chunk(words):
            a = src_to_out(max(0.0, group[0]["start"] - start), cuts) / speed
            b = src_to_out(max(0.0, group[-1]["end"] - start), cuts) / speed
            if b - a < MIN_SHOW:
                b = a + MIN_SHOW
            a, b = offset + a, offset + min(b, seg_dur)
            if b <= a:
                continue
            text = " ".join((w.get("text") or "").strip() for w in group)
            entries.append((a, b, text.upper() if UPPERCASE else text))

        offset += seg_dur

    # never let one caption overlap the next
    entries.sort(key=lambda e: e[0])
    fixed: list[tuple[float, float, str]] = []
    for a, b, t in entries:
        if fixed and a < fixed[-1][1]:
            pa, pb, pt = fixed[-1]
            fixed[-1] = (pa, min(pb, a - 0.01), pt)
            if fixed[-1][1] <= fixed[-1][0]:
                fixed.pop()
        fixed.append((a, b, t))
    return fixed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("edl", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=EDIT / "master.srt")
    ap.add_argument("--clips", type=Path, default=EDIT / "clips")
    args = ap.parse_args()

    from config import load_edl
    edl = load_edl(args.edl)
    entries = build(edl, args.clips)

    lines: list[str] = []
    for n, (a, b, text) in enumerate(entries, start=1):
        lines.append(f"{n}\n{ts(a)} --> {ts(b)}\n{text}\n")
    args.output.write_text("\n".join(lines), encoding="utf-8")

    print(f"{len(entries)} caption chunks -> {args.output}")
    if entries:
        print(f"last caption ends at {entries[-1][1] / 60:.2f} min")


if __name__ == "__main__":
    main()
