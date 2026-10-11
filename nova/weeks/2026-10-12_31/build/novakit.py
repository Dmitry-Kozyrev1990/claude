"""Мой набор для карточек Новы (по образцу nova/studio: cards.py, card.css, nova_svg.py).
tg(...) 1280x720, ig(...) 1080x1350, page(card, w, h) -> полный HTML для отрисовки."""

VIOLET, VIOLET_D, SCREEN, CYAN, LIME = "#7C3AED", "#6D28D9", "#1E1B4B", "#22D3EE", "#A3E635"


def _stroke(d, w=3):
    return f'<path d="{d}" fill="none" stroke="{CYAN}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>'


FACES = {
    "joy": f'<rect x="96" y="76" width="12" height="20" rx="6" fill="{CYAN}"/><rect x="132" y="76" width="12" height="20" rx="6" fill="{CYAN}"/>' + _stroke("M104 106 Q120 117 136 106"),
    "surprise": f'<circle cx="102" cy="86" r="9" fill="{CYAN}"/><circle cx="138" cy="86" r="9" fill="{CYAN}"/><circle cx="120" cy="110" r="6" fill="none" stroke="{CYAN}" stroke-width="3"/>',
    "think": f'<rect x="102" y="76" width="12" height="14" rx="6" fill="{CYAN}"/><rect x="138" y="76" width="12" height="14" rx="6" fill="{CYAN}"/>' + _stroke("M108 110 L132 107"),
    "proud": _stroke("M94 92 L101 83 L108 92") + _stroke("M132 92 L139 83 L146 92") + _stroke("M102 102 Q120 120 138 102"),
    "sad": f'<rect x="96" y="84" width="12" height="14" rx="6" fill="{CYAN}"/><rect x="132" y="84" width="12" height="14" rx="6" fill="{CYAN}"/>' + _stroke("M94 80 L108 75", 2.5) + _stroke("M146 80 L132 75", 2.5) + _stroke("M106 114 Q120 105 134 114"),
    "wink": f'<rect x="96" y="76" width="12" height="20" rx="6" fill="{CYAN}"/>' + _stroke("M130 88 Q138 94 146 88") + _stroke("M104 106 Q120 117 136 106"),
}

ARMS = {
    "stand": ((80, 160, 72, 192), (160, 160, 168, 192)),
    "wave": ((80, 160, 72, 192), (160, 160, 190, 128)),
    "point": ((80, 160, 72, 192), (160, 162, 204, 152)),
    "cheer": ((80, 160, 52, 130), (160, 160, 188, 130)),
}


def nova(emotion="joy", pose="stand"):
    (lx1, ly1, lx2, ly2), (rx1, ry1, rx2, ry2) = ARMS[pose]
    arms = (f'<line x1="{lx1}" y1="{ly1}" x2="{lx2}" y2="{ly2}" stroke="{VIOLET}" stroke-width="12" stroke-linecap="round"/>'
            f'<line x1="{rx1}" y1="{ry1}" x2="{rx2}" y2="{ry2}" stroke="{VIOLET}" stroke-width="12" stroke-linecap="round"/>')
    extra = ""
    if pose == "wave":
        extra = (f'<path d="M198 112 Q206 120 204 130" fill="none" stroke="{LIME}" stroke-width="3" stroke-linecap="round"/>'
                 f'<path d="M206 104 Q218 118 214 134" fill="none" stroke="{LIME}" stroke-width="3" stroke-linecap="round"/>')
    if pose == "point":
        extra = f'<path d="M212 146 L224 150 L212 156" fill="none" stroke="{LIME}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    if pose == "cheer":
        extra = f'<circle cx="48" cy="122" r="5" fill="{LIME}"/><circle cx="192" cy="122" r="5" fill="{LIME}"/>'
    return (f'<line x1="120" y1="40" x2="120" y2="20" stroke="{VIOLET}" stroke-width="4" stroke-linecap="round"/>'
            f'<circle cx="120" cy="14" r="8" fill="{LIME}"/>{arms}'
            f'<rect x="84" y="150" width="72" height="46" rx="16" fill="{VIOLET_D}"/>'
            f'<circle cx="120" cy="173" r="11" fill="{LIME}"/><circle cx="120" cy="173" r="6" fill="{VIOLET_D}"/>'
            f'<rect x="60" y="40" width="120" height="104" rx="28" fill="{VIOLET}"/>'
            f'<rect x="74" y="54" width="92" height="72" rx="18" fill="{SCREEN}"/>{FACES[emotion]}{extra}')


