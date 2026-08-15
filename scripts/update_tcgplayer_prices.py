#!/usr/bin/env python3
"""Build a variant-specific TCGplayer price cache from TCGCSV's daily API export."""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from binder_generator import load_cards  # noqa: E402

API_ROOT = "https://tcgcsv.com/tcgplayer/3"
VARIANT_SUBTYPES = {
    "Regular": "Normal",
    "Holo": "Holofoil",
    "Reverse Holo": "Reverse Holofoil",
}
SHOWCASE_SUFFIXES = {
    "poke ball": "pokeball",
    "poke ball pattern": "pokeball",
    "master ball pattern": "masterball",
    "love ball": "loveball",
    "friend ball": "friendball",
    "quick ball": "quickball",
    "dusk ball": "duskball",
    "team rocket": "teamrocket",
    "energy symbol pattern": "energy",
}
SHOWCASE_ORDER = (
    "pokeball", "masterball", "loveball", "friendball",
    "quickball", "duskball", "teamrocket", "energy",
)


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "pokemon-binder-visualizer/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def config_id(config: dict[str, Any]) -> str:
    info = config["set"]
    return str(info.get("code", info["name"])).lower().replace(" ", "-")


def load_configs() -> list[dict[str, Any]]:
    configs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "sets" / "builtin").glob("*.json"))]
    perfect_order = json.loads((ROOT / "sets" / "perfect_order.json").read_text(encoding="utf-8"))
    return [perfect_order if config_id(config) == "me03" else config for config in configs]


def choose_group(config: dict[str, Any], groups: list[dict[str, Any]]) -> dict[str, Any]:
    info = config["set"]
    wanted_name = normalized(str(info["name"]))
    wanted_code = normalized(str(info.get("code", "")))
    wanted_date = str(info.get("release_date", ""))

    ranked: list[tuple[int, dict[str, Any]]] = []
    for group in groups:
        group_name = str(group["name"])
        group_norm = normalized(group_name)
        suffix_norm = normalized(group_name.split(":", 1)[-1])
        published = str(group.get("publishedOn", ""))[:10]
        score = 0
        if wanted_date and published == wanted_date:
            score += 100
        if suffix_norm == wanted_name:
            score += 80
        elif wanted_name and wanted_name in group_norm:
            score += 30
        if wanted_code and group_norm.startswith(wanted_code):
            score += 50
        ranked.append((score, group))

    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < 80 or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
        raise RuntimeError(f"Could not uniquely match TCGplayer group for {info['name']}")
    return ranked[0][1]


def extended_value(product: dict[str, Any], name: str) -> str | None:
    for field in product.get("extendedData", []):
        if field.get("name") == name:
            return str(field.get("value", ""))
    return None


def collector_number(product: dict[str, Any]) -> int | None:
    value = extended_value(product, "Number")
    match = re.match(r"0*(\d+)", value or "")
    return int(match.group(1)) if match else None


def showcase_finish(product: dict[str, Any]) -> str | None:
    suffixes = re.findall(r"\(([^()]*)\)", str(product.get("name", "")))
    for suffix in suffixes:
        finish = SHOWCASE_SUFFIXES.get(suffix.strip().lower())
        if finish:
            return finish
    return None


def build_set_prices(config: dict[str, Any], group: dict[str, Any]) -> dict[str, Any]:
    group_id = int(group["groupId"])
    products = fetch_json(f"{API_ROOT}/{group_id}/products").get("results", [])
    prices = fetch_json(f"{API_ROOT}/{group_id}/prices").get("results", [])
    prices_by_product: dict[int, dict[str, dict[str, Any]]] = {}
    for price in prices:
        prices_by_product.setdefault(int(price["productId"]), {})[str(price["subTypeName"])] = price

    cards: dict[str, dict[str, Any]] = {}
    showcase_prices: dict[str, dict[str, Any]] = {}
    showcases: dict[str, set[str]] = {}
    expected_variants = {card.number: set(card.variants) for card in load_cards(config)}

    for product in products:
        number = collector_number(product)
        if number is None or number not in expected_variants:
            continue
        finish = showcase_finish(product)
        if finish:
            showcases.setdefault(str(number), set()).add(finish)
        product_prices = prices_by_product.get(int(product["productId"]), {})
        if finish:
            price = product_prices.get("Reverse Holofoil") or product_prices.get("Holofoil")
            if price:
                source_image = str(product.get("imageUrl") or "")
                showcase_prices.setdefault(str(number), {})[finish] = {
                    "marketPrice": price.get("marketPrice"),
                    "lowPrice": price.get("lowPrice"),
                    "midPrice": price.get("midPrice"),
                    "highPrice": price.get("highPrice"),
                    "subTypeName": price.get("subTypeName"),
                    "productId": int(product["productId"]),
                    "url": product.get("url"),
                    "imageUrl": source_image.replace("_200w.jpg", "_in_1000x1000.jpg"),
                    "thumbnailUrl": source_image.replace("_200w.jpg", "_400w.jpg"),
                }
            continue
        for variant in expected_variants[number]:
            subtype = VARIANT_SUBTYPES.get(variant)
            price = product_prices.get(subtype or "")
            if not price:
                continue
            cards.setdefault(str(number), {})[variant] = {
                "marketPrice": price.get("marketPrice"),
                "lowPrice": price.get("lowPrice"),
                "midPrice": price.get("midPrice"),
                "highPrice": price.get("highPrice"),
                "subTypeName": price.get("subTypeName"),
                "productId": int(product["productId"]),
                "url": product.get("url"),
            }
    available = {finish for finishes in showcases.values() for finish in finishes}
    return {
        "groupId": group_id,
        "groupName": group["name"],
        "finishes": [finish for finish in SHOWCASE_ORDER if finish in available],
        "showcases": {
            number: [finish for finish in SHOWCASE_ORDER if finish in finishes]
            for number, finishes in showcases.items()
        },
        "showcasePrices": showcase_prices,
        "cards": cards,
    }


def main() -> int:
    groups = fetch_json(f"{API_ROOT}/groups").get("results", [])
    catalog: dict[str, Any] = {
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "https://tcgcsv.com/docs",
        "sets": {},
    }
    for config in load_configs():
        set_id = config_id(config)
        group = choose_group(config, groups)
        print(f"{config['set']['name']}: {group['name']}")
        catalog["sets"][set_id] = build_set_prices(config, group)

    output = ROOT / "prices" / "tcgplayer.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
