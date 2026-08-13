#!/usr/bin/env python3
"""Compatibility shortcut for regenerating the included Perfect Order site."""

from pathlib import Path

from binder_generator import main


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    raise SystemExit(main([
        str(root / "sets" / "perfect_order.json"),
        "--output-dir", str(root),
        "--html-name", "index.html",
        "--text-name", "por_binder_layout.txt",
    ]))
