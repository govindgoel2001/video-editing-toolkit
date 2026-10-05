"""Regression checks for portable sessions and cut/audio timing failures."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'engine'))
import build
import captions
import config
import qc
from transcribe_local import read_pcm
from sync import best_offset
import numpy as np


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder/'screen.mp4').write_bytes(b'fixture')
        (self.folder/'camera.mp4').write_bytes(b'fixture')
        self.edl = {'sources': {'screen':'screen.mp4', 'camera':'camera.mp4'},
                    'sync': {'camera':0},
                    'ranges': [{'source':'screen','style':'screen','start':0,'end':2}]}

    def load(self):
        path = self.folder/'edl.json'
        path.write_text(json.dumps(self.edl), encoding='utf-8')
        return config.load_edl(path)

    def test_paths_are_relative_to_edl_not_shell_cwd(self):
        loaded = self.load()
        self.assertEqual(Path(loaded['sources']['screen']), self.folder/'screen.mp4')
        self.assertEqual(loaded['ranges'][0]['audio_key'], 'screen')

    def test_duplicate_stems_cannot_reuse_wrong_transcript(self):
        (self.folder/'screen.mov').write_bytes(b'fixture')
        self.edl['sources']['camera'] = 'screen.mov'
        with self.assertRaisesRegex(ValueError, 'unique source filenames'):
            self.load()

    def test_negative_source_time_rejected(self):
        self.edl['ranges'][0]['start'] = -1
        with self.assertRaisesRegex(ValueError, 'start < end'):
            self.load()

    def test_unsupported_pip_speed_rejected(self):
        self.edl['ranges'][0]['speed'] = 1.5
        with self.assertRaisesRegex(ValueError, 'speed changes'):
            self.load()

    def test_pip_does_not_seek_before_camera_begins(self):
        self.edl['ranges'][0]['face'] = 'camera'
        self.edl['sync']['camera'] = 1
        with self.assertRaisesRegex(ValueError, 'before camera starts'):
            self.load()

    def test_sync_offset_cannot_be_nonfinite(self):
        self.edl['sync']['camera'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite offset'):
            self.load()


class TimingTests(unittest.TestCase):
    def test_transcription_pcm_retains_duration_and_normalized_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            wav = Path(folder)/'test.wav'
            samples = np.array([-32768, 0, 16384, 32767], dtype='<i2')
            with wave.open(str(wav), 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                w.writeframes(samples.tobytes())
            decoded = read_pcm(wav)
            self.assertEqual(decoded.dtype, np.float32)
            np.testing.assert_allclose(decoded, [-1,0,.5,32767/32768])

    def test_caption_milliseconds_carry_into_next_minute(self):
        self.assertEqual(captions.ts(59.9996), '00:01:00,000')
        self.assertEqual(captions.ts(3599.9996), '01:00:00,000')

    def test_explicit_drop_follows_borrowed_microphone_offset(self):
        # Camera 12..13 is screen 17..18 when sync offset is +5.
        r = {'source':'camera','style':'cam','start':10,'end':20,
             'cut_silence':False,'drops':[[12,13]]}
        self.assertEqual(build.range_cuts(r, 'screen', 15), [(0,2),(3,10)])

    def test_full_range_drop_cannot_silently_restore_footage(self):
        with self.assertRaisesRegex(ValueError, 'entire range'):
            build.subtract_drops([], [[10,20]], 10, 20)

    def test_talking_word_is_protected_inside_silence_map(self):
        kept_silence = build.cuttable([(0,1)], [(.4,.6)])
        self.assertEqual(len(kept_silence), 2)
        self.assertLessEqual(kept_silence[0][1], .35+1e-8)
        self.assertGreaterEqual(kept_silence[1][0], .65-1e-8)

    def test_camera_sync_sign_matches_screen_reference(self):
        camera = np.random.default_rng(3).normal(size=1200)
        screen = np.concatenate((np.zeros(250),camera,np.zeros(30)))
        offset, _ = best_offset(screen, camera)
        self.assertAlmostEqual(offset, 2.5)

    def test_silent_audio_cannot_claim_confident_sync(self):
        self.assertEqual(best_offset(np.zeros(100), np.zeros(80)), (0.0, 0.0))

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg needed')
    def test_retimed_audio_has_exact_output_frame_sample_count(self):
        # atempo alone commonly stops short. Decode real filter output rather
        # than checking that its string matches the implementation.
        frames = 40  # two seconds accelerated 1.5x at 30fps
        p = subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
            'sine=frequency=440:sample_rate=48000:duration=2',
            '-af',build.aligned_audio('atempo=1.5', frames),
            '-ac','1','-f','s16le','-'], capture_output=True, check=True)
        self.assertEqual(len(p.stdout)//2, 64000)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg needed')
    def test_qc_decode_failure_is_not_empty_success(self):
        with self.assertRaises(subprocess.CalledProcessError):
            qc.pcm(ROOT/'tests'/'nonexistent-video.mp4')


if __name__ == '__main__':
    unittest.main()
