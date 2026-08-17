import json
import re
import shutil
import subprocess
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
        self.assertEqual([page["section"] for page in pages], ["First / Second"])
        self.assertEqual(len([p for p in pages[0]["pockets"] if p]), 5)

    def test_metrics(self):
        stats = metrics(self.config, load_cards(self.config))
        self.assertEqual(stats["master_cards"], 5)
        self.assertEqual(stats["used_pages"], 1)
        self.assertEqual(stats["blanks"], 4)

    def test_bundled_sets_render_without_import_control(self):
        cards = load_cards(self.config)
        second = json.loads(json.dumps(self.config))
        second["set"] = {"name": "Second Set", "code": "TWO"}
        html = render_html(self.config, cards, [(second, load_cards(second))])
        self.assertIn('const DATASETS=[{"id":"ex"', html)
        self.assertIn('"name":"Second Set"', html)
        self.assertNotIn("Load set JSON", html)

    def test_generated_browser_script_has_valid_javascript_syntax(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not installed")
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        script = re.search(r"<script>\s*(.*?)\s*</script>", html, re.DOTALL)
        self.assertIsNotNone(script)
        syntax_source = re.sub(
            r"const DATASETS=.*?,PRICE_CATALOG=.*?;let active=",
            "const DATASETS=[],PRICE_CATALOG={};let active=",
            script.group(1),
            count=1,
            flags=re.DOTALL,
        )
        checked = subprocess.run(
            [node, "--check", "-"],
            input=syntax_source,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_supported_binder_formats_preserve_fresh_sections(self):
        cards = load_cards(self.config)
        self.assertEqual([item["id"] for item in BINDER_FORMATS], ["2x2", "3x3", "4x3", "4x4"])
        self.assertEqual([item["label"] for item in BINDER_FORMATS], ["2 × 2", "3 × 3", "4 × 3", "4 × 4"])
        for binder_format in BINDER_FORMATS:
            page_size = binder_format["columns"] * binder_format["rows"]
            pages = build_pages(cards, page_size, "paired")
            self.assertTrue(all(len(page["pockets"]) == page_size for page in pages))
            self.assertTrue(all(all(page["pockets"]) for page in pages[:-1]))
        split_pages = build_pages(cards, 9, "split")
        self.assertEqual([page["section"] for page in split_pages], ["First", "Second"])
        self.assertEqual(sum(bool(p) for page in split_pages for p in page["pockets"]), 5)

    def test_perfect_order_master_count_and_ex_slots(self):
        path = Path(__file__).parents[1] / "sets" / "perfect_order.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        cards = load_cards(config)
        self.assertEqual(metrics(config, cards)["master_cards"], 203)
        self.assertTrue(all(len(card.variants) == 1 for card in cards if card.name.lower().endswith(" ex")))
        by_number = {card.number: card for card in cards}
        self.assertEqual(by_number[88].name, "Telepathic Psychic Energy")
        self.assertEqual(by_number[88].variants, ("Holo", "Reverse Holo"))
        self.assertEqual(by_number[6].variants, ("Holo", "Reverse Holo"))
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
            self.assertEqual(config["appearance"]["holographic_variants"], ["Reverse Holo"], path.name)
            self.assertTrue(
                all(len(card.variants) == 1 for card in cards if card.name.lower().endswith(" ex")),
                path.name,
            )

    def test_bundled_master_set_counts_match_published_checklists(self):
        expected = {
            "me01": 310, "me02": 214, "me02.5": 613, "me04": 198, "me05": 194,
            "sv01": 444, "sv02": 455, "sv03": 406, "sv03.5": 360,
            "sv04": 428, "sv04.5": 326, "sv05": 358, "sv06": 373,
            "sv06.5": 154, "sv07": 300, "sv08": 417, "sv08.5": 447,
            "sv09": 333, "sv10": 409, "sv10.5b": 406, "sv10.5w": 407,
        }
        stem_to_id = {
            "me02pt5": "me02.5", "sv03pt5": "sv03.5", "sv04pt5": "sv04.5",
            "sv06pt5": "sv06.5", "sv08pt5": "sv08.5", "sv10pt5b": "sv10.5b",
            "sv10pt5w": "sv10.5w",
        }
        root = Path(__file__).parents[1]
        catalog = json.loads((root / "prices" / "tcgplayer.json").read_text(encoding="utf-8"))["sets"]
        actual = {"me03": 203}
        for path in sorted((root / "sets" / "builtin").glob("*.json")):
            set_id = stem_to_id.get(path.stem, path.stem)
            config = json.loads(path.read_text(encoding="utf-8"))
            cards = load_cards(config)
            total = sum(len(card.variants) for card in cards)
            set_catalog = catalog.get(set_id, {})
            for card in cards:
                if "Reverse Holo" not in card.variants:
                    continue
                finishes = set_catalog.get("showcases", {}).get(str(card.number), [])
                if not finishes:
                    continue
                has_base_reverse = bool(
                    set_catalog.get("cards", {}).get(str(card.number), {}).get("Reverse Holo")
                )
                total += len(finishes) - (0 if has_base_reverse else 1)
            actual[set_id] = total
        self.assertEqual(actual, expected | {"me03": 203})

    def test_named_patterns_supplement_real_reverse_holos(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        self.assertIn("const hasBaseReverse=Boolean", html)
        self.assertIn("if(hasBaseReverse)result.push(card)", html)
        self.assertIn("if(finishSelect.value==='none')", html)
        self.assertIn("if(seen.has(card.n))return false", html)

    def test_public_catalog_is_newest_first(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        match = re.search(r"const DATASETS=(\[.*\]),PRICE_CATALOG=", html)
        self.assertIsNotNone(match)
        datasets = json.loads(match.group(1))
        dates = [item["releaseDate"] for item in datasets]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(datasets[0]["name"], "Pitch Black")

    def test_public_view_state_is_encoded_in_url(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        for parameter in ("set", "binder", "order", "finish", "page"):
            self.assertIn(f"url.searchParams.set('{parameter}'", html)
            self.assertIn(f"initialParams.get('{parameter}')", html)

    def test_cards_have_an_accessible_large_view(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        self.assertIn('<dialog id="cardDialog"', html)
        self.assertIn("cardDialog.showModal()", html)
        self.assertIn("el.setAttribute('role','button')", html)
        self.assertIn("event.key==='Enter'||event.key===' '", html)

    def test_public_site_displays_variant_specific_tcgplayer_prices(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        self.assertIn("const DATASETS=", html)
        self.assertIn(",PRICE_CATALOG=", html)
        self.assertIn("TCGplayer Market:", html)
        self.assertIn("[card.variant]", html)
        self.assertIn('class="modal-price"', html)
        catalog = json.loads((Path(__file__).parents[1] / "prices" / "tcgplayer.json").read_text(encoding="utf-8"))
        spinarak = catalog["sets"]["por"]["cards"]["1"]
        self.assertIn("Regular", spinarak)
        self.assertIn("Reverse Holo", spinarak)
        self.assertEqual(spinarak["Regular"]["subTypeName"], "Normal")
        self.assertEqual(spinarak["Reverse Holo"]["subTypeName"], "Reverse Holofoil")

    def test_special_finish_showcase_controls_are_built_in(self):
        html = (Path(__file__).parents[1] / "index.html").read_text(encoding="utf-8")
        self.assertIn('<select id="finishSelect">', html)
        self.assertIn("SHOWCASE_LABELS", html)
        self.assertIn("energy:'Energy Symbol Pattern'", html)
        self.assertIn("cardShowcases(card)", html)
        self.assertIn("'All variants':'None'", html)
        self.assertIn("const choices=['all','none']", html)
        self.assertIn("preferred==='actual'?'none':preferred", html)
        self.assertIn("expandedPockets", html)
        self.assertIn("if(layout.value==='split')", html)
        self.assertIn("pages.push({section:section.name,pockets:chunk})", html)
        self.assertIn("'each type starts on a fresh page':'types packed continuously'", html)
        self.assertNotIn("group:`${section.name} — ${group.name}`", html)
        self.assertIn("each type starts on a fresh page", html)
        self.assertIn("types packed continuously", html)
        self.assertIn("Spacing <select id=\"layout\">", html)
        self.assertIn('<option value="paired">None</option>', html)
        self.assertIn('<option value="split">Fresh page</option>', html)
        self.assertIn("variantImageUrl", html)
        self.assertIn("card.variantThumbnailUrl||card.variantImageUrl||card.url", html)
        self.assertIn("if(!card.finish||card.variantImageUrl)return null", html)
        self.assertIn("renderMode=initialParams.get('render')==='scan'?'scan':'filter'", html)
        self.assertIn("preview=renderMode==='filter'?' · recreated filters':''", html)
        self.assertNotIn("experimental recreated filters", html)
        self.assertIn("energy-vector-mark", html)
        self.assertIn(".holographic::before,.holographic::after{content:", html)
        self.assertNotIn("mask-image:linear-gradient(to bottom", html)
        self.assertIn('assets/finish-patterns/energy-grass.svg', html)
        self.assertIn('assets/finish-patterns/loveball.svg', html)
        self.assertIn("container.classList.toggle('holographic',isHolographic)", html)
        self.assertIn("mix-blend-mode:multiply", html)
        self.assertIn("pokeball-mark", html)
        self.assertIn("energy-grass", html)
        self.assertIn("energy-lightning", html)
        catalog = json.loads((Path(__file__).parents[1] / "prices" / "tcgplayer.json").read_text(encoding="utf-8"))
        ascended = catalog["sets"]["me02.5"]
        self.assertEqual(ascended["showcases"]["1"], ["pokeball", "energy"])
        self.assertEqual(ascended["showcasePrices"]["1"]["pokeball"]["productId"], 676852)
        self.assertTrue(ascended["showcasePrices"]["1"]["pokeball"]["imageUrl"].endswith("_in_1000x1000.jpg"))
        self.assertTrue(ascended["showcasePrices"]["1"]["energy"]["thumbnailUrl"].endswith("_400w.jpg"))
        self.assertNotIn("3", ascended["showcases"])
        self.assertIn("teamrocket", ascended["finishes"])
        self.assertEqual(catalog["sets"]["sv08.5"]["finishes"], ["pokeball", "masterball"])
        self.assertEqual(catalog["sets"]["por"]["finishes"], [])
        pattern_dir = Path(__file__).parents[1] / "assets" / "finish-patterns"
        for energy in ("grass", "fire", "water", "lightning", "psychic", "fighting", "darkness", "metal", "colorless", "dragon", "fairy"):
            energy_svg = pattern_dir / f"energy-{energy}.svg"
            self.assertTrue(energy_svg.is_file(), energy)
            self.assertIn('viewBox="61 67 403 403"', energy_svg.read_text(encoding="utf-8"), energy)


if __name__ == "__main__":
    unittest.main()
