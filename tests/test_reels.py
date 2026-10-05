"""Reel regression checks: ambiguous speech, timing boundaries and private input paths."""
import math
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave
import zipfile

from reels.pipeline import PROJECT_FILES, extract_narration, freelancer_pack, local_file, validate_job
from reels.timing import align_beats, make_captions, read_words, srt


class ReelTimingTests(unittest.TestCase):
    def setUp(self):
        self.words = read_words({'words': [
            {'text': 'Hello,', 'start': .1, 'end': .5},
            {'text': 'world.', 'start': .55, 'end': 1},
            {'text': 'Show', 'start': 1.4, 'end': 1.7},
            {'text': 'proof.', 'start': 1.75, 'end': 2.1}]}, 3)
        self.spec = [{'text': 'hello world', 'layout': 'face'},
                     {'text': 'Show proof', 'layout': 'graphic', 'scene': 'receipt'}]

    def test_audio_timestamps_drive_frame_grid_and_caption_kills(self):
        beats = align_beats(self.spec, self.words, 3)
        self.assertEqual(beats[0]['start'], 0)
        self.assertEqual(beats[0]['end'], beats[1]['start'])
        self.assertAlmostEqual(beats[1]['start'] * 30, round(beats[1]['start'] * 30))
        caps = make_captions(beats)
        self.assertEqual([c['text'] for c in caps], ['Hello, world.', 'Show proof.'])
        self.assertTrue(all(c['start'] < c['end'] for c in caps))
        self.assertLessEqual(caps[0]['end'], beats[1]['start'])
        self.assertEqual(caps[1]['style'], 'serif')

    def test_missing_script_match_never_invents_timing(self):
        self.spec[1]['text'] = 'Say something else'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            align_beats(self.spec, self.words, 3)

    def test_repeated_cue_requires_an_explicit_word_index(self):
        words = read_words([{'text': 'Go', 'start': .1, 'end': .4},
                            {'text': 'Go', 'start': 1, 'end': 1.4}], 2)
        with self.assertRaisesRegex(ValueError, 'repeated phrase'):
            align_beats([{'text': 'Go', 'layout': 'face'}], words, 2)
        beats = align_beats([{'word_start': 0, 'layout': 'face'},
                             {'word_start': 1, 'layout': 'graphic', 'scene': 'counter'}], words, 2)
        self.assertEqual(len(beats[1]['words']), 1)

    def test_bad_word_timestamps_are_rejected(self):
        for start, end in [(-1, .5), (.5, .2), (0, math.nan), (0, 5), (3.001, 3.01)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                read_words([{'text': 'Bad', 'start': start, 'end': end}], 3)

    def test_out_of_order_word_data_cannot_be_rendered(self):
        with self.assertRaisesRegex(ValueError, 'overlap'):
            read_words([{'text': 'one', 'start': 1, 'end': 2},
                        {'text': 'two', 'start': .5, 'end': 1}], 3)

    def test_captions_split_long_pairs_and_real_pauses(self):
        beats = [{'start': 0, 'end': 4, 'layout': 'face', 'caption_style': 'sans', 'emphasis': [],
                  'words': [{'text': 'extraordinary', 'start': .1, 'end': .5},
                            {'text': 'example', 'start': .55, 'end': 1},
                            {'text': 'later', 'start': 2, 'end': 2.4}]}]
        self.assertEqual([c['text'] for c in make_captions(beats)], ['extraordinary', 'example', 'later'])

    def test_srt_rounding_carries_to_the_next_minute(self):
        text = srt([{'text': 'a', 'start': 59.9996, 'end': 61.1}])
        self.assertIn('00:01:00,000 --> 00:01:01,100', text)

    def test_empty_or_backwards_beats_are_rejected(self):
        with self.assertRaises(ValueError):
            align_beats([], self.words, 3)
        with self.assertRaisesRegex(ValueError, 'advance'):
            align_beats([{'word_start': 0, 'layout': 'face'},
                         {'word_start': 0, 'layout': 'face'}], self.words, 3)


class ReelInputTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is needed for real resampling')
    def test_44100_audio_is_trimmed_on_the_48000_sample_grid(self):
        with tempfile.TemporaryDirectory() as d:
            source, output = Path(d) / 'source.wav', Path(d) / 'voice.wav'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'sine=frequency=440:sample_rate=44100:duration=2',
                            '-c:a', 'pcm_s16le', str(source)], check=True)
            extract_narration(source, output, 31)
            with wave.open(str(output), 'rb') as wav:
                self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getnframes()),
                                 (48000, 2, 31 * 1600))

    def test_pack_contains_current_media_and_excludes_stale_or_login_files(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            project = folder / 'project'
            (project / 'assets/fonts').mkdir(parents=True)
            for name in (*PROJECT_FILES, 'index.html', 'job.js', 'gsap.min.js',
                         'assets/presenter.mp4', 'assets/current.png', 'assets/fonts/OFL.txt',
                         'assets/stale.mp4', '.env'):
                (project / name).write_text('fixture', encoding='utf-8')
            manifest = {'keyword': 'TEST', 'duration': 1, 'beats': [],
                        'assets': {'assets/current.png': {'sha256': 'fixture'}}}
            for name in ('manifest.json', 'word-timings.json', 'captions.srt',
                         'narration.wav', 'mix-normalized.wav', 'qc.json'):
                (folder / name).write_text(json.dumps(manifest), encoding='utf-8')
            output = freelancer_pack({}, manifest, folder, project)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn('project/assets/current.png', names)
                self.assertIn('project/assets/presenter.mp4', names)
                self.assertIn('beats-with-timings.json', names)
                self.assertNotIn('project/assets/stale.mp4', names)
                self.assertNotIn('project/.env', names)

    def test_media_resolves_from_job_not_the_process_directory(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / 'presenter.mp4').write_bytes(b'fixture')
            self.assertEqual(local_file('presenter.mp4', base), base / 'presenter.mp4')

    def test_remote_media_is_not_requested_implicitly(self):
        with self.assertRaisesRegex(ValueError, 'local files'):
            local_file('https://example.com/private.mp4', Path('.'))

    def test_nonfinite_crop_and_loud_music_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / 'presenter.mp4').write_bytes(b'fixture')
            job = {'version': 1, 'presenter': 'presenter.mp4', 'beats': [{}],
                   'split': {'video_top': math.inf}}
            with self.assertRaisesRegex(ValueError, 'finite'):
                validate_job(job, base)
            job.pop('split')
            job['music'] = {'file': 'presenter.mp4', 'gain_db': 0}
            with self.assertRaisesRegex(ValueError, 'gain_db'):
                validate_job(job, base)


if __name__ == '__main__':
    unittest.main()
