"""Build centered Energy-symbol SVG masks from EssentiarumTCG.

EssentiarumTCG is distributed by Pokémon Aaah! under a non-commercial
Creative Commons license. Download it separately from:
https://www.pokemonaaah.net/art/fonts/

The font is not redistributed by this repository; only the generated
single-color glyph outlines used by the non-commercial visualizer are kept.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont


ENERGY_GLYPHS = {
    "grass": "g",
    "fire": "r",
    "water": "w",
    "lightning": "l",
    "psychic": "p",
    "fighting": "f",
    "darkness": "d",
    "metal": "m",
    "colorless": "c",
    "dragon": "n",
    "fairy": "y",
}


def build_svg(glyph_set, glyph_name: str) -> str:
    glyph = glyph_set[glyph_name]
    bounds_pen = BoundsPen(glyph_set)
    glyph.draw(bounds_pen)
    if bounds_pen.bounds is None:
        raise ValueError(f"Glyph {glyph_name!r} has no bounds")
    x_min, y_min, x_max, y_max = bounds_pen.bounds
    scale = 70 / max(x_max - x_min, y_max - y_min)
    translate_x = 50 - scale * (x_min + x_max) / 2
    translate_y = 50 + scale * (y_min + y_max) / 2
    path_pen = SVGPathPen(glyph_set)
    glyph.draw(path_pen)
    path = path_pen.getCommands()
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">\n'
        f'  <path fill="white" transform="matrix({scale:.8f} 0 0 {-scale:.8f} '
        f'{translate_x:.8f} {translate_y:.8f})" d="{path}"/>\n'
        "</svg>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=Path, help="EssentiarumTCG TTF/OTF file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parents[1] / "assets" / "finish-patterns",
    )
    args = parser.parse_args()
    font = TTFont(args.font)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for energy, character in ENERGY_GLYPHS.items():
        glyph_name = cmap.get(ord(character))
        if glyph_name is None:
            raise KeyError(f"No glyph mapped for {character!r}")
        output = args.output_dir / f"energy-{energy}.svg"
        output.write_text(build_svg(glyph_set, glyph_name), encoding="utf-8")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
