"""Align approved beats to a continuous presenter recording, without retiming speech."""
from __future__ import annotations

import math
import re

FPS = 30
SCENES = {'logo-pop', 'receipt', 'counter', 'repo-card', 'terminal', 'agents',
          'checklist', 'report', 'scan', 'page-scroll'}


def token(text: str) -> str:
    return ''.join(c for c in str(text).casefold() if c.isalnum())


def read_words(payload, duration: float) -> list[dict]:
    raw = payload if isinstance(payload, list) else payload.get('words', [])
    words = []
    for w in raw:
        if w.get('type', 'word') != 'word' or not str(w.get('text', '')).strip():
            continue
        start, end = float(w['start']), float(w['end'])
        if not all(map(math.isfinite, (start, end))) or not 0 <= start < min(end, duration) or end > duration + 1 / FPS:
            raise ValueError(f'Word has invalid timestamps: {w.get("text")!r}')
        if words and start < words[-1]['end'] - .015:
            raise ValueError('Word timestamps overlap or are out of order; correct the transcript first.')
        words.append({'text': str(w['text']).strip(), 'start': start,
                      'end': min(end, duration)})
    if not words:
        raise ValueError('A non-empty word-timed transcript is required.')
    return words


def align_beats(specs: list[dict], words: list[dict], duration: float) -> list[dict]:
    if not specs:
        raise ValueError('At least one beat is required.')
    tokens = [token(w['text']) for w in words]
    starts, cursor = [], 0
    for index, b in enumerate(specs):
        if b.get('layout') not in {'face', 'split', 'graphic'}:
            raise ValueError(f'Beat {index + 1}: layout must be face, split or graphic.')
        if b.get('scene') not in SCENES and b.get('layout') != 'face':
            raise ValueError(f'Beat {index + 1}: unknown scene {b.get("scene")!r}.')
        style = b.get('caption_style', 'sans' if b['layout'] == 'face' else 'serif')
        if style not in {'sans', 'serif'}:
            raise ValueError('caption_style must be sans or serif.')
        if not isinstance(b.get('data', {}), dict):
            raise ValueError('Beat data must be an object.')
        if not isinstance(b.get('emphasis', []), list):
            raise ValueError('Beat emphasis must be a list of spoken words.')
        if 'word_start' in b:
            at = b['word_start']
            if isinstance(at, bool) or not isinstance(at, int) or not 0 <= at < len(words):
                raise ValueError('word_start must index an existing transcript word.')
            cursor = at + 1
        else:
            phrase = b.get('cue') or b.get('text', '')
            wanted = [token(t) for t in str(phrase).split() if token(t)]
            matches = [i for i in range(cursor, len(tokens) - len(wanted) + 1)
                       if wanted and tokens[i:i + len(wanted)] == wanted]
            if not matches:
                raise ValueError(f'Beat {index + 1} does not match the spoken transcript. '
                                 'Correct text/cue or set an explicit word_start.')
            if len(matches) > 1:
                raise ValueError(f'Beat {index + 1} has a repeated phrase; use a longer cue or word_start.')
            at = matches[0]
            cursor = at + len(wanted)
        if (index == 0 and at != 0) or (starts and at <= starts[-1]):
            raise ValueError('Beats must begin with the first word and then advance through the transcript.')
        starts.append(at)
    boundaries = [0.0]
    for at in starts[1:]:
        # Land before the next word, but do not swallow the previous word's end.
        earliest = words[at - 1]['end']
        preferred = max(earliest, words[at]['start'] - .04)
        boundary = round(preferred * FPS) / FPS
        if boundary <= boundaries[-1] or boundary >= duration:
            raise ValueError('Beat boundaries are too close to resolve at 30 fps.')
        boundaries.append(boundary)
    boundaries.append(duration)
    result = []
    for i, b in enumerate(specs):
        stop = starts[i + 1] if i + 1 < len(starts) else len(words)
        result.append({**b, 'id': f'beat-{i + 1}', 'index': i,
                       'caption_style': b.get('caption_style', 'sans' if b['layout'] == 'face' else 'serif'),
                       'data': dict(b.get('data', {})), 'emphasis': list(b.get('emphasis', [])),
                       'start': boundaries[i], 'end': boundaries[i + 1],
                       'words': words[starts[i]:stop]})
    return result


def make_captions(beats: list[dict]) -> list[dict]:
    result = []
    for b in beats:
        group = []
        groups = []
        for w in b['words']:
            # Two short words, or one long one. Avoid bridging a real pause.
            if group and (len(' '.join(x['text'] for x in group + [w])) > 15
                          or w['start'] - group[-1]['end'] > .18):
                groups.append(group)
                group = []
            group.append(w)
            if len(group) == 2 or re.search(r'[.!?]$', w['text']):
                groups.append(group)
                group = []
        if group:
            groups.append(group)
        for j, group in enumerate(groups):
            start = max(b['start'], group[0]['start'])
            following = groups[j + 1][0]['start'] if j + 1 < len(groups) else b['end']
            end = min(b['end'], following, group[-1]['end'] + .08)
            if end <= start:
                continue
            result.append({'text': ' '.join(w['text'] for w in group),
                           'start': start, 'end': end, 'layout': b['layout'],
                           'style': b['caption_style'], 'emphasis': b['emphasis']})
    return result


def srt(captions: list[dict]) -> str:
    def stamp(t):
        ms = round(t * 1000)
        hours, ms = divmod(ms, 3600000)
        minutes, ms = divmod(ms, 60000)
        seconds, ms = divmod(ms, 1000)
        return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'
    return '\n'.join(f'{i}\n{stamp(c["start"])} --> {stamp(c["end"])}\n{c["text"]}\n'
                     for i, c in enumerate(captions, 1))
