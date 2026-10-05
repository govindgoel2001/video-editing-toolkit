"""Report what the cut leaves out, so nothing is dropped without you seeing it.

Two kinds of omission matter and they are different problems:

  boundary   the range ends before he finishes the thought. The fix is to move
             the EDL range end, and the report prints the words that follow so
             you can decide whether you want them.
  clipped    a silence cut landed inside a word. That is the one that sounds
             like being interrupted, and it is a bug rather than a choice.

    python edit/omissions.py edit/edl.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import probe_dur, segment_audio, silence_cuts  # noqa: E402

from config import EDIT
TERMINAL = set(".!?")
CONTEXT = 12


def words_for(key: str) -> list[dict]:
    tr = EDIT / "transcripts" / f"{key}.json"
    if not tr.exists():
        return []
    return [w for w in json.loads(tr.read_text(encoding="utf-8"))["words"]
            if w.get("type") == "word"]


def text(ws: list[dict]) -> str:
    return " ".join((w.get("text") or "").strip() for w in ws)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("edl", type=Path)
    args = ap.parse_args()

    from config import load_edl
    edl = load_edl(args.edl)
    sync = edl.get("sync", {})
    screen = Path(edl["sources"]["screen"])
    sdur = probe_dur(screen)

    trunc_end = trunc_start = clipped_total = 0

    for i, r in enumerate(edl["ranges"]):
        if not r.get("captions", True):
            continue
        style = r.get("style", "cam")
        start, end = float(r["start"]), float(r["end"])
        key, kstart, _ = segment_audio(r, sync, screen, sdur)
        kend = kstart + (end - start)
        ws = words_for(key)
        if not ws:
            continue

        inside = [w for w in ws if w["end"] > kstart and w["start"] < kend]
        if not inside:
            continue

        beat = r.get("beat", f"range {i}")
        print(f"\n[{i:02d}] {beat}  ({r['source']} {start:.1f}-{end:.1f})")

        # --- start of range ---
        before = [w for w in ws if w["end"] <= kstart][-CONTEXT:]
        first = inside[0]
        if first["start"] < kstart:
            trunc_start += 1
            print(f"     STARTS MID-WORD on '{first['text'].strip()}'")
        if before:
            prev = before[-1]["text"].strip()
            if prev and prev[-1] not in TERMINAL:
                trunc_start += 1
                print(f"     picks up mid-sentence, dropped before: ...{text(before)}")

        # --- end of range ---
        last = inside[-1]["text"].strip()
        after = [w for w in ws if w["start"] >= kend][:CONTEXT]
        if last and last[-1] not in TERMINAL:
            trunc_end += 1
            print(f"     ENDS MID-SENTENCE on '...{text(inside[-6:])}'")
            if after:
                print(f"     you lose next: {text(after)}...")
        else:
            print(f"     ends cleanly: '...{text(inside[-6:])}'")

        # --- words chopped by a silence cut ---
        if r.get("cut_silence", style != "broll"):
            from build import range_cuts
            cuts = range_cuts(r, key, kstart)
            kept = [(kstart + a, kstart + b) for a, b in cuts] if cuts else [(kstart, kend)]
            chopped = []
            for w in inside:
                covered = sum(max(0.0, min(w["end"], b) - max(w["start"], a))
                              for a, b in kept)
                dur = w["end"] - w["start"]
                if dur > 0 and covered < dur * 0.85:
                    chopped.append(w["text"].strip())
            if chopped:
                clipped_total += len(chopped)
                print(f"     CLIPPED BY A CUT ({len(chopped)}): "
                      f"{' '.join(chopped[:14])}")

    print("\n" + "=" * 64)
    print(f"ranges ending mid-sentence : {trunc_end}")
    print(f"ranges starting mid-thought: {trunc_start}")
    print(f"words clipped by a cut     : {clipped_total}")


if __name__ == "__main__":
    main()
