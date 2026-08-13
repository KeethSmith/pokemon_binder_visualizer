#!/usr/bin/env python3
"""Configuration-driven 3x3 trading-card binder visualizer generator."""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Card:
    number: int
    name: str
    section: str
    variants: tuple[str, ...]
    image_url: str


@dataclass(frozen=True)
class Pocket:
    card: Card
    variant: str


def number_set(value: Any) -> set[int]:
    """Expand a number, list, or inclusive range such as ``"1-88"``."""
    if isinstance(value, int):
        return {value}
    if isinstance(value, list):
        result: set[int] = set()
        for item in value:
            result.update(number_set(item))
        return result
    if isinstance(value, str):
        result = set()
        for part in value.split(","):
            part = part.strip()
            if "-" in part:
                first, last = (int(piece.strip()) for piece in part.split("-", 1))
                result.update(range(first, last + 1))
            elif part:
                result.add(int(part))
        return result
    raise TypeError(f"Unsupported number selection: {value!r}")


def variants_for(number: int, rules: list[dict[str, Any]]) -> tuple[str, ...]:
    for rule in rules:
        if number in number_set(rule["numbers"]):
            variants = tuple(str(item) for item in rule["variants"])
            if not variants:
                raise ValueError(f"Variant rule {rule.get('name', '')!r} is empty")
            return variants
    raise ValueError(f"Card #{number} is not covered by a variant rule")


def image_url(config: dict[str, Any], number: int) -> str:
    image = config["image"]
    padding = int(image.get("number_padding", 0))
    rendered_number = str(number).zfill(padding) if padding else str(number)
    context = {str(k): str(v) for k, v in image.get("context", {}).items()}
    context.update(number=rendered_number, number_raw=str(number))
    try:
        return str(image["url_template"]).format(**context)
    except KeyError as exc:
        raise ValueError(f"Missing image context variable {exc} for card #{number}") from exc


def load_cards(config: dict[str, Any]) -> list[Card]:
    rules = config.get("variant_rules", [])
    cards: list[Card] = []
    for section in config["sections"]:
        section_name = str(section["name"])
        start = int(section.get("start", 1))
        for offset, entry in enumerate(section["cards"]):
            if isinstance(entry, str):
                number, name, override = start + offset, entry, None
            else:
                number = int(entry.get("number", start + offset))
                name = str(entry.get("name", f"Card {number}"))
                override = entry.get("variants")
            variants = tuple(str(item) for item in override) if override else variants_for(number, rules)
            cards.append(Card(number, name, section_name, variants, image_url(config, number)))

    numbers = [card.number for card in cards]
    duplicates = sorted(n for n in set(numbers) if numbers.count(n) > 1)
    if duplicates:
        raise ValueError(f"Duplicate collector numbers: {duplicates}")
    if not cards:
        raise ValueError("The configuration contains no cards")
    return cards


def grouped(cards: Iterable[Card]) -> list[tuple[str, list[Card]]]:
    result: list[tuple[str, list[Card]]] = []
    for card in cards:
        if not result or result[-1][0] != card.section:
            result.append((card.section, []))
        result[-1][1].append(card)
    return result


def section_pockets(cards: list[Card], layout: str) -> list[Pocket]:
    if layout == "paired":
        return [Pocket(card, variant) for card in cards for variant in card.variants]
    if layout == "split":
        variant_order: list[str] = []
        for card in cards:
            for variant in card.variants:
                if variant not in variant_order:
                    variant_order.append(variant)
        return [Pocket(card, variant) for variant in variant_order for card in cards if variant in card.variants]
    raise ValueError(f"Unknown layout: {layout}")


