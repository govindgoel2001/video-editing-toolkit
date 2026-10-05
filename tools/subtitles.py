"""Readable sidecar captions, using the same microphone, cuts and frame grid as the render."""
import argparse
from pathlib import Path
import sys
import textwrap

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine'))
import captions
from config import load_edl

def stamp(t):
    ms = round(max(0,t)*1000)
    h,ms = divmod(ms,3600000)
    m,ms = divmod(ms,60000)
    s,ms = divmod(ms,1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('edl', type=Path)
    p.add_argument('--clips', type=Path, required=True)
    p.add_argument('-o','--output', type=Path, required=True)
    a = p.parse_args()
    captions.MAX_WORDS = 12
    captions.MIN_SHOW = .12
    captions.UPPERCASE = False
    cues = captions.build(load_edl(a.edl), a.clips)
    a.output.write_text('\n'.join(f'{i}\n{stamp(start)} --> {stamp(end)}\n{textwrap.fill(text,42)}\n' for i,(start,end,text) in enumerate(cues,1)), encoding='utf-8')
    print(f'{len(cues)} readable cues -> {a.output}')

if __name__ == '__main__':
    main()
