import unittest

from binder_generator import build_pages, image_url, load_cards, metrics, number_set


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


if __name__ == "__main__":
    unittest.main()
