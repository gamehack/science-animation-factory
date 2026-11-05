import copy
import hashlib
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from science_factory.audio import trim_wav_edges
from science_factory.cli import main
from science_factory.media import MediaError, scan_media_quality, subtitle_style
from science_factory.schema import SCENE_KINDS, Storyboard, StoryboardError
from science_factory.timeline import _subtitle_phrases, captions_srt, make_timeline
from science_factory.voice import VoiceCue, VoiceError, generate_voice, wav_duration
from science_factory.visuals.orbit_math import inward_arrow


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "moon_orbit.json"
ZH_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "moon_orbit.zh-CN.json"
SOUND_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sound_vacuum.json"
SOUND_ZH_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sound_vacuum.zh-CN.json"


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_valid_example(self):
        storyboard = Storyboard.from_dict(self.data)
        self.assertEqual(len(storyboard.scenes), 6)
        self.assertEqual(storyboard.scenes[0].kind, "orbit_intro")
        self.assertEqual(storyboard.scenes[2].kind, "physics_vectors")
        self.assertEqual(storyboard.scenes[4].kind, "throw_orbit")
        self.assertEqual(storyboard.scenes[5].kind, "orbit_recap")
        self.assertEqual(storyboard.to_dict(), self.data)

    def test_chinese_storyboard(self):
        data = json.loads(ZH_EXAMPLE.read_text(encoding="utf-8"))
        storyboard = Storyboard.from_dict(data)
        self.assertEqual(storyboard.language, "zh-CN")
        english = Storyboard.from_dict(self.data)
        self.assertEqual([scene.kind for scene in storyboard.scenes],
                         [scene.kind for scene in english.scenes])
        self.assertEqual(storyboard.to_dict(), data)

    def test_second_topic_has_bilingual_visual_and_source_parity(self):
        english = Storyboard.from_file(SOUND_EXAMPLE)
        chinese = Storyboard.from_file(SOUND_ZH_EXAMPLE)
        self.assertEqual(english.language, "en-US")
        self.assertEqual(chinese.language, "zh-CN")
        self.assertEqual(len(english.scenes), 6)
        self.assertEqual([s.kind for s in english.scenes],
                         [s.kind for s in chinese.scenes])
        self.assertEqual(english.sources, chinese.sources)
        self.assertEqual(english.scenes[0].kind, "sound_source")
        self.assertEqual(english.scenes[-1].kind, "sound_recap")
        self.assertEqual(len({s.kind for s in english.scenes}), 6)

    def test_templates_all_explicitly_allowlisted(self):
        for path in (EXAMPLE, ZH_EXAMPLE, SOUND_EXAMPLE, SOUND_ZH_EXAMPLE):
            storyboard = Storyboard.from_file(path)
            self.assertTrue(all(scene.kind in SCENE_KINDS for scene in storyboard.scenes))
            self.assertEqual(main(["validate", str(path)]), 0)

    def test_no_unreviewed_storyboard_code_fields(self):
        for path in (SOUND_EXAMPLE, SOUND_ZH_EXAMPLE):
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scenes"][2]["python"] = "print('not safe')"
            with self.assertRaises(StoryboardError):
                Storyboard.from_dict(data)

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
        self.assertAlmostEqual(timeline[1].start, 6.5)
        # Scenes track voice lengths, and do not pad every beat to 7.5 seconds.
        self.assertAlmostEqual(timeline[-1].start + timeline[-1].duration, 39.5)
        self.assertLess(timeline[0].duration, timeline[4].duration)

    def test_excessively_long_audio_fails_fast(self):
        storyboard = Storyboard.from_file(EXAMPLE)
        with self.assertRaises(ValueError):
            make_timeline(storyboard, [19.0] * 6)

    def test_subtitles_are_timestamped(self):
        storyboard = Storyboard.from_file(EXAMPLE)
        timeline = make_timeline(storyboard, [6] * 6)
        content = captions_srt(timeline)
        self.assertIn("00:00:00,000 -->", content)
        self.assertIn("00:00:06,400 -->", content)
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
        spoken = "".join("".join(block.splitlines()[2:]) for block in
                         content.strip().split("\n\n"))
        self.assertIn("月球为什么没有直接掉到地球上", spoken)
        for block in content.strip().split("\n\n"):
            lines = block.splitlines()[2:]
            self.assertLessEqual(len(lines), 2)
            for line in lines:
                self.assertLessEqual(len(line), 12)

    def test_chinese_punctuation_never_becomes_orphan_subtitle(self):
        for count in range(13, 55):
            text = "粒" * count + "。"
            phrases, _, _ = _subtitle_phrases(text, "zh-CN")
            self.assertEqual("".join(phrases), text)
            self.assertTrue(all(2 <= len(phrase) <= 12 for phrase in phrases),
                            (count, phrases))

    def test_subtitles_follow_real_tts_chunk_offsets(self):
        storyboard = Storyboard.from_file(EXAMPLE)
        timeline = make_timeline(storyboard, [5.5] * 6)
        cues = [[VoiceCue("First timed words.", 0.4, 1.4),
                 VoiceCue("Second timed words.", 2.3, 3.6)]
                for _ in timeline]
        content = captions_srt(timeline, cues_by_scene=cues)
        self.assertIn("00:00:00,400 --> 00:00:01,400", content)
        self.assertIn("00:00:02,300 --> 00:00:03,600", content)
        self.assertIn("First timed words.", content)
        with self.assertRaises(ValueError):
            captions_srt(timeline, cues_by_scene=cues[:-1])

    def test_bilingual_subtitle_styles_reserve_mobile_safe_area(self):
        chinese = subtitle_style("zh-CN")
        english = subtitle_style("en-US")
        self.assertIn("Noto Sans CJK SC", chinese)
        self.assertIn("DejaVu Sans", english)
        for style in (chinese, english):
            self.assertIn("MarginV=48", style)
            self.assertIn("Outline=2", style)
            self.assertIn("Bold=1", style)
        self.assertIn("FontSize=11", chinese)
        self.assertIn("FontSize=10", english)
        with self.assertRaises(ValueError):
            subtitle_style("fr-FR")


