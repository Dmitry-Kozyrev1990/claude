"""Справочники: художники, аукционные дома, курсы валют.

Художники и названия работ реальные (это общеизвестные факты). Цены, лоты и
торги в демо синтетические — их создаёт generate.py.
"""

import json
from pathlib import Path

ARTISTS = {
    "rembrandt": {
        "name": "Rembrandt Harmensz. van Rijn", "name_ru": "Рембрандт",
        "aliases": ["Rembrandt van Rijn", "Rembrandt", "Rembrandt Harmenszoon van Rijn"],
        "life": "1606–1669", "nationality": "Dutch", "segment": "Старые мастера", "market": "intl",
    },
    "durer": {
        "name": "Albrecht Dürer", "name_ru": "Альбрехт Дюрер",
        "aliases": ["Albrecht Durer", "Albrecht Duerer", "Dürer"],
        "life": "1471–1528", "nationality": "German", "segment": "Старые мастера", "market": "intl",
    },
    "goya": {
        "name": "Francisco José de Goya y Lucientes", "name_ru": "Франсиско Гойя",
        "aliases": ["Francisco de Goya", "Francisco Goya", "Goya"],
        "life": "1746–1828", "nationality": "Spanish", "segment": "Старые мастера", "market": "intl",
    },
    "picasso": {
        "name": "Pablo Picasso", "name_ru": "Пабло Пикассо",
        "aliases": ["Picasso"], "life": "1881–1973", "nationality": "Spanish",
        "segment": "Модернизм", "market": "intl",
    },
    "chagall": {
        "name": "Marc Chagall", "name_ru": "Марк Шагал",
        "aliases": ["Chagall"], "life": "1887–1985", "nationality": "French-Russian",
        "segment": "Модернизм", "market": "intl",
    },
    "matisse": {
        "name": "Henri Matisse", "name_ru": "Анри Матисс",
        "aliases": ["Matisse"], "life": "1869–1954", "nationality": "French",
        "segment": "Модернизм", "market": "intl",
    },
    "warhol": {
        "name": "Andy Warhol", "name_ru": "Энди Уорхол",
        "aliases": ["Warhol"], "life": "1928–1987", "nationality": "American",
        "segment": "Поп-арт", "market": "intl",
    },
    "lichtenstein": {
        "name": "Roy Lichtenstein", "name_ru": "Рой Лихтенштейн",
        "aliases": ["Lichtenstein"], "life": "1923–1997", "nationality": "American",
        "segment": "Поп-арт", "market": "intl",
    },
    "hockney": {
        "name": "David Hockney", "name_ru": "Дэвид Хокни",
        "aliases": ["Hockney"], "life": "род. 1937", "nationality": "British",
        "segment": "Современное искусство", "market": "intl",
    },
    "haring": {
        "name": "Keith Haring", "name_ru": "Кит Харинг",
        "aliases": ["Haring"], "life": "1958–1990", "nationality": "American",
        "segment": "Современное искусство", "market": "intl",
    },
    "banksy": {
        "name": "Banksy", "name_ru": "Бэнкси", "aliases": [],
        "life": "род. 1974", "nationality": "British", "segment": "Современное искусство", "market": "intl",
    },
    "kusama": {
        "name": "Yayoi Kusama", "name_ru": "Яёи Кусама",
        "aliases": ["Kusama", "Kusama Yayoi"], "life": "род. 1929", "nationality": "Japanese",
        "segment": "Современное искусство", "market": "intl",
    },
}

