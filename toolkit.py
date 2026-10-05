"""One entry point for the editing tools collected from Govind's Desktop."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / 'engine'

def run(script, *args, edit=None):
    env = {**os.environ, 'PYTHONUTF8':'1'}
    if edit:
        env['VIDEO_EDIT_DIR'] = str(Path(edit).resolve())
    subprocess.run([sys.executable, str(script), *map(str,args)], env=env, check=True)

def session(edl, edit):
    edl = Path(edl).resolve()
    edit = Path(edit).resolve() if edit else edl.parent / 'edit'
    os.environ['VIDEO_EDIT_DIR'] = str(edit)
    sys.path.insert(0, str(ENGINE))
    from config import load_edl
    data = load_edl(edl)
    canonical = edit / 'edl.json'
    canonical.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return edit, canonical, data

def doctor():
    missing = []
    print(f'Python {sys.version.split()[0]}')
    for name in ('ffmpeg','ffprobe','node','npm'):
        exe = shutil.which(name + '.cmd') if name == 'npm' and os.name == 'nt' else shutil.which(name)
        if exe:
            flag = '-version' if name.startswith('ff') else '--version'
            p = subprocess.run([exe, flag], capture_output=True, text=True, errors='replace')
            print(p.stdout.splitlines()[0] if p.stdout else name + ': installed')
        else:
            print(name + ': missing')
            if name.startswith('ff'):
                missing.append(name)
    for name in ('numpy','Pillow','scipy','faster-whisper','requests','librosa','matplotlib','playwright','manim','yt-dlp'):
        try:
            print(f'{name} {importlib.metadata.version(name)}')
        except importlib.metadata.PackageNotFoundError:
            print(f'{name}: not installed' + (' (optional)' if name not in ('numpy','Pillow','scipy','faster-whisper') else ''))
            if name in ('numpy','Pillow','scipy','faster-whisper'):
                missing.append(name)
    print('HyperFrames: ' + ('installed' if (ROOT/'node_modules/hyperframes').is_dir() else 'run npm ci'))
    if missing:
        raise SystemExit('Missing core tools: ' + ', '.join(missing))

def prepare(edit, data, args):
    run(ENGINE/'transcribe_local.py', *data['sources'].values(), '--edit-dir', edit,
        '--model', args.model, '--device', args.device,
        '--compute-type', 'int8' if args.device == 'cpu' else 'int8_float16', edit=edit)
    for src in data['sources'].values():
        run(ENGINE/'silences.py', src, edit=edit)
    run(ROOT/'vendor/video-use/helpers/pack_transcripts.py', '--edit-dir', edit)

def preflight(data):
    durations = {}
    for key, source in data['sources'].items():
        info = json.loads(subprocess.check_output([
            'ffprobe','-v','error','-show_entries','stream=codec_type:format=duration',
            '-of','json',source], text=True))
        kinds = {s['codec_type'] for s in info.get('streams', [])}
        if not {'video','audio'} <= kinds:
            raise ValueError(f'Source {key} needs a video track and an audio track for this editor.')
        durations[key] = float(info['format']['duration'])
    for i, r in enumerate(data['ranges']):
        if float(r['end']) > durations[r['source']] + 1/30:
            raise ValueError(f'Range {i} ends after source {r["source"]} ({durations[r["source"]]:.3f}s).')
        if r.get('face') and float(r['end']) - float(data['sync'][r['face']]) > durations[r['face']] + 1/30:
            raise ValueError(f'Range {i} ends after the synchronized PiP camera.')
    for family in ('overlays','music'):
        for item in data.get(family, []):
            if not Path(item['file']).is_file():
                raise FileNotFoundError(f'{family}: {item["file"]}')

def render(args):
    edit, edl, data = session(args.edl, args.edit_dir)
    preflight(data)
    if args.prepare:
        prepare(edit, data, args)
    # Assets are generated locally, instead of shipping session-specific images.
    run(ENGINE/'make_pip_assets.py', edit=edit)
    run(ENGINE/'sfx.py', edit=edit)
    flags = ['--draft'] if args.draft else []
    run(ENGINE/'extract_only.py', edl, *flags, edit=edit)
    clips = edit / ('clips_draft' if args.draft else 'clips')
    run(ENGINE/'captions.py', edl, '-o', edit/'master.srt', '--clips', clips, edit=edit)
    run(ROOT/'tools/subtitles.py', edl, '--clips', clips, '-o', edit/'final.srt', edit=edit)
    output = Path(args.output).resolve() if args.output else edit/'final.mp4'
    output.parent.mkdir(parents=True, exist_ok=True)
    run(ENGINE/'build.py', edl, '-o', output, *flags, edit=edit)
    run(ENGINE/'omissions.py', edl, edit=edit)
    run(ENGINE/'qc.py', output, '--edl', edl, '--clips', clips, edit=edit)
    print(f'Finished: {output}\nReadable subtitles: {edit / "final.srt"}')

def main():
    argv = sys.argv[1:]
    forwarded = []
    if argv[:1] == ['engine'] and '--' in argv:
        split = argv.index('--')
        argv, forwarded = argv[:split], argv[split+1:]
    ap = argparse.ArgumentParser(description=__doc__)
    sp = ap.add_subparsers(dest='command', required=True)
    sp.add_parser('doctor', help='Check core and optional dependencies')
    r = sp.add_parser('render', help='EDL -> captions, PiP, graphics, mix and QC')
    r.add_argument('edl', type=Path)
    r.add_argument('--edit-dir', type=Path)
    r.add_argument('-o','--output', type=Path)
    r.add_argument('--draft', action='store_true')
    r.add_argument('--prepare', action='store_true', help='Transcribe and detect silences first')
    r.add_argument('--model', default='medium')
    r.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    t = sp.add_parser('transcribe')
    t.add_argument('videos', nargs='+', type=Path)
    t.add_argument('--edit-dir', type=Path, required=True)
    t.add_argument('--model', default='medium')
    t.add_argument('--device', default='cpu', choices=['cpu','cuda'])
    t.add_argument('--language', default='en')
    s = sp.add_parser('sync', help='Propose offsets; never silently replace the EDL')
    s.add_argument('edl', type=Path)
    s.add_argument('--edit-dir', type=Path)
    p = sp.add_parser('pack')
    p.add_argument('--edit-dir', type=Path, required=True)
    d = sp.add_parser('demo', help='Generate original synthetic media and run the complete editor')
    d.add_argument('--dir', type=Path, default=ROOT/'workspaces/demo')
    d.add_argument('--graphics', action='store_true', help='Include a rendered HyperFrames alpha card')
    g = sp.add_parser('graphics')
    g.add_argument('cards', type=Path)
    g.add_argument('--output-dir', type=Path, required=True)
    g.add_argument('--only', nargs='*')
    a = sp.add_parser('engine', help='Run a Desktop-derived tool in a chosen session')
    a.add_argument('script', choices=['autocut','silences','mix','qc','omissions','make_frame_assets','make_pip_assets','sfx','captions','jev'])
    a.add_argument('--edit-dir', type=Path, required=True)
    args = ap.parse_args(argv)
    if args.command == 'doctor':
        doctor()
    elif args.command == 'render':
        render(args)
    elif args.command == 'transcribe':
        run(ENGINE/'transcribe_local.py', *args.videos, '--edit-dir', args.edit_dir,
            '--model', args.model, '--device', args.device, '--language', args.language,
            '--compute-type', 'int8' if args.device == 'cpu' else 'int8_float16')
    elif args.command == 'sync':
        edit, edl, _ = session(args.edl, args.edit_dir)
        run(ROOT/'tools/sync_sources.py', edl, edit=edit)
    elif args.command == 'pack':
        run(ROOT/'vendor/video-use/helpers/pack_transcripts.py', '--edit-dir', args.edit_dir)
    elif args.command == 'demo':
        run(ROOT/'tools/demo.py', '--dir', args.dir, *(['--graphics'] if args.graphics else []))
    elif args.command == 'graphics':
        run(ROOT/'graphics/gen.py', args.cards, '--output-dir', args.output_dir,
            *(['--only', *args.only] if args.only else []))
    elif args.command == 'engine':
        run(ENGINE/f'{args.script}.py', *forwarded, edit=args.edit_dir)

if __name__ == '__main__':
    try:
        main()
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
