"""Find screen = camera + offset, using the original multi-window RMS correlator."""
import json
import math
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine'))
from config import EDIT, load_edl
from sync import envelope, best_offset, drift_check

def main():
    data = load_edl(sys.argv[1])
    audio = EDIT/'audio'
    audio.mkdir(exist_ok=True)
    envs = {}
    for key, src in data['sources'].items():
        wav = audio/f'{Path(src).stem}.wav'
        subprocess.run(['ffmpeg','-v','error','-y','-i',src,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(wav)], check=True)
        envs[key] = envelope(wav)
    clips = {}
    for key, env in envs.items():
        if key == 'screen':
            continue
        offset, confidence = best_offset(envs['screen'], env)
        windows = drift_check(envs['screen'], env)
        clips[key] = {'offset_s':round(offset,3),
                      'confidence':round(confidence,3) if math.isfinite(confidence) else None,
                      'windows':[[round(a,2),round(b,3),round(c,3) if math.isfinite(c) else None] for a,b,c in windows]}
        print(f'{key}: screen = camera + {offset:.3f}s; confidence {confidence:.2f}')
    dest = EDIT/'sync-proposal.json'
    dest.write_text(json.dumps({'reference':'screen','clips':clips}, indent=2))
    print(f'Proposal: {dest}. Verify a shared word near the beginning and end, then set EDL sync values.')

if __name__ == '__main__':
    main()
