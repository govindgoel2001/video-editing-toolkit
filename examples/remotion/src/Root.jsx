import React from 'react';
import {
  AbsoluteFill, Composition, OffthreadVideo, Sequence, interpolate,
  staticFile, useCurrentFrame, useVideoConfig,
} from 'remotion';

// Retains the original Code/video-edit behavior: loading accelerated, then
// ordinary playback. Both sections are muted; use the FFmpeg editor for speech.
export const SpeedRamp = ({input, sourceDurationSeconds, loadingEndSeconds, speedUp}) => {
  const {fps} = useVideoConfig();
  const end = Math.min(loadingEndSeconds, sourceDurationSeconds);
  const loadingFrames = Math.max(1, Math.round(end * fps / speedUp));
  return <AbsoluteFill style={{backgroundColor: '#071426'}}>
    <Sequence durationInFrames={loadingFrames}>
      <OffthreadVideo src={staticFile(input)} endAt={Math.round(end * fps)}
        playbackRate={speedUp} muted style={{width:'100%', height:'100%', objectFit:'contain'}} />
    </Sequence>
    {end < sourceDurationSeconds && <Sequence from={loadingFrames}>
      <OffthreadVideo src={staticFile(input)} startFrom={Math.round(end * fps)}
        muted style={{width:'100%', height:'100%', objectFit:'contain'}} />
    </Sequence>}
  </AbsoluteFill>;
};

const Demo = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 12, 72, 89], [0, 1, 1, 0], {extrapolateLeft:'clamp', extrapolateRight:'clamp'});
  const y = interpolate(frame, [0, 18], [34, 0], {extrapolateRight:'clamp'});
  return <AbsoluteFill style={{backgroundColor:'#071426', color:'#edf7f8', fontFamily:'Arial, sans-serif', justifyContent:'center', padding:96}}>
    <div style={{opacity, transform:`translateY(${y}px)`}}>
      <div style={{fontSize:24, color:'#55e6cf', letterSpacing:5}}>VIDEO EDITING TOOLKIT</div>
      <div style={{fontSize:86, fontWeight:700, marginTop:24}}>Your next edit starts here.</div>
      <div style={{height:7, width:interpolate(frame,[12,40],[0,520],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}), backgroundColor:'#947aff', marginTop:40}} />
    </div>
  </AbsoluteFill>;
};

export const Root = () => <>
  <Composition id="Demo" component={Demo} durationInFrames={90} fps={30} width={1920} height={1080} />
  <Composition id="SpeedRamp" component={SpeedRamp} durationInFrames={619} fps={30} width={1920} height={1080}
    defaultProps={{input:'input.mp4', sourceDurationSeconds:60, loadingEndSeconds:45, speedUp:8}}
    calculateMetadata={({props}) => {
      const {sourceDurationSeconds:dur, loadingEndSeconds:loading, speedUp:speed} = props;
      if (!(dur > 0 && loading > 0 && speed >= 1)) throw new Error('Require positive duration/loading time, and speedUp >= 1.');
      const end = Math.min(loading, dur);
      return {durationInFrames:Math.max(1,Math.round(end*30/speed))+Math.max(0,Math.round((dur-end)*30))};
    }} />
</>;
