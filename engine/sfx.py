"""Generate the sound effects instead of sourcing them.

Every sample here is synthesised from noise and sine waves, so no downloaded
samples are required. Generated files may be used under this repository license. Written once to
edit/sfx/*.wav at 48 kHz stereo and mixed in at the end of the build.

    python edit/sfx.py
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
from config import EDIT
OUT = EDIT / "sfx"
rng = np.random.default_rng(7)


def write(name: str, x: np.ndarray, peak: float = 0.85) -> None:
    x = np.asarray(x, np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    m = np.abs(x).max()
    if m > 0:
        x = x / m * peak
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    print(f"  {name}.wav  {len(x)/SR:.2f}s")


def t(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur)) / SR


def onepole(x: np.ndarray, cutoff: np.ndarray) -> np.ndarray:
    """Time-varying one-pole lowpass; cutoff is per-sample Hz."""
    a = np.exp(-2 * np.pi * np.clip(cutoff, 20, SR / 2.2) / SR)
    y = np.empty_like(x)
    prev = 0.0
    for i in range(len(x)):
        prev = (1 - a[i]) * x[i] + a[i] * prev
        y[i] = prev
    return y


def band(x: np.ndarray, hi: np.ndarray, ratio: float = 0.42) -> np.ndarray:
    """Two-pole bandpass. One pole is not enough.

    A single one-pole rolls off at 6 dB per octave, so a sweep topping out at
    5.6 kHz still passed most of the 10 kHz noise with it and the whoosh came
    out as hiss with a shape rather than as air moving. Cascading the pole
    doubles the slope on both edges, which is what puts the energy where the
    sweep says it is.
    """
    return (onepole(onepole(x, hi), hi)
            - onepole(onepole(x, hi * ratio), hi * ratio))


def whoosh(dur: float = 0.30, up: bool = True) -> np.ndarray:
    """A short swish, not a flypast.

    The first version ran 0.55s on a symmetric swell up to 5.6 kHz with a
    tremolo on top, which is long enough to hear as a sound in its own right
    and bright enough to read as hiss. A card takes about a third of a second
    to land, so the effect does too: fast in, quick decay, and the sweep tops
    out at 3.5 kHz where it sits under the voice instead of over it.
    """
    n = t(dur)
    p = n / dur
    noise = rng.normal(0, 1, len(n))
    sweep = 300 + 3200 * (p if up else 1 - p) ** 1.5
    air = band(noise, sweep)
    env = np.sqrt(p) * np.exp(-3.0 * p)          # peaks near a sixth of the way
    return air * env / env.max()


def impact(dur: float = 0.9) -> np.ndarray:
    n = t(dur)
    p = n / dur
    body = np.sin(2 * np.pi * (58 * np.exp(-4 * p)) * n) * np.exp(-7 * p)
    sub = np.sin(2 * np.pi * 38 * n) * np.exp(-5 * p) * 0.7
    click = onepole(rng.normal(0, 1, len(n)), np.full(len(n), 3000.0))
    click *= np.exp(-70 * p) * 0.5
    return body + sub + click


def riser(dur: float = 2.2) -> np.ndarray:
    n = t(dur)
    p = n / dur
    noise = rng.normal(0, 1, len(n))
    swept = band(noise, 200 + 7000 * p ** 2.2, 0.5)
    tone = np.sin(2 * np.pi * (220 * 2 ** (2.2 * p)) * n) * 0.35 * p ** 2
    return (swept * 1.2 + tone) * (p ** 1.3)


def pop(dur: float = 0.14) -> np.ndarray:
    n = t(dur)
    p = n / dur
    f = 900 * np.exp(-6 * p)
    return np.sin(2 * np.pi * f * n) * np.exp(-26 * p)


def keyclick(dur: float = 0.09) -> np.ndarray:
    n = t(dur)
    p = n / dur
    body = onepole(rng.normal(0, 1, len(n)), np.full(len(n), 5200.0))
    return body * np.exp(-45 * p)


def main() -> None:
    print("sfx:")
    write("whoosh", whoosh())
    write("whoosh_down", whoosh(0.26, up=False))
    write("impact", impact())
    write("riser", riser())
    write("pop", pop())
    write("click", keyclick())
    # the hook stinger: riser straight into the hit
    r = riser(1.6)
    i = impact(1.1)
    stinger = np.zeros(len(r) + len(i))
    stinger[:len(r)] += r * 0.8
    stinger[len(r):] += i
    write("stinger", stinger)


if __name__ == "__main__":
    main()
