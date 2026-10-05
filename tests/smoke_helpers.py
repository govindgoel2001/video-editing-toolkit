"""Optional installed-helper smoke checks; run after `toolkit.py demo`.

    python tests/smoke_helpers.py --capture --remotion
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import wave

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'workspaces/helper-checks'

def run(*args):
    subprocess.run(list(map(str,args)), cwd=ROOT, check=True)

def tool(name, *args):
    run(sys.executable, ROOT/'tools'/f'{name}.py', *args)

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', action='store_true')
    p.add_argument('--remotion', action='store_true')
    a = p.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    video = ROOT/'workspaces/demo/screen.mp4'
    if not video.is_file():
        raise SystemExit('Run python toolkit.py demo first.')
    still = WORK/'frame.png'
    run('ffmpeg','-v','error','-y','-ss','2','-i',video,'-frames:v','1',still)
    tool('thumbnail','--title','VIDEO TOOLKIT','--subtitle','One shared workflow',
         '--badge','FFmpeg + HyperFrames','--screenshot',still,'-o',WORK/'thumbnail.png')
    voice = WORK/'voice.wav'
    run('ffmpeg','-v','error','-y','-i',video,'-vn','-ac','1','-ar','48000',voice)
    music = WORK/'music.wav'
    run('ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=120:sample_rate=48000:duration=1',music)
    cues = WORK/'cues.json'
    cues.write_text(json.dumps([{'at':0,'file':'music.wav','tape_stop':True},
                               {'at':3,'file':'music.wav'}]))
    tool('music',voice,cues,'--duration','8','-o',WORK/'bed.wav')
    with wave.open(str(WORK/'bed.wav')) as w:
        assert (w.getnchannels(),w.getframerate(),w.getnframes()) == (2,48000,384000)
    tool('extended_sfx','--output-dir',WORK/'sfx')
    assert len(list((WORK/'sfx').glob('*.wav'))) == 14
    run(sys.executable,ROOT/'toolkit.py','sync',ROOT/'workspaces/demo/edl.json',
        '--edit-dir',WORK/'sync')
    proposal = json.loads((WORK/'sync/sync-proposal.json').read_text())
    assert abs(proposal['clips']['camera']['offset_s']) <= .02
    run(sys.executable, ROOT/'vendor/watch/scripts/watch.py',video,'--no-whisper',
        '--max-frames','4','--out-dir',WORK/'watch')
    assert len(list((WORK/'watch/frames').glob('*.jpg'))) == 4
    if a.capture:
        (WORK/'index.html').write_text('<!doctype html><html><head><title>Toolkit capture</title></head>'
            '<body style="margin:80px;background:#071426;color:#55e6cf;font-family:sans-serif">'
            '<h1>Toolkit browser capture</h1><p>Generated locally for the smoke check.</p></body></html>')
        server = ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(WORK)))
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            tool('capture',f'http://127.0.0.1:{server.server_port}','--output',WORK/'capture')
            assert (WORK/'capture/overview.png').is_file()
        finally:
            server.shutdown(); server.server_close(); thread.join()
    if a.remotion:
        tool('remotion',video,'--loading-end','3','--speed','8','-o',WORK/'speed-ramp.mp4')
        info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',
            str(WORK/'speed-ramp.mp4')],text=True))
        assert int(info['streams'][0]['nb_frames']) == 161
    print(f'Installed helper checks passed: {WORK}')

if __name__ == '__main__':
    main()
