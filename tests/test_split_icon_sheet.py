import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


def load_module():
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
    return module


def opaque_pixels(image: Image.Image, threshold: int = 12) -> int:
    return sum(image.getchannel("A").histogram()[threshold:])


def blob(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=6, fill=(0, 120, 255, 255))


class GridSplitTests(unittest.TestCase):
    """The original uniform-grid contract must keep working."""

    def test_splits_transparent_sheet_into_centered_rgba_icons(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "sheet.png", root / "icons"
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

    def test_grid_does_not_drop_a_column_when_width_is_not_divisible(self) -> None:
        """131 // 3 == 43 would drop 2px; the last column must still reach the edge."""
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "sheet.png", root / "icons"
            sheet = Image.new("RGBA", (131, 50), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            # Third icon sits hard against the right edge; a dropped remainder clips it.
            for x in (6, 50, 96):
                blob(draw, x, 8, 30, 30)
            sheet.save(source)

            names = ["a", "b", "c"]
            module.split_sheet(source, output, names, columns=3, rows=1, canvas=64)
            for name in names:
                with Image.open(output / f"{name}.png") as icon:
                    self.assertGreater(opaque_pixels(icon), 0)

    def test_opaque_sheet_is_rejected(self) -> None:
        """The guard must actually fire - it used to check the padded canvas and never did."""
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sheet.png"
            Image.new("RGBA", (64, 64), (255, 255, 255, 255)).save(source)
            with self.assertRaises(ValueError) as ctx:
                module.split_sheet(source, root / "icons", ["a"], columns=1, rows=1, canvas=64)
            self.assertIn("opaque", str(ctx.exception))


class AutoSplitTests(unittest.TestCase):
    """Content-aware detection for sheets that are not on a perfect grid."""

    def test_recovers_intact_icons_from_uneven_spacing(self) -> None:
        """The reported bug: a drifting AI sheet gets sliced by a fixed grid.

        These placements sit roughly on a 4x2 grid but several straddle the cell edges at
        x=100/200/300. The old fixed-grid split mis-handled 7 of 8 here - one icon kept
        only 49% of its pixels while others absorbed a neighbour's fragment. Asserting on
        detected geometry (rather than post-scale pixel counts, which grow when a small
        icon is upscaled) proves nothing was cut and no neighbour leaked in.
        """
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "sheet.png", root / "icons"
            sheet = Image.new("RGBA", (400, 220), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            placements = [
                (70, 25, 60, 60),    # straddles x=100
                (160, 20, 55, 55),   # straddles x=200
                (250, 30, 65, 50),   # straddles x=300
                (345, 22, 50, 60),
                (40, 125, 55, 60),
                (150, 130, 60, 50),  # straddles x=200
                (250, 135, 50, 55),
                (330, 128, 55, 60),
            ]
            for x, y, w, h in placements:
                blob(draw, x, y, w, h)
            sheet.save(source)

            names = ["add", "edit", "delete", "search", "share", "filter", "sort", "more"]
            boxes = module.split_auto(source, output, names, canvas=128, expected=8)
            self.assertEqual(len(boxes), 8)

            # Detection order must match the reading order of the placements above.
            for (x, y, w, h), box in zip(placements, boxes):
                expected = (x, y, x + w + 1, y + h + 1)
                for actual_edge, expected_edge in zip(box, expected):
                    self.assertAlmostEqual(
                        actual_edge, expected_edge, delta=2,
                        msg=f"box {box} does not match placement {expected}",
                    )

            for name in names:
                with Image.open(output / f"{name}.png") as icon:
                    self.assertEqual(icon.mode, "RGBA")
                    self.assertEqual(icon.size, (128, 128))
                    self.assertEqual(icon.getchannel("A").getextrema(), (0, 255))

    def test_multi_part_icon_stays_one_icon(self) -> None:
        """A detached dot must merge with its stem, not become a separate icon."""
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sheet.png"
            sheet = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            # Icon 1: an "i" - stem plus a dot 8px above it (within the merge gap).
            blob(draw, 30, 40, 16, 40)
            blob(draw, 30, 20, 16, 12)
            # Icon 2: a plain square far away.
            blob(draw, 200, 30, 50, 50)
            sheet.save(source)

            boxes = module.split_auto(source, root / "icons", None, canvas=128, dry_run=True)
            self.assertEqual(len(boxes), 2)
            # The first box must span the dot and the stem together.
            self.assertLessEqual(boxes[0][1], 22)
            self.assertGreaterEqual(boxes[0][3], 78)

    def test_noise_speck_is_filtered(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sheet.png"
            sheet = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            blob(draw, 20, 20, 60, 60)
            blob(draw, 150, 50, 60, 60)
            # A 2x2 speck, far below min_area.
            draw.rectangle((120, 10, 121, 11), fill=(0, 120, 255, 255))
            sheet.save(source)

            boxes = module.split_auto(source, root / "icons", None, canvas=64, dry_run=True)
            self.assertEqual(len(boxes), 2)

    def test_faint_halo_does_not_inflate_bounds(self) -> None:
        """rembg leaves alpha 1-10 fringe; it must not widen the detected box."""
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sheet.png"
            sheet = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            draw.rectangle((0, 0, 119, 119), fill=(0, 120, 255, 4))  # full-bleed halo
            blob(draw, 40, 40, 30, 30)
            sheet.save(source)

            boxes = module.split_auto(source, root / "icons", None, canvas=64, dry_run=True)
            self.assertEqual(len(boxes), 1)
            left, top, right, bottom = boxes[0]
            self.assertGreater(left, 30)
            self.assertLess(right, 80)

    def test_names_map_in_reading_order(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "sheet.png", root / "icons"
            sheet = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            # Row 1 jittered vertically; row 2 below. Draw out of order on purpose.
            draw.rectangle((210, 30, 250, 70), fill=(255, 0, 0, 255))       # top-right
            draw.rectangle((20, 24, 60, 64), fill=(0, 255, 0, 255))         # top-left
            draw.rectangle((20, 130, 60, 170), fill=(0, 0, 255, 255))       # bottom-left
            sheet.save(source)

            module.split_auto(source, output, ["green", "red", "blue"], canvas=64)
            expected = {"green": (0, 255, 0), "red": (255, 0, 0), "blue": (0, 0, 255)}
            for name, rgb in expected.items():
                with Image.open(output / f"{name}.png") as icon:
                    colors = icon.convert("RGB").getcolors(maxcolors=100000) or []
                    present = {color for count, color in colors}
                    self.assertIn(rgb, present, f"{name} received the wrong icon")

    def test_small_icon_is_upscaled_to_canvas(self) -> None:
        """thumbnail() only shrank; a 20px icon used to stay 20px on a 128px canvas."""
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "sheet.png", root / "icons"
            sheet = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            ImageDraw.Draw(sheet).rectangle((40, 40, 59, 59), fill=(0, 120, 255, 255))
            sheet.save(source)

            module.split_auto(source, output, ["tiny"], canvas=128)
            with Image.open(output / "tiny.png") as icon:
                bounds = icon.getchannel("A").point(lambda v: 255 if v >= 12 else 0).getbbox()
                self.assertIsNotNone(bounds)
                drawn = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
                self.assertGreater(drawn, 90, "small icon was not upscaled to the canvas budget")

    def test_count_mismatch_fails_loudly(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sheet.png"
            sheet = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            blob(draw, 20, 20, 50, 50)
            blob(draw, 120, 20, 50, 50)
            sheet.save(source)

            with self.assertRaises(ValueError) as ctx:
                module.split_auto(source, root / "icons", ["a", "b", "c"], canvas=64)
            self.assertIn("detected 2", str(ctx.exception))

    def test_auto_matte_keys_out_a_solid_background(self) -> None:
        """Fallback for when rembg was unavailable: the sheet arrives fully opaque."""
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "sheet.png", root / "icons"
            sheet = Image.new("RGB", (240, 120), (247, 248, 250))
            draw = ImageDraw.Draw(sheet)
            draw.ellipse((30, 25, 100, 95), fill=(20, 20, 24))
            draw.ellipse((140, 25, 210, 95), fill=(20, 20, 24))
            sheet.save(source)

            # Without --auto-matte an opaque sheet must be refused outright.
            with self.assertRaises(ValueError) as ctx:
                module.split_auto(source, output, None, canvas=64, dry_run=True)
            self.assertIn("opaque", str(ctx.exception))

            boxes = module.split_auto(
                source, output, ["a", "b"], canvas=64, auto_matte=True
            )
            self.assertEqual(len(boxes), 2)
            for name in ("a", "b"):
                with Image.open(output / f"{name}.png") as icon:
                    self.assertEqual(icon.getchannel("A").getextrema(), (0, 255))

    def test_writes_auto_numbered_icons_when_no_names_given(self) -> None:
        """--layout auto without --names must number them, not crash."""
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "sheet.png", root / "icons"
            sheet = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            blob(draw, 20, 20, 50, 50)
            blob(draw, 120, 20, 50, 50)
            sheet.save(source)

            module.split_auto(source, output, None, canvas=64)
            self.assertTrue((output / "icon-01.png").exists())
            self.assertTrue((output / "icon-02.png").exists())

    def test_report_records_detected_boxes(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, report = root / "sheet.png", root / "report.json"
            sheet = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sheet)
            blob(draw, 20, 20, 50, 50)
            blob(draw, 120, 20, 50, 50)
            sheet.save(source)

            module.split_auto(source, root / "icons", None, canvas=64, dry_run=True, report=report)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["count"], 2)
            self.assertEqual(len(payload["boxes"]), 2)

    def test_dry_run_writes_nothing(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "sheet.png", root / "icons"
            sheet = Image.new("RGBA", (120, 60), (0, 0, 0, 0))
            blob(ImageDraw.Draw(sheet), 20, 10, 40, 40)
            sheet.save(source)

            module.split_auto(source, output, ["only"], canvas=64, dry_run=True)
            self.assertFalse(output.exists(), "dry run must not write files")


if __name__ == "__main__":
    unittest.main()
