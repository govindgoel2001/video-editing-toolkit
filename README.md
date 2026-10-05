# Video Editing Toolkit

The tools behind my `vid1`–`vid6` and `videoeditinggod` sessions, collected into one portable checkout: **video-use, FFmpeg, local Whisper, HyperFrames, GSAP, Remotion, Manim instructions, browser capture, thumbnails, music and sound effects.**

The shared editor comes from the most complete `vid6` version. Repeated copies are consolidated, paths are configurable, and the examples generate their own footage. Original recordings, transcripts, login state and credentials are not included.

## Start on Windows

Install **Python 3.11–3.14**, **Node.js 22+**, **Git**, and **FFmpeg with ffprobe**. Both FFmpeg commands must be on PATH. For FFmpeg, `winget install --id Gyan.FFmpeg -e` is one option; open a fresh terminal afterward.

```powershell
git clone https://github.com/govindgoel2001/video-editing-toolkit.git
cd video-editing-toolkit
powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap.ps1 -Capture -Download -Remotion
.\.venv\Scripts\python.exe toolkit.py demo --graphics
```

The demo creates test videos, removes pauses, makes captions, renders a transparent title card, combines screen and camera views, adds sound effects, and checks the export. Open **`workspaces/demo/edit/final.mp4`**. It uses a deliberately synthetic transcript, so no model download or API key is needed for this test.

Omit the three bootstrap switches for a smaller install. `-Capture` installs Playwright's Chromium browser; `-Download` adds yt-dlp; `-Remotion` installs the separate Remotion example. Python packages stay in `.venv`. Node versions are pinned in the two lockfiles.

On macOS/Linux, install Python, Node, FFmpeg and usable TrueType fonts, then run `bash bootstrap.sh`. Commands below use `python` to mean the checkout's virtual-environment interpreter; activate it first with `.\.venv\Scripts\Activate.ps1` on Windows or `source .venv/bin/activate` on macOS/Linux. For extra platform setup, see [setup.md](docs/setup.md).

## Edit your own recording

Copy [edl.single.json](examples/edl.single.json), set the video path and time range, then run:

```powershell
python toolkit.py render examples/edl.single.json --edit-dir workspaces/my-video/edit --prepare --model small
```

`--prepare` transcribes locally with faster-whisper, detects silence, and packs transcripts for inspection. The first use downloads the selected model. Remove `--prepare` on later renders to reuse that preparation. `--draft` uses faster encoding; omit it for the final quality setting.

The editor writes `final.mp4` at **1920×1080, 30 fps, H.264/AAC**, a readable `final.srt` and the burned two-word caption track in the session directory. It prints omission and QC findings in the terminal. Audio is mixed once and normalized toward −14 LUFS. Captions are composited after graphics. Intermediate MOVs carry uncompressed audio with exactly 1,600 samples per video frame at 48 kHz.

For a screen recording plus a GoPro/camera view, start from [edl.camera.json](examples/edl.camera.json). Run `python toolkit.py sync your-edl.json --edit-dir workspaces/my-video/edit`, verify the proposed offset, and enter it in the EDL before rendering. Camera files should already be copied to disk. [EDL reference](docs/edl.md) explains mic selection, cuts, crops, PiP, zooms, graphics and music.

## What's included

| Tool | Location | Use |
| --- | --- | --- |
| Desktop FFmpeg editor | `engine/`, `toolkit.py` | Silence cuts, camera/screen/PiP layouts, captions, grading, sync, effects, loudness and QC |
| Original video-use | `vendor/video-use/` | Agent editing skill, hosted transcription, packed transcripts, grading, rendering and timeline inspection |
| Local transcription | `engine/transcribe_local.py` | CPU/int8 faster-whisper; optional CUDA; word timestamps in the editor's transcript format |
| HyperFrames + GSAP | `graphics/`, root npm packages | Deterministic HTML animations rendered to transparent ProRes MOV cards |
| HyperFrames skills | `vendor/hyperframes-skills/` | Authoring, CLI, GSAP, registry and website-to-video instructions with references |
| God graphics | `examples/god-graphics/` | Twelve original HTML compositions from `videoeditinggod/v3` |
| Remotion | `examples/remotion/`, `tools/remotion.py` | Working React demo and the original loading-screen speed-up, with configurable input |
| Manim | `vendor/video-use/skills/manim-video/` | Original scene planning, animation instructions and reference examples; optional Python install |
| Browser capture | `tools/capture.py` | Playwright screenshots without a hardcoded Chrome path |
| Thumbnails | `tools/thumbnail.py` | Pillow title, screenshot card, glow and optional transparent person cutout |
| Music bed | `tools/music.py` | Loop crossfades, voice-relative levels, ducking and optional tape-stop transitions |
| Sound effects | `engine/sfx.py`, `tools/extended_sfx.py` | Locally generated effects from the shared editor and God project |
| Video review/download | `vendor/watch/` | Original `/watch` skill, yt-dlp, frame extraction, native captions and optional local Whisper |
| Experimental decision helper | `engine/jev.py` | Original OpenRouter editing-decision helper; optional API key and hosted service |

See [commands and FFmpeg recipes](docs/commands.md) for individual tools. [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) direct coding agents to the bundled skills. Nothing installs into your global agent configuration automatically.

## Optional services and licenses

The default editor works locally without API keys. The original video-use Scribe transcription explicitly uses ElevenLabs; the experimental JEV helper explicitly uses OpenRouter. Both require your own environment variables and send input to those services when you invoke them. `.env.example` contains empty placeholders; the default controller does not automatically load it.

Toolkit code is MIT. Vendored projects and installed packages retain their own terms, including HyperFrames' Apache-2.0 license, the GSAP standard license and Remotion's license. Read [THIRD_PARTY.md](THIRD_PARTY.md) before commercial use or redistribution.

This is a source checkout with command-line tools, rather than a packaged desktop application. Manim and optional cloud services were not exercised in the smoke tests. The synthetic editing demo, alpha graphics, Remotion demo/speed-up, capture, thumbnails, music, sync and local transcription are the reproducible checks described in [validation.md](docs/validation.md).
