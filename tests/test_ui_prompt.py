import unittest

from app.ui_prompt import build_ui_prompt


class UIPromptTests(unittest.TestCase):
    def test_ui_pro_adds_production_constraints_and_raw_is_unchanged(self) -> None:
        prompt = "analytics empty state with a small observatory"
        enhanced = build_ui_prompt(
            prompt,
            asset_type="empty_state",
            platform="web",
            brand_palette="graphite, white, and signal green",
        )
        self.assertIn(prompt, enhanced)
        self.assertIn("principal product designer", enhanced)
        self.assertIn("negative space", enhanced)
        self.assertIn("one readable focal metaphor", enhanced)
        self.assertIn("Do not render words", enhanced)
        self.assertEqual(build_ui_prompt(f"  {prompt}  ", profile="raw"), prompt)


if __name__ == "__main__":
    unittest.main()
