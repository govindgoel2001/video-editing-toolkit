"""Generate the God project's fourteen effect samples without its private shot plan."""
import numpy as np, wave
from scipy.signal import butter, sosfilt
SR=48000; rng=np.random.default_rng(7)
def env(n,a,r):
    t=np.arange(n)/SR; e=np.minimum(1,t/max(a,1e-4)); return e*np.exp(-np.maximum(0,t-a)/r)
def bp(x,lo,hi): return sosfilt(butter(2,[lo,hi],btype='band',fs=SR,output='sos'),x)
def hp(x,f): return sosfilt(butter(2,f,btype='high',fs=SR,output='sos'),x)
def lp(x,f): return sosfilt(butter(2,f,btype='low',fs=SR,output='sos'),x)
def norm(x,pk): return x/np.max(np.abs(x))*pk
def whoosh(d=.45,big=False):
    n=int(d*SR); t=np.arange(n)/SR; x=rng.standard_normal(n); out=np.zeros(n)
    # sweep via blocks of bandpass
    blocks=24; L=n//blocks
    for i in range(blocks):
        f=300+ (2600 if big else 1800)*np.sin(np.pi*i/blocks)
        seg=bp(x,f*.6,min(f*1.6,20000))[i*L:(i+1)*L]; out[i*L:(i+1)*L]=seg
    e=np.sin(np.pi*t/d)**1.6
    return norm(lp(out*e,9000),.9 if big else .7)
def pop(f0=900,f1=260,d=.09):
    n=int(d*SR); t=np.arange(n)/SR; f=f1+(f0-f1)*np.exp(-t/.018)
    ph=2*np.pi*np.cumsum(f)/SR; s=np.sin(ph)*np.exp(-t/.03)
    c=hp(rng.standard_normal(n),3000)*np.exp(-t/.002)*.3
    return norm(s+c,.8)
def tick():
    n=int(.02*SR); t=np.arange(n)/SR
    return norm(bp(rng.standard_normal(n),2500,7000)*np.exp(-t/.003),.5)
def ding(f=1320,d=1.0):
    n=int(d*SR); t=np.arange(n)/SR
    s=(np.sin(2*np.pi*f*t)+.5*np.sin(2*np.pi*f*1.5*t)+.25*np.sin(2*np.pi*f*2.01*t))*np.exp(-t/.25)*np.minimum(1,t/.003)
    return norm(s,.55)
def impact(d=1.2):
    n=int(d*SR); t=np.arange(n)/SR
    f=45+70*np.exp(-t/.06); boom=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t/.35)
    nz=lp(rng.standard_normal(n),3500)*np.exp(-t/.08)*.5
    return norm(np.tanh(1.6*(boom+nz)),.95)
def riser(d=1.1):
    n=int(d*SR); t=np.arange(n)/SR; p=t/d
    nz=hp(rng.standard_normal(n),800)*p**2.2*.6
    f=180+1400*p**2; tone=np.sin(2*np.pi*np.cumsum(f)/SR)*p**2*.35
    tone+=np.sin(2*np.pi*np.cumsum(f*1.5)/SR)*p**2.5*.2
    x=nz+tone; x[-int(.01*SR):]*=np.linspace(1,0,int(.01*SR))
    return norm(x,.7)
def thud():
    n=int(.5*SR); t=np.arange(n)/SR
    s=np.sin(2*np.pi*(110-50*t/.5)*t)*np.exp(-t/.12)+np.sin(2*np.pi*(90)*t)*np.exp(-t/.15)*.5
    return norm(s,.8)
def swish(): return whoosh(.22)
lib={'whoosh':whoosh(),'bigwhoosh':whoosh(.7,True),'pop':pop(),'poplo':pop(600,180,.1),'pophi':pop(1300,500,.07),
     'tick':tick(),'ding':ding(),'dinglo':ding(990,.9),'impact':impact(),'riser':riser(),'thud':thud(),'swish':swish()}
# gains in dB relative (applied later globally)
G={'whoosh':-13,'bigwhoosh':-9,'pop':-15,'poplo':-14,'pophi':-17,'tick':-24,'ding':-17,'dinglo':-17,'impact':-8,'riser':-13,'thud':-12,'swish':-16}

def scratch(d=.45):
    n=int(d*SR); t=np.arange(n)/SR
    sp=np.sin(2*np.pi*7*t)*np.sin(np.pi*t/d)   # hand wobble
    f=900+700*sp; ph=2*np.pi*np.cumsum(f)/SR
    nz=bp(rng.standard_normal(n),600,4000)*(0.6+0.4*np.abs(sp))
    x=nz*0.7+np.sign(np.sin(ph))*0.25
    return norm(lp(x*np.sin(np.pi*t/d)**.5,6000),.8)
def snap():
    w=whoosh(.18); i=impact(.5)*.6; o=np.zeros(len(w)+len(i)); o[:len(w)]+=w; o[int(.12*SR):int(.12*SR)+len(i)]+=i; return norm(o,.9)
lib['scratch']=scratch(); lib['snap']=snap()
G['scratch']=-10; G['snap']=-11

def main():
    import argparse
    import json
    from pathlib import Path
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--apply-gains', action='store_true', help='Apply original God mix levels to the samples')
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    for name, signal in lib.items():
        level = 10**(G[name]/20) if a.apply_gains else 1
        stereo = np.repeat(np.clip(signal*level, -.99, .99)[:, None], 2, axis=1)
        with wave.open(str(a.output_dir/f'{name}.wav'), 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((stereo*32767).astype('<i2').tobytes())
    (a.output_dir/'gains.json').write_text(json.dumps(G, indent=2))
    print(f'{len(lib)} effects: {a.output_dir}')

if __name__ == '__main__':
    main()
