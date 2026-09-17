"""Build 30th Celebration from Pokemon's official checklist and gallery.

All numbered cards have one standard-set foil printing in the checklist.
Classic gallery image numbers are sequential, not original collector numbers.
"""
import io
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = 'https://d1i787aglh9bmb.cloudfront.net/assets/img/me-expansions/thirty/gallery/_pdfs/P11221_30th_Celebration_Card_List_EN_HiRes.pdf'
GALLERY = 'https://tcg.pokemon.com/assets/img/me-expansions/30th-celebration/cards/cards.json'

# Visually verified against all 30 official CDN images. The checklist is in
# chronological order; the CDN is in original collector-number order instead.
CLASSIC_IMAGE_NAMES = [
    'Charizard', 'Delcatty', 'Metagross δ', 'Genesect-EX', 'Misty',
    'Dark Tyranitar', 'Sneasel', 'Pikachu & Zekrom-GX', 'Greninja BREAK', 'Uxie',
    'Crobat', 'Raikou', 'Buzzwole-GX', 'Pikachu', 'Erika’s Jigglypuff',
    'Rayquaza-EX', 'Solgaleo-GX', 'Gengar', 'Darkrai & Cresselia LEGEND',
    'Darkrai & Cresselia LEGEND', 'N', 'Palkia LV.X', 'M Gardevoir-EX',
    'Shining Celebi', 'Scizor ex', 'Mew VMAX', 'Arceus VSTAR', 'Zacian V',
    'Lugia', 'Magikarp',
]
CLASSIC_CHECKLIST_IMAGES = [14, 1, 5, 15, 7, 24, 29, 2, 6, 25, 3, 22, 10, 11, 18,
                            19, 20, 21, 16, 4, 23, 9, 17, 13, 8, 28, 12, 26, 27, 30]


def build():
    text = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(urlopen(CHECKLIST).read())).pages)
    rows = re.findall(r'^(\d+)\s+■■\s+(.+)$', text, re.M)
    # Official gallery seeall spans 1..158; classic-collection spans 1..30.
    assert [int(n) for n, _ in rows[:158]] == list(range(1, 159))
    assert len(rows[158:188]) == 30
    boundaries = [(8, 'Grass'), (15, 'Fire'), (22, 'Water'), (62, 'Lightning'),
                  (81, 'Psychic'), (86, 'Fighting'), (100, 'Darkness'),
                  (108, 'Metal'), (112, 'Dragon'), (125, 'Colorless'),
                  (128, 'Trainers'), (158, 'Secret Rares')]
    for code, name, selected, prefix in [
        ('thirty', '30th Celebration', rows[:188], '2M6P_EN'),
    ]:
        sections = {}
        for index, (original, card_name) in enumerate(selected, 1):
            section = next(s for end, s in boundaries if index <= end) if index <= 158 else 'Classic Collection'
            if index > 158:
                image_number = CLASSIC_CHECKLIST_IMAGES[index - 159]
                card_name = CLASSIC_IMAGE_NAMES[image_number - 1]
                assert card_name.replace(' ', '') == selected[index - 1][1].removesuffix(' C').replace(' ', '')
            sections.setdefault(section, []).append({'number': index, 'name': card_name, 'variants': ['Holo']})
        config = {
            'set': {'name': name, 'short_name': name, 'code': code.upper(), 'release_date': '2026-09-16'},
            'image': {'url_template': f'https://dz3we2x72f7ol.cloudfront.net/expansions/30th-celebration/en-us/{prefix}_{{number}}-2x.png', 'number_padding': 0,
                      'overrides': {str(159+i): f'https://dz3we2x72f7ol.cloudfront.net/expansions/30th-celebration/en-us/2M6P_Classic_EN_{n}-2x.png' for i, n in enumerate(CLASSIC_CHECKLIST_IMAGES)}},
            'binder': {'pockets_per_page': 9, 'columns': 3},
            'appearance': {'holographic_variants': ['Reverse Holo'], 'holographic_opacity': 0.58, 'holographic_darkening': 0.315},
            'sources': [CHECKLIST, GALLERY],
            'notes': 'Main set followed by Classic Collection in official PDF order. Classic slot IDs 159-188 are internal unique IDs, not original collector numbers. Basic product Energy/promos excluded; no official gallery Energy images are available.',
            # Keep type, Secret Rare, and Classic sections distinct in PDF order.
            'sections': [{'name': s, 'cards': cards} for s, cards in sections.items()],
        }
        (ROOT / 'sets' / 'builtin' / f'{code}.json').write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    if '--check-images' in sys.argv:
        urls = []
        for code in ['thirty']:
            config = json.loads((ROOT / 'sets' / 'builtin' / f'{code}.json').read_text(encoding='utf-8'))
            urls.extend(config['image']['overrides'].get(str(c['number']), config['image']['url_template'].format(number=c['number'])) for s in config['sections'] for c in s['cards'])
        def check(url):
            try:
                with urlopen(Request(url, method='HEAD'), timeout=20) as response:
                    assert response.status == 200
                return None
            except Exception as error:
                return f'{url}: {error}'
        failures = list(filter(None, ThreadPoolExecutor(max_workers=16).map(check, urls)))
        print(f'Checked {len(urls)} images; failures: {len(failures)}')
        print('\n'.join(failures))
        sys.exit(bool(failures))
    else:
        build()
