# Remotion example

This repairs the original `Code/video-edit` composition into a complete project with an entry point, registered compositions, pinned dependencies and configurable input.

```bash
npm ci
npm run demo
npm run studio
```

`Demo` renders a synthetic three-second title animation to `../../workspaces/remotion-demo.mp4`. From the toolkit root, run `python tools/remotion.py your-video.mp4 --loading-end 45 --speed 8 -o workspaces/loading-fast.mp4` to accelerate the opening loading sequence and retain normal playback afterward. Both sections are muted, matching the original composition. Its imported video copy is ignored by Git.

The CLI may download a compatible Chrome Headless Shell on first render. Remotion is governed by [its own license](https://www.remotion.dev/license).
