"""Dependency-light editorial schema and render adapter regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from science_factory.editorial_schema import EditorialError, EditorialStoryboard, asset_path
from science_factory.editorial_renderer import SIZES, _camera_filter


def sample():
    return {"schema_version": 2, "kind": "editorial", "title": "Kodak 1888",
            "language": "en-US", "target_seconds": 22,
            "sources": ["https://americanhistory.si.edu/collections/object/nmah_760118"],
            "scenes": [{"title": f"Beat {i}", "narration": "Camera stories changed everyday life.",
                        "image": f"scene_{i}.jpg", "motion": "push_in", "rights": "original",
                        "credit": "Original commissioned illustration"} for i in range(4)]}


class EditorialSchemaTests(unittest.TestCase):
    def test_valid(self):
        x = EditorialStoryboard.from_dict(sample())
        self.assertEqual(x.kind, "editorial")
        self.assertEqual(len(x.scenes), 4)
        self.assertIsNone(x.music)

    def test_music_license_required(self):
        x = sample()
        x["music"] = {"asset": "music.mp3", "volume": 0.14, "credit": "Creator"}
        with self.assertRaises(EditorialError):
            EditorialStoryboard.from_dict(x)
        x["music"]["rights"] = "licensed"
        self.assertEqual(EditorialStoryboard.from_dict(x).music.volume, 0.14)

    def test_no_traversal(self):
        for name in ("../private.jpg", "/tmp/secret.jpg", "scene_0.sh", "../music.mp3"):
            x = sample()
            x["scenes"][0]["image"] = name
            with self.assertRaises(EditorialError, msg=name):
                EditorialStoryboard.from_dict(x)

    def test_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            approved = base / "approved"
            approved.mkdir()
            (base / "outside.jpg").write_bytes(b"private")
            (approved / "escape.jpg").symlink_to(base / "outside.jpg")
            with self.assertRaises(EditorialError):
                asset_path(approved, "escape.jpg")

    def test_reject_unknown_motion_and_parameters(self):
        x = sample()
        x["scenes"][1]["motion"] = "run_python"
        with self.assertRaises(EditorialError):
            EditorialStoryboard.from_dict(x)
        x = sample()
        x["scenes"][1]["code"] = "print('hello')"
        with self.assertRaises(EditorialError):
            EditorialStoryboard.from_dict(x)

    def test_v1_science_still_isolated(self):
        x = sample()
        x["schema_version"] = 1
        with self.assertRaises(EditorialError):
            EditorialStoryboard.from_dict(x)

    def test_camera_motion_and_quality(self):
        self.assertEqual(SIZES["mobile"], (720, 1280))
        for motion in ("push_in", "pull_out", "pan_left", "pan_right", "still"):
            f = _camera_filter(motion, 150, 360, 640)
            self.assertIn("zoompan", f)
            self.assertIn("360x640", f)
        # EAS camera should not swing across a 14% overscan.
        self.assertIn("0.035", _camera_filter("push_in", 150, 360, 640))
        self.assertNotIn("0.13", _camera_filter("push_in", 150, 360, 640))
        self.assertIn("zoompan=z='1':x='0'", _camera_filter("still", 150, 360, 640))
        self.assertIn("0.14", _camera_filter("pan_left", 150, 360, 640))

    def test_storyboard_serialization(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "storyboard.json"
            p.write_text(json.dumps(sample()), encoding="utf8")
            self.assertEqual(EditorialStoryboard.from_file(p).title, "Kodak 1888")


if __name__ == "__main__":
    unittest.main()
