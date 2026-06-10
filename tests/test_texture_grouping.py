import unittest

from src.ai_asset_audit.pipeline.pipeline import AssetResult
from src.ai_asset_audit.pipeline.texture_grouping import (
    apply_material_group_review,
    parse_texture_role,
)


class TextureGroupingTests(unittest.TestCase):
    def test_parse_texture_role_groups_related_texture_maps(self):
        d = parse_texture_role("Bigworld_Road_Dirt_01_D.png")
        n = parse_texture_role("Bigworld_Road_Dirt_01_N.png")
        mads = parse_texture_role("Bigworld_Road_Dirt_01_MADS.png")

        self.assertEqual(d.group_key, "Bigworld_Road_Dirt_01")
        self.assertEqual(n.group_key, d.group_key)
        self.assertEqual(mads.group_key, d.group_key)
        self.assertEqual(d.role, "albedo")
        self.assertEqual(n.role, "normal")
        self.assertEqual(mads.role, "packed")

    def test_group_review_marks_isolated_auxiliary_suspicion(self):
        results = [
            AssetResult(
                file_id="sha256:1",
                relative_path="Road_01_D.png",
                asset_type="image",
                size_bytes=1,
                final_label="Likely Human",
                confidence=0.35,
            ),
            AssetResult(
                file_id="sha256:2",
                relative_path="Road_01_N.png",
                asset_type="image",
                size_bytes=1,
                final_label="Suspicious",
                confidence=0.49,
                review_required=True,
                evidence=["Pixel forensics abnormal"],
            ),
            AssetResult(
                file_id="sha256:3",
                relative_path="Road_01_MADS.png",
                asset_type="image",
                size_bytes=1,
                final_label="Likely Human",
                confidence=0.34,
            ),
        ]

        apply_material_group_review(results)

        normal = results[1]
        self.assertEqual(normal.final_label, "Likely Human")
        self.assertTrue(normal.review_required)
        self.assertIn("Isolated auxiliary texture suspicion downgraded by material group review", normal.evidence)
        self.assertEqual(normal.metadata["texture_role"], "normal")
        self.assertEqual(normal.metadata["material_group"], "Road_01")


if __name__ == "__main__":
    unittest.main()
