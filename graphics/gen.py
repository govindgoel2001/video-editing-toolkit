"""Render Desktop title-card templates with the locally pinned HyperFrames CLI."""
from __future__ import annotations
import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from cards import CSS, body, timeline

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent

def cli():
    entry = ROOT/'node_modules/hyperframes/dist/cli.js'
    package = ROOT/'node_modules/hyperframes/package.json'
    if not package.is_file():
        raise SystemExit('Run npm ci in the toolkit root first.')
    bin_name = json.loads(package.read_text())['bin']
    if isinstance(bin_name, dict):
        bin_name = bin_name.get('hyperframes') or next(iter(bin_name.values()))
    return [shutil.which('node') or 'node', str(package.parent/bin_name)]

def render(cards, output, only=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    template = (HERE/'template.html').read_text(encoding='utf-8')
    gsap = ROOT/'node_modules/gsap/dist/gsap.min.js'
    ids = set()
    for c in cards:
        name = c['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name) or name in ids:
            raise ValueError('Card IDs must be unique letters, digits, underscores or hyphens.')
        ids.add(name)
        if c['type'] not in CSS or not 2 <= float(c['dur']) <= 120:
            raise ValueError(f'Invalid card type/duration: {name}')
        if only and name not in only:
            continue
        job = output/'projects'/name
        job.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gsap, job/'gsap.min.js')
        safe = {k:html.escape(v) if isinstance(v,str) and k not in ('id','type') else v for k,v in c.items()}
        doc = (template.replace('https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js','gsap.min.js')
               .replace('__ID__',name).replace('__DUR__',str(c['dur']))
               .replace('__CSS__',CSS[c['type']]).replace('__BODY__',body(safe)).replace('__TL__',timeline(c)))
        (job/'index.html').write_text(doc, encoding='utf-8')
        shutil.copy2(HERE/'DESIGN.md', job/'DESIGN.md')
        env = {**os.environ,'HYPERFRAMES_NO_UPDATE_CHECK':'1'}
        dest = output/f'{name}.mov'
        subprocess.run([*cli(),'lint',str(job)], env=env, check=True)
        subprocess.run([*cli(),'check',str(job)], env=env, check=True)
        subprocess.run([*cli(),'render',str(job),'--format','mov','--output',str(dest),'--workers','2'], env=env, check=True)
        metadata = subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=pix_fmt:format=duration','-of','json',str(dest)], text=True)
        info = json.loads(metadata)
        if 'a' not in info['streams'][0]['pix_fmt'] or abs(float(info['format']['duration'])-float(c['dur'])) > .1:
            raise RuntimeError(f'Unexpected alpha/duration: {dest}')
        print(f'Alpha card: {dest}', flush=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cards', type=Path)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--only', nargs='*')
    a = p.parse_args()
    render(json.loads(a.cards.read_text(encoding='utf-8')), a.output_dir, set(a.only or []))

if __name__ == '__main__':
    main()
