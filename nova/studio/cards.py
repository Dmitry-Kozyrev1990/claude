"""Мастерская карточек Новы. Использование:
    from cards import tg, ig, spark, BLOB, page
    html = page(tg(...), 1280, 720)   # Telegram 16:9
    html = page(ig(...), 1080, 1350)  # Instagram 4:5
Стиль: Nunito 900 + Golos Text, плашки с 3D-кромкой. На фиолетовом фоне Нове нужна тёмная подложка: extra=BLOB(...).
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from nova_svg import nova

CSS = open(os.path.join(os.path.dirname(__file__), "card.css"), encoding="utf-8").read()
FONT = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito:wght@800;900&family=Golos+Text:wght@400;500;600&display=swap">'


def spark(x, y, s, color):
    return (f'<svg class="spark" style="left:{x}%;top:{y}%;width:{s}cqw;height:{s}cqw" viewBox="0 0 24 24" aria-hidden="true">'
            f'<path d="M12 0 C13 8 16 11 24 12 C16 13 13 16 12 24 C11 16 8 13 0 12 C8 11 11 8 12 0Z" fill="{color}"/></svg>')


def clouds(color):
    c = "".join(f'<circle cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in
                [(0,60,34),(48,52,30),(96,64,36),(150,50,32),(200,62,38),(256,54,30),(306,66,36),(360,52,34),(400,62,30)])
    return (f'<svg class="clouds" viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true">'
            f'<g fill="{color}">{c}<rect x="0" y="62" width="400" height="40"/></g></svg>')


def BLOB(right, bottom, w, color):
    return f'<div class="blob" style="right:{right}cqw;bottom:{bottom}cqw;width:{w}cqw;height:{w}cqw;background:{color}"></div>'


def _bot(emotion, pose, style):
    return (f'<svg class="bot" style="{style}" xmlns="http://www.w3.org/2000/svg" viewBox="20 0 220 210" aria-hidden="true">'
            f'{nova(emotion, pose)}</svg>')


def tg(bg, kick, kick_c, head, head_c, head_size, plate, plate_bg, plate_edge, plate_ink,
       emotion, pose, botstyle, extra="", cloud=None, src="", sub="", sub_c="#C9C4F5", txtw=56):
    """Карточка Telegram 16:9. head_size в cqw (9–17), botstyle: 'right:6cqw;bottom:6cqw;width:30cqw'."""
    cl = clouds(cloud) if cloud else ""
    s = f'<div class="src" style="color:{head_c};opacity:.75">{src}</div>' if src else ""
    sb = f'<div class="sub" style="font-size:2.3cqw;color:{sub_c}">{sub}</div>' if sub else ""
    return f'''<div class="card wide" style="--bg:{bg};--plate:{plate_bg};--plate-edge:{plate_edge};--plate-ink:{plate_ink}">
  {extra}<div class="txt" style="left:6cqw;top:8cqw;width:{txtw}cqw"><div class="kick" style="color:{kick_c}">{kick}</div>
  <div class="h" style="font-size:{head_size}cqw;color:{head_c}">{head}</div><div class="plate" style="font-size:2.7cqw">{plate}</div>{sb}</div>
  {_bot(emotion, pose, botstyle)}{s}{cl}</div>'''


def ig(bg, kick, kick_c, head, head_c, head_size, plate, plate_bg, plate_edge, plate_ink,
       emotion, pose, botstyle, extra="", cloud=None, src=""):
    """Слайд Instagram 4:5. head_size в cqw (11–26), Нова 40–52cqw."""
    cl = clouds(cloud) if cloud else ""
    s = f'<div class="src" style="color:{head_c};opacity:.75">{src}</div>' if src else ""
    return f'''<div class="card tall" style="--bg:{bg};--plate:{plate_bg};--plate-edge:{plate_edge};--plate-ink:{plate_ink}">
  {extra}<div class="txt" style="left:8cqw;top:9cqw;width:84cqw"><div class="kick" style="color:{kick_c}">{kick}</div>
  <div class="h" style="font-size:{head_size}cqw;color:{head_c}">{head}</div><div class="plate" style="font-size:4.3cqw">{plate}</div></div>
  {_bot(emotion, pose, botstyle)}{s}{cl}</div>'''


def page(card, w, h):
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONT}<style>*{{box-sizing:border-box}}'
            f'html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden}}'
            f':root{{--display:"Nunito",sans-serif;--body:"Golos Text",sans-serif}}{CSS}</style></head><body>{card}</body></html>')
