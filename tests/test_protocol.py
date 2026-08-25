import base64
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from mcp.client import Client
from mcp_types.version import (
    HANDSHAKE_PROTOCOL_VERSIONS,
    LATEST_PROTOCOL_VERSION,
    MODERN_PROTOCOL_VERSIONS,
)

from app.config import get_settings
from app.config import Settings
from app.main import app
from app.mcp_server import SERVER_VERSION, mcp, protocol_versions

# The 2026-07-28 revision carries a per-request envelope in params._meta and requires the
# request method to be echoed in an mcp-method header. Real SDK clients add both; a raw
# HTTP caller has to supply them explicitly.
PROTOCOL_VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"

# Matches the default MCP_ALLOWED_HOSTS pattern "127.0.0.1:*", which requires a port.
ALLOWED_HOST = "127.0.0.1:8000"

# StreamableHTTPSessionManager.run() may only be called once per instance, and
# mcp_http_app is created at import time, so the whole process shares one lifespan.
_client: TestClient | None = None


def setUpModule() -> None:
    global _client
    _client = TestClient(app)
    _client.__enter__()


def tearDownModule() -> None:
    if _client is not None:
        _client.__exit__(None, None, None)


def mcp_headers(version: str, *, modern: bool) -> dict[str, str]:
    headers = {
        "MCP-Protocol-Version": version,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Host": ALLOWED_HOST,
    }
    if modern:
        headers["mcp-method"] = "tools/list"
    # Authenticate with whatever the environment configures so the protocol assertions
    # hold whether or not a service key is set locally.
    key = (get_settings().service_api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


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
        assert _client is not None
        health = _client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["mcp_endpoint"], "/mcp")
        paths = _client.get("/openapi.json").json()["paths"]
        self.assertIn("/v1/images/generate", paths)
        self.assertIn("/v1/images/edit", paths)

    def test_health_reports_protocol_versions(self) -> None:
        assert _client is not None
        payload = _client.get("/health").json()
        self.assertEqual(payload["server_version"], SERVER_VERSION)
        self.assertEqual(payload["protocol_versions"]["latest"], LATEST_PROTOCOL_VERSION)


class ProtocolVersionTests(unittest.TestCase):
    """Pin the negotiated revisions so a dependency change cannot silently drop them."""

    def test_latest_revision_is_the_modern_envelope(self) -> None:
        self.assertEqual(LATEST_PROTOCOL_VERSION, "2026-07-28")
        self.assertIn(LATEST_PROTOCOL_VERSION, MODERN_PROTOCOL_VERSIONS)

    def test_server_advertises_latest_and_handshake_revisions(self) -> None:
        versions = protocol_versions()
        self.assertEqual(versions["latest"], "2026-07-28")
        self.assertIn("2025-11-25", versions["handshake"])
        # Semver belongs to the implementation, never to the wire protocol.
        self.assertNotIn(SERVER_VERSION, HANDSHAKE_PROTOCOL_VERSIONS)
        self.assertNotIn(SERVER_VERSION, MODERN_PROTOCOL_VERSIONS)


class StreamableHttpProtocolTests(unittest.TestCase):
    """Exercise /mcp over real HTTP at both protocol eras."""

    def _list_tools(self, version: str, *, modern: bool) -> list[str]:
        assert _client is not None
        params: dict = {}
        if modern:
            params["_meta"] = {PROTOCOL_VERSION_KEY: version, CLIENT_CAPABILITIES_KEY: {}}
        response = _client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": params},
            headers=mcp_headers(version, modern=modern),
        )
        self.assertEqual(response.status_code, 200, response.text)
        return [tool["name"] for tool in response.json()["result"]["tools"]]

    def test_modern_envelope_lists_tools(self) -> None:
        names = self._list_tools("2026-07-28", modern=True)
        self.assertEqual(names, ["list_ui_models", "generate_ui_asset", "edit_ui_asset"])

    def test_prior_handshake_revision_still_lists_tools(self) -> None:
        names = self._list_tools("2025-11-25", modern=False)
        self.assertEqual(names, ["list_ui_models", "generate_ui_asset", "edit_ui_asset"])


class McpProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_and_list_tools(self) -> None:
        async with Client(mcp) as client:
            result = await client.list_tools()
        self.assertEqual(
            [tool.name for tool in result.tools],
            ["list_ui_models", "generate_ui_asset", "edit_ui_asset"],
        )

    async def test_interface_mockup_asset_type_is_accepted(self) -> None:
        isolated_settings = Settings(openai_api_key="test", image_model="gpt-image-2", oss_enabled=False)
        with (
            patch("app.mcp_server.get_client", return_value=FakeOpenAI()),
            patch("app.mcp_server.settings", isolated_settings),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "generate_ui_asset",
                    {
                        "prompt": "dashboard screen concept",
                        "background": "opaque",
                        "asset_type": "interface_mockup",
                        "text_policy": "minimal_text",
                    },
                )
        self.assertFalse(result.is_error, result.content)

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
