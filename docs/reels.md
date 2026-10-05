# Portrait reels

`python toolkit.py reel` renders an existing continuous presenter recording with the Company Brain scene library. Filmed footage and a downloaded avatar clip use the same input path. The approved style is in [DESIGN.md](../reels/DESIGN.md).

Install the root Python tools and npm packages first using the bootstrap script. FFmpeg/ffprobe and Node 22+ must be on PATH. No hosted service is called by this renderer. Whisper downloads its model on first use if you omit a transcript.

```bash
python toolkit.py reel --demo --dir workspaces/reel-demo --draft
python toolkit.py reel examples/reel.json --dir workspaces/my-reel --no-render
python toolkit.py reel examples/reel.json --dir workspaces/my-reel
```

The demo generates synthetic media and a known transcript; it is a reproducible check, not a real avatar or voice. Replace the example's paths and cues before using the other commands. Use a separate ignored workspace directory per job.

## Job and speech timing

The JSON job uses `version: 1`, a local `presenter` file and an ordered `beats` list. Presenter input must contain video and narration and last 0.5–180 seconds. Paths resolve relative to the JSON file. URLs are not downloaded implicitly; capture or download source media first.

Optional `transcript` accepts the toolkit/Scribe-shaped `{"words": [{"text": "Hello", "start": 0.1, "end": 0.5}]}` or a list of those word objects. Otherwise local CPU/int8 Whisper runs with `--model medium --language auto`; review its transcript before publishing.

Each beat supplies:

- `layout`: `face`, `split` or `graphic`.
- `scene`: required for split/graphic; choose one of the ten names below.
- `cue` or `text`: a unique phrase from the spoken transcript. Alternatively use a zero-based `word_start` index, especially for repeated phrases.
- `data`: an object containing that scene's copy, facts and media.
- Optional `caption_style`: `sans` or `serif`. Defaults are sans on the face and serif on graphics.
- Optional `emphasis`: an array of spoken words to color orange.

The first beat begins at word zero; later beats must advance through the transcript. Missing or ambiguous cues fail with a correction request. Boundaries round to the 30 fps grid. Captions group at most two short words and stop at the next caption/beat or a real pause. Graphic elements use their corresponding spoken phrases where available, with deterministic entrance timings as a fallback. The presenter and narration never restart at scene changes.

## Scene data

| Scene | Data fields |
| --- | --- |
| `logo-pop` | `title`, optional `label`, optional local `logo` image. Without a logo, a typographic initial is shown. |
| `receipt` | `title`, `label`, local `image`, optional `highlight_y` between 0 and 1. Missing evidence is labeled. |
| `counter` | `label`, `value`. Supply the verified value; no statistic is fetched or invented. |
| `repo-card` | `name`, `description`, optional `stars`, `language`. This is an explanatory card, not a source screenshot. |
| `terminal` | `command`, `lines` as strings or `{text}` objects. |
| `agents` | `label`, `count`, `targets` as strings or `{label}` objects. Count must be a non-negative integer; at most six figures are displayed. |
| `checklist` | `items` as strings or `{text, status}` objects, optional `verdict`. Status is only shown when explicitly supplied. |
| `report` | `rows` as strings or `{label, value}` objects, optional `diff`. |
| `scan` | `label`, `issues` as strings or `{text}` objects. No pass/fail finding is inferred. |
| `page-scroll` | Local `video`, optional `from` offset in seconds, `title`, `source_label`. Supply a real recording covering the whole beat. |

Workflow lists support up to four rows in split mode or six in full graphics. Long copy fails with an actionable limit message. Keep headline and command copy concise and review the rendered composition. Screenshots, page videos and logo images are copied into the project with content hashes. Their authenticity and the factual copy remain the author's responsibility.

## Presenter geometry and audio

Split mode places the presenter in a rounded bottom card. Optional `cutout` accepts an existing continuous alpha video covering the source duration; this command does not remove backgrounds. Tune `split.card_top`, `split.video_top`, `split.band_top` and `split.overlap` for the alpha silhouette. Without a cutout, use `split.simple_video_top` to place the face inside the card. These are canvas coordinates in pixels; inspect your subject rather than assuming a crop fits every recording.

Optional `caption_positions` sets the top pixel position for `face`, `split` and `graphic` captions. Defaults are 1320, 940 and 1300. An alpha head may require a higher split caption. Captions render last, but their position must leave room around the face and scene content.

Input HDR HLG/PQ is converted to SDR BT.709 before rendering. The normalized presenter remains continuous. Narration is extracted once as stereo 48 kHz PCM and trimmed after resampling to exactly 1,600 samples per video frame. The original file is preserved.

Optional `sfx: true` adds quiet generated swishes at scene boundaries. Optional `music: {"file": "bed.wav", "gain_db": -22}` adds a looped, ducked bed relative to speech; allowed gains are −40 to −12 dB. The finished mix is normalized toward −14 LUFS and muxed once.

## Outputs and review

The workspace contains `final.mp4`, silent `visuals.mp4`, `project/`, `job.json`, `manifest.json`, `word-timings.json`, `captions.srt`, `narration.wav`, `mix-normalized.wav` and `qc.json`. Selected effects/music also produce separate stems.

HyperFrames lint and composition checks run before rendering. Strict delivery checks verify resolution, frame count, PCM sample alignment, decoded media, loudness, true peak, audio lag/correlation and introduced dropouts. They cannot establish factual accuracy or replace watching the final edit. `--draft` uses faster render settings; `--no-render` only prepares and checks the project.

By default `freelancer-pack.zip` contains the complete editable composition, current assets, licensed fonts/notices, timed beats, word timings, SRT captions and separate audio stems. It includes a README with exact render/mux commands. Use `--no-pack` to skip it. The ZIP is private job material; review its contents before sharing. Use the normalized mix once, or build a new mix from stems. Do not layer stems over the already mixed track.

This release provides Library rendering and the asset pack. Fresh bespoke-scene generation, link scraping/script approval/fact checking, Telegram/VPS orchestration, a queue/worker service and HeyGen avatar creation/generation are later pipeline stages. Supplying a local HeyGen export does not train a twin.
