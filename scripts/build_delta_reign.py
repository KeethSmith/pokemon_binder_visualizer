"""Build Delta Reign using its official CDN art and published master checklist."""
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://mastersetlists.com/delta-reign-master-set/'
IMAGE = 'https://dz3we2x72f7ol.cloudfront.net/expansions/delta-reign/en-us/NC3T_EN_{number}-2x.png'

BOUNDS = [(17, 'Grass'), (24, 'Fire'), (29, 'Water'), (42, 'Lightning'),
          (48, 'Psychic'), (54, 'Fighting'), (71, 'Darkness'), (76, 'Dragon'),
          (88, 'Colorless'), (103, 'Trainers'), (141, 'Secret Rares')]


def build():
    request = Request(SOURCE, headers={'User-Agent': 'pokemon-binder-visualizer/1.0'})
    soup = BeautifulSoup(urlopen(request).read(), 'html.parser')
    cards = []
    for row in soup.select('tr'):
        number_cell, name_cell = row.select_one('.num'), row.select_one('.nm')
        if not number_cell or not name_cell or not number_cell.get_text(strip=True).isdigit():
            continue
        number = int(number_cell.get_text(strip=True))
        raw = name_cell.get_text(' ', strip=True)
        match = re.match(r'(.+?)\s+\d{3}/103\s+', raw)
        if not match or not 1 <= number <= 141:
            continue
        name = match.group(1)
        is_ex = name.casefold().endswith(' ex')
        is_holo = is_ex or number > 103 or bool(re.search(r'\bRare\b', raw))
        variants = ['Holo' if is_holo else 'Regular']
        if number <= 103 and not is_ex:
            variants.append('Reverse Holo')
        section = next(label for end, label in BOUNDS if number <= end)
        cards.append((section, {'number': number, 'name': name, 'variants': variants}))
    assert [card['number'] for _, card in cards] == list(range(1, 142))
    sections = []
    for section, card in cards:
        if not sections or sections[-1]['name'] != section:
            sections.append({'name': section, 'cards': []})
        sections[-1]['cards'].append(card)
    config = {
        'set': {'name': 'Delta Reign', 'short_name': 'Delta Reign', 'code': 'ME06', 'release_date': '2026-11-06'},
        'image': {'url_template': IMAGE, 'number_padding': 0},
        'binder': {'pockets_per_page': 9, 'columns': 3},
        'appearance': {'holographic_variants': ['Reverse Holo'], 'holographic_opacity': 0.58, 'holographic_darkening': 0.315},
        'sources': ['https://tcg.pokemon.com/en-us/expansions/delta-reign/', SOURCE],
        'notes': '141 numbered cards plus reverse holos for 93 eligible main-set cards; 234 master-set slots.',
        'sections': sections,
    }
    path = ROOT / 'sets' / 'builtin' / 'me06.json'
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    build()
