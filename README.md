# Pokémon Binder Visualizer Generator

A configuration-driven generator for interactive 3×3 Pokémon TCG binder planners. Perfect Order is included as a complete example.

## Open the visualizer

Visit the published GitHub Pages site, or open `index.html` locally. The published root site is generated from `sets/perfect_order.json`.

The visualizer provides two arrangements:

- **Paired:** each regular card is followed by its reverse holo.
- **Split:** regular cards appear first, followed by reverse holos.

Every elemental type and collection section begins on a fresh nine-pocket page. The nine base-set Double Rare ex cards use one pocket each, while cards 089–124 also use one pocket each.

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

Variant labels listed in `appearance.holographic_variants` receive a CSS foil sheen. Adjust `appearance.holographic_opacity` from `0` to `0.65`; Perfect Order uses `0.38` for a visible but restrained effect.

## Contents

- `index.html` — standalone interactive visualizer.
- `por_binder_layout.txt` — complete pocket-by-pocket layout for both arrangements.
- `binder_generator.py` — reusable configuration-driven generator.
- `sets/perfect_order.json` — Perfect Order set definition and image pattern.
- `por_binder_generator.py` — compatibility shortcut that regenerates the Perfect Order site.

Card images load from the official Pokémon CloudFront CDN and are not stored in this repository.
