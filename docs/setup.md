# Setup

Core requirements: Python 3.11–3.14, FFmpeg/ffprobe, Node 22+, npm, and Git. Use a current FFmpeg build that includes libx264, AAC, subtitles/libass, drawtext, loudnorm and the standard audio filters. Windows Segoe UI, Linux DejaVu Sans and macOS Arial are tried automatically. Override fonts with `VIDEO_FONT` and `VIDEO_FONT_BOLD` pointing to `.ttf` files.

## Manual installation

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[video-use,capture,download]"
npm ci
python -m playwright install chromium
python toolkit.py doctor
```

Linux Chromium may also need OS libraries: `python -m playwright install --with-deps chromium`. That command installs system packages and may require administrator access. HyperFrames manages its own rendering browser; `HYPERFRAMES_BROWSER_PATH` can point to an existing compatible Chromium executable.

Install Remotion separately with `cd examples/remotion` and `npm ci`, then return to the root. Its first render may download Chrome Headless Shell. Install Manim only if needed with `python -m pip install -e ".[manim]"`; follow the bundled Manim skill's OS requirements for fonts, Cairo/Pango and optional LaTeX.

## Models and cloud helpers

faster-whisper downloads models to the normal Hugging Face cache. CPU/int8 is the default. `--model small` reduces memory and startup cost relative to the default `medium`; `--language auto` enables automatic language detection for the `transcribe` command. The output uses a single `S0` speaker and word timestamps; it is not speaker diarization. GPU mode needs compatible CTranslate2/CUDA libraries and is optional.

The separate vendored `/watch` helper uses `mlx-whisper` on Apple Silicon or `openai-whisper` elsewhere. It does not reuse faster-whisper. You can use `--no-whisper` for frames/native captions and use the toolkit's `transcribe` command for local files, or install the review helper's own backend in a separate environment. Its upstream installer and plugin files are preserved; read them before invoking an installer.

Cloud transcription is opt-in: set `ELEVENLABS_API_KEY` and run the original `vendor/video-use/helpers/transcribe.py` or `transcribe_batch.py` after reading its help. JEV requires `OPENROUTER_API_KEY`; it is an experimental historical integration and may require service/model updates. Neither service is called by bootstrap, demo or the default renderer.

All recordings and generated outputs belong in `workspaces/` or outside the checkout. These directories, media extensions, credential files, cookies and browser login state are ignored by Git.
