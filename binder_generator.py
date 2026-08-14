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


BINDER_FORMATS = (
    {"id": "2x2", "label": "2 × 2 — 4 pockets", "columns": 2, "rows": 2},
    {"id": "3x3", "label": "3 × 3 — 9 pockets", "columns": 3, "rows": 3},
    {"id": "4x3", "label": "4 × 3 — 12 pockets", "columns": 4, "rows": 3},
    {"id": "4x4", "label": "4 × 4 — 16 pockets", "columns": 4, "rows": 4},
)


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


def browser_pockets(cards: list[Card], layout: str) -> list[dict[str, Any]]:
    return [{
        "n": pocket.card.number,
        "name": pocket.card.name,
        "variant": pocket.variant,
        "url": pocket.card.image_url,
    } for pocket in section_pockets(cards, layout)]


def browser_dataset(config: dict[str, Any], cards: list[Card]) -> dict[str, Any]:
    set_info = config["set"]
    appearance = config.get("appearance", {})
    holo_opacity = min(0.75, max(0.0, float(appearance.get("holographic_opacity", 0.58))))
    holo_darkening = min(0.65, max(0.0, float(appearance.get("holographic_darkening", 0.315))))
    master_cards = sum(len(card.variants) for card in cards)
    return {
        "id": str(set_info.get("code", set_info["name"])).lower().replace(" ", "-"),
        "name": str(set_info["name"]),
        "code": str(set_info.get("code", "")),
        "releaseDate": str(set_info.get("release_date", "")),
        "holoVariants": [str(value) for value in appearance.get("holographic_variants", ["Reverse Holo"])],
        "holoOpacity": holo_opacity,
        "holoDarkening": holo_darkening,
        "masterCards": master_cards,
        "formats": [{
            **binder_format,
            "pageSize": int(binder_format["columns"]) * int(binder_format["rows"]),
        } for binder_format in BINDER_FORMATS],
        "sections": [{
            "name": section,
            "paired": browser_pockets(section_cards, "paired"),
            "split": browser_pockets(section_cards, "split"),
        } for section, section_cards in grouped(cards)],
    }


