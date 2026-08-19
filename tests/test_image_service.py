import base64
import unittest

from app.config import Settings
from app.image_service import decode_image_input, generate_images
from app.schemas import GenerateRequest


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-payload"


class FakeImages:
    def __init__(self) -> None:
        self.kwargs = None

    async def generate(self, **kwargs):
        self.kwargs = kwargs
        return {
            "created": 123,
            "output_format": "png",
            "size": kwargs["size"],
            "quality": kwargs["quality"],
            "data": [{"b64_json": base64.b64encode(PNG_BYTES).decode()}],
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        }


class FakeClient:
    def __init__(self) -> None:
        self.images = FakeImages()


class ImageServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_maps_gpt_image_2_parameters_and_metadata(self) -> None:
        client = FakeClient()
        settings = Settings(
            openai_api_key="test",
            image_model="gpt-image-2",
            oss_enabled=False,
            max_concurrent_generations=2,
        )
        request = GenerateRequest(
            prompt="quiet analytics empty-state illustration without text",
            size="1536x864",
            quality="high",
            background="opaque",
            output_format="png",
            moderation="auto",
        )

        response = await generate_images(client, settings, request)  # type: ignore[arg-type]

        self.assertEqual(client.images.kwargs["model"], "gpt-image-2")
        self.assertEqual(client.images.kwargs["size"], "1536x864")
        self.assertEqual(client.images.kwargs["moderation"], "auto")
        self.assertEqual(response.images[0].mime_type, "image/png")
        self.assertEqual(response.usage["total_tokens"], 3)

    def test_decodes_data_url_and_rejects_mime_mismatch(self) -> None:
        encoded = base64.b64encode(PNG_BYTES).decode()
        image = decode_image_input(f"data:image/png;base64,{encoded}", 1, 1024)
        self.assertTrue(image.name.endswith(".png"))

        with self.assertRaisesRegex(ValueError, "格式不匹配"):
            decode_image_input(f"data:image/jpeg;base64,{encoded}", 1, 1024)


if __name__ == "__main__":
    unittest.main()
