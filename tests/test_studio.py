import json
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from easy_windows_tools import ScreenRecorder
from studio import SceneCompositor, StudioProject


class StudioProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temp_dir.name) / "studio.json"
        self.project = StudioProject(self.project_path, width=320, height=240)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scene_collection_round_trips_and_duplicates_with_fresh_ids(self):
        first = self.project.active_scene
        overlay = self.project.add_source(first["id"], {
            "name": "Test background",
            "type": "color",
            "color": "#123456",
            "width": 40,
            "height": 30,
            "opacity": 0.5,
        })
        duplicate = self.project.duplicate_scene(first["id"])
        self.assertNotEqual(duplicate["id"], first["id"])
        self.assertNotEqual(duplicate["sources"][0]["id"], overlay["id"])
        self.project.transition = {"type": "dissolve", "duration_ms": 250}
        self.project.save()

        restored = StudioProject(self.project_path)
        self.assertEqual(len(restored.scenes), 2)
        self.assertEqual(restored.transition, {"type": "dissolve", "duration_ms": 250})
        copied = next(scene for scene in restored.scenes if scene["id"] == duplicate["id"])
        self.assertEqual(copied["sources"][1]["color"], "#123456")
        self.assertEqual(copied["sources"][1]["opacity"], 0.5)

    def test_compositor_layers_sources_and_applies_opacity(self):
        scene = self.project.active_scene
        self.project.add_source(scene["id"], {
            "name": "Translucent red",
            "type": "color",
            "color": "#ff0000",
            "width": 20,
            "height": 20,
            "opacity": 0.5,
        })
        compositor = SceneCompositor(self.project)
        result = compositor.render(Image.new("RGB", (320, 240), "#ffffff"))
        red, green, blue = result.getpixel((5, 5))
        self.assertGreaterEqual(red, 250)
        self.assertTrue(120 <= green <= 135)
        self.assertTrue(120 <= blue <= 135)
        self.assertEqual(result.getpixel((100, 100)), (255, 255, 255))
        self.assertEqual(
            len(compositor.render_bgra(Image.new("RGB", (320, 240), "white"))),
            320 * 240 * 4,
        )

    def test_dissolve_transition_blends_previous_and_current_scenes(self):
        first = self.project.active_scene
        first["sources"][0]["visible"] = False
        self.project.add_source(first["id"], {
            "name": "White",
            "type": "color",
            "color": "#ffffff",
            "width": 320,
            "height": 240,
        })
        second = self.project.create_scene("Black")
        self.project.add_source(second["id"], {
            "name": "Black",
            "type": "color",
            "color": "#000000",
            "width": 320,
            "height": 240,
        })
        self.project.transition = {"type": "dissolve", "duration_ms": 1000}
        self.project.active_scene_id = first["id"]
        compositor = SceneCompositor(self.project)
        compositor.switch_scene(second["id"])
        midpoint = compositor.render(now=compositor._transition_started + 0.5)
        self.assertEqual(midpoint.getpixel((10, 10)), (127, 127, 127))

    def test_invalid_project_import_is_rejected_without_replacing_current_state(self):
        current_id = self.project.active_scene_id
        self.project_path.write_text(json.dumps({
            "schema": 1,
            "canvas": {"width": 320, "height": 240},
            "scenes": [{"id": "bad", "name": "Bad", "sources": [{
                "id": "bad-source",
                "name": "Bad source",
                "type": "unknown",
            }]}],
            "active_scene_id": "bad",
            "transition": {"type": "cut", "duration_ms": 0},
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Desteklenmeyen kaynak"):
            self.project.load(self.project_path)
        self.assertEqual(self.project.active_scene_id, current_id)
        self.assertEqual(len(self.project.scenes), 1)

    @unittest.skipUnless(os.name == "nt", "ScreenRecorder encoding smoke test requires Windows")
    def test_composited_frame_provider_produces_a_real_mp4(self):
        from imageio_ffmpeg import get_ffmpeg_exe

        with tempfile.TemporaryDirectory() as output_dir:
            frame = Image.new("RGB", (320, 240), "#204060").convert("RGBA")
            bgra = frame.tobytes("raw", "BGRA")
            recorder = ScreenRecorder(
                output_dir=output_dir,
                fps=5,
                resolution=(320, 240),
                ffmpeg_path=get_ffmpeg_exe(),
            )
            path, elapsed, stopped = recorder.record(
                duration=0.65,
                frame_provider=lambda: bgra,
                frame_size=(320, 240),
            )
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 1000)
            self.assertGreater(elapsed, 0)
            self.assertFalse(stopped)


if __name__ == "__main__":
    unittest.main()
