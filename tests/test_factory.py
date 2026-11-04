import copy
import json
import tempfile
import unittest
from pathlib import Path

from science_factory.cli import main
from science_factory.schema import Storyboard, StoryboardError
from science_factory.timeline import captions_srt, make_timeline
from science_factory.voice import generate_voice, wav_duration


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "moon_orbit.json"


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_valid_example(self):
        storyboard = Storyboard.from_dict(self.data)
        self.assertEqual(len(storyboard.scenes), 6)
        self.assertEqual(storyboard.scenes[0].kind, "orbit")
        self.assertEqual(storyboard.to_dict(), self.data)

    def test_unknown_template_rejected(self):
        data = copy.deepcopy(self.data)
        data["scenes"][0]["kind"] = "eval_python"
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(data)

    def test_injection_keys_rejected(self):
        data = copy.deepcopy(self.data)
        data["scenes"][0]["code"] = "import os"
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(data)

    def test_markup_and_multiline_rejected(self):
        data = copy.deepcopy(self.data)
        data["scenes"][0]["narration"] = "first line\nsecond line"
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(data)

    def test_bad_source_url_rejected(self):
        data = copy.deepcopy(self.data)
        data["sources"] = ["file:///etc/passwd"]
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(data)

    def test_invalid_language_rejected(self):
        data = copy.deepcopy(self.data)
        data["language"] = "fr-FR"
        with self.assertRaises(StoryboardError):
            Storyboard.from_dict(data)

    def test_cli_validation(self):
        self.assertEqual(main(["validate", str(EXAMPLE)]), 0)


class TimelineTests(unittest.TestCase):
    def test_measured_audio_drives_scenes(self):
        storyboard = Storyboard.from_file(EXAMPLE)
        timeline = make_timeline(storyboard, [6.1, 6.0, 5.5, 6.6, 6.9, 6.0])
        self.assertEqual(timeline[0].start, 0)
        self.assertAlmostEqual(timeline[1].start, 7.5)
        # An unusually long voice beat expands the corresponding scene.
        self.assertAlmostEqual(timeline[-1].start + timeline[-1].duration, 45.05)

    def test_excessively_long_audio_fails_fast(self):
        storyboard = Storyboard.from_file(EXAMPLE)
        with self.assertRaises(ValueError):
            make_timeline(storyboard, [19.0] * 6)

    def test_subtitles_are_timestamped(self):
        storyboard = Storyboard.from_file(EXAMPLE)
        timeline = make_timeline(storyboard, [6] * 6)
        content = captions_srt(timeline)
        self.assertIn("00:00:00,000 -->", content)
        self.assertIn("00:00:07,500 -->", content)
        self.assertIn("Why doesn't the Moon", content)


class VoiceTests(unittest.TestCase):
    def test_free_diagnostic_tone_writes_real_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "tone.wav"
            expected = generate_voice("a short test", file, backend="tone")
            self.assertTrue(file.exists())
            self.assertAlmostEqual(wav_duration(file), expected, places=2)


if __name__ == "__main__":
    unittest.main()

