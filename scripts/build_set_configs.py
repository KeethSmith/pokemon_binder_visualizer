#!/usr/bin/env python3
"""Build bundled set configurations using TCGdex metadata and official images."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sets" / "builtin"
API = "https://api.tcgdex.net/v2/en"

SETS = [
    ("scarlet-violet", "SV01_EN", "sv01"),
    ("paldea-evolved", "SV02_EN", "sv02"),
    ("obsidian-flames", "SV03_EN", "sv03"),
    ("151", "SV3pt5_EN", "sv03.5"),
    ("paradox-rift", "SV04_EN", "sv04"),
    ("paldean-fates", "SV4pt5_EN", "sv04.5"),
    ("temporal-forces", "SV05_EN", "sv05"),
    ("twilight-masquerade", "SV06_EN", "sv06"),
    ("shrouded-fable", "SV6pt5_EN", "sv06.5"),
    ("stellar-crown", "SV07_EN", "sv07"),
    ("surging-sparks", "SV08_EN", "sv08"),
    ("prismatic-evolutions", "SV8pt5_EN", "sv08.5"),
    ("journey-together", "SV09_EN", "sv09"),
    ("destined-rivals", "SV10_EN", "sv10"),
    ("black-white", "SV10pt5_ZSV_EN", "sv10.5b"),
    ("black-white", "SV10pt5_RSV_EN", "sv10.5w"),
    ("mega-evolution", "JL2G_EN", "me01"),
    ("phantasmal-flames", "8BXG_EN", "me02"),
    ("ascended-heroes", "M7XJ_EN", "me02.5"),
    ("perfect-order", "P614_EN", "me03"),
    ("chaos-rising", "SN54_EN", "me04"),
    ("pitch-black", "KD5B_EN", "me05"),
]

SECTION_ORDER = [
    "Grass", "Fire", "Water", "Lightning", "Psychic", "Fighting",
    "Darkness", "Metal", "Dragon", "Colorless", "Trainers", "Energy",
    "Secret Rares",
]


def get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "pokemon-binder-visualizer/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def variants(card: dict) -> list[str]:
    available = card.get("variants") or {}
    result = []
    is_ex = str(card.get("name", "")).casefold().endswith(" ex")
    if available.get("normal") and not is_ex:
        result.append("Regular")
    if available.get("holo"):
        result.append("Holo")
    if available.get("reverse"):
        result.append("Reverse Holo")
    return result or ["Regular"]


def section_name(card: dict, official_count: int) -> str:
    if int(card["localId"]) > official_count:
        return "Secret Rares"
    category = card.get("category")
    if category == "Trainer":
        return "Trainers"
    if category == "Energy":
        return "Energy"
    types = card.get("types") or ["Colorless"]
    return str(types[0])


def build_set(set_slug: str, image_prefix: str, tcgdex_id: str) -> dict:
    set_data = get_json(f"{API}/sets/{tcgdex_id}")
    summaries = set_data["cards"]
    with ThreadPoolExecutor(max_workers=20) as pool:
        cards = list(pool.map(lambda item: get_json(f"{API}/cards/{item['id']}"), summaries))
    cards.sort(key=lambda card: int(card["localId"]))
    official_count = int(set_data["cardCount"]["official"])
    grouped = {name: [] for name in SECTION_ORDER}
    for card in cards:
        section = section_name(card, official_count)
        if section not in grouped:
            grouped[section] = []
        grouped[section].append({
            "number": int(card["localId"]),
            "name": card["name"],
            "variants": variants(card),
        })
    sections = [{"name": name, "cards": grouped[name]} for name in SECTION_ORDER if grouped.get(name)]
    return {
        "set": {
            "name": set_data["name"],
            "short_name": set_data["name"],
            "code": tcgdex_id.upper(),
            "release_date": set_data.get("releaseDate", ""),
        },
        "image": {
            "url_template": (
                "https://dz3we2x72f7ol.cloudfront.net/expansions/"
                f"{set_slug}/en-us/{image_prefix}_{{number}}-2x.png"
            ),
            "number_padding": 0,
        },
        "binder": {"pockets_per_page": 9, "columns": 3},
        "master_set": {
            "reverse_holo_main_non_ex": tcgdex_id in {"me01", "me02", "me03", "me04", "me05"},
        },
        "appearance": {
            "holographic_variants": ["Reverse Holo"],
            "holographic_opacity": 0.58,
            "holographic_darkening": 0.315,
        },
        "sections": sections,
        "metadata": {
            "card_data_source": f"{API}/sets/{tcgdex_id}",
            "official_count": official_count,
            "unique_cards": len(cards),
        },
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for set_slug, image_prefix, tcgdex_id in SETS:
        config = build_set(set_slug, image_prefix, tcgdex_id)
        path = OUTPUT / f"{tcgdex_id.replace('.', 'pt')}.json"
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{config['set']['name']}: {config['metadata']['unique_cards']} cards -> {path.name}")


if __name__ == "__main__":
    main()