class VoiceTests(unittest.TestCase):
    def test_trim_only_long_wav_edge_silences(self):
        import wave
        from array import array
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "speech.wav"
            rate = 24_000
            samples = array("h", [0] * rate)
            samples.extend(int(9000 * math.sin(2 * math.pi * 180 * i / rate))
                           for i in range(rate))
            samples.extend([0] * rate)
            with wave.open(str(path), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(rate)
                writer.writeframes(samples.tobytes())
            result = trim_wav_edges(path)
            self.assertGreater(result.removed_start, 0.7)
            self.assertGreater(result.removed_end, 0.7)
            self.assertAlmostEqual(result.duration, 1.32, delta=0.08)
            self.assertAlmostEqual(wav_duration(path), result.duration)

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


class MediaQualityTests(unittest.TestCase):
    def test_quality_scan_records_nonblocking_speech_pause(self):
        report = SimpleNamespace(returncode=0, stderr="silence_duration: 1.45")
        with patch("science_factory.media.require_tools"), patch(
                "science_factory.media.subprocess.run", return_value=report):
            result = scan_media_quality(Path("unopened-example.mp4"))
        self.assertEqual(result["max_black_seconds"], 0)
        self.assertEqual(result["max_silence_seconds"], 1.45)

    def test_quality_scan_rejects_long_black_and_silent_sections(self):
        for description in ("black_duration:0.66", "silence_duration:3.2"):
            report = SimpleNamespace(returncode=0, stderr=description)
            with patch("science_factory.media.require_tools"), patch(
                    "science_factory.media.subprocess.run", return_value=report):
                with self.assertRaises(MediaError):
                    scan_media_quality(Path("unopened-example.mp4"))


if __name__ == "__main__":
    unittest.main()

