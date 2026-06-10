import unittest

from src.ai_asset_audit.pipeline.scorer import (
    ScoreComponents,
    compute_final_score,
    label_from_score,
    texture_model_weight_factor,
)


class ScorerTests(unittest.TestCase):
    def test_metadata_confirmed_returns_one(self):
        components = ScoreComponents(metadata_confirmed=True)
        self.assertEqual(compute_final_score(components), 1.0)

    def test_label_thresholds(self):
        self.assertEqual(label_from_score(0.9), "Confirmed AI")
        self.assertEqual(label_from_score(0.7), "Likely AI")
        self.assertEqual(label_from_score(0.5), "Suspicious")
        self.assertEqual(label_from_score(0.3), "Likely Human")
        self.assertEqual(label_from_score(0.1), "Low AI evidence")

    def test_model_score_weighted(self):
        components = ScoreComponents(
            metadata_score=0.6,
            forensics_score=0.5,
            model_score=0.8,
        )
        score = compute_final_score(components)
        self.assertGreater(score, 0.5)
        self.assertLessEqual(score, 1.0)

    def test_texture_model_weight_factor_reduces_non_albedo_maps(self):
        self.assertEqual(texture_model_weight_factor("Road_01_D.png"), 1.0)
        self.assertLess(texture_model_weight_factor("Road_01_N.png"), 1.0)
        self.assertLess(texture_model_weight_factor("Road_01_MADS.png"), 1.0)
        self.assertLess(texture_model_weight_factor("Road_01_E.png"), 1.0)


if __name__ == "__main__":
    unittest.main()
