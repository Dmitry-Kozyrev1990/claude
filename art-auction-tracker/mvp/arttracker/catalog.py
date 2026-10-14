"""Справочники: художники, аукционные дома, курсы валют.

Художники и названия работ реальные (это общеизвестные факты). Цены, лоты и
торги в демо синтетические — их создаёт generate.py.
"""

ARTISTS = {
    "rembrandt": {
        "name": "Rembrandt Harmensz. van Rijn", "name_ru": "Рембрандт",
        "aliases": ["Rembrandt van Rijn", "Rembrandt", "Rembrandt Harmenszoon van Rijn"],
        "life": "1606–1669", "nationality": "Dutch", "segment": "Старые мастера",
    },
    "durer": {
        "name": "Albrecht Dürer", "name_ru": "Альбрехт Дюрер",
        "aliases": ["Albrecht Durer", "Albrecht Duerer", "Dürer"],
        "life": "1471–1528", "nationality": "German", "segment": "Старые мастера",
    },
    "goya": {
        "name": "Francisco José de Goya y Lucientes", "name_ru": "Франсиско Гойя",
        "aliases": ["Francisco de Goya", "Francisco Goya", "Goya"],
        "life": "1746–1828", "nationality": "Spanish", "segment": "Старые мастера",
    },
    "picasso": {
        "name": "Pablo Picasso", "name_ru": "Пабло Пикассо",
        "aliases": ["Picasso"], "life": "1881–1973", "nationality": "Spanish",
        "segment": "Модернизм",
    },
    "chagall": {
        "name": "Marc Chagall", "name_ru": "Марк Шагал",
        "aliases": ["Chagall"], "life": "1887–1985", "nationality": "French-Russian",
        "segment": "Модернизм",
    },
    "matisse": {
        "name": "Henri Matisse", "name_ru": "Анри Матисс",
        "aliases": ["Matisse"], "life": "1869–1954", "nationality": "French",
        "segment": "Модернизм",
    },
    "warhol": {
        "name": "Andy Warhol", "name_ru": "Энди Уорхол",
        "aliases": ["Warhol"], "life": "1928–1987", "nationality": "American",
        "segment": "Поп-арт",
    },
    "lichtenstein": {
        "name": "Roy Lichtenstein", "name_ru": "Рой Лихтенштейн",
        "aliases": ["Lichtenstein"], "life": "1923–1997", "nationality": "American",
        "segment": "Поп-арт",
    },
    "hockney": {
        "name": "David Hockney", "name_ru": "Дэвид Хокни",
        "aliases": ["Hockney"], "life": "род. 1937", "nationality": "British",
        "segment": "Современное искусство",
    },
    "haring": {
        "name": "Keith Haring", "name_ru": "Кит Харинг",
        "aliases": ["Haring"], "life": "1958–1990", "nationality": "American",
        "segment": "Современное искусство",
    },
    "banksy": {
        "name": "Banksy", "name_ru": "Бэнкси", "aliases": [],
        "life": "род. 1974", "nationality": "British", "segment": "Современное искусство",
    },
    "kusama": {
        "name": "Yayoi Kusama", "name_ru": "Яёи Кусама",
        "aliases": ["Kusama", "Kusama Yayoi"], "life": "род. 1929", "nationality": "Japanese",
        "segment": "Современное искусство",
    },
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
}

# Среднегодовые курсы к доллару (приближённые).
FX_TO_USD = {
    "USD": {y: 1.0 for y in range(2015, 2027)},
    "GBP": {2015: 1.53, 2016: 1.36, 2017: 1.29, 2018: 1.34, 2019: 1.28, 2020: 1.28,
            2021: 1.38, 2022: 1.24, 2023: 1.24, 2024: 1.28, 2025: 1.32, 2026: 1.34},
    "EUR": {2015: 1.11, 2016: 1.11, 2017: 1.13, 2018: 1.18, 2019: 1.12, 2020: 1.14,
            2021: 1.18, 2022: 1.05, 2023: 1.08, 2024: 1.08, 2025: 1.13, 2026: 1.16},
}


def fx(currency: str, year: int) -> float:
    table = FX_TO_USD[currency]
    return table.get(year, table[max(table)])
