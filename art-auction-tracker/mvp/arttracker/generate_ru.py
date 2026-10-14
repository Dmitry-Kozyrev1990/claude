"""Синтетический российский рынок: уникальные картины и работы на бумаге.

В отличие от тиражной графики здесь каждая работа существует в одном экземпляре,
а названия типовые («Морской пейзаж», «Натюрморт»): разные картины часто называются
одинаково, а одна и та же картина в Москве и в Лондоне — по-разному. Сопоставлять
приходится по размеру, году и изображению.

Российские дома (Литфонд, Совком, Vladey, Гелос, Империя) пишут каталоги по-русски
и в рублях, с разными форматами имени («И.К. Айвазовский», «АЙВАЗОВСКИЙ Иван
Константинович») и сокращениями («Х., м.»). Русские торги Christie's, Sotheby's и
Bonhams в Лондоне идут до 2021 года включительно.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from .catalog import ARTISTS, HOUSES, fx

YEARS = list(range(2015, 2027))

# artist: (рост по периодам, лотов в год, база USD за работу 60×80, годы работы, техники, сюжеты RU/EN)
PAINT = ("холст, масло", "Х., м.", "oil on canvas")
BOARD = ("картон, масло", "К., м.", "oil on board")
TEMPERA = ("холст, темпера", "Х., темпера", "tempera on canvas")
TEMP_BOARD = ("картон, темпера", "К., темпера", "tempera on cardboard")
WATERCOLOR = ("бумага, акварель", "Б., акв.", "watercolour on paper")
GOUACHE = ("бумага, гуашь", "Б., гуашь", "gouache on paper")
PENCIL = ("бумага, графитный карандаш", "Б., кар.", "pencil on paper")
INK = ("бумага, акварель, тушь", "Б., акв., тушь", "watercolour and ink on paper")

RU_WORKS = {
    "aivazovsky": dict(growth={2015: 0.02, 2022: -0.12, 2023: 0.07}, per_year=30, base=420000, years=(1850, 1899),
                       media=[(PAINT, 0.9), (PENCIL, 0.1)], size=(30, 110), themes=[
                           ("Морской пейзаж с парусником", "Seascape with a Sailing Ship"),
                           ("Лунная ночь на море", "Moonlit Night at Sea"),
                           ("Буря у скалистых берегов", "Storm off a Rocky Coast"),
                           ("Корабль в бурном море", "Ship in a Stormy Sea"),
                           ("Закат на море", "Sunset at Sea"), ("Рыбаки на берегу", "Fishermen on the Shore"),
                           ("Вид Константинополя", "View of Constantinople"), ("Штиль", "Calm Sea")]),
    "shishkin": dict(growth={2015: 0.02, 2022: -0.08, 2023: 0.06}, per_year=20, base=230000, years=(1860, 1898),
                     media=[(PAINT, 0.6), (PENCIL, 0.4)], size=(25, 100), themes=[
                         ("Лесной пейзаж", "Forest Landscape"), ("Сосновый бор", "Pine Forest"),
                         ("Ручей в лесу", "Forest Stream"), ("Опушка леса", "Edge of the Forest"),
                         ("Дубы", "Oak Trees"), ("Лесная тропа", "Forest Path")]),
    "korovin": dict(growth={2015: 0.03, 2022: -0.06, 2023: 0.08}, per_year=22, base=140000, years=(1890, 1938),
                    media=[(PAINT, 0.7), (BOARD, 0.3)], size=(25, 90), themes=[
                        ("Париж ночью", "Paris at Night"), ("Гурзуф", "Gurzuf"), ("Натюрморт с розами", "Still Life with Roses"),
                        ("Зимний пейзаж", "Winter Landscape"), ("Кафе в Париже", "Paris Café"), ("Северная идиллия", "Northern Idyll")]),
    "kustodiev": dict(growth={2015: 0.03, 2022: -0.05, 2023: 0.09}, per_year=10, base=380000, years=(1905, 1927),
                      media=[(PAINT, 0.6), (WATERCOLOR, 0.4)], size=(25, 100), themes=[
                          ("Масленица", "Maslenitsa"), ("Портрет купчихи", "Portrait of a Merchant's Wife"),
                          ("Ярмарка", "Village Fair"), ("Катание на санях", "Sleigh Ride"), ("Летний день", "Summer Day")]),
    "roerich": dict(growth={2015: 0.04, 2022: -0.06, 2023: 0.05}, per_year=14, base=260000, years=(1900, 1947),
                    media=[(TEMPERA, 0.8), (TEMP_BOARD, 0.2)], size=(30, 120), themes=[
                        ("Гималаи", "Himalayas"), ("Тибет", "Tibet"), ("Горы. Закат", "Mountains at Sunset"),
                        ("Монастырь в горах", "Monastery in the Mountains"), ("Путь", "The Path")]),
    "kandinsky": dict(growth={2015: 0.04, 2022: 0.0, 2023: 0.03}, per_year=10, base=480000, years=(1908, 1944),
                      media=[(WATERCOLOR, 0.6), (PAINT, 0.4)], size=(20, 80), themes=[
                          ("Композиция", "Composition"), ("Импровизация", "Improvisation"), ("Без названия", "Untitled"),
                          ("Пейзаж с башней", "Landscape with Tower")]),
    "goncharova": dict(growth={2015: 0.03, 2022: -0.04, 2023: 0.04}, per_year=12, base=260000, years=(1906, 1960),
                       media=[(PAINT, 0.6), (GOUACHE, 0.4)], size=(25, 100), themes=[
                           ("Испанка", "Spanish Woman"), ("Натюрморт", "Still Life"), ("Лучистский пейзаж", "Rayonist Landscape"),
                           ("Цветы", "Flowers"), ("Эскиз декорации", "Set Design")]),
    "deineka": dict(growth={2015: 0.05, 2022: 0.09, 2024: 0.05}, per_year=10, base=230000, years=(1925, 1968),
                    media=[(PAINT, 0.5), (WATERCOLOR, 0.5)], size=(25, 120), themes=[
                        ("Спортсмены", "Athletes"), ("На море", "By the Sea"), ("Москва. Вечер", "Moscow Evening"),
                        ("Девушка с мячом", "Girl with a Ball"), ("Купальщицы", "Bathers")]),
    "pimenov": dict(growth={2015: 0.05, 2022: 0.10, 2024: 0.04}, per_year=10, base=110000, years=(1930, 1976),
                    media=[(PAINT, 0.7), (GOUACHE, 0.3)], size=(30, 100), themes=[
                        ("Московская улица", "Moscow Street"), ("Новые кварталы", "New Neighbourhoods"),
                        ("Весна в городе", "Spring in the City"), ("Вечер", "Evening")]),
    "rabin": dict(growth={2015: 0.05, 2022: 0.07}, per_year=14, base=55000, years=(1958, 2015),
                  media=[(PAINT, 0.9), (GOUACHE, 0.1)], size=(40, 110), themes=[
                      ("Барак", "Barrack"), ("Лианозово", "Lianozovo"), ("Натюрморт с бутылкой", "Still Life with a Bottle"),
                      ("Город", "Town"), ("Скрипка на кладбище", "Violin in a Cemetery")]),
    "zverev": dict(growth={2015: 0.06, 2022: 0.09, 2024: 0.03}, per_year=40, base=12000, years=(1955, 1986),
                   media=[(GOUACHE, 0.6), (PAINT, 0.4)], size=(30, 80), themes=[
                       ("Портрет", "Portrait"), ("Автопортрет", "Self-Portrait"), ("Лошади", "Horses"),
                       ("Пейзаж", "Landscape"), ("Портрет девушки", "Portrait of a Girl")]),
    "yakovlev": dict(growth={2015: 0.06, 2022: 0.08}, per_year=22, base=18000, years=(1960, 1997),
                     media=[(GOUACHE, 0.8), (PAINT, 0.2)], size=(30, 70), themes=[
                         ("Цветок", "Flower"), ("Цветок в вазе", "Flower in a Vase"), ("Портрет", "Portrait"),
                         ("Кошка", "Cat")]),
    "krasnopevtsev": dict(growth={2015: 0.05, 2022: 0.08}, per_year=8, base=65000, years=(1960, 1994),
                          media=[(BOARD, 1.0)], size=(30, 70), themes=[
                              ("Натюрморт с кувшинами", "Still Life with Jugs"),
                              ("Метафизический натюрморт", "Metaphysical Still Life"), ("Раковины", "Shells")]),
    "koshlyakov": dict(growth={2015: 0.07, 2022: 0.02}, per_year=12, base=22000, years=(1995, 2024),
                       media=[(TEMP_BOARD, 1.0)], size=(60, 200), themes=[
                           ("Архитектурная фантазия", "Architectural Fantasy"), ("Руины", "Ruins"), ("Город", "City")]),
    "pepperstein": dict(growth={2015: 0.08, 2022: 0.03}, per_year=14, base=7000, years=(2000, 2025),
                        media=[(INK, 1.0)], size=(25, 60), themes=[
                            ("Без названия", "Untitled"), ("Город будущего", "City of the Future"), ("Утопия", "Utopia")]),
}

# Какие дома какие сегменты продают и сколько сессий в год.
RU_SALES = {
    "litfond": (4, "Русская живопись и графика", None),
    "sovcom": (4, "Русское искусство", None),
    "gelos": (3, "Живопись и графика", None),
    "imperia": (2, "Русская живопись", None),
    "vladey": (4, "Неофициальное и современное искусство", {"Нонконформизм", "Современное российское искусство",
                                                           "Советское искусство"}),
    "christies_ru": (2, "Russian Art", None),
    "sothebys_ru": (2, "Russian Pictures", None),
    "bonhams_ru": (2, "Russian Art", None),
}


@dataclass
class Painting:
    id: str
    artist: str
    title_ru: str
    title_en: str
    year: int
    medium: tuple
    size: tuple
    base: float
    emb: list
    sales: list = field(default_factory=list)
    last_offer: float = -99.0


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def _noise(rng, base, scale):
    return _unit([b + rng.gauss(0, scale) for b in base])


def ru_index(artist: str, year_frac: float) -> float:
    level, y = 1.0, 2015.0
    periods = sorted(RU_WORKS[artist]["growth"].items())
    while y < year_frac:
        rate = [r for start, r in periods if start <= y][-1]
        step = min(1.0, year_frac - y)
        level *= (1 + rate) ** step
        y += step
    return level


def make_paintings(rng: random.Random, emb_dim: int) -> dict[str, list[Painting]]:
    out = {}
    for aid, cfg in RU_WORKS.items():
        style = _unit([rng.gauss(0, 1) for _ in range(emb_dim)])
        theme_vecs = {t: _noise(rng, style, 0.12) for t in cfg["themes"]}
        n = max(25, int(cfg["per_year"] * 12 / 2.2))
        works = []
        for i in range(n):
            theme = rng.choice(cfg["themes"])
            r = rng.random()
            medium = next(m for m, p in _cumulative(cfg["media"]) if r <= p)
            lo, hi = cfg["size"]
            if medium in (WATERCOLOR, GOUACHE, PENCIL, INK):  # работы на бумаге меньше
                lo, hi = max(15, lo * 0.6), min(hi, 65)
            h = round(rng.uniform(lo, hi) / 0.5) * 0.5
            w = round(h * rng.choice([0.75, 0.8, 1.0, 1.25, 1.33, 1.5]) / 0.5) * 0.5
            area_k = math.sqrt((h * w) / (60 * 80))
            on_paper = medium in (WATERCOLOR, GOUACHE, PENCIL, INK)
            base = cfg["base"] * area_k * (0.35 if on_paper else 1.0) * math.exp(rng.gauss(0, 0.35))
            works.append(Painting(f"{aid}:{i + 1:03d}", aid, theme[0], theme[1], rng.randint(*cfg["years"]),
                                  medium, (h, w), base, _noise(rng, theme_vecs[theme], 0.05)))
        out[aid] = works
    return out


def _cumulative(items):
    acc = 0.0
    for v, p in items:
        acc += p
        yield v, acc
    yield items[-1][0], 1.01


def ru_calendar(rng: random.Random, today: date):
    sales = []
    for hid, (per_year, title, _) in RU_SALES.items():
        until = HOUSES[hid].get("until", 2026)
        for y in YEARS:
            if y > until:
                continue
            for k in range(per_year):
                d = date(y, 1, 1) + timedelta(days=int((k + 0.5) / per_year * 360 + rng.randint(-15, 15)))
                d = min(max(d, date(y, 2, 1)), date(y, 12, 15))
                sales.append({"sale_id": f"{hid[:3].upper()}R{y}{k + 1:02d}", "house": hid, "date": d, "title": title})
    return sorted(sales, key=lambda s: s["date"])


def rub(x: int) -> str:
    return f"{x:,}".replace(",", " ")


def ru_raw_lot(rng, hid: str, sale: dict, lot_no: int, p: Painting, copy: bool, price, est, status) -> dict:
    a = ARTISTS[p.artist]
    h = HOUSES[hid]
    surname = a["name_ru"].split()[-1]
    full_ru = next((x for x in a["aliases"] if len(x.split()) == 3 and x.split()[2] == surname), a["name_ru"])
    first, patr, last = (full_ru.split() + ["", "", ""])[:3] if len(full_ru.split()) == 3 else (
        a["name_ru"].split()[0], "", surname)
    initials = f"{first[0]}.{patr[0]}. {last}" if patr else a["name_ru"]
    year_txt = f"{p.year // 10 * 10}-е" if rng.random() < 0.3 and p.year < 1950 else str(p.year)
    medium_full, medium_abbr, medium_en = p.medium
    hh, ww = p.size
    sig = rng.choice(["Подпись в левом нижнем углу", "Подпись в правом нижнем углу", "Подпись и дата справа внизу"])
    est_lo, est_hi = est
    rec = {"source": hid, "sale_id": sale["sale_id"], "sale_title": sale["title"], "sale_date": sale["date"].isoformat(),
           "lot_number": str(lot_no), "source_lot_id": f"{sale['sale_id']}-{lot_no}", "currency": h["currency"],
           "image_ref": f"img/{sale['sale_id']}-{lot_no}.jpg", "status_raw": status}
    life = a["life"]
    if hid == "litfond":
        artist = f"Копия с работы {initials}" if copy else f"{last} {first} {patr} ({life})".strip()
        rec |= {"artist_raw": artist, "title_raw": p.title_ru, "date_raw": year_txt,
                "medium_raw": f"{medium_full.capitalize()}. {sig}", "dimensions_raw": f"{hh:g} × {ww:g} см".replace(".", ","),
                "estimate_raw": f"Эстимейт: {rub(est_lo)} – {rub(est_hi)} руб.",
                "price_raw": f"Продано за {rub(price)} руб." if price else None}
    elif hid == "sovcom":
        artist = f"Последователь {initials}" if copy else initials
        rec |= {"artist_raw": artist, "title_raw": f"{p.title_ru}. {year_txt}", "date_raw": None,
                "medium_raw": f"{medium_full.capitalize()}. {sig}", "dimensions_raw": f"{hh:g} х {ww:g} см".replace(".", ","),
                "estimate_raw": f"Эстимейт: {rub(est_lo)} – {rub(est_hi)} ₽",
                "price_raw": f"Цена продажи: {rub(price)} ₽" if price else None}
    elif hid == "gelos":
        artist = f"Копия с работы {initials}" if copy else f"{last.upper()} {first} {patr}. {life}".strip()
        rec |= {"artist_raw": artist, "title_raw": p.title_ru, "date_raw": year_txt,
                "medium_raw": medium_abbr, "dimensions_raw": f"{hh:g} х {ww:g}".replace(".", ","),
                "estimate_raw": f"Оценка: {rub(est_lo)} – {rub(est_hi)} руб.",
                "price_raw": f"Продано: {rub(price)} руб." if price else None}
    elif hid == "imperia":
        artist = f"Копия с работы {initials}" if copy else f"{first} {patr} {last} ({life})".strip()
        rec |= {"artist_raw": artist, "title_raw": p.title_ru, "date_raw": year_txt,
                "medium_raw": f"{medium_full}. {sig}", "dimensions_raw": f"{hh:g} × {ww:g} см".replace(".", ","),
                "estimate_raw": f"{rub(est_lo)} — {rub(est_hi)} руб.",
                "price_raw": f"{rub(price)} руб." if price else None}
    elif hid == "vladey":
        artist = f"Копия с работы {initials}" if copy else a["name_ru"]
        rec |= {"artist_raw": artist, "title_raw": p.title_ru, "date_raw": str(p.year),
                "medium_raw": medium_full.capitalize(), "dimensions_raw": f"{hh:g} × {ww:g} см".replace(".", ","),
                "estimate_raw": f"{rub(est_lo)} — {rub(est_hi)} ₽",
                "price_raw": f"Продано: {rub(price)} ₽" if price else None}
    else:  # русские торги Christie's, Sotheby's, Bonhams в Лондоне
        name = a["aliases"][0] if hid == "bonhams_ru" else a["name"]
        artist = f"Circle of {a['name']}" if copy else (
            f"{name.upper()} ({life.replace('–', '-')})" if hid == "christies_ru" else name)
        sep = {"christies_ru": " x ", "sothebys_ru": " by ", "bonhams_ru": " x "}[hid]
        sym = "£"
        rec |= {"artist_raw": artist, "title_raw": p.title_en, "date_raw": str(p.year),
                "medium_raw": f"{medium_en}, signed", "dimensions_raw": f"{hh:g}{sep}{ww:g} cm",
                "estimate_raw": f"Estimate {sym}{est_lo:,} - {sym}{est_hi:,}",
                "price_raw": f"Sold for {sym}{price:,}" if price else None}
    return rec


def generate_ru(seed: int, today: date, emb_dim: int, est_round, nice_round, raws, truth, images):
    """Дописывает лоты российского рынка в общие списки raws/truth/images."""
    rng = random.Random(seed)
    works = make_paintings(rng, emb_dim)
    for sale in ru_calendar(rng, today):
        hid = sale["house"]
        h = HOUSES[hid]
        segs = RU_SALES[hid][2]
        upcoming = sale["date"] > today
        yf = sale["date"].year + sale["date"].timetuple().tm_yday / 366
        sessions_per_year = sum(v[0] for k, v in RU_SALES.items() if HOUSES[k].get("until", 2026) >= sale["date"].year)
        lot_no = 0
        for aid, pool in works.items():
            if segs and ARTISTS[aid]["segment"] not in segs:
                continue
            exp = RU_WORKS[aid]["per_year"] / sessions_per_year * (1.3 if h["region"] == "ru" and yf >= 2022 else 1.0)
            n = sum(1 for _ in range(4) if rng.random() < exp / 4)
            if upcoming:
                n = 1 if rng.random() < 0.35 else 0
            for _ in range(n):
                copy = rng.random() < 0.03 and not upcoming
                reoffer = [p for p in pool if not p.sales and 0.4 <= yf - p.last_offer <= 2.0]
                resale = [p for p in pool if p.sales and yf - p.sales[-1] >= 2.5]
                fresh = [p for p in pool if p.last_offer < 0]
                r = rng.random()
                if reoffer and r < 0.25:
                    p = rng.choice(reoffer)
                elif resale and (r < 0.45 or not fresh):
                    p = rng.choice(resale)
                else:
                    p = rng.choice(fresh or pool)
                fair_usd = p.base * ru_index(aid, yf) * (0.04 if copy else 1.0)
                local = 1 / fx(h["currency"], sale["date"].year)
                lag = ru_index(aid, max(2015.0, yf - 1.0)) / ru_index(aid, yf)
                est_mid = fair_usd * local * lag * rng.uniform(0.75, 1.25)
                est_lo = est_round(est_mid * 0.8)
                est_hi = est_round(est_mid * 1.25)
                if est_hi <= est_lo:
                    est_hi = est_round(est_lo * 1.5)
                hammer_local = fair_usd * local * math.exp(rng.gauss(0, 0.25))
                if upcoming:
                    status, price = "upcoming", None
                elif rng.random() < 0.02:
                    status, price = "withdrawn", None
                elif hammer_local < est_lo * 0.9:
                    status, price = "bought_in", None
                else:
                    status = "sold"
                    hammer = nice_round(hammer_local)
                    price = int(round(hammer * (1 + h["premium"]), -1)) if h["price_mode"] == "total" else hammer
                lot_no += rng.randint(1, 6)
                rec = ru_raw_lot(rng, hid, sale, lot_no, p, copy, price, (est_lo, est_hi), status)
                raws.append(rec)
                oid = f"after:{p.id}:{len(raws)}" if copy else p.id
                truth.append({"source_lot_id": rec["source_lot_id"], "object_id": oid,
                              "variant_id": oid if copy else f"{p.id}:ed", "work_id": oid, "artist": aid})
                base = _noise(rng, p.emb, 0.18) if copy else p.emb
                images[rec["image_ref"]] = [round(x, 4) for x in
                                            _noise(rng, base, 0.065 if rng.random() < 0.1 else 0.02)]
                if rng.random() < 0.03:
                    rec["dimensions_raw"] = None
                if not copy:
                    p.last_offer = yf
                    if status == "sold":
                        p.sales.append(yf)
