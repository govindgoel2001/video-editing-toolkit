# Validation

Checked on Windows on 2026-10-05 with Python 3.14.4, FFmpeg 8.1.1, Node 24.12.0 and npm 11.6.0. All media used for these checks was generated locally. Recordings, test outputs, model caches and browser downloads are excluded from the repository.

## Timing and editing

```bash
python -m unittest discover -s tests -v
python toolkit.py demo --graphics
```

All **15 regression checks passed**. They cover relative EDL paths, invalid source ranges/sync offsets, duplicate transcript stems, PiP restrictions, caption timestamp carry, borrowed-microphone cuts, word protection, silent-input sync confidence, PCM transcription input and real FFmpeg retiming. A fully dropped range and a failed audio decode cannot silently report success.

The full synthetic demo rendered and decoded successfully at 1920×1080, 30 fps, H.264/AAC: **189 frames / 6.30 seconds**. Its three intermediate clips had **zero samples of frame/audio mismatch**. QC measured **−13.9 LUFS**, **−5.4 dBTP**, no introduced speech dropouts, no clipped words and no mid-sentence boundaries. These are fixture results, not an assurance about arbitrary source footage.

HyperFrames lint, composition checks and rendering passed for the four-second opener. Its ProRes 4444 MOV retained alpha through the FFmpeg compositor. Export samples were inspected visually for camera/screen layouts, PiP, graphics, captions and the retimed ending.

## Installed helpers

After installing the optional capture and Remotion dependencies:

```bash
python tests/smoke_helpers.py --capture --remotion
```

All helper checks passed:

| Tool | Observed result |
| --- | --- |
| Thumbnail | 1280×720 Pillow composition with generated screenshot |
| Music | Eight seconds of stereo 48 kHz PCM; loops, ducking and tape stop exercised |
| Extended SFX | Fourteen generated WAV effects |
| Sync proposal | Synthetic camera offset within 0.02 seconds of zero |
| Vendored watch | Four extracted frames with `--no-whisper`; all four inspected |
| Browser capture | Playwright screenshot of a generated page served on localhost |
| Remotion speed-up | 161 frames from the eight-second fixture, first three seconds at 8× speed |

The independent Remotion demo also rendered successfully:

```bash
cd examples/remotion
npm run demo
```

It produced 90 frames / three seconds. These renders exercise the pinned Remotion packages and their downloaded browser, not just source compilation.

## Local speech transcription

CPU/int8 faster-whisper `tiny` transcribed a generated Windows text-to-speech WAV into 21 timed words. FFmpeg decoded the input to mono 16 kHz PCM; the transcriber supplied normalized NumPy samples to Whisper, avoiding an incompatible PyAV file-decoder API. No hosted transcription API was called. The generated fixture was used with:

```bash
python toolkit.py transcribe workspaces/whisper-fixture/voice.wav --edit-dir workspaces/whisper-fixture/edit --model tiny
```

Use your own speech file in place of this ignored fixture. `python -m pip check` also reported no broken requirements in the tested environment.

## Continuous checks and limits

`.github/workflows/checks.yml` runs the regression checks and the synthetic FFmpeg demo on Ubuntu/Python 3.12. The graphics and installed-helper commands above are separate local checks; the workflow does not download their browsers or render them.

Manim rendering, CUDA transcription, hosted ElevenLabs/OpenRouter services, external video downloads and all twelve legacy God HTML templates were not exercised. Their instructions or source are included with attribution; cloud calls remain explicit choices. Review real edits and their synchronization before sharing an export.
