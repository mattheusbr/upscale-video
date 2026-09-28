import tempfile
import unittest
from pathlib import Path

from upscaler.media import crop_filter_for_aspect
from upscaler.tui import build_output_path, resolve_input_path


class CropFilterTests(unittest.TestCase):
    def test_landscape_to_vertical_crops_width(self) -> None:
        crop, width, height = crop_filter_for_aspect(1920, 1080, 1080, 1920)
        self.assertEqual((width, height), (606, 1080))
        self.assertEqual(crop, "crop=606:1080:657:0")

    def test_portrait_to_vertical_crops_height(self) -> None:
        crop, width, height = crop_filter_for_aspect(1080, 1920, 1080, 1920)
        self.assertEqual((width, height), (1080, 1920))
        self.assertEqual(crop, "crop=1080:1920:0:0")


class OutputPathTests(unittest.TestCase):
    def test_build_output_path_prefixes_profile_and_level(self) -> None:
        output = build_output_path(Path("C:/videos/sample.mp4"), "clean", "alto")
        self.assertEqual(output.name, "clean_alto_sample.mp4")
        self.assertEqual(output.parent, Path("C:/videos"))

    def test_build_output_path_avoids_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "sample.mp4"
            input_path.write_bytes(b"video")

            first = build_output_path(input_path, "max", "medio")
            first.write_bytes(b"result")

            second = build_output_path(input_path, "max", "medio")
            self.assertEqual(second.name, "max_medio_sample_1.mp4")

    def test_resolve_input_path_keeps_windows_absolute_value(self) -> None:
        path = resolve_input_path(r"C:\Users\mathe\Downloads\video.mp4")
        self.assertEqual(str(path), r"C:\Users\mathe\Downloads\video.mp4")

