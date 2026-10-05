"""Session paths and fonts shared by the Desktop-derived editor."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path

EDIT = Path(os.environ.get('VIDEO_EDIT_DIR', 'edit')).resolve()
EDIT.mkdir(parents=True, exist_ok=True)

def font_path(bold=False):
    override = os.environ.get('VIDEO_FONT_BOLD' if bold else 'VIDEO_FONT')
    candidates = ([Path(override)] if override else []) + [
        Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / ('segoeuib.ttf' if bold else 'segoeui.ttf'),
        Path('/usr/share/fonts/truetype/dejavu') / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
        Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold else '/System/Library/Fonts/Supplemental/Arial.ttf'),
    ]
    for p in candidates:
        if p.is_file():
            return p.resolve()
    raise SystemExit('No usable font found. Set VIDEO_FONT and VIDEO_FONT_BOLD to .ttf files.')

def filter_path(path):
    return str(Path(path).resolve()).replace('\\', '/').replace(':', r'\:').replace("'", r"\'")

def load_edl(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not data.get('sources') or 'screen' not in data['sources']:
        raise ValueError('EDL sources must include screen (the reference video/microphone).')
    if not data.get('ranges'):
        raise ValueError('EDL ranges cannot be empty.')
    for key, value in data.get('sync', {}).items():
        data['sync'][key] = float(value)
        if not math.isfinite(data['sync'][key]):
            raise ValueError(f'Sync {key}: require a finite offset.')
    for key, value in data['sources'].items():
        p = Path(value)
        data['sources'][key] = str((path.parent / p).resolve() if not p.is_absolute() else p.resolve())
        if not Path(data['sources'][key]).is_file():
            raise FileNotFoundError(f'Source {key}: {data["sources"][key]}')
    stems = [Path(p).stem for p in data['sources'].values()]
    if len(set(stems)) != len(stems):
        raise ValueError('Use unique source filenames: transcript and audio caches are keyed by stem.')
    for i, r in enumerate(data['ranges']):
        if r.get('source') not in data['sources']:
            raise ValueError(f'Range {i}: unknown source')
        a, b = float(r['start']), float(r['end'])
        if not 0 <= a < b:
            raise ValueError(f'Range {i}: require 0 <= start < end')
        if r.get('style', 'cam') not in {'cam','screen','broll'}:
            raise ValueError(f'Range {i}: style must be cam, screen or broll')
        speed = float(r.get('speed', 1))
        if not 0.5 <= speed <= 2:
            raise ValueError(f'Range {i}: supported speed is 0.5..2')
        if r.get('style') == 'screen' and speed != 1:
            raise ValueError(f'Range {i}: screen/PiP speed changes are not supported')
        r.setdefault('audio_key', Path(data['sources'][r['source']]).stem)
        if r['audio_key'] != Path(data['sources'][r['source']]).stem:
            raise ValueError(f'Range {i}: audio_key must be the source filename stem; camera mic borrowing uses sync automatically.')
        for x, y in r.get('drops', []):
            if not math.isfinite(float(x)) or not math.isfinite(float(y)) or not float(x) < float(y):
                raise ValueError(f'Range {i}: drop windows need finite start < end.')
        face = r.get('face')
        if face:
            if face not in data['sources'] or face not in data.get('sync', {}):
                raise ValueError(f'Range {i}: PiP face needs a source and sync offset')
            if a - float(data['sync'][face]) < 0:
                raise ValueError(f'Range {i}: PiP would seek before camera starts')
    for family in ('overlays','music'):
        for item in data.get(family, []):
            p = Path(item['file'])
            item['file'] = str((path.parent / p).resolve() if not p.is_absolute() else p.resolve())
    return data
