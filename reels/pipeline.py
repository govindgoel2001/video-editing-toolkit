"""Prepare and render a local continuous presenter into a word-timed portrait reel."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave
import zipfile

from .timing import FPS, align_beats, make_captions, read_words, srt

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SR = 48000
PROJECT_FILES = ('layout.css', 'proof.css', 'workflow.css', 'composition.js',
                 'scenes-proof.js', 'scenes-workflow.js', 'DESIGN.md')


def command(argv, **kwargs):
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def probe(path: Path) -> dict:
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], text=True))


def local_file(value, base: Path) -> Path:
    if not isinstance(value, str) or not value.strip() or re.match(r'^[a-z]+://', value, re.I):
        raise ValueError('Media paths must refer to local files. Download/capture a source first.')
    path = Path(value).expanduser()
    path = (base / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Missing media: {path}')
    return path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def hf_cli():
    package = ROOT / 'node_modules/hyperframes/package.json'
    if not package.is_file():
        raise FileNotFoundError('Run npm ci in the toolkit root before rendering reels.')
    entry = json.loads(package.read_text())['bin']
    if isinstance(entry, dict):
        entry = entry.get('hyperframes') or next(iter(entry.values()))
    return [shutil.which('node') or 'node', str(package.parent / entry)]


def validate_job(job: dict, base: Path) -> Path:
    if job.get('version') != 1:
        raise ValueError('Reel job version must be 1.')
    presenter = local_file(job.get('presenter'), base)
    if not isinstance(job.get('beats'), list) or not job['beats']:
        raise ValueError('A job needs an ordered beats list.')
    for family in ('split', 'caption_positions'):
        options = job.get(family, {})
        if not isinstance(options, dict):
            raise ValueError(f'{family} must be an object.')
        for value in options.values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'{family} coordinates must be finite numbers.')
    for name in ('transcript', 'cutout'):
        if job.get(name):
            local_file(job[name], base)
    if job.get('music'):
        music = job['music']
        if not isinstance(music, dict):
            raise ValueError('music must be an object with file and optional gain_db.')
        local_file(music.get('file'), base)
        gain = float(music.get('gain_db', -22))
        if not math.isfinite(gain) or not -40 <= gain <= -12:
            raise ValueError('Music gain_db must be between -40 and -12 relative to speech.')
    return presenter


def normalize_presenter(source: Path, output: Path, frames: int, info: dict, draft: bool):
    stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
    filters = []
    if stream.get('color_transfer') in {'arib-std-b67', 'smpte2084'}:
        # Phone HDR is converted once, before Chrome or social video encoding.
        filters += ['zscale=t=linear:npl=100', 'format=gbrpf32le',
                    'tonemap=tonemap=mobius:desat=0', 'zscale=p=bt709:t=bt709:m=bt709:r=tv']
    filters += ['fps=30', 'scale=1080:1920:force_original_aspect_ratio=increase',
                'crop=1080:1920', 'setsar=1', 'tpad=stop_mode=clone:stop_duration=0.1', 'format=yuv420p']
    command(['ffmpeg', '-v', 'error', '-y', '-i', source, '-map', '0:v:0', '-an',
             '-vf', ','.join(filters), '-frames:v', frames, '-c:v', 'libx264',
             '-preset', 'veryfast' if draft else 'fast', '-crf', '18',
             '-g', '30', '-keyint_min', '30', '-sc_threshold', '0',
             '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
             '-movflags', '+faststart', output])


def extract_narration(source: Path, output: Path, frames: int):
    command(['ffmpeg', '-v', 'error', '-y', '-i', source, '-map', '0:a:0', '-vn',
             '-af', f'aresample=48000,apad,atrim=end_sample={frames * (SR // FPS)},asetpts=N/SR/TB',
             '-ar', SR, '-ac', '2', '-c:a', 'pcm_s16le', output])


def prepare(job_path: Path, folder: Path, model='medium', language='auto', draft=False):
    job_path, folder = job_path.resolve(), folder.resolve()
    job = json.loads(job_path.read_text(encoding='utf-8-sig'))
    source = validate_job(job, job_path.parent)
    info = probe(source)
    kinds = {s['codec_type'] for s in info['streams']}
    if not {'audio', 'video'} <= kinds:
        raise ValueError('Presenter needs both video and continuous narration audio.')
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    duration = float(video.get('duration') or info['format']['duration'])
    if not math.isfinite(duration) or not .5 <= duration <= 180:
        raise ValueError('Presenter length must be 0.5 to 180 seconds.')
    frames = math.ceil(duration * FPS - 1e-5)
    duration = frames / FPS
    project = folder / 'project'
    assets = project / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    if job.get('transcript'):
        transcript = local_file(job['transcript'], job_path.parent)
    else:
        command([sys.executable, ROOT / 'engine/transcribe_local.py', source,
                 '--edit-dir', folder, '--model', model, '--language', language,
                 '--device', 'cpu', '--compute-type', 'int8'])
        transcript = folder / 'transcripts' / f'{source.stem}.json'
    words = read_words(json.loads(transcript.read_text(encoding='utf-8-sig')), duration)
    beats = align_beats(job['beats'], words, duration)
    copied = {}

    def copy_asset(value):
        path = local_file(value, job_path.parent)
        key = digest(path)
        relative = f'assets/{key[:16]}{path.suffix.lower()}'
        destination = project / relative
        if path != destination.resolve():
            shutil.copy2(path, destination)
        copied[relative] = {'sha256': key, 'source': str(path)}
        return relative

    cutout = None
    if job.get('cutout'):
        path = local_file(job['cutout'], job_path.parent)
        if float(probe(path)['format']['duration']) < duration - 1 / FPS:
            raise ValueError('Cutout must cover the continuous presenter duration.')
        cutout = copy_asset(job['cutout'])
    for b in beats:
        for field in ('image', 'logo', 'video'):
            if b['data'].get(field):
                original = local_file(b['data'][field], job_path.parent)
                if field == 'video':
                    media = probe(original)
                    offset = float(b['data'].get('from', 0))
                    if not math.isfinite(offset) or offset < 0 or offset + b['end'] - b['start'] > float(media['format']['duration']) + 1 / FPS:
                        raise ValueError('Page recording does not cover the beat at its requested from offset.')
                b['data'][field] = copy_asset(b['data'][field])
    normalize_presenter(source, assets / 'presenter.mp4', frames, info, draft)
    voice = folder / 'narration.wav'
    extract_narration(source, voice, frames)
    captions = make_captions(beats)
    payload = {'duration': duration, 'keyword': job.get('keyword', ''), 'beats': beats,
               'words': words, 'captions': captions, 'split': job.get('split', {}),
               'caption_positions': job.get('caption_positions', {})}
    for filename in PROJECT_FILES:
        shutil.copy2(HERE / filename, project / filename)
    shutil.copytree(HERE / 'fonts', assets / 'fonts', dirs_exist_ok=True)
    gsap = ROOT / 'node_modules/gsap/dist/gsap.min.js'
    if not gsap.is_file():
        raise FileNotFoundError('Run npm ci before preparing a reel project.')
    shutil.copy2(gsap, project / 'gsap.min.js')
    cutout_html = (f'<div id="cutout-window"><video id="cutout" class="clip" src="{cutout}" '
                   f'data-start="0" data-duration="{duration}" data-track-index="2" '
                   'data-media-start="0" data-volume="0" muted playsinline></video></div>') if cutout else ''
    template = (HERE / 'template.html').read_text(encoding='utf-8')
    page_media = ''.join(
        f'<video id="page-video-{b["index"]}" class="clip" src="{b["data"]["video"]}" '
        f'data-start="{b["start"]}" data-duration="{b["end"] - b["start"]}" '
        f'data-track-index="{b["index"] + 10}" data-media-start="{b["data"].get("from", 0)}" '
        'data-volume="0" muted playsinline></video>'
        for b in beats if b.get('scene') == 'page-scroll' and b['data'].get('video'))
    (project / 'index.html').write_text(template.replace('__DURATION__', str(duration))
                                      .replace('__CUTOUT__', cutout_html)
                                      .replace('__PAGE_MEDIA__', page_media), encoding='utf-8')
    # job.js is data, and scene builders insert user text with textContent.
    (project / 'job.js').write_text('window.REEL = ' + json.dumps(payload, ensure_ascii=True)
                                   .replace('</', '<\\/') + ';\n', encoding='utf-8')
    (folder / 'captions.srt').write_text(srt(captions), encoding='utf-8')
    manifest = {'version': 1, 'frames': frames, 'sample_rate': SR, 'fps': FPS,
                **payload, 'presenter_sha256': digest(source), 'assets': copied}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    shutil.copy2(transcript, folder / 'word-timings.json')
    (folder / 'job.json').write_text(json.dumps(job, indent=2), encoding='utf-8')
    return job, manifest, project, voice


def mix_audio(job: dict, manifest: dict, folder: Path, base: Path, voice: Path) -> Path:
    import numpy as np
    from tools.music import pcm, render as music_bed
    data = pcm(voice)
    if job.get('music'):
        m = job['music']
        music_path = local_file(m['file'], base)
        bed = folder / 'music-bed.wav'
        music_bed(voice, [{'at': 0, 'file': str(music_path), 'gain_db': m.get('gain_db', -22)}],
                  manifest['duration'], bed, base)
        data += pcm(bed)[:len(data)]
    if job.get('sfx', False):
        from tools.extended_sfx import lib
        effects = np.zeros_like(data)
        for b in manifest['beats'][1:]:
            effect = lib['swish'] * 10 ** (-30 / 20)
            at = round(b['start'] * SR)
            take = min(len(effect), len(data) - at)
            effects[at:at + take] += effect[:take, None]
        with wave.open(str(folder / 'sfx-stem.wav'), 'wb') as stem:
            stem.setnchannels(2); stem.setsampwidth(2); stem.setframerate(SR)
            stem.writeframes((np.clip(effects, -.999, .999) * 32767).astype('<i2').tobytes())
        data += effects
    # Preserve the mixed waveform before loudness normalization instead of
    # clipping a hot source plus its bed/effects into the temporary PCM file.
    peak = float(np.max(np.abs(data)))
    if peak > .999:
        data *= .999 / peak
    mix = folder / 'mix.wav'
    with wave.open(str(mix), 'wb') as audio:
        audio.setnchannels(2); audio.setsampwidth(2); audio.setframerate(SR)
        audio.writeframes((np.clip(data, -.999, .999) * 32767).astype('<i2').tobytes())
    scan = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(mix), '-vn',
                           '-af', 'loudnorm=I=-14:TP=-1.5:LRA=9:print_format=json', '-f', 'null', '-'],
                          capture_output=True, text=True, check=True).stderr
    measurement = json.loads(scan[scan.rfind('{'):scan.rfind('}') + 1])
    if not math.isfinite(float(measurement['input_i'])):
        raise ValueError('Narration is silent; cannot normalize a silent reel.')
    filters = ('loudnorm=I=-14:TP=-1.5:LRA=9:linear=true:'
               f'measured_I={measurement["input_i"]}:measured_TP={measurement["input_tp"]}:'
               f'measured_LRA={measurement["input_lra"]}:measured_thresh={measurement["input_thresh"]}:'
               f'offset={measurement["target_offset"]},aresample=48000,apad,'
               f'atrim=end_sample={manifest["frames"] * 1600},asetpts=N/SR/TB')
    normalized = folder / 'mix-normalized.wav'
    command(['ffmpeg', '-v', 'error', '-y', '-i', mix, '-af', filters, '-ar', SR,
             '-ac', 2, '-c:a', 'pcm_s16le', normalized])
    return normalized


def quality_check(output: Path, manifest: dict, voice: Path, normalized: Path) -> dict:
    # Reuse the editor's control-based dropout detector and envelope sync check.
    from engine.qc import pcm, best_lag, count_dropouts
    info = probe(output)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    failures = []
    frames = int(video.get('nb_frames', 0))
    if (video['width'], video['height'], video['r_frame_rate']) != (1080, 1920, '30/1'):
        failures.append('Expected 1080x1920 at 30 fps.')
    if frames != manifest['frames']:
        failures.append(f'Frame count {frames} differs from expected {manifest["frames"]}.')
    with wave.open(str(normalized), 'rb') as wav:
        samples = wav.getnframes()
        if wav.getframerate() != SR or samples != frames * 1600:
            failures.append('PCM audio must contain exactly 1600 samples per video frame.')
    if int(audio['sample_rate']) != SR:
        failures.append('Delivery audio is not 48 kHz.')
    if abs(float(info['format']['duration']) - manifest['duration']) > .07:
        failures.append('Delivery duration differs from the continuous source.')
    log = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(output),
                          '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True, check=True).stderr
    tail = log[log.rfind('Summary:'):]
    values = {}
    for label in ('I', 'Peak'):
        match = re.search(rf'{label}:\s*(-?\d+(?:\.\d+)?)', tail)
        values[label] = float(match.group(1)) if match else None
    if values['I'] is None or not -16 <= values['I'] <= -12:
        failures.append(f'Loudness outside -16..-12 LUFS: {values["I"]}.')
    if values['Peak'] is None or values['Peak'] > -.5:
        failures.append(f'True peak exceeds -0.5 dBTP: {values["Peak"]}.')
    out, control = pcm(str(output)), pcm(str(voice))
    lag, correlation = best_lag(out, control)
    if correlation < .55 or abs(lag) > .08:
        failures.append(f'Audio sync not verified: {lag:.3f}s lag, correlation {correlation:.3f}.')
    drops, reference_drops = count_dropouts(out), count_dropouts(control)
    if drops > reference_drops + 2:
        failures.append(f'{drops} audio dropouts versus {reference_drops} in the source.')
    command(['ffmpeg', '-v', 'error', '-i', output, '-f', 'null', '-'], capture_output=True)
    report = {'passed': not failures, 'frames': frames, 'pcm_samples': samples,
              'lufs': values['I'], 'true_peak_dbtp': values['Peak'],
              'sync_lag_seconds': lag, 'sync_correlation': correlation,
              'dropouts': drops, 'source_dropouts': reference_drops, 'failures': failures}
    (output.parent / 'qc.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if failures:
        raise ValueError('Reel QC failed: ' + ' '.join(failures))
    return report


def freelancer_pack(job: dict, manifest: dict, folder: Path, project: Path) -> Path:
    """Bundle an editable, self-contained project and separate continuous stems."""
    (folder / 'beats-with-timings.json').write_text(
        json.dumps({'keyword': manifest['keyword'], 'duration': manifest['duration'],
                    'beats': manifest['beats']}, indent=2), encoding='utf-8')
    readme = '''# Editable portrait reel

The project/ folder contains the 1080x1920 composition, licensed fonts,
muted continuous presenter video, optional alpha cutout and source captures.
Edit project/job.js to change copy or scene data; preserve its spoken timings.
beats-with-timings.json and word-timings.json contain the timed edit plan.
captions.srt is supplied for a separate editor. The HTML already burns captions.

Install Node.js 22+ and FFmpeg, then run from the extracted folder:

    npx --yes hyperframes@0.8.40 check project
    npx --yes hyperframes@0.8.40 render project --output visuals.mp4 --fps 30 --quality high --workers 2
    ffmpeg -y -i visuals.mp4 -i mix-normalized.wav -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -ar 48000 -t __DURATION__ -movflags +faststart final.mp4

mix-normalized.wav is the finished audio mix. Use it once. narration.wav is
the separate presenter voice; sfx-stem.wav and music-bed.wav are included
when selected for this job. Do not layer the stems over the finished mix.
qc.json records checks on the supplied render, not on later edits.
manifest.json records asset hashes and provenance for this private job.
'''.replace('__DURATION__', str(manifest['duration']))
    output = folder / 'freelancer-pack.zip'
    current_files = {*PROJECT_FILES, 'index.html', 'job.js', 'gsap.min.js',
                     'assets/presenter.mp4', *manifest['assets']}
    current_files.update(p.relative_to(project).as_posix()
                         for p in (project / 'assets/fonts').rglob('*') if p.is_file())
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('README.md', readme)
        for name in sorted(current_files):
            path = project / name
            archive.write(path, path.relative_to(folder))
        names = ['manifest.json', 'beats-with-timings.json', 'word-timings.json',
                 'captions.srt', 'narration.wav', 'mix-normalized.wav', 'qc.json']
        if job.get('sfx', False):
            names.append('sfx-stem.wav')
        if job.get('music'):
            names.append('music-bed.wav')
        for name in names:
            archive.write(folder / name, name)
    return output


def render_job(job_path: Path, folder: Path, *, model='medium', language='auto',
               draft=False, no_render=False, pack=True):
    folder = folder.resolve()
    job, manifest, project, voice = prepare(job_path, folder, model, language, draft)
    env = {**os.environ, 'HYPERFRAMES_NO_UPDATE_CHECK': '1'}
    command([*hf_cli(), 'lint', project], env=env)
    command([*hf_cli(), 'check', project], env=env)
    if no_render:
        print(f'Prepared and checked: {project}', flush=True)
        return project
    silent = folder / 'visuals.mp4'
    command([*hf_cli(), 'render', project, '--output', silent, '--fps', FPS,
             '--quality', 'draft' if draft else 'high', '--workers', 2], env=env)
    normalized = mix_audio(job, manifest, folder, job_path.resolve().parent, voice)
    output = folder / 'final.mp4'
    command(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-i', normalized,
             '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
             '-ar', SR, '-t', manifest['duration'], '-movflags', '+faststart', output])
    report = quality_check(output, manifest, voice, normalized)
    if pack:
        freelancer_pack(job, manifest, folder, project)
    print(f'Finished: {output}\nQC: {report["lufs"]} LUFS; '
          f'{report["sync_lag_seconds"] * 1000:.0f} ms audio lag; {report["frames"]} frames.', flush=True)
    return output
