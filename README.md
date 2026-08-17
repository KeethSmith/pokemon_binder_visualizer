# Pokémon Binder Visualizer Generator

A set-agnostic, configuration-driven generator and browser app for interactive 3×3 Pokémon TCG binder planners. Every expansion in Pokémon's current All Galleries catalog is built into the published site.

## Open the visualizer

Visit the published GitHub Pages site, or open `index.html` locally. Choose any bundled expansion directly from the **Set** menu; no downloads or JSON imports are required. Sets are listed newest to oldest.

The current set, binder format, ordering, showcased finish, and page are stored in the URL as `set`, `binder`, `order`, `finish`, and `page` parameters. Refreshing or sharing the URL restores the same view.

The **Spacing** control determines type boundaries. **None — continuous** packs one type directly after another without leaving gaps. **Between types — fresh page** starts every elemental/type section on a fresh binder page. Both choices include the same selected cards and keep each card's variants together; only type-page boundaries differ.

The **Variants** menu applies to the complete master set. **All variants** includes every eligible Regular, Holo, Reverse Holo, Ball/Team Rocket, Energy, and other supported pattern printing. **None** shows one base slot per numbered card. Ex cards and other ineligible cards remain single-slot. Variants flow through the normal binder pages automatically; the page selector does not separate them into special variant pages. Supported catalog patterns currently include Ascended Heroes' Ball families, Team Rocket, and Energy symbols plus Poké Ball and Master Ball patterns in Prismatic Evolutions, Black Bolt, and White Flare. The selection is stored in the URL as `finish`, and old `finish=actual` links map to **None**.

Special variants use the recreated filters on top of the official Pokémon base images by default. Add `render=scan` to the URL to use catalog scans instead. The filter mode uses centered vector masks for Ball, Team Rocket, and modern TCG Energy symbols. The Energy outlines are generated from the non-commercial Creative Commons EssentiarumTCG symbol font, which is not redistributed by this repository.

## Verified master-set counts

The visualizer's **All variants** option means one copy of every numbered set card, every eligible regular/holo/reverse-holo printing, every named set parallel, and every secret rare. Promos, stamped product variants, and other unnumbered cards are excluded.

| Set | Cards | Set | Cards |
|---|---:|---|---:|
| Pitch Black | 194 | Chaos Rising | 198 |
| Perfect Order | 203 | Ascended Heroes | 613 |
| Phantasmal Flames | 214 | Mega Evolution | 310 |
| Black Bolt | 406 | White Flare | 407 |
| Destined Rivals | 409 | Journey Together | 333 |
| Prismatic Evolutions | 447 | Surging Sparks | 417 |
| Stellar Crown | 300 | Shrouded Fable | 154 |
| Twilight Masquerade | 373 | Temporal Forces | 358 |
| Paldean Fates | 326 | Paradox Rift | 428 |
| 151 | 360 | Obsidian Flames | 406 |
| Paldea Evolved | 455 | Scarlet & Violet | 444 |

Prismatic Evolutions is sometimes reported as **455** when its eight unnumbered Basic Energy reverse holos are included. Those unnumbered Energy cards are outside the numbered-card scope above. Regression tests lock all 22 totals and distinguish sets where named patterns supplement an ordinary reverse holo from Ascended Heroes, where the named Pokémon patterns replace it.

The recreated Poké Ball mask is based on [Poke ball by SoyGalem](https://thenounproject.com/icon/poke-ball-1390899/) from Noun Project (icon 1390899), with its dark artwork inverted to the visualizer's light watermark treatment.

Click a card—or focus it and press Enter—to open a large card view. Reverse-holo cards retain their tonal treatment, border glow, and full-card shimmer in the enlarged view; standard Holo cards display the unmodified scan.

Each pocket also shows its latest cached **TCGplayer Market Price** for the correct finish. Regular, Holo, and Reverse Holo prices remain separate. Pricing is refreshed from TCGCSV's daily export of TCGplayer's API, so the public GitHub Pages site never exposes a private API key.

The visualizer provides two arrangements:

- **Paired:** each regular card is followed by its reverse holo.
- **Split:** regular cards appear first, followed by reverse holos.

The **Binder** menu supports 2 × 2, 3 × 3, 4 × 3, and 4 × 4 pocket pages. Page totals and intentional blanks recalculate for the selected format, while every elemental type and collection section continues to begin on a fresh page.

Card variants are defined per set. Non-holo cards are labeled **Regular**, holo rares are labeled **Holo**, and their parallel finish is labeled **Reverse Holo**. ex cards use one pocket each unless the source data explicitly identifies another physical variant.

## Generate another set

1. Copy `sets/perfect_order.json` to a new JSON file.
2. Change the set information and the image configuration.
3. Replace the sections, card names, and variant rules with those for the new set.
4. Run:

```shell
python binder_generator.py sets/your_set.json --output-dir dist/your-set --check-images
```

The command produces a standalone `index.html` visualizer and `binder_layout.txt`. `--check-images` verifies that every configured image exists before creating the output.

### Image patterns

`image.url_template` may contain `{number}`, `{number_raw}`, and any values declared in `image.context`:

```json
"image": {
  "url_template": "https://example.test/{set_slug}/{prefix}_{number}.png",
  "context": {
    "set_slug": "your-set",
    "prefix": "SET_EN"
  },
  "number_padding": 0
}
```

Set `number_padding` to `3` when a site expects `001`, `002`, and so on. Use `0` for filenames such as Perfect Order's `1`, `2`, and `124`.

### Card variants

`variant_rules` controls the pockets assigned to collector numbers. Rules are evaluated from top to bottom. This handles sets where ordinary cards have regular and reverse-holo copies while special cards only need one pocket. A card entry may also provide its own `variants` array to override the rules.

Every object in `sections` starts on a fresh binder page. Each section provides its first collector number and a sequential list of card names.

### Holographic appearance

Variant labels listed in `appearance.holographic_variants` receive the complete CSS reverse-holo treatment. `holographic_darkening` controls a uniform full-card darkening layer, while `holographic_opacity` controls the broad full-card static shimmer rendered with `mix-blend-mode: screen`. Tonal adjustment, border glow, darkening, and shimmer also remain beneath named master-set patterns.

## Contents

- `index.html` — standalone interactive visualizer.
- `por_binder_layout.txt` — complete pocket-by-pocket layout for both arrangements.
- `binder_generator.py` — reusable configuration-driven generator.
- `sets/perfect_order.json` — Perfect Order set definition and image pattern.
- `sets/builtin/` — generated definitions for all 22 expansions; the public build keeps the curated `perfect_order.json` definition at its chronological position.
- `sets/official_gallery_sources.json` — first-card image sources and reusable `-2x` URL templates extracted from every set on Pokémon's official All Galleries page.
- `scripts/build_set_configs.py` — refreshes bundled names, types, and variants from TCGdex metadata while retaining official Pokémon image URLs.
- `scripts/update_tcgplayer_prices.py` — refreshes variant-specific TCGplayer market prices from TCGCSV's daily API export.
- `prices/tcgplayer.json` — generated price cache embedded into the standalone visualizer.
- `por_binder_generator.py` — regenerates the public multi-set site in newest-to-oldest release order.

Base card images load from the official Pokémon CloudFront CDN. Named master-set variants use the matching TCGplayer product scan when available, with the official base scan and CSS treatment retained as a fallback. Images are not stored in this repository.
