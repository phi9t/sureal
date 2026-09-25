#!/usr/bin/env python3
"""Create compact, deterministic visual evidence from rendered PNG views."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw


def make_contact_sheet(
    images: Sequence[Path],
    output: Path,
    *,
    columns: int = 4,
    cell_size: tuple[int, int] = (256, 192),
    label_height: int = 20,
) -> None:
    if not images:
        raise ValueError("a contact sheet needs at least one image")
    if columns <= 0 or label_height < 0:
        raise ValueError("columns must be positive and label_height non-negative")
    width, height = cell_size
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * width, rows * (height + label_height)), "black")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(images):
        row, column = divmod(index, columns)
        x = column * width
        y = row * (height + label_height)
        with Image.open(path) as source:
            image = source.convert("RGB")
            if image.size != cell_size:
                image = image.resize(cell_size, Image.Resampling.LANCZOS)
            sheet.paste(image, (x, y))
        if label_height:
            draw.text((x + 4, y + height + 2), path.stem, fill="white")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=False, compress_level=9)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()
    images = sorted(args.input.glob("*.png"))
    make_contact_sheet(images, args.output, columns=args.columns)


if __name__ == "__main__":
    main()
