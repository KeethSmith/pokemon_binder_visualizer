"""Render official Classic Collection images in numbered sheets for metadata QA."""
import io
from pathlib import Path
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]

def fetch(n):
    url = f'https://dz3we2x72f7ol.cloudfront.net/expansions/30th-celebration/en-us/2M6P_Classic_EN_{n}-2x.png'
    return Image.open(io.BytesIO(urlopen(url).read())).convert('RGB')

if __name__ == '__main__':
    output = ROOT / 'tmp' / 'classic-qa'
    output.mkdir(parents=True, exist_ok=True)
    images = list(ThreadPoolExecutor(max_workers=10).map(fetch, range(1, 31)))
    for batch in range(3):
        sheet = Image.new('RGB', (1500, 880), 'white')
        draw = ImageDraw.Draw(sheet)
        for i, card in enumerate(images[batch*10:batch*10+10]):
            card.thumbnail((290, 400))
            x, y = (i % 5)*300, (i // 5)*440
            sheet.paste(card, (x, y+25))
            draw.text((x+10, y+5), str(batch*10+i+1), fill='black')
        sheet.save(output / f'sheet-{batch+1}.png')
