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

if __name__ == "__main__":
    unittest.main()
