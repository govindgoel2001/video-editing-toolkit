"""Find each GoPro clip's offset against the screen recording by audio.

Both devices captured the same room, so the clips are one multi-camera shoot:
GX010237 opens with a to-camera intro, then from ~0:30 it is the face angle of
exactly what the screen recording shows. Knowing the offset to the frame lets
the edit cut between angles instead of treating them as separate footage.

Cross-correlates short-term energy envelopes rather than raw samples — the two
mics differ wildly in gain, placement and codec, but the *shape* of when speech
happens is identical.

    python edit/sync.py
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

from config import EDIT
AUDIO = EDIT / "audio"
REF = "screen"
HOP = 160          # 10ms at 16kHz
OUT = EDIT / "sync.json"


def envelope(wav_path: Path) -> np.ndarray:
    """RMS energy per 10ms frame, log-scaled and normalised."""
    with wave.open(str(wav_path), "rb") as w:
        n = w.getnframes()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    frames = len(x) // HOP
    x = x[: frames * HOP].reshape(frames, HOP)
    rms = np.sqrt((x ** 2).mean(axis=1) + 1e-10)
    env = np.log10(rms + 1e-6)

    env -= env.mean()
    sd = env.std()
    return env / sd if sd > 0 else env


def best_offset(ref: np.ndarray, clip: np.ndarray) -> tuple[float, float]:
    """Offset in seconds of `clip` within `ref`, plus a confidence score.

    Confidence is the peak correlation over the runner-up outside a guard band;
    a clean lock sits well above 1.3, an ambiguous one hovers near 1.0.
    """
    if not len(ref) or not len(clip) or np.linalg.norm(ref) < 1e-8 or np.linalg.norm(clip) < 1e-8:
        return 0.0, 0.0
    # Pad the front of the reference by a clip length so negative lags are
    # searchable too — GX010237 starts its intro before the screen capture
    # was rolling, so its true offset is negative.
    pad = len(clip)
    ref_p = np.concatenate([np.zeros(pad, np.float32), ref])

    size = 1 << int(np.ceil(np.log2(len(ref_p) + len(clip))))
    corr = np.fft.irfft(
        np.fft.rfft(ref_p, size) * np.conj(np.fft.rfft(clip, size)), size
    )
    valid = corr[: max(len(ref_p) - len(clip), 1) + 1]
    peak = int(np.argmax(valid))

    guard = 300                                    # 3s either side of the peak
    masked = valid.copy()
    masked[max(0, peak - guard): peak + guard] = -np.inf
    runner = float(np.max(masked)) if np.isfinite(masked).any() else 0.0
    conf = float(valid[peak]) / runner if runner > 0 else float("inf")

    return (peak - pad) * HOP / 16000.0, conf


def drift_check(ref: np.ndarray, clip: np.ndarray, window_s: float = 45.0
                ) -> list[tuple[float, float, float]]:
    """Re-solve the offset on successive windows of the clip.

    A single correlation peak can be a coincidence, and two devices running on
    separate clocks drift apart over twelve minutes. Agreement across windows
    is what makes the lock trustworthy; a steady slope is drift, which the cut
    would otherwise smear into a lip-sync error late in the video.

    Returns [(window_start_s, offset_s, confidence), ...].
    """
    w = int(window_s * 100)
    out: list[tuple[float, float, float]] = []
    for i in range(0, max(len(clip) - w, 1), w):
        chunk = clip[i: i + w]
        if len(chunk) < w * 0.6:
            break
        off, conf = best_offset(ref, chunk)
        out.append((i / 100.0, off - i / 100.0, conf))
    return out


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ignored", nargs="*")
    ap.add_argument("--ref", default=REF)
    ap.add_argument("--glob", default="GX*.wav")
    a = ap.parse_args()
    ref = a.ref
    ref_env = envelope(AUDIO / f"{ref}.wav")
    print(f"reference: {ref}  ({len(ref_env) / 100 / 60:.2f} min)\n")

    results: dict[str, dict] = {}
    for wav in sorted(AUDIO.glob(a.glob)):
        env = envelope(wav)
        off, conf = best_offset(ref_env, env)
        lock = "locked" if conf >= 1.30 else "WEAK — verify by eye"
        results[wav.stem] = {"offset_s": round(off, 3),
                             "confidence": round(conf, 3),
                             "duration_s": round(len(env) / 100, 3)}
        _ = lock
        print(f"{wav.stem}:  screenrec {off:8.2f}s   conf {conf:5.2f}  {lock}")

        wins = [w for w in drift_check(ref_env, env) if w[2] >= 1.25]
        if len(wins) >= 2:
            offs = [w[1] for w in wins]
            spread = max(offs) - min(offs)
            print(f"    {len(wins)} windows agree, offsets "
                  f"{min(offs):.2f}..{max(offs):.2f}s (spread {spread:.2f}s)"
                  + ("  <- drift, worth a per-section offset"
                     if spread > 0.35 else "  <- stable"))
            results[wav.stem] = {**results.get(wav.stem, {}),
                                 "windows": [[round(a, 1), round(b, 3),
                                              round(c, 2)] for a, b, c in wins]}
        else:
            print(f"    only {len(wins)} confident window(s) — treat as approximate")

    OUT.write_text(json.dumps({"reference": ref, "clips": results}, indent=1))
    print(f"\nwrote {OUT.name}")
    print("\nA GoPro time T maps to screenrec time T + offset.")


if __name__ == "__main__":
    main()
