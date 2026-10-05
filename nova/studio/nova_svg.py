"""Генератор персонажа Нова (вариант A, экран-компаньон).
nova(emotion, pose) -> SVG-фрагмент в рамке 240x220 (координаты от 0,0).
Эмоции: joy, surprise, think, proud, sad, wink. Позы: stand, wave, point, cheer."""

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

ARMS = {  # (левая рука, правая рука) — отрезки от плеча к кисти
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
    return (
        f'<line x1="120" y1="40" x2="120" y2="20" stroke="{VIOLET}" stroke-width="4" stroke-linecap="round"/>'
        f'<circle cx="120" cy="14" r="8" fill="{LIME}"/>'
        f'{arms}'
        f'<rect x="84" y="150" width="72" height="46" rx="16" fill="{VIOLET_D}"/>'
        f'<circle cx="120" cy="173" r="11" fill="{LIME}"/><circle cx="120" cy="173" r="6" fill="{VIOLET_D}"/>'
        f'<rect x="60" y="40" width="120" height="104" rx="28" fill="{VIOLET}"/>'
        f'<rect x="74" y="54" width="92" height="72" rx="18" fill="{SCREEN}"/>'
        f'{FACES[emotion]}{extra}'
    )

def standalone(emotion, pose, size=480):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="20 0 220 210" width="{size}" height="{int(size*210/220)}">'
            f'{nova(emotion, pose)}</svg>')

if __name__ == "__main__":
    import os
    os.makedirs("out", exist_ok=True)
    for e in FACES:
        open(f"out/nova_{e}.svg", "w").write(standalone(e, "stand"))
    for p in ARMS:
        open(f"out/nova_pose_{p}.svg", "w").write(standalone("joy" if p != "cheer" else "proud", p))
    print(sorted(os.listdir("out")))
