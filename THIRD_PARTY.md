# Sources and licenses

The root MIT license applies to this toolkit's original code and Govind's adapted session scripts. It does not replace licenses or usage terms of vendored code, dependencies, fonts or services.

| Component | Source/version | Terms and attribution |
| --- | --- | --- |
| video-use | [browser-use/video-use](https://github.com/browser-use/video-use), `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66` | MIT, Copyright 2026 BrowserUse. Original license is in `vendor/video-use/LICENSE`; files are copied unchanged. |
| HyperFrames skills | Local HyperFrames plugin skills from the editing environment; [upstream](https://github.com/heygen-com/hyperframes) | Apache-2.0, Copyright 2026 HeyGen, Inc. License retained at `vendor/hyperframes-skills/LICENSE`; source instructions are unchanged. The npm CLI is pinned to 0.8.40; use its help if a skill describes a newer command. |
| watch | [mathiaschu/watch](https://github.com/mathiaschu/watch), `14c780e47bbafaf3b6ae22ec108615470cc89476` | MIT; original Bradley Bonanno and Mathias Schusterman notices retained in `vendor/watch/LICENSE`. Tracked source files are copied unchanged. |
| FFmpeg | Installed separately | [FFmpeg legal and licensing](https://ffmpeg.org/legal.html): terms depend on the build, enabled libraries and distribution. Binary not bundled. |
| GSAP | npm 3.14.2 | [GSAP standard license](https://gsap.com/standard-license/). Installed by npm; no assertion that it is MIT. |
| Remotion | npm 4.0.447 | [Remotion license](https://www.remotion.dev/license). Review the applicable usage/company terms. Installed in its example, not vendored. |
| faster-whisper / CTranslate2 | pip dependencies | Retain each installed package's license; model weights have their own terms. |
| NumPy, SciPy, Pillow, Playwright, Manim, yt-dlp, librosa, Matplotlib, Requests, React | pip/npm dependencies | Installed separately with their upstream license files and notices. |

System fonts are referenced locally and are not distributed. Generated synthetic footage and sound effects are produced on the user's machine. Screenshots, input recordings, imported images, music and model outputs remain subject to their owners' terms.

[docs/provenance.json](docs/provenance.json) records source paths relative to the original home directory and hashes of selected source files before adaptation. Vendored license files and notices must stay with redistributed copies.