def build_pages(cards: list[Card], page_size: int, layout: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for section, section_cards in grouped(cards):
        pockets = section_pockets(section_cards, layout)
        for offset in range(0, len(pockets), page_size):
            chunk: list[Pocket | None] = list(pockets[offset : offset + page_size])
            chunk.extend([None] * (page_size - len(chunk)))
            pages.append({"section": section, "pockets": chunk})
    return pages


def metrics(config: dict[str, Any], cards: list[Card]) -> dict[str, int]:
    binder = config.get("binder", {})
    page_size = int(binder.get("pockets_per_page", 9))
    pages = build_pages(cards, page_size, "paired")
    card_count = sum(len(card.variants) for card in cards)
    blanks = sum(pocket is None for page in pages for pocket in page["pockets"])
    capacity = int(binder.get("binder_capacity", len(pages) * page_size))
    return {
        "unique_cards": len(cards),
        "master_cards": card_count,
        "used_pages": len(pages),
        "blanks": blanks,
        "capacity": capacity,
        "unused_pockets": capacity - card_count - blanks,
        "unused_pages": max(0, capacity // page_size - len(pages)),
    }


def pocket_label(pocket: Pocket) -> str:
    return f"#{pocket.card.number:03d} {pocket.card.name} — {pocket.variant}"


def render_text(config: dict[str, Any], cards: list[Card]) -> str:
    set_info = config["set"]
    binder = config.get("binder", {})
    page_size = int(binder.get("pockets_per_page", 9))
    columns = int(binder.get("columns", 3))
    stats = metrics(config, cards)
    lines = [
        f"{set_info['name'].upper()} — BINDER LAYOUT",
        "=" * 64,
        "",
        f"Image template: {config['image']['url_template']}",
        "Every configured section begins on a fresh page.",
        "",
        f"Totals: {stats['master_cards']} cards | {stats['used_pages']} used pages | "
        f"{stats['blanks']} deliberate blanks | {stats['unused_pages']} unused pages.",
    ]
    for layout in ("paired", "split"):
        lines.extend(["", "", f"{layout.upper()} LAYOUT", "-" * 64])
        for page_number, page in enumerate(build_pages(cards, page_size, layout), 1):
            lines.extend(["", f"PAGE {page_number:02d} — {page['section']}"])
            for offset in range(0, page_size, columns):
                cells = []
                for index, pocket in enumerate(page["pockets"][offset : offset + columns], offset + 1):
                    cells.append(f"{index}. {'EMPTY' if pocket is None else pocket_label(pocket)}")
                lines.append(" | ".join(cells))
    return "\n".join(lines) + "\n"


def browser_data(cards: list[Card], page_size: int, layout: str) -> list[dict[str, Any]]:
    result = []
    for page in build_pages(cards, page_size, layout):
        pockets = []
        for pocket in page["pockets"]:
            pockets.append(None if pocket is None else {
                "n": pocket.card.number,
                "name": pocket.card.name,
                "variant": pocket.variant,
                "url": pocket.card.image_url,
            })
        result.append({"section": page["section"], "pockets": pockets})
    return result


def render_html(config: dict[str, Any], cards: list[Card]) -> str:
    set_info = config["set"]
    binder = config.get("binder", {})
    page_size = int(binder.get("pockets_per_page", 9))
    columns = int(binder.get("columns", 3))
    stats = metrics(config, cards)
    appearance = config.get("appearance", {})
    holo_variants = json.dumps(
        [str(value) for value in appearance.get("holographic_variants", ["Reverse Holo"])],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    holo_opacity = min(0.65, max(0.0, float(appearance.get("holographic_opacity", 0.38))))
    data = json.dumps({
        "paired": browser_data(cards, page_size, "paired"),
        "split": browser_data(cards, page_size, "split"),
    }, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = escape(str(set_info["name"]))
    summary = (
        f"{stats['master_cards']} cards · {stats['used_pages']} used pages · "
        f"{stats['blanks']} intentional blanks · each section starts fresh"
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} Binder Visualizer</title>
<style>
:root{{color-scheme:dark;--bg:#10161f;--panel:#192332;--ink:#f5f7fb;--muted:#aab7c7;--accent:#ffcb05}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.4 system-ui,sans-serif;background:radial-gradient(circle at top,#24364d,var(--bg) 52%);color:var(--ink)}}
header{{position:sticky;top:0;z-index:2;padding:14px 18px;background:rgba(16,22,31,.94);backdrop-filter:blur(10px);border-bottom:1px solid #35465a}}
.bar{{max-width:1180px;margin:auto;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}h1{{font-size:20px;margin:0 auto 0 0}}
button,select{{color:var(--ink);background:#243449;border:1px solid #4a607a;border-radius:8px;padding:8px 11px;font-weight:650}}button:hover{{border-color:var(--accent);cursor:pointer}}button:disabled{{opacity:.42;cursor:not-allowed}}.page-nav{{display:flex;gap:6px}}
main{{max-width:1180px;margin:22px auto 60px;padding:0 16px}}.summary,.note{{color:var(--muted)}}.page-head{{display:flex;align-items:end;justify-content:space-between;margin-bottom:10px}}.page-head h2{{margin:0;font-size:22px}}
.page{{display:grid;grid-template-columns:repeat({columns},minmax(0,1fr));gap:14px;padding:18px;border:2px solid #50657e;border-radius:18px;background:linear-gradient(145deg,#202c3c,#141c27);box-shadow:0 18px 50px #0008}}
.pocket{{position:relative;min-width:0;aspect-ratio:2.5/3.5;border-radius:12px;padding:8px;background:#0b1017;border:1px solid #3b4b5f;overflow:hidden;display:flex;align-items:center;justify-content:center}}
.pocket img{{display:block;width:100%;height:100%;object-fit:contain;border-radius:7px}}.holographic{{border-color:rgba(165,243,252,.6);box-shadow:0 0 15px rgba(167,139,250,.14)}}.holographic img{{filter:saturate(1.14) contrast(1.04) brightness(1.03)}}
.holographic::after{{content:"";position:absolute;inset:8px;border-radius:7px;pointer-events:none;background-image:linear-gradient(120deg,rgba(34,211,238,.38),rgba(244,114,182,.4) 24%,rgba(250,204,21,.34) 48%,rgba(167,139,250,.38) 72%,rgba(34,211,238,.38)),repeating-linear-gradient(115deg,transparent 0 13px,rgba(255,255,255,.14) 14px,transparent 17px);background-size:240% 240%,100% 100%;mix-blend-mode:overlay;opacity:{holo_opacity};animation:holo-shift 5.5s ease-in-out infinite}}
@keyframes holo-shift{{0%,100%{{background-position:100% 15%,0 0}}50%{{background-position:0 85%,0 0}}}}@media(prefers-reduced-motion:reduce){{.holographic::after{{animation:none;background-position:50% 50%,0 0}}}}
.tag{{position:absolute;z-index:1;left:8px;right:8px;bottom:8px;padding:6px 7px;border-radius:6px;color:white;background:rgba(5,8,12,.88);font-size:12px;text-align:center}}.tag strong{{color:var(--accent)}}
.empty{{border-style:dashed;color:#627187;font-weight:700;letter-spacing:.12em}}.error{{padding:14px;color:#ffb4b4;text-align:center;overflow-wrap:anywhere}}.note{{margin-top:18px;font-size:13px}}
@media(max-width:700px){{h1{{flex-basis:100%}}.bar{{justify-content:center}}.page{{gap:6px;padding:8px}}.tag{{inset:auto 4px 4px;font-size:9px;padding:3px}}}}@media print{{header,.note{{display:none}}body{{background:white;color:black}}main{{margin:0}}.page{{box-shadow:none;break-after:page}}}}
</style></head><body>
<header><div class="bar"><h1>{title} · Binder</h1><nav class="page-nav" aria-label="Binder pages"><button id="prev">← Previous</button><button id="next">Next →</button></nav><label>Layout <select id="layout"><option value="paired">Paired</option><option value="split">Split</option></select></label><label>Page <select id="pageSelect"></select></label></div></header>
<main><p class="summary">{escape(summary)}</p><div class="page-head"><h2 id="title"></h2><span id="count"></span></div><section class="page" id="page"></section><p class="note">Images load from the URL template configured for this set. Pocket labels identify card variants that share an image.</p></main>
<script>const DATA={data};const HOLO_VARIANTS=new Set({holo_variants});const layout=document.querySelector('#layout'),pageSelect=document.querySelector('#pageSelect'),grid=document.querySelector('#page');let index=0;
function resetPages(){{const pages=DATA[layout.value];pageSelect.innerHTML=pages.map((p,i)=>`<option value="${{i}}">${{i+1}}. ${{p.section}}</option>`).join('');index=Math.min(index,pages.length-1);render()}}
function render(){{const pages=DATA[layout.value],data=pages[index];pageSelect.value=index;document.querySelector('#title').textContent=`Page ${{index+1}} — ${{data.section}}`;document.querySelector('#count').textContent=`${{index+1}} / ${{pages.length}}`;grid.innerHTML='';data.pockets.forEach(card=>{{const el=document.createElement('article');el.className='pocket'+(card?'':' empty');if(!card)el.textContent='EMPTY';else{{if(HOLO_VARIANTS.has(card.variant))el.classList.add('holographic');const img=document.createElement('img');img.src=card.url;img.alt=`#${{String(card.n).padStart(3,'0')}} ${{card.name}}`;img.onerror=()=>{{el.innerHTML=`<div class="error">Image failed to load<br>${{card.url}}</div>`}};const tag=document.createElement('div');tag.className='tag';tag.innerHTML=`<strong>#${{String(card.n).padStart(3,'0')}}</strong> ${{card.name}}<br>${{card.variant}}`;el.append(img,tag)}}grid.append(el)}});document.querySelector('#prev').disabled=index===0;document.querySelector('#next').disabled=index===pages.length-1}}
layout.addEventListener('change',()=>{{index=0;resetPages()}});pageSelect.addEventListener('change',()=>{{index=Number(pageSelect.value);render()}});document.querySelector('#prev').addEventListener('click',()=>{{if(index>0){{index--;render()}}}});document.querySelector('#next').addEventListener('click',()=>{{if(index<DATA[layout.value].length-1){{index++;render()}}}});document.addEventListener('keydown',e=>{{if(e.key==='ArrowLeft')document.querySelector('#prev').click();if(e.key==='ArrowRight')document.querySelector('#next').click()}});resetPages();</script></body></html>'''


def check_images(cards: list[Card], workers: int = 12) -> None:
    def check(card: Card) -> tuple[int, str | None]:
        try:
            request = urllib.request.Request(card.image_url, method="HEAD", headers={"User-Agent": "binder-generator/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                content_type = response.headers.get("Content-Type", "")
                if response.status != 200 or not content_type.startswith("image/"):
                    return card.number, f"HTTP {response.status} ({content_type})"
            return card.number, None
        except Exception as exc:  # URL/network errors need the card number in the report.
            return card.number, str(exc)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        failures = [(number, error) for number, error in executor.map(check, cards) if error]
    if failures:
        detail = "\n".join(f"  #{number}: {error}" for number, error in failures)
        raise RuntimeError(f"{len(failures)} image checks failed:\n{detail}")


def generate(config_path: Path, output_dir: Path, html_name: str, text_name: str, verify_images: bool) -> dict[str, int]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    cards = load_cards(config)
    if verify_images:
        check_images(cards)
    stats = metrics(config, cards)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / html_name).write_text(render_html(config, cards), encoding="utf-8")
    (output_dir / text_name).write_text(render_text(config, cards), encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="JSON set configuration")
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--html-name", default="index.html")
    parser.add_argument("--text-name", default="binder_layout.txt")
    parser.add_argument("--check-images", action="store_true", help="require every configured image URL to return an image")
    args = parser.parse_args(argv)
    try:
        stats = generate(args.config, args.output_dir, args.html_name, args.text_name, args.check_images)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
