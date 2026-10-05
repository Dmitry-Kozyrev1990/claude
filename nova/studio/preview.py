"""Быстрый предпросмотр карточек (шрифты подменяются системными — только для проверки компоновки).
python3 preview.py week.json out.png   # week.json: {"name": [w, h, html], ...}"""
import sys, json
from playwright.sync_api import sync_playwright
from PIL import Image
cards = json.load(open(sys.argv[1]))
tiles = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for n, (w, h, html) in cards.items():
        pg = b.new_page(viewport={"width": w, "height": h}); pg.set_content(html); pg.wait_for_timeout(150)
        pg.screenshot(path=f"/tmp/{n}.png"); pg.close(); tiles.append(Image.open(f"/tmp/{n}.png"))
    b.close()
H = 300; row = [t.resize((int(t.width * H / t.height), H)) for t in tiles]
sheet = Image.new("RGB", (sum(r.width for r in row) + 8 * len(row), H), "white"); x = 0
for r in row: sheet.paste(r, (x, 0)); x += r.width + 8
sheet.save(sys.argv[2]); print(sys.argv[2])
