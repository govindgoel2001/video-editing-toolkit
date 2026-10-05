"""Original test fixtures, clearly labelled and entirely generated locally."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .pipeline import command


def font(size):
    for path in ('C:/Windows/Fonts/seguisb.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def create(folder: Path) -> Path:
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    specs = [
        ('This is synthetic footage.', 'face', None, {}),
        ('Here is Company Brain.', 'graphic', 'logo-pop', {'title': 'Company Brain', 'label': 'DEMO FIXTURE'}),
        ('Inspect a source capture.', 'graphic', 'receipt', {'title': 'Read the source', 'label': 'DEMO FIXTURE', 'image': 'receipt.png', 'highlight_y': .5}),
        ('Count three local tools.', 'split', 'counter', {'value': '3', 'label': 'Local tools'}),
        ('See the sample repository.', 'graphic', 'repo-card', {'name': 'demo/toolkit', 'description': 'Synthetic sample; no real repository statistics.', 'language': 'Python'}),
        ('Run the local editor.', 'split', 'terminal', {'command': 'python toolkit.py reel --demo', 'lines': ['Load word timings', 'Render portrait video', 'Verify continuous audio']}),
        ('Agents explain the workflow.', 'graphic', 'agents', {'count': 3, 'targets': ['Source', 'Script', 'Edit'], 'label': 'Demo workflow'}),
        ('Check sound and captions.', 'split', 'checklist', {'items': [{'text': 'Audio timing'}, {'text': 'Caption fit'}, {'text': 'Frame count'}], 'verdict': 'DEMO CHECKLIST'}),
        ('Read the quality report.', 'graphic', 'report', {'rows': [{'label': 'Canvas', 'value': '1080 x 1920'}, {'label': 'Frame rate', 'value': '30 fps'}, {'label': 'Audio', 'value': '48 kHz'}]}),
        ('Scan every visual frame.', 'graphic', 'scan', {'label': 'Demo visual checks', 'issues': ['Caption overflow', 'Missing assets', 'Off-canvas text']}),
        ('Watch the captured page.', 'graphic', 'page-scroll', {'title': 'Source page', 'source_label': 'Synthetic capture fixture', 'video': 'page.mp4'}),
        ('Your next reel starts.', 'face', None, {}),
    ]
    words, beats = [], []
    for i, (text, layout, scene, data) in enumerate(specs):
        beat_words = text.split()
        for j, word in enumerate(beat_words):
            start = i * 3 + .12 + j * .55
            words.append({'text': word, 'start': round(start, 3), 'end': round(start + .42, 3), 'type': 'word'})
        beats.append({'text': text, 'layout': layout, 'scene': scene, 'data': data,
                      'emphasis': ['Brain', 'three', 'local', 'quality']})
    duration = len(specs) * 3
    speech = np.zeros(duration * 48000, dtype=np.float32)
    for i, w in enumerate(words):
        length = round((w['end'] - w['start']) * 48000)
        t = np.arange(length) / 48000
        # Vary the envelope and frequency so the audio sync check has a useful control.
        envelope = np.sin(np.pi * np.arange(length) / length) ** 2
        sound = (.15 + .04 * (i % 4)) * envelope * (np.sin(2 * np.pi * (170 + (i * 37) % 430) * t)
                 + .35 * np.sin(2 * np.pi * (730 + i * 13) * t))
        at = round(w['start'] * 48000)
        speech[at:at + length] += sound
    with wave.open(str(folder / 'voice.wav'), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000)
        wav.writeframes((speech * 32767).astype('<i2').tobytes())
    encoder = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                '-s', '540x960', '-r', '30', '-i', '-', '-i', str(folder / 'voice.wav'),
                                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                                '-c:a', 'aac', '-b:a', '128k', '-t', str(duration), str(folder / 'presenter.mp4')],
                               stdin=subprocess.PIPE)
    try:
        for frame in range(duration * 30):
            image = Image.new('RGB', (540, 960), '#dedfd9')
            draw = ImageDraw.Draw(image)
            draw.rectangle((36, 40, 504, 188), fill='#fafafa')
            draw.text((62, 66), 'SYNTHETIC FIXTURE', font=font(30), fill='#111114')
            draw.text((62, 114), 'No real presenter or voice', font=font(23), fill='#52525b')
            draw.rounded_rectangle((80, 580, 460, 970), 140, fill='#111114')
            draw.ellipse((136, 250, 404, 602), fill='#d7a886')
            draw.arc((130, 237, 412, 500), 180, 360, fill='#111114', width=48)
            draw.ellipse((204, 394, 225, 410), fill='#111114')
            draw.ellipse((315, 394, 336, 410), fill='#111114')
            mouth = 5 + (frame % 12)
            draw.ellipse((238, 482 - mouth, 304, 482 + mouth), fill='#704739')
            draw.rectangle((60, 800, 480, 856), fill='#ff5c00')
            draw.text((86, 816), 'SCENE LIBRARY TEST', font=font(25), fill='#ffffff')
            encoder.stdin.write(image.tobytes())
    finally:
        encoder.stdin.close()
    if encoder.wait():
        raise RuntimeError('Synthetic presenter encoding failed.')
    receipt = Image.new('RGB', (900, 1000), '#ffffff')
    draw = ImageDraw.Draw(receipt)
    draw.text((70, 62), 'DEMO CAPTURE', font=font(44), fill='#b84000')
    draw.text((70, 150), 'Source evidence', font=font(56), fill='#111114')
    for i, line in enumerate(('A real job supplies its own screenshot.', 'This image is only a test fixture.',
                              'No claims, statistics or receipts invented.')):
        draw.text((70, 320 + i * 150), line, font=font(32), fill='#52525b')
    receipt.save(folder / 'receipt.png')
    page = Image.new('RGB', (540, 1800), '#fafafa')
    draw = ImageDraw.Draw(page)
    draw.text((40, 70), 'DEMO PAGE', font=font(42), fill='#b84000')
    for i in range(8):
        draw.rounded_rectangle((40, 200 + i * 185, 500, 345 + i * 185), 15, fill='#ffffff', outline='#e4e4e7', width=2)
        draw.text((65, 235 + i * 185), f'Synthetic section {i + 1}', font=font(26), fill='#111114')
    page.save(folder / 'page.png')
    command(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', folder / 'page.png', '-vf',
             "crop=540:960:0:'min(n*4,840)',fps=30", '-frames:v', 120, '-c:v', 'libx264',
             '-preset', 'veryfast', '-pix_fmt', 'yuv420p', folder / 'page.mp4'])
    (folder / 'words.json').write_text(json.dumps({'words': words}, indent=2), encoding='utf-8')
    job = {'version': 1, 'presenter': 'presenter.mp4', 'transcript': 'words.json',
           'keyword': 'DEMO', 'split': {'simple_video_top': 740}, 'sfx': True, 'beats': beats}
    job_path = folder / 'reel.json'
    job_path.write_text(json.dumps(job, indent=2), encoding='utf-8')
    return job_path
