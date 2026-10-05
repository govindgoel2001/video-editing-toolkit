"""Lay the sound effects, and optionally a music bed, over the finished cut.

Runs after build.py. Video is stream-copied, so this is cheap and repeatable:
re-run it with a different track without re-encoding a frame.

Cues are read from the same EDL the graphics use, so a whoosh lands on its
title card and a pop lands on its chip no matter how the silence cuts move.

    python edit/mix.py edit/final.mp4 -o edit/final_mixed.mp4
    python edit/mix.py edit/final.mp4 --music track.mp3 -o edit/final_mixed.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import probe_dur, resolve_cards, silence_cuts, segment_audio, frame_count, FPS, sfx_cues, range_cuts  # noqa: E402

from config import EDIT
SFX = EDIT / "sfx"

# How loud each effect sits under the speech. Set by ear against a -20 LUFS
# bed: the stinger is the only one meant to be heard as an event.
GAIN = {
    "stinger": 0.55,
    "impact": 0.34,
    "whoosh": 0.22,
    "whoosh_down": 0.20,
    "riser": 0.24,
    "pop": 0.16,
    "click": 0.13,
}


def segment_times(edl: dict, clips: Path | None = None) -> tuple[list[float], list[float], list]:
    """Output offset, duration and (start, cuts) for every range."""
    clips = clips or EDIT / "clips"
    sync = edl.get("sync", {})
    screen = Path(edl["sources"]["screen"])
    screen_dur = probe_dur(screen)

    offsets, durations, seg_cuts = [], [], []
    t = 0.0
    for i, r in enumerate(edl["ranges"]):
        start, end = float(r["start"]), float(r["end"])
        speed = float(r.get("speed", 1.0))
        style = r.get("style", "cam")
        key, key_start, _ = segment_audio(r, sync, screen, screen_dur)

        cuts = range_cuts(r, key, key_start)

        seg = clips / f"seg_{i:03d}.mov"
        dur = probe_dur(seg) if seg.exists() else frame_count(cuts, end - start, speed) / FPS

        offsets.append(t)
        durations.append(dur)
        seg_cuts.append((start, cuts))
        t += dur
    return offsets, durations, seg_cuts


def cues(edl: dict) -> list[tuple[str, float]]:
    """(effect, output time) for the whole video."""
    offsets, durations, seg_cuts = segment_times(edl)
    return [(name, at) for at, name, _ in sfx_cues(edl, offsets, durations, seg_cuts)]


def build_graph(cue_list, music: Path | None, total: float,
                music_gain: float) -> tuple[list[str], str]:
    inputs: list[str] = []
    parts: list[str] = []
    mix_labels: list[str] = []

    # speech, split so the music can duck against it
    if music is not None:
        parts.append("[0:a]asplit=2[sp][key]")
        speech = "[sp]"
    else:
        speech = "[0:a]"
    mix_labels.append(speech)

    idx = 1
    if music is not None:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        music_idx = idx
        idx += 1

    for name, at in cue_list:
        f = SFX / f"{name}.wav"
        if not f.exists():
            continue
        inputs += ["-i", str(f)]
        ms = int(round(at * 1000))
        lbl = f"[s{idx}]"
        parts.append(
            f"[{idx}:a]adelay={ms}|{ms},volume={GAIN.get(name, 0.2):.3f}{lbl}")
        mix_labels.append(lbl)
        idx += 1

    if music is not None:
        fade_out = max(0.0, total - 4.0)
        parts.append(
            f"[{music_idx}:a]atrim=0:{total:.3f},asetpts=N/SR/TB,"
            f"afade=t=in:st=0:d=2.5,afade=t=out:st={fade_out:.3f}:d=4,"
            f"volume={music_gain:.3f}[musraw]")
        # Duck the bed under him rather than riding a fixed level: the speech
        # is the key input, so the music drops only while he is talking.
        parts.append(
            "[musraw][key]sidechaincompress=threshold=0.035:ratio=9"
            ":attack=25:release=420:makeup=1[mus]")
        mix_labels.append("[mus]")

    parts.append(
        "".join(mix_labels) +
        f"amix=inputs={len(mix_labels)}:normalize=0:dropout_transition=0,"
        f"loudnorm=I=-14:TP=-1.5:LRA=11,"
        # Limiter last, or loudnorm's makeup walks the peak back up over the
        # ceiling it was asked to hold.
        f"alimiter=limit=0.84:level=disabled[a]")
    return inputs, ";".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--edl", type=Path, default=EDIT / "edl.json")
    ap.add_argument("--music", type=Path)
    ap.add_argument("--music-gain", type=float, default=0.22)
    ap.add_argument("--no-sfx", action="store_true")
    args = ap.parse_args()

    from config import load_edl
    edl = load_edl(args.edl)
    total = probe_dur(args.video)
    cue_list = [] if args.no_sfx else cues(edl)

    print(f"{len(cue_list)} cues over {total/60:.2f} min"
          + (f", music {args.music.name}" if args.music else ", no music"))
    for name, at in cue_list[:60]:
        print(f"  {at:7.2f}s  {name}")

    inputs, graph = build_graph(cue_list, args.music, total, args.music_gain)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(args.video), *inputs,
           "-filter_complex", graph,
           "-map", "0:v", "-map", "[a]", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-shortest", str(args.output)]
    subprocess.run(cmd, check=True)
    print(f"-> {args.output}  {args.output.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
