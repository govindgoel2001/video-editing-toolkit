# Company Brain reels

## Style prompt

A 1080 by 1920 editorial technology reel based on the approved Nick Saraev reference: real presenter footage alternates with a rounded bottom presenter window and full-frame explanatory graphics. Real screenshots provide evidence; animated interfaces explain actions. The graphics feel light and spacious, with one orange accent, large type, and short movements that land on spoken words.

## Colors

- `#fafafa`: canvas
- `#111114`: ink and terminal canvas
- `#ffffff`: card surfaces and face captions
- `#52525b`: secondary text
- `#e4e4e7`: borders
- `#ff5c00`: orange emphasis and motion accents
- `#b84000`: readable orange text on light surfaces

## Typography

Inter heavy sans for presenter captions and interface headings, Fraunces italic for graphic captions, JetBrains Mono for commands and data. This pairing comes from the approved existing composition. Caption size 88 to 112 pixels, headings 60 to 92 pixels, body 32 to 42 pixels. Limit caption groups to two short words; split long groups rather than clipping them. Keep captions inside 80-pixel horizontal margins, above social controls and away from the face.

## Motion and layout

Use one paused, deterministic GSAP root timeline. Each scene has an entrance, a readable hold, and a short crossfade at its boundary. Scene changes do not cut or retime the presenter audio. Word timings drive captions and beat boundaries. Keep a stable initial frame and restore the correct state when seeking backwards. Use flex containers that fill the scene, with padding and gaps. Do not put CSS transforms on elements animated by GSAP.

Full-face footage fills the canvas. Split mode uses a rounded presenter window at the bottom and reserves the upper portion for graphics; an optional existing alpha cutout can overlap the window edge. Full graphics hide the presenter while its voice continues. Captions are the final visual layer.

## What not to do

- No neon grids, invented statistics, fabricated source screenshots, or random animation.
- No text hidden behind graphics or placed over the presenter's mouth.
- No autoplay, infinite loops, asynchronous timeline construction, or timers.
- No new font/palette per scene, tiny interface text, or forced line breaks in dynamic copy.
- No training footage, credentials, private transcripts, or generated media in source control.
