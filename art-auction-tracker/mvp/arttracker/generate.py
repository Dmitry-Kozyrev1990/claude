"""Генератор синтетических аукционных данных для демо.

Имитирует то, что отдают парсеры разных домов: у каждого дома свой формат имени
автора, названия, размеров, эстимейта и цены, свой язык и валюта. Конвейер
(normalize → matching → analytics) получает только эти «сырые» записи.
Истинные идентификаторы объектов пишутся в отдельный файл truth.jsonl и
используются только для оценки качества сопоставления.

Визуальный признак смоделирован: вместо CLIP-эмбеддингов настоящих фотографий
генерируются векторы, где разные оттиски одной работы близки, а фото одного
и того же оттиска почти совпадают.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .catalog import ARTISTS, HOUSES, fx

SEED = 20261014
TODAY = date(2026, 10, 14)
YEARS = list(range(2015, 2027))
EMB_DIM = 32

# Рост рынка по художникам: доходность в год по периодам (год начала периода → ставка).
GROWTH = {
    "rembrandt": {2015: 0.035}, "durer": {2015: 0.03}, "goya": {2015: 0.015},
    "picasso": {2015: 0.05, 2023: 0.01}, "chagall": {2015: -0.01},
    "matisse": {2015: 0.03}, "warhol": {2015: 0.07, 2023: 0.02},
    "lichtenstein": {2015: 0.04}, "hockney": {2015: 0.12, 2024: 0.03},
    "haring": {2015: 0.09}, "banksy": {2015: 0.24, 2022: -0.14},
    "kusama": {2015: 0.15, 2023: -0.06},
}
# Сколько лотов художника в среднем выходит на торги за год.
LOTS_PER_YEAR = {
    "rembrandt": 14, "durer": 11, "goya": 9, "picasso": 13, "chagall": 12,
    "matisse": 9, "warhol": 17, "lichtenstein": 9, "hockney": 10, "haring": 11,
    "banksy": 16, "kusama": 12,
}

# Работы. variants: (код, подпись EN, подпись DE, множитель цены, тираж или None).
WORKS = [
    # --- Рембрандт
    dict(id="rem-3crosses", artist="rembrandt", year="1653", year_raw=["circa 1653", "1653", "um 1653"],
         titles_en=["The Three Crosses", "Christ Crucified between the Two Thieves: The Three Crosses"],
         title_de="Die drei Kreuze", medium="drypoint and burin", medium_de="Kaltnadel und Grabstichel",
         ref="B. 78", size=(38.5, 45.0), base=260000,
         variants=[("III", 1.5, None), ("IV", 1.0, None), ("V", 0.45, None)], copies=7),
    dict(id="rem-100guilder", artist="rembrandt", year="c. 1648", year_raw=["circa 1648", "c. 1648", "um 1648"],
         titles_en=["Christ Healing the Sick ('The Hundred Guilder Print')", "The Hundred Guilder Print"],
         title_de="Das Hundertguldenblatt", medium="etching, drypoint and burin",
         medium_de="Radierung, Kaltnadel und Grabstichel", ref="B. 74", size=(28.0, 39.3), base=220000,
         variants=[("II", 1.0, None)], copies=6),
    dict(id="rem-selfsill", artist="rembrandt", year="1639", year_raw=["1639"],
         titles_en=["Self-Portrait Leaning on a Stone Sill", "Self-portrait leaning on a stone sill"],
         title_de="Selbstbildnis, an eine Steinbrüstung gelehnt", medium="etching", medium_de="Radierung",
         ref="B. 21", size=(20.5, 16.4), base=95000, variants=[("II", 1.0, None)], copies=6),
    dict(id="rem-shell", artist="rembrandt", year="1650", year_raw=["1650"],
         titles_en=["The Shell (Conus marmoreus)", "The Shell"], title_de="Die Muschel",
         medium="etching, drypoint and burin", medium_de="Radierung, Kaltnadel und Grabstichel",
         ref="B. 159", size=(9.7, 13.2), base=70000, variants=[("II", 1.0, None), ("III", 0.6, None)], copies=5),
    # --- Дюрер
    dict(id="dur-melencolia", artist="durer", year="1514", year_raw=["1514"],
         titles_en=["Melencolia I", "Melancholia I"], title_de="Melencolia I", medium="engraving",
         medium_de="Kupferstich", ref="B. 74", size=(24.0, 18.8), base=330000,
         variants=[("II", 1.0, None)], copies=6),
    dict(id="dur-knight", artist="durer", year="1513", year_raw=["1513"],
         titles_en=["Knight, Death and the Devil", "The Knight, Death and the Devil"],
         title_de="Ritter, Tod und Teufel", medium="engraving", medium_de="Kupferstich", ref="B. 98",
         size=(24.5, 18.9), base=280000, variants=[("I", 1.0, None)], copies=6),
    dict(id="dur-jerome", artist="durer", year="1514", year_raw=["1514"],
         titles_en=["Saint Jerome in his Study", "St. Jerome in His Study"],
         title_de="Der heilige Hieronymus im Gehäus", medium="engraving", medium_de="Kupferstich",
         ref="B. 60", size=(24.7, 18.8), base=190000, variants=[("I", 1.0, None)], copies=6),
    dict(id="dur-adam", artist="durer", year="1504", year_raw=["1504"],
         titles_en=["Adam and Eve", "Adam and Eve (The Fall of Man)"], title_de="Adam und Eva",
         medium="engraving", medium_de="Kupferstich", ref="B. 1", size=(25.1, 19.4), base=380000,
         variants=[("III", 1.0, None)], copies=5),
    # --- Гойя
    dict(id="goy-sleep", artist="goya", year="1799", year_raw=["1799", "1797-99"],
         titles_en=["El sueño de la razón produce monstruos (The Sleep of Reason Produces Monsters)",
                    "The Sleep of Reason Produces Monsters, from Los Caprichos"],
         title_de="Der Schlaf der Vernunft gebiert Ungeheuer", medium="etching and aquatint",
         medium_de="Radierung und Aquatinta", ref="Harris 78", size=(21.6, 15.2), base=38000,
         variants=[("1st edition", 1.0, None), ("4th edition", 0.3, None)], copies=7),
    dict(id="goy-disparate", artist="goya", year="c. 1816-23", year_raw=["circa 1816-23", "c. 1816-1823"],
         titles_en=["Disparate de miedo (Fearful Folly)", "Fearful Folly, from Los Disparates"],
         title_de="Disparate de miedo", medium="etching and aquatint", medium_de="Radierung und Aquatinta",
         ref=None, size=(24.5, 35.0), base=14000, variants=[("1st edition", 1.0, None)], copies=6),
    # --- Пикассо
    dict(id="pic-minotauro", artist="picasso", year="1935", year_raw=["1935"],
         titles_en=["La Minotauromachie", "The Minotauromachy"], title_de="La Minotauromachie",
         medium="etching and engraving", medium_de="Radierung und Kupferstich", ref="Bloch 288",
         size=(49.6, 69.6), base=1100000, variants=[("VII", 1.0, None)], copies=5),
    dict(id="pic-repas", artist="picasso", year="1904", year_raw=["1904"],
         titles_en=["Le Repas frugal", "The Frugal Repast"], title_de="Le Repas frugal",
         medium="etching", medium_de="Radierung", ref="Bloch 1", size=(46.3, 37.7), base=520000,
         variants=[("Vollard edition", 1.0, None)], copies=5),
    dict(id="pic-francoise", artist="picasso", year="1950", year_raw=["1950"],
         titles_en=["Françoise sur fond gris", "Francoise on a Grey Background"],
         title_de="Françoise sur fond gris", medium="lithograph", medium_de="Lithographie", ref=None,
         size=(64.5, 49.5), base=110000, variants=[("ed", 1.0, 50)], copies=None),
    # --- Шагал
    dict(id="cha-daphnis", artist="chagall", year="1961", year_raw=["1961"],
         titles_en=["Le Printemps, from Daphnis et Chloé", "Spring (Daphnis and Chloe)"],
         title_de="Der Frühling, aus: Daphnis et Chloé", medium="lithograph in colours",
         medium_de="Farblithographie", ref=None, size=(42.0, 32.0), base=14000, variants=[("ed", 1.0, 60)], copies=None),
    dict(id="cha-cirque", artist="chagall", year="1967", year_raw=["1967"],
         titles_en=["Le Cirque (plate 23)", "The Circus, plate 23"], title_de="Der Zirkus, Blatt 23",
         medium="lithograph in colours", medium_de="Farblithographie", ref=None, size=(42.2, 32.4),
         base=16000, variants=[("ed", 1.0, 250)], copies=None),
    # --- Матисс
    dict(id="mat-icarus", artist="matisse", year="1947", year_raw=["1947"],
         titles_en=["Icarus, from Jazz", "Icare (Jazz, plate VIII)"], title_de="Ikarus, aus: Jazz",
         medium="pochoir in colours", medium_de="Pochoir in Farben", ref=None, size=(42.2, 32.5),
         base=32000, variants=[("ed", 1.0, 250)], copies=None),
    dict(id="mat-odalisque", artist="matisse", year="1925", year_raw=["1925"],
         titles_en=["Odalisque à la culotte de satin rouge", "Odalisque in Red Satin Culottes"],
         title_de="Odaliske mit roter Satinhose", medium="lithograph", medium_de="Lithographie", ref=None,
         size=(47.0, 33.0), base=45000, variants=[("ed", 1.0, 50)], copies=None),
    # --- Уорхол
    dict(id="war-marilyn", artist="warhol", year="1967", year_raw=["1967"],
         titles_en=["Marilyn Monroe (Marilyn)", "Marilyn"], title_de="Marilyn Monroe (Marilyn)",
         medium="screenprint in colours", medium_de="Farbserigraphie", ref="F. & S. II.31",
         size=(91.5, 91.5), base=380000, variants=[("ed", 1.0, 250)], copies=None),
    dict(id="war-tomato", artist="warhol", year="1968", year_raw=["1968"],
         titles_en=["Tomato, from Campbell's Soup I", "Campbell's Soup I: Tomato"],
         title_de="Tomato, aus: Campbell's Soup I", medium="screenprint in colours",
         medium_de="Farbserigraphie", ref="F. & S. II.46", size=(89.0, 58.5), base=65000,
         variants=[("ed", 1.0, 250)], copies=None),
    dict(id="war-mao", artist="warhol", year="1972", year_raw=["1972"],
         titles_en=["Mao", "Mao (one plate)"], title_de="Mao", medium="screenprint in colours",
         medium_de="Farbserigraphie", ref="F. & S. II.91", size=(91.5, 91.5), base=110000,
         variants=[("ed", 1.0, 250)], copies=None),
    dict(id="war-flowers", artist="warhol", year="1970", year_raw=["1970"],
         titles_en=["Flowers", "Flowers (one plate)"], title_de="Flowers", medium="screenprint in colours",
         medium_de="Farbserigraphie", ref="F. & S. II.64", size=(91.5, 91.5), base=55000,
         variants=[("ed", 1.0, 250)], copies=None),
    # --- Лихтенштейн
    dict(id="lic-sweet", artist="lichtenstein", year="1965", year_raw=["1965"],
         titles_en=["Sweet Dreams, Baby!", "Sweet Dreams Baby!, from 11 Pop Artists, Volume III"],
         title_de="Sweet Dreams, Baby!", medium="screenprint in colours", medium_de="Farbserigraphie",
         ref="Corlett II.5", size=(95.6, 70.0), base=110000, variants=[("ed", 1.0, 200)], copies=None),
    dict(id="lic-reflections", artist="lichtenstein", year="1990", year_raw=["1990"],
         titles_en=["Reflections on Brushstrokes, from Reflections", "Reflections on Brushstrokes"],
         title_de="Reflections on Brushstrokes", medium="lithograph, screenprint and woodcut",
         medium_de="Lithographie, Serigraphie und Holzschnitt", ref=None, size=(113.0, 145.0),
         base=60000, variants=[("ed", 1.0, 68)], copies=None),
    # --- Хокни
    dict(id="hoc-water", artist="hockney", year="1978-80", year_raw=["1978-80", "1978-1980"],
         titles_en=["Lithograph of Water Made of Lines", "Lithograph of Water Made of Lines, from Paper Pools"],
         title_de="Lithograph of Water Made of Lines", medium="lithograph in colours",
         medium_de="Farblithographie", ref=None, size=(74.3, 85.7), base=42000,
         variants=[("ed", 1.0, 70)], copies=None),
    dict(id="hoc-swimming", artist="hockney", year="1979-80", year_raw=["1979-80"],
         titles_en=["Afternoon Swimming", "Afternoon Swimming, 1979-80"], title_de="Afternoon Swimming",
         medium="lithograph and screenprint in colours", medium_de="Farblithographie und Serigraphie",
         ref=None, size=(76.2, 90.2), base=95000, variants=[("ed", 1.0, 55)], copies=None),
    # --- Харинг
    dict(id="har-popshop", artist="haring", year="1987", year_raw=["1987"],
         titles_en=["Pop Shop I (one plate)", "Pop Shop I"], title_de="Pop Shop I",
         medium="screenprint in colours", medium_de="Farbserigraphie", ref="Littmann p. 86-87",
         size=(30.5, 38.1), base=26000, variants=[("ed", 1.0, 200)], copies=None),
    dict(id="har-growing", artist="haring", year="1988", year_raw=["1988"],
         titles_en=["Growing (one plate)", "Growing, from Growing Suite"], title_de="Growing",
         medium="screenprint in colours", medium_de="Farbserigraphie", ref=None, size=(101.6, 76.2),
         base=42000, variants=[("ed", 1.0, 100)], copies=None),
    # --- Бэнкси
    dict(id="ban-girl", artist="banksy", year="2004", year_raw=["2004"],
         titles_en=["Girl with Balloon", "Girl With Balloon"], title_de="Girl with Balloon",
         medium="screenprint in colours", medium_de="Farbserigraphie", ref=None, size=(70.0, 50.0),
         base=14000, variants=[("signed", 3.2, 150), ("unsigned", 1.0, 600)], copies=None),
    dict(id="ban-love", artist="banksy", year="2003", year_raw=["2003"],
         titles_en=["Love is in the Air", "Love Is in the Air (Flower Thrower)"],
         title_de="Love is in the Air", medium="screenprint in colours", medium_de="Farbserigraphie",
         ref=None, size=(70.0, 50.0), base=12000, variants=[("signed", 3.0, 150), ("unsigned", 1.0, 500)],
         copies=None),
    dict(id="ban-kate", artist="banksy", year="2005", year_raw=["2005"],
         titles_en=["Kate Moss", "Kate Moss (Pink)"], title_de="Kate Moss", medium="screenprint in colours",
         medium_de="Farbserigraphie", ref=None, size=(70.0, 70.0), base=45000,
         variants=[("signed", 1.0, 50)], copies=None),
    # --- Кусама
    dict(id="kus-pumpkin92", artist="kusama", year="1992", year_raw=["1992"],
         titles_en=["Pumpkin", "Pumpkin (Yellow)"], title_de="Kürbis", medium="screenprint in colours",
         medium_de="Farbserigraphie", ref=None, size=(60.6, 72.7), base=22000,
         variants=[("ed", 1.0, 120)], copies=None),
    dict(id="kus-pumpkinred", artist="kusama", year="2000", year_raw=["2000"],
         titles_en=["Pumpkin (Red)", "Red Pumpkin"], title_de="Kürbis (Rot)", medium="screenprint in colours",
         medium_de="Farbserigraphie", ref=None, size=(54.0, 65.0), base=18000,
         variants=[("ed", 1.0, 120)], copies=None),
]

ROMAN_ORD_EN = {"I": "first", "II": "second", "III": "third", "IV": "fourth", "V": "fifth",
                "VI": "sixth", "VII": "seventh"}
STATE_TOTAL = {"rem-3crosses": "five", "rem-100guilder": "two", "rem-selfsill": "two",
               "rem-shell": "three", "dur-melencolia": "two", "dur-knight": "one",
               "dur-jerome": "one", "dur-adam": "four", "pic-minotauro": "seven"}


@dataclass
class Obj:
    """Физический экземпляр: конкретный оттиск."""
    id: str
    work: dict
    variant: tuple
    number: int | None          # номер в тираже (для нумерованных эдиций)
    quality: float              # качество оттиска/сохранность — множитель цены
    size: tuple                 # размер листа: у старых оттисков поля обрезаны по-разному
    emb: list = field(default_factory=list)
    sales: list = field(default_factory=list)


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def _noise(rng, base, scale):
    return _unit([b + rng.gauss(0, scale) for b in base])


def artist_index(artist: str, year_frac: float) -> float:
    """Истинный (скрытый) уровень цен художника относительно 2015 года."""
    level, y = 1.0, 2015.0
    periods = sorted(GROWTH[artist].items())
    while y < year_frac:
        rate = [r for start, r in periods if start <= y][-1]
        step = min(1.0, year_frac - y)
        level *= (1 + rate) ** step
        y += step
    return level


def nice_round(x: float) -> int:
    if x <= 0:
        return 0
    mag = 10 ** max(0, int(math.log10(x)) - 1)
    for step in (1, 2, 2.5, 5, 10):
        if x <= step * mag * 10:
            unit = step * mag / 2
            return int(round(x / unit) * unit)
    return int(round(x, -3))


LADDER = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10]


def est_round(x: float) -> int:
    """Эстимейты дома ставят по «круглой» лестнице: 15 000, 20 000, 25 000, 30 000…"""
    mag = 10 ** int(math.log10(x))
    return int(min((step * mag for step in LADDER), key=lambda v: abs(v - x)))


def fmt_num(x: int, lang: str) -> str:
    s = f"{x:,}"
    return s.replace(",", ".") if lang == "de" else s


def inches(cm: float) -> str:
    total = cm / 2.54
    whole = int(total)
    eighths = round((total - whole) * 8)
    if eighths == 8:
        whole, eighths = whole + 1, 0
    if eighths == 0:
        return f"{whole}"
    num, den = eighths, 8
    while num % 2 == 0:
        num, den = num // 2, den // 2
    return f"{whole} {num}/{den}"


def make_world(rng: random.Random):
    """Создаёт работы, варианты и физические экземпляры с «фото»-векторами."""
    objects = []
    for w in WORKS:
        w_emb = _unit([rng.gauss(0, 1) for _ in range(EMB_DIM)])
        w["emb"] = w_emb
        for v in w["variants"]:
            code, mult, ed = v
            v_emb = _noise(rng, w_emb, 0.10)
            if ed:  # нумерованная эдиция: экземпляры почти неразличимы на фото
                numbers = rng.sample(range(1, ed + 1), k=min(ed, rng.randint(9, 16)))
                for n in numbers:
                    objects.append(Obj(f"{w['id']}:{code}:{n}", w, v, n, rng.uniform(0.9, 1.1),
                                       w["size"], _noise(rng, v_emb, 0.015)))
            else:  # старые оттиски: различаются качеством, полями и следами бытования
                for i in range(w["copies"]):
                    q = rng.choice([0.7, 0.85, 1.0, 1.0, 1.2, 1.5])
                    size = (round(w["size"][0] * rng.uniform(0.97, 1.0), 1),
                            round(w["size"][1] * rng.uniform(0.97, 1.0), 1))
                    objects.append(Obj(f"{w['id']}:{code}:imp{i + 1}", w, v, None, q, size,
                                       _noise(rng, v_emb, 0.04)))
    return objects


def sale_calendar(rng: random.Random):
    """Торги: у каждого дома несколько сессий графики в год."""
    sales = []
    for hid, h in HOUSES.items():
        per_year = {"christies": 4, "sothebys": 4, "phillips": 3, "bonhams": 3, "heritage": 3,
                    "dorotheum": 3, "ketterer": 2}[hid]
        for y in YEARS:
            for k in range(per_year):
                d = date(y, 1, 1) + timedelta(days=int((k + 0.5) / per_year * 360 + rng.randint(-20, 20)))
                d = min(max(d, date(y, 1, 10)), date(y, 12, 15))
                if y == 2026 and d > date(2026, 12, 15):
                    continue
                code = f"{hid[:3].upper()}{y}{k + 1:02d}"
                title = {"en": "Prints & Multiples", "de": "Druckgraphik"}[h["lang"]]
                sales.append({"sale_id": code, "house": hid, "date": d, "title": title})
    return sorted(sales, key=lambda s: s["date"])


def raw_lot(rng, house_id, sale, lot_no, obj: Obj, after: bool, price, est, status):
    """Сериализует лот в формате конкретного дома."""
    h = HOUSES[house_id]
    w, (vcode, _, ed) = obj.work, obj.variant
    a = ARTISTS[w["artist"]]
    cur, lang = h["currency"], h["lang"]
    title_en = rng.choice(w["titles_en"])
    year_raw = rng.choice(w["year_raw"])
    h_cm, w_cm = obj.size
    ref = w["ref"]
    numbered = f"{obj.number}/{ed}" if obj.number else None
    state_txt_en = state_txt_de = ""
    if vcode in ROMAN_ORD_EN:
        state_txt_en = f"{ROMAN_ORD_EN[vcode]} state (of {STATE_TOTAL.get(w['id'], 'several')})"
        state_txt_de = f"{vcode}. Zustand"
    elif "edition" in vcode:
        state_txt_en = vcode
        state_txt_de = vcode.replace("1st edition", "1. Ausgabe").replace("4th edition", "4. Ausgabe")
    elif vcode == "Vollard edition":
        state_txt_en, state_txt_de = "from the edition of 1913 published by Vollard", "Ausgabe Vollard 1913"

    signed_en = {"signed": "signed in pencil", "unsigned": "unsigned"}.get(vcode, "")
    signed_de = {"signed": "signiert", "unsigned": "unsigniert"}.get(vcode, "")
    if not signed_en and obj.number:
        signed_en, signed_de = "signed in pencil", "signiert"

    est_lo, est_hi = est
    rec = {"source": house_id, "sale_id": sale["sale_id"], "sale_title": sale["title"],
           "sale_date": sale["date"].isoformat(), "lot_number": str(lot_no),
           "source_lot_id": f"{sale['sale_id']}-{lot_no}", "currency": cur,
           "image_ref": f"img/{sale['sale_id']}-{lot_no}.jpg"}

    if house_id == "christies":
        artist = (f"AFTER {a['name'].upper()}" if after else f"{a['name'].upper()} ({a['life'].replace('род. ', 'B. ')})")
        desc = "; ".join(x for x in [w["medium"] + ("" if ed else ", on laid paper"), state_txt_en and f"a fine impression of the {state_txt_en}",
                                     signed_en, numbered and f"numbered {numbered}", ref] if x)
        rec |= {"artist_raw": artist, "title_raw": title_en, "date_raw": year_raw, "medium_raw": desc,
                "dimensions_raw": f"Sheet: {round(h_cm * 10)} x {round(w_cm * 10)} mm.",
                "estimate_raw": f"GBP {fmt_num(est_lo, lang)} – {fmt_num(est_hi, lang)}",
                "price_raw": f"GBP {fmt_num(price, lang)}" if price else None}
    elif house_id == "sothebys":
        artist = f"After {a['aliases'][0] if a['aliases'] else a['name']}" if after else (a["aliases"][0] if a["aliases"] else a["name"])
        title = title_en + (f", State {vcode}" if vcode in ROMAN_ORD_EN else "")
        desc = ". ".join(x for x in [w["medium"].capitalize(), signed_en.capitalize(), numbered and f"Numbered {numbered}", ref] if x)
        rec |= {"artist_raw": artist, "title_raw": title, "date_raw": year_raw, "medium_raw": desc,
                "dimensions_raw": f"{inches(h_cm)} by {inches(w_cm)} in. ({round(h_cm * 10)} by {round(w_cm * 10)} mm)",
                "estimate_raw": f"{fmt_num(est_lo, lang)}–{fmt_num(est_hi, lang)} USD",
                "price_raw": f"Sold for {fmt_num(price, lang)} USD" if price else None}
    elif house_id == "phillips":
        artist = f"AFTER {a['name'].upper()}" if after else a["name"].upper()
        title = title_en + (f" ({ref})" if ref else "")
        desc = ", ".join(x for x in [w["medium"], state_txt_en, signed_en, numbered and f"numbered {numbered}"] if x)
        rec |= {"artist_raw": artist, "title_raw": title, "date_raw": year_raw, "medium_raw": desc,
                "dimensions_raw": f"{h_cm} x {w_cm} cm ({inches(h_cm)} x {inches(w_cm)} in.)",
                "estimate_raw": f"Estimate ${fmt_num(est_lo, lang)} - {fmt_num(est_hi, lang)}",
                "price_raw": f"Sold for ${fmt_num(price, lang)}" if price else None}
    elif house_id == "bonhams":
        artist = (f"After {a['name']}" if after else
                  f"{a['name']} ({a['nationality']}, {a['life'].replace('род. ', 'born ').replace('–', '-')})")
        desc = " ".join(x for x in [w["medium"].capitalize() + ".", state_txt_en and f"The {state_txt_en}.",
                                    signed_en and signed_en.capitalize() + ".", numbered and f"Numbered {numbered}.",
                                    ref and f"{ref}."] if x)
        rec |= {"artist_raw": artist, "title_raw": title_en, "date_raw": year_raw, "medium_raw": desc,
                "dimensions_raw": f"{inches(h_cm)} x {inches(w_cm)}in ({h_cm} x {w_cm}cm)",
                "estimate_raw": f"£{fmt_num(est_lo, lang)} - £{fmt_num(est_hi, lang)}",
                "price_raw": f"Sold for £{fmt_num(price, lang)} inc. premium" if price else None}
    elif house_id == "heritage":
        alias = a["aliases"][0] if a["aliases"] else a["name"]
        artist = f"After {alias}" if after else f"{alias} ({a['nationality']}, {a['life'].replace('род. ', 'b. ').replace('–', '-')})"
        desc = ", ".join(x for x in [w["medium"], state_txt_en, signed_en, numbered and f"Ed. {numbered}", ref] if x)
        rec |= {"artist_raw": artist, "title_raw": f"{title_en}, {year_raw}", "date_raw": None, "medium_raw": desc,
                "dimensions_raw": f"{inches(h_cm).replace(' ', '-')} x {inches(w_cm).replace(' ', '-')} inches ({h_cm} x {w_cm} cm)",
                "estimate_raw": f"Estimate: ${fmt_num(est_lo, lang)} - ${fmt_num(est_hi, lang)}",
                "price_raw": f"Sold for: ${fmt_num(price, lang)}" if price else None}
    elif house_id == "dorotheum":
        artist = f"Nach {a['name']}" if after else a["name"]
        desc = ", ".join(x for x in [w["medium_de"], state_txt_de, signed_de, numbered and f"nummeriert {numbered}", ref] if x)
        rec |= {"artist_raw": artist, "title_raw": w["title_de"], "date_raw": year_raw.replace("circa", "um"),
                "medium_raw": desc, "dimensions_raw": f"{str(h_cm).replace('.', ',')} x {str(w_cm).replace('.', ',')} cm",
                "estimate_raw": f"Schätzwert EUR {fmt_num(est_lo, lang)} bis EUR {fmt_num(est_hi, lang)}",
                "price_raw": f"Zuschlag EUR {fmt_num(price, lang)}" if price else None}
    elif house_id == "ketterer":
        parts = a["name"].rsplit(" ", 1)
        artist = f"Nach {a['name']}" if after else (f"{parts[1]}, {parts[0]}" if len(parts) == 2 else a["name"])
        desc = ". ".join(x for x in [w["medium_de"], state_txt_de, signed_de and signed_de.capitalize(),
                                     numbered and f"Exemplar {numbered}", ref] if x)
        mid = est_round((est_lo + est_hi) / 2)
        rec |= {"artist_raw": artist, "title_raw": f"{w['title_de']}. {year_raw}.", "date_raw": None,
                "medium_raw": desc, "dimensions_raw": f"{str(h_cm).replace('.', ',')} : {str(w_cm).replace('.', ',')} cm",
                "estimate_raw": f"Schätzung: € {fmt_num(mid, lang)}",
                "price_raw": f"Zuschlag: € {fmt_num(price, lang)}" if price else None}
    rec["status_raw"] = status
    return rec


def generate(out_dir: Path, seed: int = SEED):
    rng = random.Random(seed)
    objects = make_world(rng)
    by_artist = {}
    for o in objects:
        by_artist.setdefault(o.work["artist"], []).append(o)
    sales = sale_calendar(rng)
    lot_counter = {}
    raws, truth, images = [], [], {}

    for sale in sales:
        h = HOUSES[sale["house"]]
        upcoming = sale["date"] > TODAY
        yf = sale["date"].year + sale["date"].timetuple().tm_yday / 366
        for artist, objs in by_artist.items():
            expected = LOTS_PER_YEAR[artist] / 22  # ~22 сессий в год на все дома
            n = sum(1 for _ in range(4) if rng.random() < expected / 4 * (1.2 if h["lang"] == "en" else 0.8))
            if upcoming:
                n = 1 if rng.random() < 0.55 else 0
            for _ in range(n):
                after = rng.random() < 0.04 and not upcoming
                # Повторная продажа уже известного экземпляра или первое появление.
                sold_before = [o for o in objs if o.sales and (yf - o.sales[-1]) >= 2.0]
                fresh = [o for o in objs if not o.sales]
                if sold_before and (rng.random() < 0.35 or not fresh):
                    obj = rng.choice(sold_before)
                else:
                    obj = rng.choice(fresh or objs)
                vmult = obj.variant[1]
                level = artist_index(artist, yf)
                fair_usd = obj.work["base"] * vmult * obj.quality * level * (0.06 if after else 1.0)
                usd_to_local = 1 / fx(h["currency"], sale["date"].year)
                # Эстимейт: дом опирается на прошлые цены и закладывает консерватизм.
                lag = artist_index(artist, max(2015.0, yf - 1.0)) / level
                est_mid = fair_usd * usd_to_local * lag * rng.uniform(0.75, 1.3)
                est_lo = est_round(est_mid * 0.8)
                est_hi = est_round(est_mid * 1.25)
                if est_hi <= est_lo:
                    est_hi = est_round(est_lo * 1.5)
                hammer_local = fair_usd * usd_to_local * math.exp(rng.gauss(0, 0.22))
                reserve = est_lo * 0.92
                if upcoming:
                    status, price = "upcoming", None
                elif rng.random() < 0.02:
                    status, price = "withdrawn", None
                elif hammer_local < reserve:
                    status, price = "bought_in", None
                else:
                    status = "sold"
                    hammer = est_round(hammer_local) if hammer_local < 1000 else nice_round(hammer_local)
                    if h["price_mode"] == "total":
                        price = int(round(hammer * (1 + h["premium"]), -1))
                    else:
                        price = hammer
                lot_counter[sale["sale_id"]] = lot_counter.get(sale["sale_id"], 100) + rng.randint(1, 9)
                lot_no = lot_counter[sale["sale_id"]]
                rec = raw_lot(rng, sale["house"], sale, lot_no, obj, after, price, (est_lo, est_hi), status)
                raws.append(rec)
                obj_id = f"after:{obj.work['id']}:{len(raws)}" if after else obj.id
                truth.append({"source_lot_id": rec["source_lot_id"], "object_id": obj_id,
                              "variant_id": f"after:{obj.work['id']}:{len(raws)}" if after else f"{obj.work['id']}:{obj.variant[0]}",
                              "work_id": f"after:{obj.work['id']}:{len(raws)}" if after else obj.work["id"],
                              "artist": artist})
                # «Фото» лота: вектор экземпляра + шум съёмки; у копий «after» — смещение.
                base = _noise(rng, obj.emb, 0.18) if after else obj.emb
                # Часть фото плохие: рама, блики, съёмка под углом.
                photo_noise = 0.065 if rng.random() < 0.1 else 0.02
                images[rec["image_ref"]] = [round(x, 4) for x in _noise(rng, base, photo_noise)]
                if rng.random() < 0.04:  # размеры не указаны в описании
                    rec["dimensions_raw"] = None
                if status == "sold" and not after:
                    obj.sales.append(yf)

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "raw_lots.jsonl", "w", encoding="utf-8") as f:
        for r in raws:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(out_dir / "truth.jsonl", "w", encoding="utf-8") as f:
        for t in truth:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    with open(out_dir / "image_embeddings.json", "w", encoding="utf-8") as f:
        json.dump(images, f)
    return len(raws)


if __name__ == "__main__":
    n = generate(Path(__file__).resolve().parent.parent / "data")
    print(f"raw lots: {n}")