# Российский рынок: художники, которые продаются на российских аукционах и на русских
# торгах международных домов. Работы и цены в демо синтетические.
RU_ARTISTS = {
    "aivazovsky": {
        "name": "Ivan Aivazovsky", "name_ru": "Иван Айвазовский",
        "aliases": ["Ivan Konstantinovich Aivazovsky", "Ivan Aivazovskii", "Ivan Ayvazovsky",
                    "Иван Константинович Айвазовский", "Айвазовский Иван Константинович", "Айвазовский"],
        "life": "1817–1900", "nationality": "Russian", "segment": "Русская классика", "market": "ru"},
    "shishkin": {
        "name": "Ivan Shishkin", "name_ru": "Иван Шишкин",
        "aliases": ["Ivan Ivanovich Shishkin", "Иван Иванович Шишкин", "Шишкин Иван Иванович", "Шишкин"],
        "life": "1832–1898", "nationality": "Russian", "segment": "Русская классика", "market": "ru"},
    "korovin": {
        "name": "Konstantin Korovin", "name_ru": "Константин Коровин",
        "aliases": ["Konstantin Alexeevich Korovin", "Константин Алексеевич Коровин", "Коровин Константин Алексеевич", "Коровин"],
        "life": "1861–1939", "nationality": "Russian", "segment": "Русская классика", "market": "ru"},
    "kustodiev": {
        "name": "Boris Kustodiev", "name_ru": "Борис Кустодиев",
        "aliases": ["Boris Mikhailovich Kustodiev", "Борис Михайлович Кустодиев", "Кустодиев Борис Михайлович", "Кустодиев"],
        "life": "1878–1927", "nationality": "Russian", "segment": "Русская классика", "market": "ru"},
    "roerich": {
        "name": "Nicholas Roerich", "name_ru": "Николай Рерих",
        "aliases": ["Nikolai Roerich", "Nicholas Rerikh", "Nikolai Konstantinovich Roerich",
                    "Николай Константинович Рерих", "Рерих Николай Константинович", "Рерих"],
        "life": "1874–1947", "nationality": "Russian", "segment": "Русская классика", "market": "ru"},
    "kandinsky": {
        "name": "Wassily Kandinsky", "name_ru": "Василий Кандинский",
        "aliases": ["Vasily Kandinsky", "Wassily Kandinskij", "Василий Васильевич Кандинский",
                    "Кандинский Василий Васильевич", "Кандинский"],
        "life": "1866–1944", "nationality": "Russian", "segment": "Русский авангард", "market": "ru"},
    "goncharova": {
        "name": "Natalia Goncharova", "name_ru": "Наталья Гончарова",
        "aliases": ["Natalya Goncharova", "Natalia Sergeevna Goncharova", "Наталья Сергеевна Гончарова",
                    "Гончарова Наталья Сергеевна", "Гончарова"],
        "life": "1881–1962", "nationality": "Russian", "segment": "Русский авангард", "market": "ru"},
    "deineka": {
        "name": "Alexander Deineka", "name_ru": "Александр Дейнека",
        "aliases": ["Aleksandr Deineka", "Alexander Deyneka", "Александр Александрович Дейнека",
                    "Дейнека Александр Александрович", "Дейнека"],
        "life": "1899–1969", "nationality": "Soviet", "segment": "Советское искусство", "market": "ru"},
    "pimenov": {
        "name": "Yuri Pimenov", "name_ru": "Юрий Пименов",
        "aliases": ["Yury Pimenov", "Yuri Ivanovich Pimenov", "Юрий Иванович Пименов", "Пименов Юрий Иванович", "Пименов"],
        "life": "1903–1977", "nationality": "Soviet", "segment": "Советское искусство", "market": "ru"},
    "rabin": {
        "name": "Oscar Rabin", "name_ru": "Оскар Рабин",
        "aliases": ["Oskar Rabin", "Оскар Яковлевич Рабин", "Рабин Оскар Яковлевич", "Рабин"],
        "life": "1928–2018", "nationality": "Russian", "segment": "Нонконформизм", "market": "ru"},
    "zverev": {
        "name": "Anatoly Zverev", "name_ru": "Анатолий Зверев",
        "aliases": ["Anatolii Zverev", "Anatoly Timofeevich Zverev", "Анатолий Тимофеевич Зверев",
                    "Зверев Анатолий Тимофеевич", "Зверев"],
        "life": "1931–1986", "nationality": "Russian", "segment": "Нонконформизм", "market": "ru"},
    "yakovlev": {
        "name": "Vladimir Yakovlev", "name_ru": "Владимир Яковлев",
        "aliases": ["Vladimir Igorevich Yakovlev", "Владимир Игоревич Яковлев", "Яковлев Владимир Игоревич"],
        "life": "1934–1998", "nationality": "Russian", "segment": "Нонконформизм", "market": "ru"},
    "krasnopevtsev": {
        "name": "Dmitri Krasnopevtsev", "name_ru": "Дмитрий Краснопевцев",
        "aliases": ["Dmitry Krasnopevtsev", "Dmitri Mikhailovich Krasnopevtsev", "Дмитрий Михайлович Краснопевцев",
                    "Краснопевцев Дмитрий Михайлович", "Краснопевцев"],
        "life": "1925–1995", "nationality": "Russian", "segment": "Нонконформизм", "market": "ru"},
    "koshlyakov": {
        "name": "Valery Koshlyakov", "name_ru": "Валерий Кошляков",
        "aliases": ["Valeriy Koshlyakov", "Валерий Николаевич Кошляков", "Кошляков Валерий Николаевич", "Кошляков"],
        "life": "род. 1962", "nationality": "Russian", "segment": "Современное российское искусство", "market": "ru"},
    "pepperstein": {
        "name": "Pavel Pepperstein", "name_ru": "Павел Пепперштейн",
        "aliases": ["Pavel Peppershtein", "Павел Викторович Пепперштейн", "Пепперштейн Павел Викторович", "Пепперштейн"],
        "life": "род. 1966", "nationality": "Russian", "segment": "Современное российское искусство", "market": "ru"},
}
ARTISTS.update(RU_ARTISTS)

MARKETS = {"intl": "Зарубежный рынок", "ru": "Российский рынок"}
SEGMENTS = {
    "intl": ["Старые мастера", "Модернизм", "Поп-арт", "Современное искусство"],
    "ru": ["Русская классика", "Русский авангард", "Советское искусство", "Нонконформизм",
           "Современное российское искусство"],
}

