"""Editorial calls on the transcript, answered by Jev.

Jev does not write text. It answers typed questions about a piece of state and
returns calibrated probabilities, which is exactly the shape of the judgement
calls an edit is made of: is this sentence a retake, is this dead talk, does a
new topic start here. The EDL is still written by hand; this file supplies the
evidence, sentence by sentence, with a number on it.

Each sentence is judged with the one before and the two after it in the state,
because a false start only reads as one next to the sentence that replaces it.

    OPENROUTER_API_KEY=... python edit/jev.py jevscreenrec
    python edit/jev.py GX010248 --from 30 --to 320

Answers are cached in jev/<stem>.json keyed by the sentence text, so a rerun
only pays for sentences it has not seen.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import EDIT
OUT = EDIT / "jev"
URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "~typesafe/jev-latest"

QUESTIONS = {
    "retake": {
        "type": "noul",
        "instructions": (
            "Look at the sentence marked >>> <<<. In a recorded tutorial, is it a "
            "false start, flub or abandoned attempt that the speaker then says "
            "again or corrects in a following sentence, so an editor should cut it?"),
        "criteria": {
            "true": "Abandoned, repeated or corrected by what follows; cut it",
            "false": "A real line the viewer needs; keep it",
        },
    },
    "dead": {
        "type": "noul",
        "instructions": (
            "Is the sentence marked >>> <<< dead air in words: the speaker "
            "muttering to himself, waiting for something to load, asking for an "
            "edit ('cut this', 'scratch that'), or filler with no information?"),
        "criteria": {
            "true": "No value to a viewer",
            "false": "Carries information, a point or personality worth keeping",
        },
    },
    "new_topic": {
        "type": "noul",
        "instructions": (
            "Does the sentence marked >>> <<< open a new section of the tutorial, "
            "the kind of moment a chapter title card would sit on?"),
        "criteria": {
            "true": "Clearly starts a new topic or step",
            "false": "Continues the current topic",
        },
    },
}


def sentences(stem: str, t0: float, t1: float) -> list[dict]:
    """Group transcript words into sentences by terminal punctuation."""
    data = json.loads((EDIT / "transcripts" / f"{stem}.json").read_text(encoding="utf-8"))
    out, cur = [], []
    for w in data["words"]:
        if w.get("type") != "word":
            continue
        if not t0 <= float(w["start"]) < t1:
            continue
        cur.append(w)
        if w["text"].rstrip().endswith((".", "?", "!")) or len(cur) >= 45:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [{"start": float(s[0]["start"]), "end": float(s[-1]["end"]),
             "text": " ".join(w["text"] for w in s)} for s in out]


def ask(state: str, key: str) -> dict:
    body = json.dumps({"model": MODEL, "state": state,
                       "questions": QUESTIONS}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "X-Title": "video-editing-toolkit"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                a = json.loads(r.read())["answers"]
            return {k: round(float(v["noul"]), 3) for k, v in a.items()}
        except Exception as exc:  # noqa: BLE001
            if attempt == 3:
                print(f"  jev failed: {exc}", file=sys.stderr)
                return {}
    return {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stem")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=1e9)
    ap.add_argument("--min", type=float, default=0.5,
                    help="print sentences where any answer reaches this")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("set OPENROUTER_API_KEY")

    OUT.mkdir(exist_ok=True)
    cache_path = OUT / f"{args.stem}.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    sents = sentences(args.stem, args.t0, args.t1)

    def state(i: int) -> str:
        ctx = []
        for j in range(max(0, i - 1), min(len(sents), i + 3)):
            s = sents[j]["text"]
            ctx.append(f">>> {s} <<<" if j == i else s)
        return "\n".join(ctx)

    todo = [i for i, s in enumerate(sents) if f"{s['start']:.2f}" not in cache]
    with ThreadPoolExecutor(8) as pool:
        for i, ans in zip(todo, pool.map(lambda i: ask(state(i), key), todo)):
            s = sents[i]
            if ans:
                cache[f"{s['start']:.2f}"] = {**s, **ans}
    cache_path.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    rows = sorted(cache.values(), key=lambda r: r["start"])
    rows = [r for r in rows if args.t0 <= r["start"] < args.t1]
    print(f"{args.stem}: {len(rows)} sentences judged, {len(todo)} new calls")
    for r in rows:
        flags = [f"{k}={r[k]:.2f}" for k in QUESTIONS if r.get(k, 0) >= args.min]
        if flags:
            print(f"  {r['start']:7.2f}-{r['end']:7.2f}  {' '.join(flags):32s} {r['text'][:110]}")


if __name__ == "__main__":
    main()
