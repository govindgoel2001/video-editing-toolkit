# Individual tools

Run commands from the repository root using the virtual-environment Python. Write outputs into `workspaces/`.

## Preparation and inspection

```bash
python toolkit.py doctor
python toolkit.py transcribe media/screen.mp4 media/camera.mp4 --edit-dir workspaces/take/edit --model small --language auto
python toolkit.py engine silences --edit-dir workspaces/take/edit -- media/screen.mp4 --noise -40
python toolkit.py pack --edit-dir workspaces/take/edit
python toolkit.py sync examples/edl.camera.json --edit-dir workspaces/take/edit
python vendor/video-use/helpers/timeline_view.py media/screen.mp4 0 15 -o workspaces/take/timeline.png
python vendor/watch/scripts/watch.py media/screen.mp4 --no-whisper --max-frames 12 --out-dir workspaces/review
```

The upstream video-use helpers are preserved with their own CLIs; read their `--help` and [SKILL.md](../vendor/video-use/SKILL.md). `/watch` can also accept video URLs after installing the download extra. Its separate Whisper backend is optional, as explained in [setup.md](setup.md).

## Graphics and Remotion

```bash
python toolkit.py graphics graphics/cards.example.json --output-dir workspaces/cards --only opener
# npm ci must already have run inside examples/remotion:
python tools/remotion.py media/screen.mp4 --loading-end 45 --speed 8 -o workspaces/loading-fast.mp4
```

The Remotion speed-up retains the original muted-video behavior; it is for visual loading/demo sequences. Speech editing belongs in the FFmpeg pipeline. `npm run demo` inside `examples/remotion` creates a three-second React animation without source footage. `npm run studio` opens its compositions for preview.

The God HTML examples have their own [render instructions](../examples/god-graphics/README.md). Read the design notes and the bundled HyperFrames/GSAP skills before customizing them. For Manim, install the optional extra and follow `vendor/video-use/skills/manim-video/SKILL.md`; scene-planning examples are bundled with it.

## Capture, thumbnail and audio helpers

```bash
python tools/capture.py http://localhost:3000 --output workspaces/screenshots
python tools/thumbnail.py --title "MY NEXT VIDEO" --subtitle "Made with this toolkit" --badge "FFmpeg + HyperFrames" --screenshot workspaces/screenshots/overview.png -o workspaces/thumbnail.png
python tools/extended_sfx.py --output-dir workspaces/god-sfx
python tools/music.py media/voice.wav workspaces/music-cues.json --duration 60 -o workspaces/ducked-bed.wav
```

Capture's optional `--pages` JSON is `[{"name":"dashboard","path":"/dashboard","selector":"main"}]`. Pass `--storage-state` only for your own local Playwright login-state file; keep it outside tracked files. Thumbnail's optional `--cutout` accepts a PNG with transparency. It does not automatically remove a photo's background.

The God sound generator writes fourteen stereo 48 kHz samples plus original suggested gains. `--apply-gains` bakes those levels into the files. The main editor generates its own seven core effect samples automatically.

Music cues are a JSON list with files relative to that list:

```json
[
  {"at": 0, "file": "../media/music-a.mp3", "from": 0, "gain_db": -15, "tape_stop": true},
  {"at": 30, "file": "../media/music-b.mp3", "gain_db": -18}
]
```

Here `gain_db` is relative to the detected active voice level. The helper loops tracks with crossfades and ducks under speech. It emits a music-only WAV; include that bed once in your edit/mix.

## FFmpeg recipes

```bash
# Probe duration, tracks and pixel format.
ffprobe -v error -show_streams -show_format -of json media/input.mp4
# PCM speech extraction for analysis.
ffmpeg -i media/input.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le workspaces/voice.wav
# Still frame for inspection or a thumbnail.
ffmpeg -ss 10 -i media/input.mp4 -frames:v 1 workspaces/frame.png
# Decode every audio/video frame to catch a corrupt export.
ffmpeg -v error -i workspaces/take/edit/final.mp4 -f null -
# Integrated loudness and true peak.
ffmpeg -hide_banner -nostats -i workspaces/take/edit/final.mp4 -af ebur128=peak=true -f null -
```

For a complete render use `toolkit.py render`, which handles PCM intermediate clips, graphics/captions and mixing consistently. `engine mix` remains available for an explicitly separate postmix experiment; it should not be run automatically after the controller, which already mixes effects/music.
