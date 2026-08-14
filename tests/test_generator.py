import json
import re
import unittest
from pathlib import Path

from binder_generator import BINDER_FORMATS, build_pages, image_url, load_cards, metrics, number_set, render_html


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "set": {"name": "Example Set", "short_name": "Example", "code": "EX"},
            "image": {
                "url_template": "https://images.example/{slug}/CARD_{number}.png",
                "context": {"slug": "example-set"},
                "number_padding": 3,
            },
            "binder": {"pockets_per_page": 9, "columns": 3, "binder_capacity": 18},
            "variant_rules": [
                {"numbers": [2], "variants": ["Special"]},
                {"numbers": "1-3", "variants": ["Regular", "Reverse"]},
            ],
            "sections": [
                {"name": "First", "start": 1, "cards": ["One", "Two"]},
                {"name": "Second", "start": 3, "cards": ["Three"]},
            ],
        }

    def test_number_ranges(self):
        self.assertEqual(number_set("1-3, 7"), {1, 2, 3, 7})

    def test_config_drives_images_variants_and_fresh_pages(self):
        cards = load_cards(self.config)
        self.assertEqual(image_url(self.config, 1), "https://images.example/example-set/CARD_001.png")
        self.assertEqual(cards[1].variants, ("Special",))
        pages = build_pages(cards, 9, "paired")
        self.assertEqual([page["section"] for page in pages], ["First", "Second"])
        self.assertEqual(len([p for p in pages[0]["pockets"] if p]), 3)
        self.assertEqual(len([p for p in pages[1]["pockets"] if p]), 2)

    def test_metrics(self):
        stats = metrics(self.config, load_cards(self.config))
        self.assertEqual(stats["master_cards"], 5)
        self.assertEqual(stats["used_pages"], 2)
        self.assertEqual(stats["blanks"], 13)

    def test_bundled_sets_render_without_import_control(self):
        cards = load_cards(self.config)
        second = json.loads(json.dumps(self.config))
        second["set"] = {"name": "Second Set", "code": "TWO"}
        html = render_html(self.config, cards, [(second, load_cards(second))])
        self.assertIn('const DATASETS=[{"id":"ex"', html)
        self.assertIn('"name":"Second Set"', html)
        self.assertNotIn("Load set JSON", html)

    def test_supported_binder_formats_preserve_fresh_sections(self):
        cards = load_cards(self.config)
        self.assertEqual([item["id"] for item in BINDER_FORMATS], ["2x2", "3x3", "4x3", "4x4"])
        for binder_format in BINDER_FORMATS:
            page_size = binder_format["columns"] * binder_format["rows"]
            pages = build_pages(cards, page_size, "paired")
            self.assertEqual([page["section"] for page in pages], ["First", "Second"])
            self.assertTrue(all(len(page["pockets"]) == page_size for page in pages))

    def test_perfect_order_master_count_and_ex_slots(self):
        path = Path(__file__).parents[1] / "sets" / "perfect_order.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        cards = load_cards(config)
        self.assertEqual(metrics(config, cards)["master_cards"], 203)
        self.assertTrue(all(len(card.variants) == 1 for card in cards if card.name.lower().endswith(" ex")))
        by_number = {card.number: card for card in cards}
        self.assertEqual(by_number[88].name, "Telepathic Psychic Energy")
        self.assertEqual(by_number[88].variants, ("Holo", "Reverse Holo"))
        self.assertEqual(by_number[12].variants, ("Holo",))
        self.assertEqual(by_number[1].variants, ("Regular", "Reverse Holo"))

    def test_all_bundled_sets_load_and_keep_ex_cards_single_slot(self):
        directory = Path(__file__).parents[1] / "sets" / "builtin"
        paths = sorted(directory.glob("*.json"))
        self.assertEqual(len(paths), 22)
        for path in paths:
            config = json.loads(path.read_text(encoding="utf-8"))
            cards = load_cards(config)
            self.assertTrue(cards, path.name)
            self.assertTrue(
                all(len(card.variants) == 1 for card in cards if card.name.lower().endswith(" ex")),
                path.name,
            )

    def test_public_catalog_is_newest_first(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        match = re.search(r"const DATASETS=(\[.*\]);let active=", html)
        self.assertIsNotNone(match)
        datasets = json.loads(match.group(1))
        dates = [item["releaseDate"] for item in datasets]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(datasets[0]["name"], "Pitch Black")

    def test_public_view_state_is_encoded_in_url(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        for parameter in ("set", "binder", "order", "page"):
            self.assertIn(f"url.searchParams.set('{parameter}'", html)
            self.assertIn(f"initialParams.get('{parameter}')", html)

    def test_cards_have_an_accessible_large_view(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        self.assertIn('<dialog id="cardDialog"', html)
        self.assertIn("cardDialog.showModal()", html)
        self.assertIn("el.setAttribute('role','button')", html)
        self.assertIn("event.key==='Enter'||event.key===' '", html)


if __name__ == "__main__":
    unittest.main()
