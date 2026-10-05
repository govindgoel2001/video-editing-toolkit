"""Run the portable version of the original Remotion loading-screen speed-up."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'examples/remotion'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    p.add_argument('--loading-end',type=float,default=45)
    p.add_argument('--speed',type=float,default=8)
    p.add_argument('-o','--output',type=Path,required=True)
    a = p.parse_args()
    source = a.input.resolve(strict=True)
    if a.loading_end <= 0 or a.speed < 1:
        raise SystemExit('Require loading-end > 0 and speed >= 1.')
    package = PROJECT/'node_modules/@remotion/cli/package.json'
    if not package.is_file():
        raise SystemExit('Run npm ci in examples/remotion first.')
    duration = float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(source)],text=True))
    key = hashlib.sha256(f'{source}:{source.stat().st_mtime_ns}:{source.stat().st_size}'.encode()).hexdigest()[:16]
    public = PROJECT/'public/imported'
    public.mkdir(parents=True,exist_ok=True)
    copied = public/f'{key}{source.suffix}'
    if not copied.exists():
        shutil.copy2(source,copied)
    a.output = a.output.resolve()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    props = a.output.parent/f'{a.output.stem}.props.json'
    props.write_text(json.dumps({'input':f'imported/{copied.name}','sourceDurationSeconds':duration,
        'loadingEndSeconds':a.loading_end,'speedUp':a.speed}),encoding='utf-8')
    bin_name = json.loads(package.read_text())['bin']
    if isinstance(bin_name,dict):
        bin_name = bin_name['remotion']
    subprocess.run([shutil.which('node') or 'node',str(package.parent/bin_name),'render','src/index.jsx','SpeedRamp',
        str(a.output),'--props',str(props),'--concurrency','2'],cwd=PROJECT,check=True)
    print(a.output)

if __name__ == '__main__':
    main()
