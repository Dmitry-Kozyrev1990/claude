import sys, json, zlib, base64
sys.path.insert(0, "/home/claude/nova/preview")
import build_week1 as w
html = open("/home/claude/nova/preview/nova-posts-preview.html", encoding="utf-8").read()
card_css = "\n".join(l for l in html.splitlines() if l.startswith(".card")).replace(".card.tall{aspect-ratio:4/5;border-radius:6px}", ".card.tall{aspect-ratio:4/5}")
FONT = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito:wght@800;900&family=Golos+Text:wght@400;500;600&display=swap">'
def page(card, W, H):
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONT}<style>*{{box-sizing:border-box}}html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden}}'
            f':root{{--display:"Nunito",sans-serif;--body:"Golos Text",sans-serif}}{card_css}</style></head><body>{card}</body></html>')
cards = {k: [1280, 720, page(v, 1280, 720)] for k, v in w.C.items()}
for i, c in enumerate(w.IG_SH, 1): cards[f"ig_0810_{i}"] = [1080, 1350, page(c, 1080, 1350)]
for i, c in enumerate(w.IG_UROK, 1): cards[f"ig_1010_{i}"] = [1080, 1350, page(c, 1080, 1350)]
B = {"cards": cards, "texts": w.T, "poll2": [w.POLL2_Q, w.POLL2_O]}
json.dump(B, open("/tmp/claude-0/week1.json", "w"), ensure_ascii=False)
z = base64.b64encode(zlib.compress(json.dumps(B, ensure_ascii=False).encode(), 9)).decode()
open("/tmp/claude-0/week1.z64", "w").write(z); print(len(z))
if "--local" in sys.argv:
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import os; os.makedirs("/tmp/claude-0/w1", exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for k, (W, H, h) in cards.items():
            pg = b.new_page(viewport={"width": W, "height": H}); pg.set_content(h); pg.wait_for_timeout(150)
            pg.screenshot(path=f"/tmp/claude-0/w1/{k}.png"); pg.close()
        b.close()
    tiles = [Image.open(f"/tmp/claude-0/w1/{k}.png") for k in cards]
    Hh = 300; row = [t.resize((int(t.width * Hh / t.height), Hh)) for t in tiles]
    rows = [row[:5], row[5:10], row[10:]]
    Wd = max(sum(r.width for r in rr) + 8 * len(rr) for rr in rows)
    sheet = Image.new("RGB", (Wd, Hh * 3 + 16), "white"); y = 0
    for rr in rows:
        x = 0
        for r in rr: sheet.paste(r, (x, y)); x += r.width + 8
        y += Hh + 8
    sheet.save("/tmp/claude-0/w1/sheet.png")
