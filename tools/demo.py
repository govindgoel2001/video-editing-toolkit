"""An eight-second, entirely synthetic integration fixture for the real editor."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dir', type=Path, required=True)
    p.add_argument('--graphics', action='store_true')
    a = p.parse_args()
    folder = a.dir.resolve()
    marker = folder/'.toolkit-demo.json'
    if folder.exists() and any(folder.iterdir()) and not marker.is_file():
        raise SystemExit('Demo directory must be empty, or a previous toolkit demo.')
    folder.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"synthetic":true}')
    edit = folder/'edit'
    (edit/'transcripts').mkdir(parents=True, exist_ok=True)
    rate = 48000
    t = np.arange(rate*8)/rate
    env = .18 + .16*np.sin(2*np.pi*2.7*t)**2
    x = env*(.7*np.sin(2*np.pi*220*t)+.3*np.sin(2*np.pi*430*t))
    for start,end in ((1,1.6),(4,4.7)):
        x[round(start*rate):round(end*rate)] = 0
    wav = folder/'demo_audio.wav'
    with wave.open(str(wav),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes((x*32767).astype('<i2').tobytes())
    for name,pattern in [('screen','testsrc=size=1280x720:rate=30'),('camera','testsrc2=size=960x540:rate=30')]:
        subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',pattern,'-i',str(wav),'-t','8',
            '-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p',
            '-c:a','aac','-b:a','192k','-ar','48000',str(folder/f'{name}.mp4')], check=True)
        words = [{'text':text,'start':start,'end':start+.25,'type':'word','speaker_id':'S0'}
                 for start,text in [(0.2,'A'),(.5,'synthetic'),(.8,'demo.'),(2.1,'Picture'),(2.5,'and'),(2.9,'sound.'),
                                    (3.6,'One'),(3.9,'grid.'),(4.9,'No'),(5.2,'private'),(5.6,'footage.'),(6.3,'Ready'),(6.8,'to'),(7.3,'edit.')]]
        (edit/'transcripts'/f'{name}.json').write_text(json.dumps({'language_code':'en','text':'Synthetic test captions','words':words}))
        subprocess.run([sys.executable,str(ROOT/'toolkit.py'),'engine','silences','--edit-dir',str(edit),'--',str(folder/f'{name}.mp4'),'--noise','-40'],check=True)
    edl = {'sources':{'screen':'screen.mp4','camera':'camera.mp4'},'sync':{'camera':0},
           'ranges':[{'source':'camera','style':'cam','start':0,'end':2},
                     {'source':'screen','style':'screen','face':'camera','start':2,'end':6,
                      'drops':[[3.2,3.5]],'zooms':[{'at':2.6,'to':1.2,'fx':.55,'fy':.5,'dur':.3,'hold':.5}]},
                     {'source':'camera','style':'broll','start':6,'end':8,'speed':1.5}],
           'titles':[{'seg':0,'offset':.1,'dur':1,'text':'SYNTHETIC DEMO','sub':'Test your installation'}],
           'chips':[{'seg':1,'offset':.3,'dur':1,'text':'FRAME LOCKED'}],
           'sfx':[{'seg':2,'offset':.1,'name':'pop','gain_db':-25}], 'progress_bar':True}
    if a.graphics:
        subprocess.run([sys.executable,str(ROOT/'toolkit.py'),'graphics',str(ROOT/'graphics/cards.example.json'),
                        '--output-dir',str(edit/'graphics'),'--only','opener'],check=True)
        edl['overlays'] = [{'seg':1,'offset':.1,'dur':3,'file':'edit/graphics/opener.mov'}]
    path = folder/'edl.json'
    path.write_text(json.dumps(edl,indent=2))
    subprocess.run([sys.executable,str(ROOT/'toolkit.py'),'pack','--edit-dir',str(edit)],check=True)
    subprocess.run([sys.executable,str(ROOT/'toolkit.py'),'render',str(path),'--draft'],check=True)
    subprocess.run(['ffmpeg','-v','error','-i',str(edit/'final.mp4'),'-f','null','-'],check=True)
    print(f'Demo decoded successfully: {edit / "final.mp4"}')

if __name__ == '__main__':
    main()
