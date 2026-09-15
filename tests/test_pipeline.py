import unittest

from upscaler.pipeline import _even_output_scale


class OutputScaleTests(unittest.TestCase):
    def test_output_scale_produces_even_intermediate_dimensions(self) -> None:
        scale = _even_output_scale(1920, 886, 2772 / 1920)

        self.assertEqual(int(1920 * scale) % 2, 0)
        self.assertEqual(int(886 * scale) % 2, 0)


if __name__ == "__main__":
    unittest.main()