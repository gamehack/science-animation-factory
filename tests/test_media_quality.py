import unittest
from science_factory.media import parse_ebur128_summary

class Ebur128Tests(unittest.TestCase):
    def test_parses_summary(self):
        log = """[Parsed_ebur128_0] Summary:
    Integrated loudness:
        I:         -16.2 LUFS
    True peak:
        Peak:       -1.4 dBFS
"""
        self.assertEqual(parse_ebur128_summary(log), (-16.2, -1.4))

    def test_rejects_missing_measurement(self):
        with self.assertRaises(Exception):
            parse_ebur128_summary("no audio metrics")


class MuxTruePeakTests(unittest.TestCase):
    def test_encoded_audio_has_headroom_limiter(self):
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from science_factory.media import mux_video
        scene = SimpleNamespace(start=0.0, duration=8.0, language="en-US")
        with patch("science_factory.media.require_tools"), patch("science_factory.media._run") as run:
            mux_video(Path("silent.mp4"), [Path("speech.wav")],
                      [scene], Path("captions.srt"), Path("final.mp4"))
        command = run.call_args.args[0]
        graph = command[command.index("-filter_complex") + 1]
        self.assertIn("loudnorm=I=-16:TP=-3:LRA=11", graph)
        self.assertIn("alimiter=limit=0.65", graph)
        self.assertIn("level=0", graph)
        self.assertIn("-c:a", command)
        self.assertEqual(command[command.index("-c:a") + 1], "aac")

    def test_true_peak_gate_does_not_silently_relax(self):
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from science_factory.media import MediaError, measure_audio_quality
        log = "Integrated loudness:\\n    I: -16.0 LUFS\\nTrue peak:\\n    Peak: -0.3 dBFS\\n"
        with patch("science_factory.media.require_tools"), patch(
            "science_factory.media.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stderr=log)
        ):
            with self.assertRaisesRegex(MediaError, "true peak"):
                measure_audio_quality(Path("final.mp4"))

if __name__ == "__main__":
    unittest.main()
