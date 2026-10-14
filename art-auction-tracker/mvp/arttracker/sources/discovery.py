"""Поиск кандидатов в источники через Wikidata: аукционные дома, музеи, коллекции банков
и частные коллекции по всему миру.

Все найденные получают статус pending_review: из них ничего не собирается, пока не
проверены условия сайта. Цен в музеях и коллекциях обычно нет — они нужны как эталон
работ, изображения и провенанс.

Типы ищутся по английской метке класса и всем его подклассам, поэтому не зависят от
конкретных идентификаторов Wikidata.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlencode

from .base import PoliteClient

SPARQL = "https://query.wikidata.org/sparql"

# Категория → условие на ?item в SPARQL.
CATEGORIES = {
    "auction_house": '?cls rdfs:label "auction house"@en. ?item wdt:P31/wdt:P279* ?cls.',
    "art_museum": '?cls rdfs:label "art museum"@en. ?item wdt:P31/wdt:P279* ?cls.',
    # Коллекции, которыми владеет банк (или его подкласс): Deutsche Bank, UBS и т. п.
    "bank_collection": ('?bank_cls rdfs:label "bank"@en. ?owner wdt:P31/wdt:P279* ?bank_cls. '
                        '?cls rdfs:label "art collection"@en. ?item wdt:P31/wdt:P279* ?cls; wdt:P127 ?owner.'),
    # Коллекции, которыми владеет человек (Q5 — «человек»).
    "private_collection": ('?cls rdfs:label "art collection"@en. ?item wdt:P31/wdt:P279* ?cls; '
                           'wdt:P127 ?owner. ?owner wdt:P31 wd:Q5.'),
}


@dataclass
class Candidate:
    category: str
    wikidata_id: str
    name: str
    country: str | None
    city: str | None
    website: str | None
    status: str = "pending_review"


def discovery_query(category: str, limit: int, offset: int) -> str:
    return f"""SELECT DISTINCT ?item ?itemLabel ?countryLabel ?cityLabel ?website WHERE {{
  {CATEGORIES[category]}
  OPTIONAL {{ ?item wdt:P17 ?country. }}
  OPTIONAL {{ ?item wdt:P131 ?city. }}
  OPTIONAL {{ ?item wdt:P856 ?website. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,de,fr,ru". }}
}} ORDER BY ?item LIMIT {limit} OFFSET {offset}"""


def parse_discovery(category: str, payload: dict) -> list[Candidate]:
    out = {}
    for b in payload["results"]["bindings"]:
        get = lambda k: b.get(k, {}).get("value")  # noqa: E731
        qid = get("item").rsplit("/", 1)[-1]
        name = get("itemLabel")
        if not name or name == qid:   # без названия на понятных языках — пропускаем
            continue
        c = out.get(qid)
        if c is None:
            out[qid] = Candidate(category, qid, name, get("countryLabel"), get("cityLabel"), get("website"))
        elif not c.website and get("website"):
            c.website = get("website")
    return list(out.values())


def discover(client: PoliteClient, categories=None, page: int = 2000, max_pages: int = 20) -> list[dict]:
    found = []
    for cat in categories or CATEGORIES:
        for i in range(max_pages):
            q = discovery_query(cat, page, i * page)
            resp = client.get(f"{SPARQL}?{urlencode({'query': q, 'format': 'json'})}")
            if resp.status != 200:
                break
            rows = resp.json()["results"]["bindings"]
            found += [asdict(c) for c in parse_discovery(cat, resp.json())]
            if len(rows) < page:
                break
    seen, unique = set(), []
    for c in found:
        key = (c["category"], c["wikidata_id"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique
