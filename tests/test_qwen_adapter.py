import unittest
from unittest.mock import patch

from app.config import Settings
from app.image_service import _generate_qwen
from app.schemas import GenerateRequest


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "output": {
                "choices": [
                    {"message": {"content": [{"image": "https://example.com/qwen.png"}]}}
                ]
            },
            "usage": {"image_count": 1},
        }


class FakeHttpClient:
    last_request = None

    def __init__(self, *args, **kwargs) -> None:
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, url, **kwargs):
        self.request = (url, kwargs)
        type(self).last_request = self.request
        return FakeResponse()


class QwenAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_maps_native_dashscope_response_to_common_data_shape(self) -> None:
        settings = Settings(
            openai_api_key="openai",
            qwen_api_key="qwen",
            qwen_base_url="https://qwen.example/generate",
        )
        request = GenerateRequest(
            prompt="empty state",
            model="qwen-image-2.0-pro",
            size="1024x1024",
            prompt_profile="raw",
        )
        with patch("app.image_service.httpx.AsyncClient", FakeHttpClient):
            payload = await _generate_qwen(settings, request, request.prompt)
        self.assertEqual(payload["data"][0]["url"], "https://example.com/qwen.png")
        self.assertEqual(payload["usage"]["image_count"], 1)
        body = FakeHttpClient.last_request[1]["json"]
        self.assertEqual(body["parameters"]["size"], "1024*1024")
        self.assertFalse(body["parameters"]["prompt_extend"])


if __name__ == "__main__":
    unittest.main()
