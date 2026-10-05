"""RMS-matched, voice-ducked music bed derived from videoeditinggod/v3/music.py."""
import argparse
import json
from pathlib import Path
import subprocess
import wave
import numpy as np

SR = 48000
def pcm(path, channels=2):
    p = subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vn','-f','f32le','-ar',str(SR),'-ac',str(channels),'-'],capture_output=True,check=True)
    return np.frombuffer(p.stdout,'<f4').reshape(-1,channels).copy()

def render(voice, cues, duration, output, relative, gain_db=-15):
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError('Duration must be a positive number of seconds.')
    n = round(duration*SR)
    v = pcm(voice,1)[:,0]
    v = np.pad(v,(0,max(0,n-len(v))))[:n]
    speech = v[np.abs(v)>.02]
    vr = float(np.sqrt(np.mean(speech**2))) if len(speech) else .1
    hop = 960
    padded = np.pad(v,(0,(-n)%hop))
    activity = np.sqrt(np.mean(padded.reshape(-1,hop)**2,axis=1)) > vr*.25
    state = 0.
    sm = []
    for active in activity:
        state += (float(active)-state)*(.5 if active > state else .06)
        sm.append(state)
    duck = 1-.55*np.repeat(sm,hop)[:n]
    bed = np.zeros((n,2),dtype=np.float32)
    cues = sorted(cues,key=lambda c:c['at'])
    for i,c in enumerate(cues):
        start = float(c['at'])
        end = float(cues[i+1]['at']) if i+1 < len(cues) else duration
        if not 0 <= start < end <= duration:
            raise ValueError('Music anchors must be inside duration and strictly increasing.')
        path = Path(c['file'])
        x = pcm(path if path.is_absolute() else relative/path)
        x = x[round(float(c.get('from',0))*SR):]
        if not len(x):
            raise ValueError(f'Music offset is beyond the file: {path}')
        length = round(end*SR)-round(start*SR)
        # Crossfade loops instead of a discontinuity at each repeat.
        original = x.copy()
        while len(x) < length:
            xf = min(2*SR,len(original)//4,len(x)//4)
            ramp = np.linspace(0,1,xf,dtype=np.float32)[:,None]
            x = np.concatenate((x[:-xf],x[-xf:]*(1-ramp)+original[:xf]*ramp,original[xf:])) if xf else np.concatenate((x,original))
        x = x[:length]
        rms = float(np.sqrt(np.mean(x**2)))
        x *= vr*10**(float(c.get('gain_db',gain_db))/20)/max(rms,1e-8)
        fade = min(round(.1*SR),len(x)//2)
        if fade:
            x[:fade] *= np.linspace(0,1,fade)[:,None]
            x[-fade:] *= np.linspace(1,0,fade)[:,None]
        if i+1 < len(cues) and c.get('tape_stop', False):
            tail_len = min(round(.5*SR),len(x)//2)
            if tail_len > 1:
                tail = x[-tail_len:].copy()
                pos = np.clip(np.cumsum(np.linspace(1,.05,tail_len)),0,len(tail)-2)
                indices = pos.astype(int)
                frac = (pos-indices)[:,None]
                x[-tail_len:] = (tail[indices]*(1-frac)+tail[indices+1]*frac) * np.linspace(1,0,tail_len)[:,None]**.6
        bed[round(start*SR):round(end*SR)] += x
    bed *= duck[:,None]
    output.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(output),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR)
        w.writeframes((np.clip(bed,-.99,.99)*32767).astype('<i2').tobytes())
    print(output)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('voice',type=Path)
    p.add_argument('cues',type=Path,help='JSON list: [{"at":0,"file":"track.mp3","gain_db":-15}]')
    p.add_argument('--duration',type=float,required=True)
    p.add_argument('-o','--output',type=Path,required=True)
    a = p.parse_args()
    render(a.voice,json.loads(a.cues.read_text()),a.duration,a.output,a.cues.resolve().parent)

if __name__ == '__main__':
    main()
