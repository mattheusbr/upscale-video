import unittest

from upscaler.media import crop_filter_for_aspect


class CropFilterTests(unittest.TestCase):
    def test_landscape_to_vertical_crops_width(self) -> None:
        crop, width, height = crop_filter_for_aspect(1920, 1080, 1080, 1920)
        self.assertEqual((width, height), (606, 1080))
        self.assertEqual(crop, "crop=606:1080:657:0")

    def test_portrait_to_vertical_crops_height(self) -> None:
        crop, width, height = crop_filter_for_aspect(1080, 1920, 1080, 1920)
        self.assertEqual((width, height), (1080, 1920))
        self.assertEqual(crop, "crop=1080:1920:0:0")

