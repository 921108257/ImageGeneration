#!/usr/bin/env python3
"""Split a transparent regular icon sheet into centered PNG resources."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def split_sheet(source: Path, output_dir: Path, names: list[str], columns: int, rows: int, canvas: int) -> None:
    image = Image.open(source).convert("RGBA")
    if len(names) != columns * rows:
        raise ValueError(f"expected {columns * rows} names for a {columns}x{rows} sheet")
    output_dir.mkdir(parents=True, exist_ok=True)
    cell_width, cell_height = image.width // columns, image.height // rows
    for index, name in enumerate(names):
        cell = image.crop(
            (
                (index % columns) * cell_width,
                (index // columns) * cell_height,
                (index % columns + 1) * cell_width,
                (index // columns + 1) * cell_height,
            )
        )
        bounds = cell.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"{name}: no visible pixels after background removal")
        cell = cell.crop(bounds)
        cell.thumbnail((canvas - 24, canvas - 24), Image.Resampling.LANCZOS)
        result = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        result.alpha_composite(cell, ((canvas - cell.width) // 2, (canvas - cell.height) // 2))
        if result.getchannel("A").getextrema() == (255, 255):
            raise ValueError(f"{name}: output is opaque; run rembg before splitting")
        result.save(output_dir / f"{name}.png", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--names", nargs="+", required=True)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--canvas", type=int, default=256)
    args = parser.parse_args()
    split_sheet(args.input, args.output_dir, args.names, args.columns, args.rows, args.canvas)


if __name__ == "__main__":
    main()
