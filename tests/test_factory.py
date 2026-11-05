import copy
import hashlib
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path

from science_factory.cli import main
from science_factory.schema import Storyboard, StoryboardError
from science_factory.timeline import captions_srt, make_timeline
from science_factory.voice import VoiceError, generate_voice, wav_duration
from science_factory.visuals.orbit_math import inward_arrow


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "moon_orbit.json"
ZH_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "moon_orbit.zh-CN.json"


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_valid_example(self):
        storyboard = Storyboard.from_dict(self.data)
        self.assertEqual(len(storyboard.scenes), 6)
        self.assertEqual(storyboard.scenes[0].kind, "orbit")
        self.assertEqual(storyboard.to_dict(), self.data)

    def test_chinese_storyboard(self):
        data = json.loads(ZH_EXAMPLE.read_text(encoding="utf-8"))
        storyboard = Storyboard.from_dict(data)
        self.assertEqual(storyboard.language, "zh-CN")
        self.assertEqual(storyboard.to_dict(), data)

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
        self.assertEqual(main(["validate", str(ZH_EXAMPLE)]), 0)


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

    def test_subtitle_cards_fit_two_short_lines(self):
        storyboard = Storyboard.from_file(EXAMPLE)
        timeline = make_timeline(storyboard, [6] * 6)
        for block in captions_srt(timeline).strip().split("\n\n"):
            lines = block.splitlines()[2:]
            self.assertLessEqual(len(lines), 2)
            for line in lines:
                self.assertLessEqual(len(line), 24)

    def test_chinese_subtitle_cards_fit_phone(self):
        storyboard = Storyboard.from_file(ZH_EXAMPLE)
        timeline = make_timeline(storyboard, [6] * 6)
        self.assertEqual(timeline[0].language, "zh-CN")
        self.assertEqual(timeline[0].to_dict()["language"], "zh-CN")
        content = captions_srt(timeline)
        self.assertIn("月球为什么没有直接掉到地球上", content.replace("\n", ""))
        for block in content.strip().split("\n\n"):
            lines = block.splitlines()[2:]
            self.assertLessEqual(len(lines), 2)
            for line in lines:
                self.assertLessEqual(len(line), 12)


class VoiceTests(unittest.TestCase):
    def test_free_diagnostic_tone_writes_real_wav(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "tone.wav"
            expected = generate_voice("a short test", file, backend="tone")
            self.assertTrue(file.exists())
            self.assertAlmostEqual(wav_duration(file), expected, places=2)

    def test_chinese_tone_duration_uses_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "tone.wav"
            duration = generate_voice("月球围绕地球运动。", file, backend="tone", language="zh-CN")
            self.assertGreaterEqual(duration, 2.5)
            self.assertAlmostEqual(wav_duration(file), duration, places=2)

    def test_unknown_voice_language_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "tone.wav"
            with self.assertRaises(VoiceError):
                generate_voice("bonjour", file, backend="tone", language="fr-FR")


class VisualAssetTests(unittest.TestCase):
    def test_nasa_discs_are_committed_and_match_provenance(self):
        directory = EXAMPLE.parents[1] / "science_factory" / "assets"
        provenance = json.loads((directory / "provenance.json").read_text(encoding="utf-8"))
        for body in ("earth", "moon"):
            data = (directory / f"{body}_disc.png").read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512))
            self.assertEqual(hashlib.sha256(data).hexdigest(),
                             provenance[body]["generated_sha256"])
            self.assertIn("raw.githubusercontent.com/nasa/", provenance[body]["source"])

    def test_gravity_arrow_points_inward_everywhere_on_orbit(self):
        center = (0.0, 0.5, 0.0)
        for angle in (0, math.pi / 4, math.pi / 2, math.pi, 1.5 * math.pi):
            position = (2.05 * math.cos(angle), 0.5 + 2.05 * math.sin(angle), 0.0)
            start, end = inward_arrow(center, position)
            distance_start = math.dist(center, start)
            distance_end = math.dist(center, end)
            self.assertLess(distance_end, distance_start)
            self.assertAlmostEqual(distance_start - distance_end, 0.61, places=6)

    def test_gravity_arrow_rejects_degenerate_orbit(self):
        with self.assertRaises(ValueError):
            inward_arrow((0, 0, 0), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()

