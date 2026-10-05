# Validation

Checked on Windows on 2026-10-05 with Python 3.14.4, FFmpeg 8.1.1, Node 24.12.0 and npm 11.6.0. All media used for these checks was generated locally. Recordings, test outputs, model caches and browser downloads are excluded from the repository.

## Timing and editing

```bash
python -m unittest discover -s tests -v
python toolkit.py demo --graphics
```

All **28 regression checks passed**. They cover relative EDL paths, invalid source ranges/sync offsets, duplicate transcript stems, PiP restrictions, caption timestamp carry, borrowed-microphone cuts, word protection, silent-input sync confidence, PCM transcription input and real FFmpeg retiming. Reel checks also cover ambiguous speech cues, invalid word timings, caption boundaries, local media resolution, crop/music validation, real 44.1-to-48 kHz resampling and exclusion of stale media/login files from freelancer packs. A fully dropped range and a failed audio decode cannot silently report success.

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

## Portrait scene library

```bash
python toolkit.py reel --demo --dir workspaces/reel-demo --draft
```

HyperFrames 0.8.40 lint, runtime, motion and layout checks passed for the portrait composition. All ten scene types rendered in the generated 36-second fixture. The delivered MP4 decoded at **1080×1920, 30 fps, 1,080 frames**. Its PCM mix contained exactly **1,728,000 samples** at 48 kHz. Export QC measured **−14.0 LUFS**, **−3.8 dBTP**, zero audio lag against the continuous source, and no introduced dropouts. Backward seeks and both split/graphic layouts were checked during scene development.

Export frames were inspected for source-page playback, caption placement and layout transitions. The captured page advances within its scene. A dense transition inspection identified hidden counter-strip rows outside their deliberate one-digit clipping window; those rows now have an explicit occlusion annotation. A focused follow-up at six timestamps found no errors or warnings. Pack contents include licensed fonts, the current source assets, timed beats, captions and continuous narration/mix/SFX stems.

A separate private presenter clip exercised the alpha cutout and all three layouts at 388 frames, with −14.0 LUFS and zero measured audio lag. That media and its transcript are excluded from the repository. It is a style preview, not a fact-checked, publication-ready reel. Fresh generation, Telegram/VPS scheduling and HeyGen training/API generation remain unverified and unimplemented here.

## Local speech transcription

CPU/int8 faster-whisper `tiny` transcribed a generated Windows text-to-speech WAV into 21 timed words. FFmpeg decoded the input to mono 16 kHz PCM; the transcriber supplied normalized NumPy samples to Whisper, avoiding an incompatible PyAV file-decoder API. No hosted transcription API was called. The generated fixture was used with:

```bash
python toolkit.py transcribe workspaces/whisper-fixture/voice.wav --edit-dir workspaces/whisper-fixture/edit --model tiny
```

Use your own speech file in place of this ignored fixture. `python -m pip check` also reported no broken requirements in the tested environment.

## Continuous checks and limits

`.github/workflows/checks.yml` runs the regression checks and the synthetic FFmpeg demo on Ubuntu/Python 3.12. The graphics and installed-helper commands above are separate local checks; the workflow does not download their browsers or render them.

Manim rendering, CUDA transcription, hosted ElevenLabs/OpenRouter services, external video downloads and all twelve legacy God HTML templates were not exercised. Their instructions or source are included with attribution; cloud calls remain explicit choices. Review real edits and their synchronization before sharing an export.