# Аукционные дома. premium — упрощённая плоская ставка премии покупателя;
# price_mode: "total" — дом публикует цену с премией, "hammer" — только цену молотка.
HOUSES = {
    "christies": {"name": "Christie's", "city": "Лондон", "currency": "GBP", "premium": 0.25, "price_mode": "total", "lang": "en"},
    "sothebys": {"name": "Sotheby's", "city": "Нью-Йорк", "currency": "USD", "premium": 0.26, "price_mode": "total", "lang": "en"},
    "phillips": {"name": "Phillips", "city": "Нью-Йорк", "currency": "USD", "premium": 0.26, "price_mode": "total", "lang": "en"},
    "bonhams": {"name": "Bonhams", "city": "Лондон", "currency": "GBP", "premium": 0.27, "price_mode": "total", "lang": "en"},
    "heritage": {"name": "Heritage Auctions", "city": "Даллас", "currency": "USD", "premium": 0.25, "price_mode": "total", "lang": "en"},
    "dorotheum": {"name": "Dorotheum", "city": "Вена", "currency": "EUR", "premium": 0.28, "price_mode": "hammer", "lang": "de"},
    "ketterer": {"name": "Ketterer Kunst", "city": "Мюнхен", "currency": "EUR", "premium": 0.32, "price_mode": "hammer", "lang": "de"},
    # Российские дома (ставки премии приближённые).
    "litfond": {"name": "Литфонд", "city": "Москва", "currency": "RUB", "premium": 0.15, "price_mode": "hammer", "lang": "ru", "region": "ru"},
    "sovcom": {"name": "Совком", "city": "Москва", "currency": "RUB", "premium": 0.15, "price_mode": "hammer", "lang": "ru", "region": "ru"},
    "vladey": {"name": "Vladey", "city": "Москва", "currency": "RUB", "premium": 0.15, "price_mode": "hammer", "lang": "ru", "region": "ru"},
    "gelos": {"name": "Гелос", "city": "Москва", "currency": "RUB", "premium": 0.15, "price_mode": "hammer", "lang": "ru", "region": "ru"},
    "imperia": {"name": "Империя", "city": "Москва", "currency": "RUB", "premium": 0.15, "price_mode": "total", "lang": "ru", "region": "ru"},
    # Русские торги международных домов: проводились в Лондоне до 2022 года.
    "christies_ru": {"name": "Christie's", "city": "Лондон", "currency": "GBP", "premium": 0.25, "price_mode": "total", "lang": "en", "until": 2021},
    "sothebys_ru": {"name": "Sotheby's", "city": "Лондон", "currency": "GBP", "premium": 0.25, "price_mode": "total", "lang": "en", "until": 2021},
    "bonhams_ru": {"name": "Bonhams", "city": "Лондон", "currency": "GBP", "premium": 0.27, "price_mode": "total", "lang": "en", "until": 2021},
}
for _h in HOUSES.values():
    _h.setdefault("region", "intl")

# Среднегодовые курсы к доллару (приближённые).
FX_TO_USD = {
    "USD": {y: 1.0 for y in range(2015, 2027)},
    "GBP": {2015: 1.53, 2016: 1.36, 2017: 1.29, 2018: 1.34, 2019: 1.28, 2020: 1.28,
            2021: 1.38, 2022: 1.24, 2023: 1.24, 2024: 1.28, 2025: 1.32, 2026: 1.34},
    "EUR": {2015: 1.11, 2016: 1.11, 2017: 1.13, 2018: 1.18, 2019: 1.12, 2020: 1.14,
            2021: 1.18, 2022: 1.05, 2023: 1.08, 2024: 1.08, 2025: 1.13, 2026: 1.16},
    # Рубль: приближённые среднегодовые значения (USD за 1 рубль); точные — из ЦБ РФ (collect fx-cbr).
    "RUB": {y: round(1 / r, 6) for y, r in {2015: 61.0, 2016: 67.0, 2017: 58.3, 2018: 62.7, 2019: 64.7,
                                            2020: 72.1, 2021: 73.7, 2022: 68.5, 2023: 85.2, 2024: 92.6,
                                            2025: 84.0, 2026: 85.0}.items()},
}


REFERENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


def _load_ecb_rates():
    """Собранные курсы (ECB — collect fx, ЦБ РФ — collect fx-cbr) заменяют приближённые."""
    for name in ("fx.json", "fx_cbr.json"):
        path = REFERENCE_DIR / name
        if not path.exists():
            continue
        annual = json.loads(path.read_text(encoding="utf-8")).get("annual", {})
        for cur, table in annual.items():
            FX_TO_USD.setdefault(cur, {}).update({int(y): float(v) for y, v in table.items()})


_load_ecb_rates()


def register_houses(houses: dict):
    """Дома из импортированных архивов (data/imported/houses.json)."""
    for hid, h in houses.items():
        HOUSES[hid] = {"premium": 0.0, "price_mode": "hammer", "lang": "ru", "region": "ru", **h}


_imported = Path(__file__).resolve().parent.parent / "data" / "imported" / "houses.json"
if _imported.exists():
    register_houses(json.loads(_imported.read_text(encoding="utf-8")))


def fx(currency: str, year: int) -> float:
    table = FX_TO_USD[currency]
    return table.get(year, table[max(table)])
