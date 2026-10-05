"""Automated QC. Every check here exists because something shipped broken.

    python edit/qc.py edit/final_sfx.mp4 --edl edit/edl.json

Checks, and the bug each one catches:

  frame/sample   audio and video cut on different grids, so hundreds of cuts
                 each rounded differently and the sound walked off the picture
  dropouts       the same bug heard directly: speech stuttering many times a
                 second. Loudness, peak and sync all measure clean while this
                 is happening, which is why it survived three rounds of fixes
  sync           picture and sound pointing at different source instants
  loudness       too quiet, or peaks that will clip after YouTube re-encodes
  length         frames lost or duplicated across the concat
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import EDIT
SR = 16000
HOP = 80


def pcm(path: str, start: float = 0.0, dur: float | None = None,
        rate: int = SR) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", str(path), "-vn", "-f", "f32le", "-ac", "1",
            "-ar", str(rate), "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).astype(np.float64)


def count_dropouts(x: np.ndarray, win: int = 64) -> int:
    """Short near-silent gaps sitting inside otherwise loud speech.

    Deliberately a blunt instrument. It cannot tell a punched hole from the
    closure of a plosive, and every threshold tried here flagged either both or
    neither. It is only meaningful against a control, so `main` runs it on the
    output and on the same speech taken straight from the source, and compares
    the two counts. See the paired sweep below.
    """
    n = len(x) // win * win
    if n == 0:
        return 0
    f = np.abs(x[:n].reshape(-1, win)).max(1)
    loud = np.percentile(f, 80)
    if loud <= 0:
        return 0
    idx = [i for i in np.where(f < loud * 0.02)[0]
           if (f[max(0, i - 20):i].max() if i else 0) > loud * 0.3
           and (f[i + 1:i + 21].max() if i + 1 < len(f) else 0) > loud * 0.3]
    if not idx:
        return 0
    clusters = 1
    for a, b in zip(idx, idx[1:]):
        if b - a > 2:
            clusters += 1
    return clusters


def envelope(x: np.ndarray) -> np.ndarray:
    n = len(x) // HOP * HOP
    if n == 0:
        return np.array([])
    e = np.log(np.sqrt((x[:n].reshape(-1, HOP) ** 2).mean(1) + 1e-12) + 1e-8)
    return e - e.mean()


def best_lag(a: np.ndarray, b: np.ndarray, maxlag: float = 0.4):
    ea, eb = envelope(a), envelope(b)
    n = min(len(ea), len(eb))
    if n < 40:
        return 0.0, 0.0
    ea, eb = ea[:n], eb[:n]
    m = int(maxlag * SR / HOP)
    best, lag = -9.0, 0
    for L in range(-m, m + 1):
        x, y = (ea[-L:], eb[:L]) if L < 0 else ((ea[:-L], eb[L:]) if L else (ea, eb))
        if len(x) < 30:
            continue
        c = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))
        if c > best:
            best, lag = c, L
    return lag * HOP / SR, best


def probe(path: Path, stream: str, entries: str) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", entries, "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--edl", type=Path, default=EDIT / "edl.json")
    ap.add_argument("--clips", type=Path, default=EDIT / "clips")
    args = ap.parse_args()
    fails: list[str] = []

    print(f"QC {args.video.name}")

    from config import load_edl
    edl = load_edl(args.edl)

    # 1. every clip must hold exactly SAMPLE_RATE/FPS samples per frame
    import build
    ratio = build.SAMPLE_RATE // build.FPS
    clips = [args.clips / f'seg_{i:03d}.mov' for i in range(len(edl['ranges']))]
    if not clips or any(not c.is_file() for c in clips):
        raise SystemExit('QC needs the MOV segment directory used for this render.')
    total_frames = 0
    worst = 0
    for c in clips:
        nf = int(probe(c, "v:0", "stream=nb_read_packets").split(",")[0] or 0) \
            if False else int(subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-count_packets", "-show_entries", "stream=nb_read_packets",
                 "-of", "csv=p=0", str(c)],
                capture_output=True, text=True).stdout.strip() or 0)
        ns = len(pcm(str(c), rate=48000))
        total_frames += nf
        d = ns - nf * ratio
        worst = max(worst, abs(d))
        if d:
            print(f"  {c.name}: {d:+d} samples ({d / 48:+.1f} ms)")
    if worst:
        fails.append(f"clip frame/sample mismatch up to {worst} samples")
    print(f"  frame/sample alignment: worst {worst} samples across {len(clips)} clips")

    # 2. length matches the clips it was built from
    dur = float(probe(args.video, "v:0", "format=duration").split(",")[0] or 0) \
        if False else float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(args.video)],
            capture_output=True, text=True).stdout.strip())
    expect = total_frames / build.FPS
    if abs(dur - expect) > 0.1:
        fails.append(f"length {dur:.2f}s but clips total {expect:.2f}s")
    print(f"  length: {dur / 60:.2f} min ({total_frames} frames, expected {expect:.2f}s)")

    # 4. loudness
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(args.video), "-vn",
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    tail = log[log.rfind("Summary:"):]
    import re

    def grab(label):
        m = re.search(rf"{label}:\s*(-?\d+(?:\.\d+)?)", tail)
        return float(m.group(1)) if m else None
    lufs, peak = grab("I"), grab("Peak")
    if lufs is None or peak is None:
        fails.append('could not measure loudness/true peak')
    if lufs is not None and not -16 <= lufs <= -12:
        fails.append(f"loudness {lufs} LUFS outside -16..-12")
    if peak is not None and peak > -0.5:
        fails.append(f"true peak {peak} dBTP")
    print(f"  loudness: {lufs} LUFS, true peak {peak} dBTP")

    import mix as mixmod
    from styles import src_to_out
    offs, durs, sc = mixmod.segment_times(edl, args.clips)
    sync = edl.get("sync", {})
    screen = Path(edl["sources"]["screen"])
    sdur = build.probe_dur(screen)

    # 3. dropout sweep, against a control
    #
    # Each sampled window is mapped back through the cut to the source spans it
    # came from, and the same speech is pulled straight off the source file. The
    # detector then runs on both. Identical content, one copy through the edit
    # and one not, so only the difference means anything.
    def source_at(ot: float, want: float) -> np.ndarray:
        got: list[np.ndarray] = []
        need = want
        for i, r in enumerate(edl["ranges"]):
            t0, tot = offs[i], durs[i]
            if ot >= t0 + tot or need <= 0:
                continue
            _, cuts = sc[i]
            key, kstart, _ = build.segment_audio(r, sync, screen, sdur)
            by_stem = {Path(v).stem: v for v in edl["sources"].values()}
            apath = edl["sources"].get(key) or by_stem.get(key)
            if apath is None:
                continue
            spans = cuts or [(0.0, tot)]
            at = t0
            for a, b in spans:
                span = b - a
                if need <= 0:
                    break
                if ot < at + span:
                    skip = max(0.0, ot - at)
                    take = min(span - skip, need)
                    if take > 0.05:
                        got.append(pcm(apath, kstart + a + skip, take))
                        need -= take
                    ot = at + span
                at += span
        return np.concatenate(got) if got else np.array([])

    out_drop = src_drop = 0
    for t in range(10, int(dur) - 10, 25):
        out_drop += count_dropouts(pcm(str(args.video), t, 6.0))
        ctrl = source_at(float(t), 6.0)
        if len(ctrl) > 48000:
            src_drop += count_dropouts(ctrl)
    if out_drop > src_drop + 2:
        fails.append(f"{out_drop} dropouts against {src_drop} in the same "
                     "speech taken from the source")
    print(f"  dropouts: {out_drop} in the cut, {src_drop} in the same "
          f"speech from the source")

    # 5. sync, measured inside uncut spans only
    lags = []
    for i, r in enumerate(edl["ranges"]):
        seg_start, cuts = sc[i]
        if float(r.get('speed', 1)) != 1:
            continue  # Compare ordinary playback; retimed waveform needs resampling.
        if not cuts:
            continue
        a, b = max(cuts, key=lambda c: c[1] - c[0])
        if b - a < 3.1:
            continue
        src_local = a + 0.3
        t = offs[i] + src_to_out(src_local, cuts)
        key, kstart, _ = build.segment_audio(r, sync, screen, sdur)
        apath = str(screen) if key == screen.stem else edl["sources"][r["source"]]
        lag, c = best_lag(pcm(str(args.video), t, 2.5),
                          pcm(apath, kstart + src_local, 2.5))
        if c > 0.55:
            lags.append(abs(lag))
    if lags:
        if max(lags) > 0.08:
            fails.append(f"sync off by {max(lags) * 1000:.0f} ms")
        print(f"  sync: {len(lags)} segments, worst {max(lags) * 1000:.0f} ms")

    print()
    if fails:
        print("FAILED")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