CSS = """.card{container-type:inline-size;position:relative;overflow:hidden;background:var(--bg);width:100%;font-family:var(--display)}
.card.wide{aspect-ratio:16/9}
.card.tall{aspect-ratio:4/5}
.card .txt{position:absolute;display:flex;flex-direction:column;align-items:flex-start;gap:2.4cqw;z-index:2}
.card .kick{font-family:var(--body);font-weight:600;text-transform:uppercase;letter-spacing:.08em;font-size:2.2cqw}
.card.tall .kick{font-size:3.4cqw}
.card.tall .plate{max-width:72cqw}
.card .h{font-weight:900;line-height:.95;letter-spacing:-.02em;text-wrap:balance}
.card .plate{font-family:var(--body);font-weight:500;line-height:1.25;background:var(--plate);color:var(--plate-ink);padding:1.1em 1.3em;border-radius:.9em;box-shadow:0 .9cqw 0 var(--plate-edge);max-width:100%;margin-top:1cqw}
.card .sub{font-family:var(--body);font-weight:500}
.card .bot{position:absolute;z-index:1}
.card .blob{position:absolute;border-radius:50%}
.card .spark{position:absolute;z-index:1}
.card .clouds{position:absolute;left:0;right:0;bottom:-1px;width:100%;height:9cqw;z-index:0}
.card .src{position:absolute;left:6cqw;bottom:3cqw;font-family:var(--body);font-size:1.7cqw;color:#A9A4D6;z-index:2}
.card.tall .src{left:8cqw;bottom:4cqw;font-size:2.8cqw}
.card .tag{position:absolute;left:8cqw;bottom:7cqw;font-family:var(--body);font-weight:600;font-size:3.6cqw;color:#A3E635;z-index:2}"""
FONT = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito:wght@800;900&family=Golos+Text:wght@400;500;600&display=swap">'


def spark(x, y, s, color):
    return (f'<svg class="spark" style="left:{x}%;top:{y}%;width:{s}cqw;height:{s}cqw" viewBox="0 0 24 24" aria-hidden="true">'
            f'<path d="M12 0 C13 8 16 11 24 12 C16 13 13 16 12 24 C11 16 8 13 0 12 C8 11 11 8 12 0Z" fill="{color}"/></svg>')


def clouds(color):
    c = "".join(f'<circle cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in
                [(0, 60, 34), (48, 52, 30), (96, 64, 36), (150, 50, 32), (200, 62, 38), (256, 54, 30), (306, 66, 36), (360, 52, 34), (400, 62, 30)])
    return (f'<svg class="clouds" viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true">'
            f'<g fill="{color}">{c}<rect x="0" y="62" width="400" height="40"/></g></svg>')


def BLOB(right, bottom, w, color):
    return f'<div class="blob" style="right:{right}cqw;bottom:{bottom}cqw;width:{w}cqw;height:{w}cqw;background:{color}"></div>'


def _bot(emotion, pose, style):
    return f'<svg class="bot" style="{style}" xmlns="http://www.w3.org/2000/svg" viewBox="20 0 220 210" aria-hidden="true">{nova(emotion, pose)}</svg>'


def tg(bg, kick, kick_c, head, head_c, head_size, plate, plate_bg, plate_edge, plate_ink,
       emotion, pose, botstyle, extra="", cloud=None, src="", sub="", sub_c="#C9C4F5", txtw=56):
    cl = clouds(cloud) if cloud else ""
    s = f'<div class="src" style="color:{head_c};opacity:.75">{src}</div>' if src else ""
    sb = f'<div class="sub" style="font-size:2.3cqw;color:{sub_c}">{sub}</div>' if sub else ""
    return (f'<div class="card wide" style="--bg:{bg};--plate:{plate_bg};--plate-edge:{plate_edge};--plate-ink:{plate_ink}">'
            f'{extra}<div class="txt" style="left:6cqw;top:8cqw;width:{txtw}cqw"><div class="kick" style="color:{kick_c}">{kick}</div>'
            f'<div class="h" style="font-size:{head_size}cqw;color:{head_c}">{head}</div><div class="plate" style="font-size:2.7cqw">{plate}</div>{sb}</div>'
            f'{_bot(emotion, pose, botstyle)}{s}{cl}</div>')


def ig(bg, kick, kick_c, head, head_c, head_size, plate, plate_bg, plate_edge, plate_ink,
       emotion, pose, botstyle, extra="", cloud=None, src=""):
    cl = clouds(cloud) if cloud else ""
    s = f'<div class="src" style="color:{head_c};opacity:.75">{src}</div>' if src else ""
    return (f'<div class="card tall" style="--bg:{bg};--plate:{plate_bg};--plate-edge:{plate_edge};--plate-ink:{plate_ink}">'
            f'{extra}<div class="txt" style="left:8cqw;top:9cqw;width:84cqw"><div class="kick" style="color:{kick_c}">{kick}</div>'
            f'<div class="h" style="font-size:{head_size}cqw;color:{head_c}">{head}</div><div class="plate" style="font-size:4.3cqw">{plate}</div></div>'
            f'{_bot(emotion, pose, botstyle)}{s}{cl}</div>')


def page(card, w, h):
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONT}<style>*{{box-sizing:border-box}}'
            f'html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden}}'
            f':root{{--display:"Nunito",sans-serif;--body:"Golos Text",sans-serif}}{CSS}</style></head><body>{card}</body></html>')
