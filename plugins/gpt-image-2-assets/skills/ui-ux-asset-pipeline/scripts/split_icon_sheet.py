#!/usr/bin/env python3
"""Split an icon sheet into centered transparent PNG resources.

Two layout modes:

* ``auto`` (default) finds each icon from the alpha channel with connected-component
  analysis, so it tolerates the uneven spacing and drift of AI-generated sheets that a
  fixed grid slices through. Nearby fragments (a detached dot, a dashed stroke, a badge)
  are merged back into one icon so detection never *over*-splits.
* ``grid`` keeps the original uniform ``columns``x``rows`` contract for sheets that really
  are laid out on a regular grid.

Both modes trim each icon to its true alpha bounds and recenter it on a transparent
canvas. ``--dry-run`` reports what was detected without writing, which is the safe way to
confirm the icon count before committing cut files to a project.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops

# Alpha at or above this is treated as "ink"; below it is background or an rembg halo.
DEFAULT_ALPHA_THRESHOLD = 12
# Components smaller than this many pixels are noise (stray matte specks, JPEG fringe).
DEFAULT_MIN_AREA = 64
# Fragments within this many pixels belong to the same icon and are merged.
DEFAULT_MERGE_GAP = 12
# Transparent margin kept around each icon, as a fraction of the canvas edge.
DEFAULT_PADDING_RATIO = 0.10

Box = tuple[int, int, int, int]  # (left, top, right, bottom), right/bottom exclusive


# --------------------------------------------------------------------------- masking


def alpha_bytes(image: Image.Image, threshold: int) -> tuple[bytes, int, int]:
    """Return a 1-byte-per-pixel mask (255 = ink) plus the image dimensions."""
    alpha = image.getchannel("A").point(lambda v: 255 if v >= threshold else 0)
    return alpha.tobytes(), image.width, image.height


def _row_runs(mask: bytes, width: int, y: int) -> list[tuple[int, int]]:
    """Horizontal runs of ink on row ``y`` as (start, end-exclusive) pairs."""
    row = mask[y * width : (y + 1) * width]
    runs: list[tuple[int, int]] = []
    pos = 0
    while True:
        start = row.find(0xFF, pos)
        if start < 0:
            break
        end = row.find(0x00, start)
        if end < 0:
            end = width
        runs.append((start, end))
        pos = end
    return runs


# ------------------------------------------------------------- connected components


class _Union:
    """Minimal union-find over integer labels."""

    def __init__(self) -> None:
        self.parent: list[int] = [0]  # label 0 is a reserved sentinel

    def make(self) -> int:
        label = len(self.parent)
        self.parent.append(label)
        return label

    def find(self, label: int) -> int:
        root = label
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[label] != root:
            label, self.parent[label] = self.parent[label], root
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def find_components(mask: bytes, width: int, height: int, min_area: int) -> list[Box]:
    """Label connected ink regions and return their bounding boxes.

    Runs on adjacent rows that overlap (with one pixel of slack, so diagonally touching
    strokes stay together) share a label via union-find. Each run keeps its own label;
    bounding boxes and ink area are accumulated per root in a single final pass, so a
    component spanning many rows is measured across all of them. Boxes with fewer than
    ``min_area`` ink pixels are dropped as noise.
    """
    union = _Union()
    runs: list[tuple[int, int, int, int]] = []  # (start, end, y, label)
    prev: list[tuple[int, int, int]] = []  # (start, end, label) for the previous row

    for y in range(height):
        current: list[tuple[int, int, int]] = []
        for start, end in _row_runs(mask, width, y):
            label = 0
            for pstart, pend, plabel in prev:
                # Overlap with 1px slack bridges diagonal adjacency.
                if pstart - 1 < end and start < pend + 1:
                    if label == 0:
                        label = plabel
                    else:
                        union.union(label, plabel)
            if label == 0:
                label = union.make()
            current.append((start, end, label))
            runs.append((start, end, y, label))
        prev = current

    # Accumulate bbox and ink area per connected root in one pass.
    stats: dict[int, list[int]] = {}  # root -> [left, top, right, bottom, area]
    for start, end, y, label in runs:
        root = union.find(label)
        box = stats.get(root)
        if box is None:
            stats[root] = [start, y, end, y + 1, end - start]
        else:
            box[0] = min(box[0], start)
            box[1] = min(box[1], y)
            box[2] = max(box[2], end)
            box[3] = max(box[3], y + 1)
            box[4] += end - start

    return [
        (left, top, right, bottom)
        for left, top, right, bottom, area in stats.values()
        if area >= min_area
    ]


# ----------------------------------------------------------------- box arrangement


def _gap(a: Box, b: Box) -> float:
    """Edge-to-edge distance between two boxes; 0 when they overlap on both axes.

    ``hypot`` covers all three cases at once: when the boxes overlap on one axis that
    axis contributes 0 and the result is the plain gap on the other; when they are
    diagonal it is the corner-to-corner distance.
    """
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return math.hypot(dx, dy)


def merge_nearby(boxes: list[Box], gap: int) -> list[Box]:
    """Union boxes closer than ``gap`` so multi-part icons stay one icon."""
    boxes = list(boxes)
    changed = True
    while changed:
        changed = False
        result: list[Box] = []
        while boxes:
            left, top, right, bottom = boxes.pop()
            keep: list[Box] = []
            for other in boxes:
                if _gap((left, top, right, bottom), other) <= gap:
                    left = min(left, other[0])
                    top = min(top, other[1])
                    right = max(right, other[2])
                    bottom = max(bottom, other[3])
                    changed = True
                else:
                    keep.append(other)
            boxes = keep
            result.append((left, top, right, bottom))
        boxes = result
    return boxes


def reading_order(boxes: list[Box], row_tolerance: float = 0.5) -> list[Box]:
    """Order boxes top-to-bottom then left-to-right, grouping into visual rows."""
    if not boxes:
        return []
    heights = sorted(b[3] - b[1] for b in boxes)
    median_h = heights[len(heights) // 2]
    tolerance = max(1, int(median_h * row_tolerance))

    rows: list[list[Box]] = []
    for box in sorted(boxes, key=lambda b: (b[1] + b[3]) / 2):
        center = (box[1] + box[3]) / 2
        for row in rows:
            row_center = sum((b[1] + b[3]) / 2 for b in row) / len(row)
            if abs(center - row_center) <= tolerance:
                row.append(box)
                break
        else:
            rows.append([box])

    ordered: list[Box] = []
    for row in sorted(rows, key=lambda r: sum((b[1] + b[3]) / 2 for b in r) / len(r)):
        ordered.extend(sorted(row, key=lambda b: b[0]))
    return ordered


# --------------------------------------------------------------------- normalization


def normalize(
    cell: Image.Image,
    canvas: int,
    padding_ratio: float,
    allow_upscale: bool,
    threshold: int,
) -> Image.Image:
    """Trim to alpha bounds, scale to the canvas budget, and center on transparency."""
    bounds = cell.getchannel("A").point(lambda v: 255 if v >= threshold else 0).getbbox()
    if bounds is None:
        raise ValueError("no visible pixels after thresholding")
    cell = cell.crop(bounds)

    budget = max(1, int(round(canvas * (1 - 2 * padding_ratio))))
    scale = budget / max(cell.width, cell.height)
    if scale < 1 or (scale > 1 and allow_upscale):
        new_size = (max(1, round(cell.width * scale)), max(1, round(cell.height * scale)))
        cell = cell.resize(new_size, Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    result.alpha_composite(cell, ((canvas - cell.width) // 2, (canvas - cell.height) // 2))
    return result


def _matte_to_alpha(image: Image.Image, threshold: int) -> Image.Image:
    """Key out a solid background by sampling the corners (fallback when rembg was skipped).

    Vectorized with channel ops instead of a per-pixel loop: build the Manhattan distance
    from the sampled background color, then clear alpha wherever it is within tolerance.
    This is a global color key, not a flood fill, so a background-colored region *inside*
    an icon also goes transparent. rembg remains the better tool; this is a fallback.
    """
    rgba = image.convert("RGBA")
    corners = [
        rgba.getpixel((0, 0)),
        rgba.getpixel((rgba.width - 1, 0)),
        rgba.getpixel((0, rgba.height - 1)),
        rgba.getpixel((rgba.width - 1, rgba.height - 1)),
    ]
    background = [sum(corner[channel] for corner in corners) // 4 for channel in range(3)]

    channels = rgba.split()
    distance = Image.new("L", rgba.size, 0)
    for channel, level in zip(channels[:3], background):
        distance = ImageChops.add(
            distance, ImageChops.difference(channel, Image.new("L", rgba.size, level))
        )

    tolerance = min(255, 3 * threshold)
    keep = distance.point(lambda value: 0 if value <= tolerance else 255)
    rgba.putalpha(ImageChops.multiply(channels[3], keep))
    return rgba


# ------------------------------------------------------------------------- pipelines


def detect_boxes(
    image: Image.Image,
    *,
    threshold: int = DEFAULT_ALPHA_THRESHOLD,
    min_area: int = DEFAULT_MIN_AREA,
    merge_gap: int = DEFAULT_MERGE_GAP,
) -> list[Box]:
    """Return icon bounding boxes in reading order."""
    mask, width, height = alpha_bytes(image, threshold)
    boxes = find_components(mask, width, height, min_area)
    boxes = merge_nearby(boxes, merge_gap)
    return reading_order(boxes)


def split_auto(
    source: Path,
    output_dir: Path,
    names: list[str] | None,
    canvas: int,
    *,
    threshold: int = DEFAULT_ALPHA_THRESHOLD,
    min_area: int = DEFAULT_MIN_AREA,
    merge_gap: int = DEFAULT_MERGE_GAP,
    padding_ratio: float = DEFAULT_PADDING_RATIO,
    allow_upscale: bool = True,
    expected: int | None = None,
    dry_run: bool = False,
    auto_matte: bool = False,
    report: Path | None = None,
) -> list[Box]:
    """Detect, verify, and (unless dry-run) write centered icons."""
    image = Image.open(source).convert("RGBA")
    if auto_matte and image.getchannel("A").getextrema() == (255, 255):
        image = _matte_to_alpha(image, threshold)
    if image.getchannel("A").getextrema() == (255, 255):
        raise ValueError(
            f"{source.name}: sheet is fully opaque; run rembg first or pass --auto-matte"
        )

    boxes = detect_boxes(image, threshold=threshold, min_area=min_area, merge_gap=merge_gap)

    if expected is not None and len(boxes) != expected:
        raise ValueError(
            f"detected {len(boxes)} icons but expected {expected}; "
            f"tune --min-area/--merge-gap. Boxes: {boxes}"
        )
    if names is not None and len(boxes) != len(names):
        raise ValueError(
            f"detected {len(boxes)} icons but {len(names)} names were given; "
            f"run with --dry-run to inspect. Boxes: {boxes}"
        )

    # Without explicit names, number them and echo the mapping so the caller can rename.
    auto_named = names is None
    if auto_named:
        names = [f"icon-{index:02d}" for index in range(1, len(boxes) + 1)]

    if report is not None:
        report.write_text(
            json.dumps(
                {"count": len(boxes), "boxes": [list(box) for box in boxes], "names": names},
                indent=2,
            ),
            encoding="utf-8",
        )

    if dry_run or auto_named:
        for name, box in zip(names, boxes):
            print(f"{name}: box={box} size={box[2] - box[0]}x{box[3] - box[1]}")
    if dry_run:
        return boxes

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, box in zip(names, boxes):
        icon = normalize(image.crop(box), canvas, padding_ratio, allow_upscale, threshold)
        icon.save(output_dir / f"{name}.png", optimize=True)
    return boxes


def split_sheet(
    source: Path,
    output_dir: Path,
    names: list[str],
    columns: int,
    rows: int,
    canvas: int,
    *,
    threshold: int = DEFAULT_ALPHA_THRESHOLD,
    padding_ratio: float = DEFAULT_PADDING_RATIO,
    allow_upscale: bool = True,
) -> None:
    """Split a uniform grid sheet. Kept for sheets that really are on a regular grid."""
    image = Image.open(source).convert("RGBA")
    if len(names) != columns * rows:
        raise ValueError(f"expected {columns * rows} names for a {columns}x{rows} sheet")
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, name in enumerate(names):
        col, row = index % columns, index // columns
        # Rounded edges distribute the remainder instead of dropping the last column/row.
        left = col * image.width // columns
        right = (col + 1) * image.width // columns
        top = row * image.height // rows
        bottom = (row + 1) * image.height // rows
        cell = image.crop((left, top, right, bottom))

        if cell.getchannel("A").getextrema()[0] == 255:
            raise ValueError(f"{name}: cell is fully opaque; run rembg before splitting")

        thresholded = cell.getchannel("A").point(lambda v: 255 if v >= threshold else 0)
        bounds = thresholded.getbbox()
        if bounds is None:
            raise ValueError(f"{name}: no visible pixels after background removal")
        if _touches_border(thresholded, bounds):
            print(f"warning: {name} touches its cell border; the grid may be cutting it")

        icon = normalize(cell, canvas, padding_ratio, allow_upscale, threshold)
        icon.save(output_dir / f"{name}.png", optimize=True)


def _touches_border(mask: Image.Image, bounds: Box) -> bool:
    left, top, right, bottom = bounds
    return left == 0 or top == 0 or right == mask.width or bottom == mask.height


# ------------------------------------------------------------------------------ CLI


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--names", nargs="*", default=None)
    parser.add_argument("--layout", choices=("auto", "grid"), default="auto")
    parser.add_argument("--columns", type=int, default=4, help="grid layout only")
    parser.add_argument("--rows", type=int, default=2, help="grid layout only")
    parser.add_argument("--canvas", type=int, default=256)
    parser.add_argument("--alpha-threshold", type=int, default=DEFAULT_ALPHA_THRESHOLD)
    parser.add_argument("--min-area", type=int, default=DEFAULT_MIN_AREA)
    parser.add_argument("--merge-gap", type=int, default=DEFAULT_MERGE_GAP)
    parser.add_argument("--padding-ratio", type=float, default=DEFAULT_PADDING_RATIO)
    parser.add_argument("--expected", type=int, default=None, help="fail unless this many icons are found")
    parser.add_argument("--report", type=Path, default=None, help="write detected boxes as JSON")
    parser.add_argument("--dry-run", action="store_true", help="detect and report without writing")
    parser.add_argument("--auto-matte", action="store_true", help="key out a solid background if rembg was skipped")
    upscale = parser.add_mutually_exclusive_group()
    upscale.add_argument("--allow-upscale", dest="allow_upscale", action="store_true", default=True)
    upscale.add_argument("--no-upscale", dest="allow_upscale", action="store_false")
    args = parser.parse_args()

    if args.layout == "grid":
        if args.names is None:
            parser.error("--names is required for --layout grid")
        split_sheet(
            args.input,
            args.output_dir,
            args.names,
            args.columns,
            args.rows,
            args.canvas,
            threshold=args.alpha_threshold,
            padding_ratio=args.padding_ratio,
            allow_upscale=args.allow_upscale,
        )
    else:
        split_auto(
            args.input,
            args.output_dir,
            args.names,
            args.canvas,
            threshold=args.alpha_threshold,
            min_area=args.min_area,
            merge_gap=args.merge_gap,
            padding_ratio=args.padding_ratio,
            allow_upscale=args.allow_upscale,
            expected=args.expected,
            dry_run=args.dry_run,
            auto_matte=args.auto_matte,
            report=args.report,
        )


if __name__ == "__main__":
    main()
