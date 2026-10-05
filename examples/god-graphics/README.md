# Original God graphics

Twelve unchanged compositions from `videoeditinggod/v3`: bundle, calls, data, drops, edge, features, feed, fineprint, harness, private, title and tokens. Their text belongs to the original explainer; change it for your own story. They use remote GSAP from jsDelivr, so the original templates need internet access.

Read [DESIGN.md](DESIGN.md), then use the pinned CLI from the repository root:

```bash
npx --no-install hyperframes lint examples/god-graphics/title
npx --no-install hyperframes check examples/god-graphics/title
npx --no-install hyperframes render examples/god-graphics/title --format mp4 --output workspaces/god-title.mp4 --workers 2
```

These are the original full-frame compositions, including their backgrounds. The reusable transparent title-card generator lives separately in `graphics/`. The original template set is retained for reference; the toolkit's generated alpha cards are the graphics path covered by the synthetic integration test.
