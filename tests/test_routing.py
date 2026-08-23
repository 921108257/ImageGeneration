import unittest

from app.config import Settings
from app.openai_client import provider_for_model, resolve_api_key, resolve_base_url, uses_small_image_key
from app.schemas import validate_size


class ProviderRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            openai_api_key="default-key",
            openai_api_key_1k="small-key",
            openai_base_url="https://openai.example/v1",
            qwen_api_key="qwen-key",
            qwen_base_url="https://qwen.example/generate",
            seedream_api_key="seedream-key",
            seedream_base_url="https://seedream.example/v3",
        )

    def test_gpt_image_2_uses_small_key_only_for_explicit_1k_or_smaller_size(self) -> None:
        self.assertTrue(uses_small_image_key("gpt-image-2", "1024x768", self.settings))
        self.assertEqual(resolve_api_key("gpt-image-2", "1024x768", self.settings), "small-key")
        for size in ("auto", "1536x1024"):
            with self.subTest(size=size):
                self.assertEqual(resolve_api_key("gpt-image-2", size, self.settings), "default-key")

        self.settings.openai_api_key_1k = None
        self.assertEqual(resolve_api_key("gpt-image-2", "512x512", self.settings), "default-key")

    def test_routes_qwen_and_seedream_to_their_own_credentials(self) -> None:
        cases = (
            ("qwen-image-2.0-pro", "qwen", "qwen-key", "https://qwen.example/generate"),
            ("doubao-seedream-4-0-250828", "seedream", "seedream-key", "https://seedream.example/v3"),
        )
        for model, provider, key, base_url in cases:
            with self.subTest(model=model):
                self.assertEqual(provider_for_model(model, self.settings), provider)
                self.assertEqual(resolve_api_key(model, "1024x1024", self.settings), key)
                self.assertEqual(resolve_base_url(model, self.settings), base_url)

    def test_accepts_seedream_size_presets(self) -> None:
        self.assertEqual(validate_size("2K", "doubao-seedream-4-0-250828"), "2K")


if __name__ == "__main__":
    unittest.main()
