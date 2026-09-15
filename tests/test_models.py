import unittest

from upscaler.models import SIMPLE_LEVELS, get_profile, tile_candidates


class ModelTests(unittest.TestCase):
    def test_profiles_match_upstream_names(self) -> None:
        self.assertEqual(get_profile("clean").model_name, "RealESRGAN_x4plus")
        self.assertEqual(get_profile("compressed").model_name, "realesr-general-x4v3")
        self.assertEqual(get_profile("anime").model_name, "realesr-animevideov3")

    def test_tile_fallbacks_are_unique_and_descending(self) -> None:
        candidates = tile_candidates(256)
        self.assertEqual(candidates[0], 256)
        self.assertEqual(len(candidates), len(set(candidates)))
        self.assertTrue(all(left >= right for left, right in zip(candidates, candidates[1:])))

    def test_simple_levels_are_bounded_by_4k(self) -> None:
        self.assertEqual(SIMPLE_LEVELS, {"baixo": 1280, "medio": 1920, "alto": 3840})
        self.assertLessEqual(max(SIMPLE_LEVELS.values()), 3840)


if __name__ == "__main__":
    unittest.main()

