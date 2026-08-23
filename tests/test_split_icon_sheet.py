import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


class SplitIconSheetTests(unittest.TestCase):
    def test_splits_transparent_sheet_into_centered_rgba_icons(self) -> None:
        script = (
            Path(__file__).parents[1]
            / "plugins"
            / "gpt-image-2-assets"
            / "skills"
            / "ui-ux-asset-pipeline"
            / "scripts"
            / "split_icon_sheet.py"
        )
        spec = importlib.util.spec_from_file_location("split_icon_sheet", script)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sheet.png"
            output = root / "icons"
            sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            for x, y in ((8, 8), (72, 8), (8, 72), (72, 72)):
                draw.rounded_rectangle((x, y, x + 40, y + 40), radius=8, fill=(0, 120, 255, 255))
            sheet.save(source)

            names = ["add", "edit", "delete", "search"]
            module.split_sheet(source, output, names, columns=2, rows=2, canvas=64)

            for name in names:
                with Image.open(output / f"{name}.png") as icon:
                    self.assertEqual(icon.mode, "RGBA")
                    self.assertEqual(icon.size, (64, 64))
                    self.assertEqual(icon.getchannel("A").getextrema(), (0, 255))


if __name__ == "__main__":
    unittest.main()
