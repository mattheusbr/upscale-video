import unittest

from upscaler.cli import build_parser, normalize_argv
from upscaler.models import SIMPLE_LEVELS, get_profile, tile_candidates


class ModelTests(unittest.TestCase):
    def test_profiles_match_upstream_names(self) -> None:
        self.assertEqual(get_profile("clean").model_name, "RealESRGAN_x4plus")
        self.assertEqual(get_profile("compressed").model_name, "realesr-general-x4v3")
        self.assertEqual(get_profile("anime").model_name, "realesr-animevideov3")
        self.assertEqual(get_profile("max").model_name, "RealESRGAN_x4plus")

    def test_tile_fallbacks_are_unique_and_descending(self) -> None:
        candidates = tile_candidates(256)
        self.assertEqual(candidates[0], 256)
        self.assertEqual(len(candidates), len(set(candidates)))
        self.assertTrue(all(left >= right for left, right in zip(candidates, candidates[1:])))

    def test_simple_levels_are_bounded_by_4k(self) -> None:
        self.assertEqual(SIMPLE_LEVELS["baixo"], 1280)
        self.assertEqual(SIMPLE_LEVELS["medio"], 1920)
        self.assertEqual(SIMPLE_LEVELS["alto"], 3840)
        self.assertEqual(SIMPLE_LEVELS["max"], 3840)
        self.assertLessEqual(max(SIMPLE_LEVELS.values()), 3840)

    def test_max_profile_is_the_heaviest_quality_profile(self) -> None:
        self.assertEqual(get_profile("max").key, "max")
        self.assertIn("max", sorted(get_profile("max").key for _ in [0]))

    def test_bare_input_defaults_to_simple_mode(self) -> None:
        args = build_parser().parse_args(normalize_argv(["input.mp4", "--nivel", "alto"]))
        self.assertEqual(args.command, "simple")
        self.assertEqual(args.input, "input.mp4")
        self.assertEqual(args.nivel, "alto")


if __name__ == "__main__":
    unittest.main()

