# Amber glass overlays

Derived from the actual title cards in vid2–vid6. These are transparent overlays over footage, with a deep green pane, amber hairline and pale text.

## Colors

- `#081814`: pane, at 86–90% opacity
- `#e8b964`: amber accents
- `#f4f8f5`: headline
- `#c3d8cc`: supporting text
- `#bee8d6`: translucent rim

## Typography

Segoe UI and Bahnschrift on Windows; system sans-serif fallback elsewhere. Headline 62–150 px, labels 21–27 px. Keep text inside the card with comfortable padding.

## Motion

One seekable, paused GSAP timeline per card. A slight perspective entrance, text reveal, one sheen pass, a readable hold and a final fade. No random values, autoplay or infinite repeats. Export transparent ProRes 4444 MOV.

## Avoid

Do not cover the face box or bottom subtitles. Do not shrink text to fit long copy; shorten it. Do not introduce a new palette. Do not combine cards into multiple scenes without proper transitions.
