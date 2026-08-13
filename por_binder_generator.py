#!/usr/bin/env python3
"""Generate the Perfect Order 3x3 binder visualizer and pocket-by-pocket layouts.

Rules:
* Every section starts on a fresh nine-pocket page.
* Base-set non-ex cards have regular and reverse-holo pockets.
* The nine base-set Double Rare ex cards have one pocket only.
* Secret cards 089-124 have one pocket each.
* Official images use P614_EN_<collector number>-2x.png (number is not padded).
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable


CDN = (
    "https://dz3we2x72f7ol.cloudfront.net/expansions/"
    "perfect-order/en-us/P614_EN_{number}-2x.png"
)

NAMES = [
    "Spinarak", "Ariados", "Shaymin", "Snivy", "Servine", "Serperior",
    "Scatterbug", "Spewpa", "Vivillon", "Rowlet", "Dartrix", "Decidueye ex",
    "Fletchinder", "Talonflame", "Salandit", "Salazzle ex", "Turtonator",
    "Seel", "Dewgong", "Staryu", "Mega Starmie ex", "Lapras ex", "Amaura",
    "Aurorus", "Volcanion", "Shinx", "Luxio", "Luxray", "Dedenne",
    "Clefairy", "Mega Clefable ex", "Mawile", "Espurr", "Meowstic", "Spritzee",
    "Aromatisse", "Nosepass", "Probopass", "Hippopotas", "Hippowdon", "Landorus",
    "Binacle", "Barbaracle", "Tyrunt", "Tyrantrum", "Hawlucha", "Mega Zygarde ex",
    "Gastly", "Haunter", "Gengar", "Skorupi", "Drapion", "Yveltal ex", "Chien-Pao",
    "Mega Skarmory ex", "Honedge", "Doublade", "Aegislash", "Klefki", "Rattata",
    "Raticate", "Meowth ex", "Snorlax", "Bunnelby", "Diggersby", "Fletchling",
    "Furfrou", "Antique Jaw Fossil", "Antique Sail Fossil", "Core Memory",
    "Crushing Hammer", "Energy Search", "Energy Swatter", "Hole-Digging Shovel",
    "Jacinthe", "Judge", "Lumiose City", "Lumiose Galette", "Naveen", "Poké Ball",
    "Poké Pad", "Pokémon Catcher", "Potion", "Rosa's Encouragement", "Tarragon",
    "Growing Grass Energy", "Rocky Fighting Energy", "Telepathic Psychic Energy",
    "Spewpa", "Rowlet", "Talonflame", "Aurorus", "Dedenne", "Clefairy", "Espurr",
    "Probopass", "Drapion", "Doublade", "Raticate", "Decidueye ex", "Salazzle ex",
    "Mega Starmie ex", "Mega Clefable ex", "Mega Zygarde ex", "Yveltal ex",
    "Mega Skarmory ex", "Meowth ex", "Energy Recycler", "Forest of Vitality",
    "Jacinthe", "Lumiose City", "Naveen", "Poké Pad", "Rosa's Encouragement",
    "Sacred Ash", "Tarragon", "Wondrous Patch", "Mega Starmie ex",
    "Mega Clefable ex", "Mega Zygarde ex", "Meowth ex", "Jacinthe",
    "Rosa's Encouragement", "Mega Zygarde ex",
]

SECTIONS = [
    ("Grass", 1, 12),
    ("Fire", 13, 17),
    ("Water", 18, 25),
    ("Lightning", 26, 29),
    ("Psychic", 30, 36),
    ("Fighting", 37, 47),
    ("Darkness", 48, 54),
    ("Metal", 55, 59),
    ("Colorless", 60, 67),
    ("Trainers", 68, 85),
    ("Energy", 86, 88),
    ("Secret Rares", 89, 124),
]

BASE_EX = {12, 16, 21, 22, 31, 47, 53, 55, 62}


@dataclass(frozen=True)
class Pocket:
    number: int
    name: str
    variant: str
    section: str

    @property
    def image_url(self) -> str:
        return CDN.format(number=self.number)

    @property
    def label(self) -> str:
        return f"#{self.number:03d} {self.name} — {self.variant}"


def section_pockets(section: str, start: int, end: int, layout: str) -> list[Pocket]:
    cards = [(n, NAMES[n - 1]) for n in range(start, end + 1)]
    if section == "Secret Rares":
        return [Pocket(n, name, "Secret", section) for n, name in cards]

    if layout == "paired":
        pockets: list[Pocket] = []
        for n, name in cards:
            pockets.append(Pocket(n, name, "Regular", section))
            if n not in BASE_EX:
                pockets.append(Pocket(n, name, "Reverse Holo", section))
        return pockets

    if layout == "split":
        regular = [Pocket(n, name, "Regular", section) for n, name in cards]
        reverse = [
            Pocket(n, name, "Reverse Holo", section)
            for n, name in cards
            if n not in BASE_EX
        ]
        return regular + reverse

    raise ValueError(f"Unknown layout: {layout}")


def build_pages(layout: str) -> list[dict]:
    pages: list[dict] = []
    for section, start, end in SECTIONS:
        pockets = section_pockets(section, start, end, layout)
        for offset in range(0, len(pockets), 9):
            chunk: list[Pocket | None] = pockets[offset : offset + 9]
            chunk.extend([None] * (9 - len(chunk)))
            pages.append({"section": section, "pockets": chunk})
    return pages


def validate() -> None:
    assert len(NAMES) == 124
    assert len(BASE_EX) == 9
    for layout in ("paired", "split"):
        pages = build_pages(layout)
        cards = [p for page in pages for p in page["pockets"] if p is not None]
        assert len(pages) == 26
        assert len(cards) == 203
        assert sum(p is None for page in pages for p in page["pockets"]) == 31
        assert all(sum(p.number == n for p in cards) == 1 for n in BASE_EX)
        assert all(sum(p.number == n for p in cards) == 1 for n in range(89, 125))
        section_first_pages: dict[str, int] = {}
        for page_number, page in enumerate(pages, 1):
            section_first_pages.setdefault(page["section"], page_number)
        assert len(section_first_pages) == len(SECTIONS)


def render_text() -> str:
    lines = [
        "PERFECT ORDER (POR) — 3x3 MASTER-SET BINDER LAYOUT",
        "=" * 58,
        "",
        "Official image pattern:",
        CDN.format(number="<collector-number>"),
        "Examples: #001 -> P614_EN_1-2x.png; #124 -> P614_EN_124-2x.png",
        "",
        "Rules: each section begins on a fresh page; base non-ex cards get Regular +",
        "Reverse Holo; the nine base Double Rare ex cards get one Regular pocket;",
        "cards #089-124 get one Secret pocket each.",
        "",
        "Totals: 203 cards | 26 used pages | 31 deliberate blanks | 14 unused",
        "pages in a 40-page / 360-pocket binder.",
    ]
    for layout in ("paired", "split"):
        lines.extend(["", "", f"{layout.upper()} LAYOUT", "-" * 58])
        pages = build_pages(layout)
        for page_number, page in enumerate(pages, 1):
            lines.extend(["", f"PAGE {page_number:02d} — {page['section']}"])
            pockets = page["pockets"]
            for row in range(3):
                cells = []
                for col in range(3):
                    slot = row * 3 + col
                    pocket = pockets[slot]
                    value = "EMPTY" if pocket is None else pocket.label
                    cells.append(f"{slot + 1}. {value}")
                lines.append(" | ".join(cells))
    return "\n".join(lines) + "\n"


def js_pages(layout: str) -> str:
    pages = build_pages(layout)
    rendered = []
    for page in pages:
        pockets = []
        for p in page["pockets"]:
            if p is None:
                pockets.append("null")
            else:
                pockets.append(
                    "{" + ",".join([
                        f'n:{p.number}',
                        f'name:"{escape(p.name).replace(chr(34), chr(92)+chr(34))}"',
                        f'variant:"{p.variant}"',
                        f'url:"{p.image_url}"',
                    ]) + "}"
                )
        rendered.append(
            "{" + f'section:"{page["section"]}",pockets:[' + ",".join(pockets) + "]}"
        )
    return "[" + ",".join(rendered) + "]"


def render_html() -> str:
    paired = js_pages("paired")
    split = js_pages("split")
    template = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Perfect Order 3x3 Binder Visualizer</title>
<style>
:root { color-scheme: dark; --bg:#10161f; --panel:#192332; --ink:#f5f7fb; --muted:#aab7c7; --accent:#ffcb05; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.4 system-ui,sans-serif; background:radial-gradient(circle at top,#24364d,var(--bg) 52%); color:var(--ink); }
header { position:sticky; top:0; z-index:2; padding:14px 18px; background:rgba(16,22,31,.94); backdrop-filter:blur(10px); border-bottom:1px solid #35465a; }
.bar { max-width:1180px; margin:auto; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
h1 { font-size:20px; margin:0 auto 0 0; }
button,select { color:var(--ink); background:#243449; border:1px solid #4a607a; border-radius:8px; padding:8px 11px; font-weight:650; }
button:hover { border-color:var(--accent); cursor:pointer; }
main { max-width:1180px; margin:22px auto 60px; padding:0 16px; }
.summary { color:var(--muted); margin:0 0 16px; }
.page-head { display:flex; align-items:end; justify-content:space-between; margin-bottom:10px; }
.page-head h2 { margin:0; font-size:22px; }
.page-head span { color:var(--muted); }
.page { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; padding:18px; border:2px solid #50657e; border-radius:18px; background:linear-gradient(145deg,#202c3c,#141c27); box-shadow:0 18px 50px #0008; }
.pocket { position:relative; min-width:0; aspect-ratio:2.5/3.5; border-radius:12px; padding:8px; background:#0b1017; border:1px solid #3b4b5f; overflow:hidden; display:flex; align-items:center; justify-content:center; }
.pocket img { display:block; width:100%; height:100%; object-fit:contain; border-radius:7px; }
.tag { position:absolute; left:8px; right:8px; bottom:8px; padding:6px 7px; border-radius:6px; color:white; background:rgba(5,8,12,.88); font-size:12px; text-align:center; }
.tag strong { color:var(--accent); }
.empty { border-style:dashed; color:#627187; font-weight:700; letter-spacing:.12em; }
.error { padding:14px; color:#ffb4b4; text-align:center; overflow-wrap:anywhere; }
.nav { margin-top:16px; display:flex; justify-content:space-between; gap:12px; }
.note { color:var(--muted); margin-top:18px; font-size:13px; }
@media (max-width:700px) { .page { gap:6px; padding:8px; } .tag { inset:auto 4px 4px; font-size:9px; padding:3px; } }
@media print { header,.nav,.note { display:none; } body { background:white; color:black; } main { margin:0; } .page { box-shadow:none; break-after:page; } }
</style>
</head>
<body>
<header><div class="bar">
  <h1>Perfect Order · 3×3 Binder</h1>
  <label>Layout <select id="layout"><option value="paired">Paired</option><option value="split">Split</option></select></label>
  <label>Page <select id="pageSelect"></select></label>
</div></header>
<main>
  <p class="summary">203 cards · 26 used pages · 31 intentional blanks · each section starts fresh · base ex cards are single-slot only</p>
  <div class="page-head"><h2 id="title"></h2><span id="count"></span></div>
  <section class="page" id="page"></section>
  <div class="nav"><button id="prev">← Previous</button><button id="next">Next →</button></div>
  <p class="note">Images load directly from the official Pokémon CloudFront CDN using <code>P614_EN_&lt;number&gt;-2x.png</code>. Regular and reverse-holo pockets intentionally share the same official card image; the pocket label identifies the variant.</p>
</main>
<script>
const DATA={paired:__PAIRED__,split:__SPLIT__};
const layout=document.querySelector('#layout'), pageSelect=document.querySelector('#pageSelect'), grid=document.querySelector('#page');
let index=0;
function resetPages(){ const pages=DATA[layout.value]; pageSelect.innerHTML=pages.map((p,i)=>`<option value="${i}">${i+1}. ${p.section}</option>`).join(''); index=Math.min(index,pages.length-1); render(); }
function render(){ const pages=DATA[layout.value], data=pages[index]; pageSelect.value=index; document.querySelector('#title').textContent=`Page ${index+1} — ${data.section}`; document.querySelector('#count').textContent=`${index+1} / ${pages.length}`; grid.innerHTML=''; data.pockets.forEach((card,i)=>{ const el=document.createElement('article'); el.className='pocket'+(card?'':' empty'); if(!card){el.textContent='EMPTY';}else{const img=document.createElement('img'); img.src=card.url; img.alt=`#${String(card.n).padStart(3,'0')} ${card.name}`; img.loading='eager'; img.onerror=()=>{el.innerHTML=`<div class="error">Official image failed to load<br>${card.url}</div>`}; const tag=document.createElement('div'); tag.className='tag'; tag.innerHTML=`<strong>#${String(card.n).padStart(3,'0')}</strong> ${card.name}<br>${card.variant}`; el.append(img,tag);} grid.append(el); }); document.querySelector('#prev').disabled=index===0; document.querySelector('#next').disabled=index===pages.length-1; }
layout.addEventListener('change',()=>{index=0;resetPages()}); pageSelect.addEventListener('change',()=>{index=Number(pageSelect.value);render()});
document.querySelector('#prev').addEventListener('click',()=>{if(index>0){index--;render()}}); document.querySelector('#next').addEventListener('click',()=>{if(index<DATA[layout.value].length-1){index++;render()}});
document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')document.querySelector('#prev').click();if(e.key==='ArrowRight')document.querySelector('#next').click()}); resetPages();
</script>
</body></html>'''
    return template.replace("__PAIRED__", paired).replace("__SPLIT__", split)


def main() -> None:
    validate()
    output_dir = Path(__file__).resolve().parent
    (output_dir / "por_binder_layout.txt").write_text(render_text(), encoding="utf-8")
    (output_dir / "por_binder_visualizer.html").write_text(render_html(), encoding="utf-8")
    print("Generated por_binder_layout.txt and por_binder_visualizer.html")
    print("Validated: 203 cards, 26 pages, 31 blanks, 9 single-slot base ex cards")


if __name__ == "__main__":
    main()
