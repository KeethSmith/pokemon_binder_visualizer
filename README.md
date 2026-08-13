# Pokémon Binder Visualizer Generator

A set-agnostic, configuration-driven generator and browser app for interactive 3×3 Pokémon TCG binder planners. Every expansion in Pokémon's current All Galleries catalog is built into the published site.

## Open the visualizer

Visit the published GitHub Pages site, or open `index.html` locally. Choose any bundled expansion directly from the **Set** menu; no downloads or JSON imports are required. Sets are listed newest to oldest with their release dates.

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

Variant labels listed in `appearance.holographic_variants` receive a CSS reverse-holo treatment. `holographic_darkening` controls the darker printed header and text field, while `holographic_opacity` controls a full-card static shimmer rendered with `mix-blend-mode: screen`. The effect includes a strong fixed diagonal silver highlight with no animation or cursor tracking.

## Contents

- `index.html` — standalone interactive visualizer.
- `por_binder_layout.txt` — complete pocket-by-pocket layout for both arrangements.
- `binder_generator.py` — reusable configuration-driven generator.
- `sets/perfect_order.json` — Perfect Order set definition and image pattern.
- `sets/builtin/` — generated definitions for all 22 expansions; the public build keeps the curated `perfect_order.json` definition at its chronological position.
- `sets/official_gallery_sources.json` — first-card image sources and reusable `-2x` URL templates extracted from every set on Pokémon's official All Galleries page.
- `scripts/build_set_configs.py` — refreshes bundled names, types, and variants from TCGdex metadata while retaining official Pokémon image URLs.
- `por_binder_generator.py` — regenerates the public multi-set site in newest-to-oldest release order.

Card images load from the official Pokémon CloudFront CDN and are not stored in this repository.
