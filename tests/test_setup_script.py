import contextlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SetupScriptTests(unittest.TestCase):
    def test_qwen_only_configuration_does_not_require_openai_key(self) -> None:
        script = Path(__file__).parents[1] / "scripts" / "setup.py"
        spec = importlib.util.spec_from_file_location("setup_script", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(directory):
            with (
                patch.object(sys, "argv", [str(script)]),
                patch("builtins.input", return_value="qwen"),
                patch("getpass.getpass", side_effect=["", "", "qwen-key", ""]),
            ):
                module.main()
            content = Path(".env").read_text(encoding="utf-8")
        self.assertIn("IMAGE_MODEL=qwen-image-2.0-pro", content)
        self.assertIn("QWEN_API_KEY=qwen-key", content)
        self.assertIn("OPENAI_API_KEY=\n", content)


if __name__ == "__main__":
    unittest.main()
