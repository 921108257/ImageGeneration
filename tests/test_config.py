import os
import unittest
from unittest.mock import patch

from app.config import Settings


class EnvironmentAliasTests(unittest.TestCase):
    def test_compatibility_aliases_load_service_security_settings(self) -> None:
        env = {
            "API_KEY": "service-token",
            "MCP_HOSTS": "image.example.com,image.example.com:*",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.service_api_key, "service-token")
        self.assertEqual(settings.allowed_mcp_hosts(), ["image.example.com", "image.example.com:*"])

    def test_canonical_names_take_precedence_over_compatibility_aliases(self) -> None:
        env = {
            "SERVICE_API_KEY": "canonical-token",
            "API_KEY": "compat-token",
            "MCP_ALLOWED_HOSTS": "canonical.example.com",
            "MCP_HOSTS": "compat.example.com",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.service_api_key, "canonical-token")
        self.assertEqual(settings.allowed_mcp_hosts(), ["canonical.example.com"])


if __name__ == "__main__":
    unittest.main()
