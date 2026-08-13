#!/usr/bin/env python3
"""Regenerate the public multi-set site with Perfect Order as the default."""

from __future__ import annotations

import json
from pathlib import Path

from binder_generator import load_cards, render_html, render_text


BUILTIN_ORDER = [
    "me05", "me04", "perfect_order", "me02pt5", "me02", "me01",
    "sv10pt5b", "sv10pt5w", "sv10", "sv09", "sv08pt5", "sv08",
    "sv07", "sv06pt5", "sv06", "sv05", "sv04pt5", "sv04",
    "sv03pt5", "sv03", "sv02", "sv01",
]


def read_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    config_dir = root / "sets" / "builtin"
    perfect_order_config = read_config(root / "sets" / "perfect_order.json")
    configs = [
        perfect_order_config
        if name == "perfect_order"
        else read_config(config_dir / f"{name}.json")
        for name in BUILTIN_ORDER
    ]
    loaded = [(config, load_cards(config)) for config in configs]
    primary_config, primary_cards = loaded[0]
    (root / "index.html").write_text(
        render_html(primary_config, primary_cards, loaded[1:]),
        encoding="utf-8",
    )
    (root / "por_binder_layout.txt").write_text(
        render_text(perfect_order_config, load_cards(perfect_order_config)),
        encoding="utf-8",
    )
    print(f"Generated index.html with {len(loaded)} built-in sets")
