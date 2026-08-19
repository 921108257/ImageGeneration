import base64
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from mcp.client import Client

from app.config import Settings
from app.main import app
from app.mcp_server import mcp


class FakeImages:
    async def generate(self, **kwargs):
        return {
            "created": 123,
            "output_format": kwargs.get("output_format", "png"),
            "data": [{"b64_json": base64.b64encode(b"\x89PNG\r\n\x1a\nmock").decode()}],
        }


class FakeOpenAI:
    def __init__(self) -> None:
        self.images = FakeImages()


class HttpSmokeTests(unittest.TestCase):
    def test_health_and_openapi(self) -> None:
        with TestClient(app) as client:
            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["mcp_endpoint"], "/mcp")
            paths = client.get("/openapi.json").json()["paths"]
            self.assertIn("/v1/images/generate", paths)
            self.assertIn("/v1/images/edit", paths)


class McpProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_and_list_tools(self) -> None:
        async with Client(mcp) as client:
            result = await client.list_tools()
        self.assertEqual(
            [tool.name for tool in result.tools],
            ["generate_ui_asset", "edit_ui_asset"],
        )

    async def test_generate_tool_returns_standard_image_content(self) -> None:
        isolated_settings = Settings(openai_api_key="test", image_model="gpt-image-2", oss_enabled=False)
        with (
            patch("app.mcp_server.get_client", return_value=FakeOpenAI()),
            patch("app.mcp_server.settings", isolated_settings),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "generate_ui_asset",
                    {"prompt": "simple opaque UI placeholder", "background": "opaque"},
                )
        self.assertFalse(result.is_error)
        self.assertTrue(any(block.type == "image" for block in result.content))
        self.assertEqual(result.structured_content["model"], "gpt-image-2")


if __name__ == "__main__":
    unittest.main()
