"""Проверка компоновки: рендер с локальными шрифтами-заменителями (Inter), поиск наложений и вылетов.
python3 check_cards.py cards_week.json outdir"""
import json, sys, os
from playwright.sync_api import sync_playwright
from PIL import Image

cards = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
SUB = '<style>:root{--display:"Inter","Inter Display",sans-serif !important;--body:"Inter",sans-serif !important}.card .h{font-weight:900}</style>'
JS = """() => {
 const W = document.body.clientWidth, H = document.body.clientHeight;
 const r = e => { const b = e.getBoundingClientRect(); return {x:b.left,y:b.top,r:b.right,b:b.bottom,n:e.className.baseVal||e.className}; };
 const els = [...document.querySelectorAll('.kick,.h,.plate,.sub,.src,.tag')].map(r);
 const bot = r(document.querySelector('.bot'));
 // реальная фигура робота занимает ~ x 12..96%, y 3..95% от svg
 const bw = bot.r-bot.x, bh = bot.b-bot.y;
 const B = {x:bot.x+bw*.12, r:bot.x+bw*.96, y:bot.y+bh*.03, b:bot.y+bh*.95};
 const hit = (a,b,m=4) => a.x < b.r-m && a.r > b.x+m && a.y < b.b-m && a.b > b.y+m;
 const probs = [];
 for (const e of els) {
   if (hit(e,B)) probs.push('бот×'+e.n);
   if (e.r > W-8 || e.b > H-4 || e.x < 0) probs.push('край×'+e.n);
 }
 for (let i=0;i<els.length;i++) for (let j=i+1;j<els.length;j++) if (hit(els[i],els[j],1)) probs.push(els[i].n+'×'+els[j].n);
 if (bot.y < 2 || B.r > W) probs.push('бот за краем');
 const h = document.querySelector('.h'); const rg=document.createRange(); rg.selectNodeContents(h); const hr=rg.getBoundingClientRect(); if (hr.right > W*0.94) probs.push('заголовок у края '+Math.round(100*hr.right/W)+'%'); if (h.scrollWidth > h.clientWidth+2) probs.push('заголовок шире блока');
 let txt = 0; for (const e of els) txt += (e.r-e.x)*(e.b-e.y);
 return {probs, txtShare: Math.round(100*txt/(W*H))};
}"""
rep = {}; tiles = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for n, (w, h, html) in cards.items():
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.set_content(html.replace("</head>", SUB + "</head>")); pg.wait_for_timeout(80)
        rep[n] = pg.evaluate(JS)
        pg.screenshot(path=f"{out}/{n}.png"); pg.close()
    b.close()
bad = {k: v for k, v in rep.items() if v["probs"]}
for k, v in rep.items():
    flag = "  !! " + ", ".join(v["probs"]) if v["probs"] else ""
    print(f"{k:22s} текст≈{v['txtShare']}%{flag}")
print("проблем:", len(bad))
json.dump(rep, open(f"{out}/report.json", "w"), ensure_ascii=False)
