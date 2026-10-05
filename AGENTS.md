# Working in this toolkit

Use `toolkit.py` as the default entry point. Keep recordings, transcripts, login state and generated files in an ignored `workspaces/<session>/` directory. Preserve original source videos. The editable EDL is the source of truth; see `docs/edl.md`.

For an actual editing task, read `vendor/video-use/SKILL.md` and the applicable helper documentation. Follow the user's instructions and approved edit scope. Prepare transcripts, inspect the footage, then design the cuts. The default controller uses local faster-whisper; the hosted Scribe helpers are separate, explicit choices.

Before creating or changing HTML animation, read `vendor/hyperframes-skills/hyperframes/SKILL.md`, `hyperframes-cli/SKILL.md`, and `gsap/SKILL.md`, plus the referenced design guidance. Read the relevant project `DESIGN.md` before coding. Use a paused, seekable GSAP timeline with HyperFrames metadata and a stable initial state. Render alpha overlays as MOV; captions must remain the final compositor layer.

For Manim, read `vendor/video-use/skills/manim-video/SKILL.md` and the relevant references. For video review/download, read `vendor/watch/SKILL.md` and its scripts. Bundled skills are not registered globally; use their paths explicitly in either Codex or Claude Code.

The FFmpeg engine uses 30 fps and 48 kHz audio. Keep intermediate MOV audio as PCM, round ranges to the same frame/sample grid, and do not mix an already mixed export again. Changes to timing require the synthetic demo and strict QC. Keep source/provenance and upstream licenses when altering vendored code.

Useful checks:

```bash
python -m unittest discover -s tests -v
python toolkit.py demo
python toolkit.py demo --graphics
```

Add no private session files or credentials to commits. `docs/validation.md` distinguishes verified paths from optional integrations.
