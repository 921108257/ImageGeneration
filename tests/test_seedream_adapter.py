import base64
import unittest

from app.config import Settings
from app.image_service import to_image_response


class SeedreamNormalizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_url_and_base64_compatible_shapes(self) -> None:
        settings = Settings(openai_api_key="test", seedream_api_key="seed", oss_enabled=False)
        url_response = await to_image_response(
            "doubao-seedream-4-0-250828",
            {"data": [{"url": "https://example.com/seedream.png"}]},
            settings,
        )
        self.assertEqual(url_response.provider, "seedream")
        self.assertEqual(url_response.images[0].url, "https://example.com/seedream.png")

        encoded = base64.b64encode(b"\x89PNG\r\n\x1a\nmock").decode()
        base64_response = await to_image_response(
            "doubao-seedream-4-0-250828",
            {"data": [{"b64_json": encoded}]},
            settings,
            "png",
        )
        self.assertEqual(base64_response.images[0].mime_type, "image/png")


if __name__ == "__main__":
    unittest.main()
