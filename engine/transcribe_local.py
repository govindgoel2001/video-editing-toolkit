"""Local word-level transcription via faster-whisper, emitted in ElevenLabs
Scribe JSON shape so video-use's pack_transcripts.py can read it unchanged.

Scribe shape we emit:
  {"language_code": "en", "text": "...", "words": [
      {"text": "Ninety", "start": 2.52, "end": 2.81, "type": "word", "speaker_id": "S0"},
      {"text": " ",      "start": 2.81, "end": 2.86, "type": "spacing"},
      ...
  ]}

Single speaker per source (these are solo takes), so speaker_id is always S0.

Usage:
    python transcribe_local.py <video> [<video> ...] --edit-dir <dir> [--model medium]
"""

from __future__ import annotations

import argparse
import json
import hashlib
import subprocess
import sys
import wave
from pathlib import Path
import numpy as np


def extract_audio(video: Path, out_wav: Path) -> None:
    if out_wav.exists() and out_wav.stat().st_size > 1024:
        return
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video),
         "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
         str(out_wav)],
        check=True,
    )


def to_scribe(segments, language: str) -> dict:
    words: list[dict] = []
    full_text: list[str] = []
    prev_end: float | None = None

    for seg in segments:
        for w in (seg.words or []):
            text = w.word
            stripped = text.strip()
            if not stripped:
                continue
            start = float(w.start)
            end = float(w.end)
            # emit the gap before this word as a spacing entry (carries silence info)
            if prev_end is not None and start > prev_end:
                words.append({"text": " ", "start": round(prev_end, 3),
                              "end": round(start, 3), "type": "spacing"})
            words.append({"text": stripped, "start": round(start, 3),
                          "end": round(end, 3), "type": "word", "speaker_id": "S0"})
            full_text.append(stripped)
            prev_end = end

    return {"language_code": language, "text": " ".join(full_text), "words": words}

def read_pcm(wav: Path) -> np.ndarray:
    """FFmpeg already decoded this file; supply Whisper its supported array input.

    This also avoids PyAV decoder API changes affecting generated PCM WAVs.
    """
    with wave.open(str(wav), 'rb') as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1,2,16000):
            raise ValueError('Expected mono 16-bit PCM at 16 kHz from FFmpeg.')
        return np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype(np.float32)/32768


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+", type=Path)
    ap.add_argument("--edit-dir", type=Path, required=True)
    ap.add_argument("--model", default="medium")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--language", default="en")
    ap.add_argument("--compute-type", default="int8")
    args = ap.parse_args()

    from faster_whisper import WhisperModel

    tdir = args.edit_dir / "transcripts"
    adir = args.edit_dir / "audio"
    tdir.mkdir(parents=True, exist_ok=True)
    adir.mkdir(parents=True, exist_ok=True)

    pending = []
    for video in args.videos:
        if not video.is_file():
            raise SystemExit(f'Missing input: {video}')
        key = hashlib.sha256(json.dumps([str(video.resolve()), video.stat().st_size,
            video.stat().st_mtime_ns, args.model, args.language]).encode()).hexdigest()
        receipt = tdir / f'{video.stem}.cache.json'
        transcript = tdir / f'{video.stem}.json'
        if transcript.exists() and receipt.exists() and receipt.read_text() == key:
            print(f'skip {video.stem} (cached)', flush=True)
        else:
            pending.append((video, key, receipt))
    if not pending:
        print('All transcripts are cached.')
        return

    print(f"loading {args.model} on {args.device} ({args.compute_type})", flush=True)
    try:
        model = WhisperModel(args.model, device=args.device,
                             compute_type=args.compute_type)
    except Exception as exc:  # noqa: BLE001
        if args.device == 'cpu':
            raise
        print(f"GPU load failed ({exc}); falling back to CPU int8", flush=True)
        model = WhisperModel(args.model, device="cpu", compute_type="int8")

    for video, key, receipt in pending:
        stem = video.stem
        out_json = tdir / f"{stem}.json"

        wav = adir / f"{stem}.wav"
        print(f"[{stem}] extracting audio", flush=True)
        wav.unlink(missing_ok=True)
        extract_audio(video, wav)

        print(f"[{stem}] transcribing", flush=True)
        segments, info = model.transcribe(
            read_pcm(wav),
            language=None if args.language == "auto" else args.language,
            word_timestamps=True,
            vad_filter=False,          # keep silences — we need the gaps
            condition_on_previous_text=False,
            beam_size=5,
        )
        payload = to_scribe(list(segments), info.language or "en")
        out_json.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        receipt.write_text(key)
        n = sum(1 for w in payload["words"] if w["type"] == "word")
        print(f"[{stem}] done — {n} words -> {out_json}", flush=True)

    print("ALL DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
