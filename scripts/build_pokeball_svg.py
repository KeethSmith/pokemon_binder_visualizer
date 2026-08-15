"""Trace the referenced Noun Project Poké Ball PNG into an SVG mask.

Source: Poke ball by SoyGalem, Noun Project icon 1390899.
https://thenounproject.com/icon/poke-ball-1390899/
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import potrace
from PIL import Image


def number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def point(value) -> str:
    return f"{number(value.x)} {number(value.y)}"


def curve_path(curve) -> str:
    commands = [f"M{point(curve.start_point)}"]
    for segment in curve.segments:
        if segment.is_corner:
            commands.extend((f"L{point(segment.c)}", f"L{point(segment.end_point)}"))
        else:
            commands.append(
                f"C{point(segment.c1)} {point(segment.c2)} {point(segment.end_point)}"
            )
    commands.append("Z")
    return "".join(commands)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("png", type=Path)
    parser.add_argument("svg", type=Path)
    args = parser.parse_args()
    image = Image.open(args.png).convert("RGBA")
    alpha = np.asarray(image.getchannel("A"))
    curves = potrace.Bitmap(alpha < 128).trace(
        turdsize=2,
        alphamax=1.0,
        opticurve=True,
        opttolerance=0.08,
    )
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("PNG has no opaque pixels")
    left, top, right, bottom = bounds
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    button_radius = (right - left) * 0.13
    button_stroke = (right - left) * 0.04
    # The supplied icon has a solid center dot, while the printed reverse-holo
    # stamp uses a hollow button. Drop only that small central contour.
    visible_curves = [
        curve
        for curve in curves
        if not (
            abs(curve.start_point.x - center_x) < (right - left) * 0.15
            and abs(curve.start_point.y - center_y) < (bottom - top) * 0.15
        )
    ]
    paths = "".join(curve_path(curve) for curve in visible_curves)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left} {top} '
        f'{right-left} {bottom-top}">\n'
        "  <title>Inverted Poké Ball pattern</title>\n"
        "  <desc>Vector trace of Poke ball by SoyGalem, Noun Project icon 1390899, with a hollow center button matching the printed card pattern.</desc>\n"
        f'  <path fill="white" fill-rule="evenodd" d="{paths}"/>\n'
        f'  <circle cx="{number(center_x)}" cy="{number(center_y)}" '
        f'r="{number(button_radius)}" fill="none" stroke="white" '
        f'stroke-width="{number(button_stroke)}"/>\n'
        "</svg>\n"
    )
    args.svg.write_text(svg, encoding="utf-8")
    print(args.svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