def render_html(
    config: dict[str, Any],
    cards: list[Card],
    additional_sets: list[tuple[dict[str, Any], list[Card]]] | None = None,
) -> str:
    bundled = [(config, cards), *(additional_sets or [])]
    datasets = json.dumps(
        [browser_dataset(set_config, set_cards) for set_config, set_cards in bundled],
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pokémon Binder Visualizer</title>
<style>
:root{{color-scheme:dark;--bg:#10161f;--panel:#192332;--ink:#f5f7fb;--muted:#aab7c7;--accent:#ffcb05;--columns:3;--holo-opacity:.58;--holo-darkening:.315}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.4 system-ui,sans-serif;background:radial-gradient(circle at top,#24364d,var(--bg) 52%);color:var(--ink)}}
header{{position:sticky;top:0;z-index:2;padding:14px 18px;background:rgba(16,22,31,.94);backdrop-filter:blur(10px);border-bottom:1px solid #35465a}}
.bar{{max-width:1180px;margin:auto;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}h1{{font-size:20px;margin:0 auto 0 0}}
button,select{{color:var(--ink);background:#243449;border:1px solid #4a607a;border-radius:8px;padding:8px 11px;font-weight:650}}button:hover{{border-color:var(--accent);cursor:pointer}}button:disabled{{opacity:.42;cursor:not-allowed}}.page-nav{{display:flex;justify-content:space-between;gap:12px;margin:0 0 12px}}
main{{max-width:1180px;margin:22px auto 60px;padding:0 16px}}.summary,.note{{color:var(--muted)}}.page-head{{display:flex;align-items:end;justify-content:space-between;margin-bottom:10px}}.page-head h2{{margin:0;font-size:22px}}
.page{{display:grid;grid-template-columns:repeat(var(--columns),minmax(0,1fr));gap:14px;padding:18px;border:2px solid #50657e;border-radius:18px;background:linear-gradient(145deg,#202c3c,#141c27);box-shadow:0 18px 50px #0008}}
.pocket{{position:relative;min-width:0;aspect-ratio:2.5/3.5;border-radius:12px;padding:8px;background:#0b1017;border:1px solid #3b4b5f;overflow:hidden;display:flex;align-items:center;justify-content:center}}
.pocket.clickable{{cursor:zoom-in}}.pocket.clickable:hover{{border-color:var(--accent);transform:translateY(-2px)}}.pocket.clickable:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}
.pocket img{{display:block;width:100%;height:100%;object-fit:contain;border-radius:7px}}.holographic{{border-color:rgba(112,132,118,.72);box-shadow:0 0 18px rgba(0,0,0,.65),inset 0 0 12px rgba(120,140,125,.1)}}.holographic img{{filter:brightness(.928) saturate(.93) contrast(1.04)}}
.holographic::before,.holographic::after{{content:"";position:absolute;z-index:1;inset:8px;border-radius:7px;pointer-events:none}}
.holographic::before{{background:rgb(62,76,18);mix-blend-mode:multiply;opacity:var(--holo-darkening);-webkit-mask-image:linear-gradient(to bottom,#000 0 9.5%,transparent 9.5% 48%,#000 48% 100%);mask-image:linear-gradient(to bottom,#000 0 9.5%,transparent 9.5% 48%,#000 48% 100%)}}
.holographic::after{{background-image:linear-gradient(125deg,rgba(255,255,255,.14) 0%,rgba(22,30,24,.38) 18%,rgba(0,0,0,.58) 36%,rgba(245,250,247,.68) 46%,rgba(185,200,190,.34) 52%,rgba(0,0,0,.52) 68%,rgba(255,255,255,.14) 100%),repeating-linear-gradient(115deg,transparent 0 10px,rgba(8,14,10,.2) 11px,rgba(225,238,230,.18) 12px,transparent 15px);background-size:100% 100%;mix-blend-mode:screen;opacity:var(--holo-opacity)}}
.tag{{position:absolute;z-index:1;left:8px;right:8px;bottom:8px;padding:6px 7px;border-radius:6px;color:white;background:rgba(5,8,12,.88);font-size:12px;text-align:center}}.tag strong{{color:var(--accent)}}
.empty{{border-style:dashed;color:#627187;font-weight:700;letter-spacing:.12em}}.error{{padding:14px;color:#ffb4b4;text-align:center;overflow-wrap:anywhere}}.note{{margin-top:18px;font-size:13px}}
dialog{{width:min(720px,96vw);max-height:96vh;padding:18px;border:1px solid #607895;border-radius:18px;color:var(--ink);background:#111a25;box-shadow:0 24px 80px #000c}}dialog::backdrop{{background:rgba(3,7,12,.86);backdrop-filter:blur(5px)}}.modal-close{{position:absolute;z-index:3;right:12px;top:12px;width:42px;height:42px;padding:0;border-radius:50%;font-size:25px;line-height:1;background:#101722e8}}.modal-card{{position:relative;width:min(660px,100%);margin:auto;aspect-ratio:660/921;overflow:hidden;border-radius:14px;background:#080c12}}.modal-card img{{display:block;width:100%;height:100%;object-fit:contain}}.modal-title{{margin:12px 0 0;text-align:center;font-size:17px;font-weight:700}}
@media(max-width:700px){{h1{{flex-basis:100%}}.bar{{justify-content:center}}.page{{gap:6px;padding:8px}}.tag{{inset:auto 4px 4px;font-size:9px;padding:3px}}}}@media print{{header,.page-nav,.note{{display:none}}body{{background:white;color:black}}main{{margin:0}}.page{{box-shadow:none;break-after:page}}}}
</style></head><body>
<header><div class="bar"><h1>Pokémon Binder Visualizer</h1><label>Set <select id="setSelect"></select></label><label>Binder <select id="binderFormat"></select></label><label>Order <select id="layout"><option value="paired">Paired</option><option value="split">Split</option></select></label><label>Page <select id="pageSelect"></select></label></div></header>
<main><p class="summary" id="summary"></p><div class="page-head"><h2 id="title"></h2><span id="count"></span></div><nav class="page-nav" aria-label="Binder pages"><button id="prev">← Previous</button><button id="next">Next →</button></nav><section class="page" id="page"></section><p class="note">Click any card to view it larger. All supported sets are built in, and images load from Pokémon's official image CDN.</p></main>
<dialog id="cardDialog" aria-labelledby="modalTitle"><button class="modal-close" id="modalClose" aria-label="Close enlarged card">×</button><div class="modal-card" id="modalCard"><img id="modalImage" alt=""></div><p class="modal-title" id="modalTitle"></p></dialog>
<script>
const DATASETS={datasets};let active=DATASETS[0],activeFormatId='3x3',index=0;
const setSelect=document.querySelector('#setSelect'),binderFormat=document.querySelector('#binderFormat'),layout=document.querySelector('#layout'),pageSelect=document.querySelector('#pageSelect'),grid=document.querySelector('#page'),cardDialog=document.querySelector('#cardDialog'),modalCard=document.querySelector('#modalCard'),modalImage=document.querySelector('#modalImage'),modalTitle=document.querySelector('#modalTitle');
function refreshSetOptions(){{setSelect.innerHTML=DATASETS.map((set,i)=>`<option value="${{i}}">${{set.name}}</option>`).join('');setSelect.value=String(DATASETS.indexOf(active))}}
function currentFormat(){{return active.formats.find(format=>format.id===activeFormatId)||active.formats[0]}}
function currentPages(){{const pageSize=currentFormat().pageSize,pages=[];active.sections.forEach(section=>{{const pockets=section[layout.value];for(let offset=0;offset<pockets.length;offset+=pageSize){{const chunk=pockets.slice(offset,offset+pageSize);while(chunk.length<pageSize)chunk.push(null);pages.push({{section:section.name,pockets:chunk}})}}}});return pages}}
function refreshBinderOptions(){{binderFormat.innerHTML=active.formats.map(format=>`<option value="${{format.id}}">${{format.label}}</option>`).join('');if(!active.formats.some(format=>format.id===activeFormatId))activeFormatId=active.formats[0].id;binderFormat.value=activeFormatId}}
function updateSummary(pages=currentPages()){{const blanks=pages.reduce((total,page)=>total+page.pockets.filter(pocket=>pocket===null).length,0);document.querySelector('#summary').textContent=`${{active.masterCards}} cards · ${{pages.length}} used pages · ${{blanks}} intentional blanks · each section starts fresh`}}
function syncUrl(){{const url=new URL(location.href);url.searchParams.set('set',active.id);url.searchParams.set('binder',activeFormatId);url.searchParams.set('order',layout.value);url.searchParams.set('page',String(index+1));history.replaceState(null,'',url)}}
function activate(dataset,page=0){{active=dataset;index=page;refreshBinderOptions();document.documentElement.style.setProperty('--holo-opacity',String(active.holoOpacity));document.documentElement.style.setProperty('--holo-darkening',String(active.holoDarkening));document.title=`${{active.name}} · Pokémon Binder Visualizer`;updateSummary();resetPages()}}
function resetPages(){{const format=currentFormat(),pages=currentPages();document.documentElement.style.setProperty('--columns',String(format.columns));pageSelect.innerHTML=pages.map((p,i)=>`<option value="${{i}}">${{i+1}}. ${{p.section}}</option>`).join('');index=Math.min(index,Math.max(0,pages.length-1));updateSummary(pages);render(pages)}}
function openCard(card,isHolographic){{modalImage.src=card.url;modalImage.alt=`#${{String(card.n).padStart(3,'0')}} ${{card.name}}`;modalTitle.textContent=`#${{String(card.n).padStart(3,'0')}} ${{card.name}} — ${{card.variant}}`;modalCard.className='modal-card'+(isHolographic?' holographic':'');cardDialog.showModal()}}
function render(pages=currentPages()){{const data=pages[index];if(!data){{grid.innerHTML='<div class="error">This set has no pages.</div>';return}}pageSelect.value=String(index);document.querySelector('#title').textContent=`${{active.name}} · Page ${{index+1}} — ${{data.section}}`;document.querySelector('#count').textContent=`${{index+1}} / ${{pages.length}}`;grid.innerHTML='';const holoVariants=new Set(active.holoVariants);data.pockets.forEach(card=>{{const el=document.createElement('article');el.className='pocket'+(card?' clickable':' empty');if(!card)el.textContent='EMPTY';else{{const isHolographic=holoVariants.has(card.variant);if(isHolographic)el.classList.add('holographic');el.tabIndex=0;el.setAttribute('role','button');el.setAttribute('aria-label',`Enlarge #${{String(card.n).padStart(3,'0')}} ${{card.name}} — ${{card.variant}}`);const show=()=>openCard(card,isHolographic);el.addEventListener('click',show);el.addEventListener('keydown',event=>{{if(event.key==='Enter'||event.key===' '){{event.preventDefault();show()}}}});const img=document.createElement('img');img.src=card.url;img.alt=`#${{String(card.n).padStart(3,'0')}} ${{card.name}}`;img.onerror=()=>{{el.innerHTML=`<div class="error">Image failed to load<br>${{card.url}}</div>`}};const tag=document.createElement('div');tag.className='tag';tag.innerHTML=`<strong>#${{String(card.n).padStart(3,'0')}}</strong> ${{card.name}}<br>${{card.variant}}`;el.append(img,tag)}}grid.append(el)}});document.querySelector('#prev').disabled=index===0;document.querySelector('#next').disabled=index===pages.length-1;syncUrl()}}
setSelect.addEventListener('change',()=>activate(DATASETS[Number(setSelect.value)]));binderFormat.addEventListener('change',()=>{{activeFormatId=binderFormat.value;index=0;resetPages()}});layout.addEventListener('change',()=>{{index=0;resetPages()}});pageSelect.addEventListener('change',()=>{{index=Number(pageSelect.value);render()}});document.querySelector('#prev').addEventListener('click',()=>{{if(index>0){{index--;render()}}}});document.querySelector('#next').addEventListener('click',()=>{{if(index<currentPages().length-1){{index++;render()}}}});document.querySelector('#modalClose').addEventListener('click',()=>cardDialog.close());cardDialog.addEventListener('click',event=>{{if(event.target===cardDialog)cardDialog.close()}});document.addEventListener('keydown',event=>{{if(cardDialog.open)return;if(event.key==='ArrowLeft')document.querySelector('#prev').click();if(event.key==='ArrowRight')document.querySelector('#next').click()}});const initialParams=new URLSearchParams(location.search),requestedSet=initialParams.get('set'),requestedBinder=initialParams.get('binder'),requestedOrder=initialParams.get('order'),requestedPage=Math.max(0,(Number.parseInt(initialParams.get('page')||'1',10)||1)-1),matchedSet=DATASETS.find(dataset=>dataset.id===String(requestedSet||'').toLowerCase());if(matchedSet)active=matchedSet;if(active.formats.some(format=>format.id===requestedBinder))activeFormatId=requestedBinder;if(['paired','split'].includes(requestedOrder))layout.value=requestedOrder;refreshSetOptions();activate(active,requestedPage);
</script></body></html>'''


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
