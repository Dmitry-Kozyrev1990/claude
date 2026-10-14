"""Адаптеры открытых источников. Каждый возвращает записи в форматах конвейера.

- Wikidata → справочник художников (имена на языках, даты, ID в Getty ULAN);
- Art Institute of Chicago и The Met → эталонные карточки работ с изображениями;
- ECB → ежедневные курсы валют;
- JSON-LD → лоты с аукционных страниц, которые публикуют разметку schema.org
  (только для доменов, прошедших проверку условий).
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from urllib.parse import quote, urlencode

from ..normalize import parse_dimensions, parse_year
from .base import PoliteClient

# ---------------- Wikidata ----------------

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"


@dataclass
class ArtistRecord:
    wikidata_id: str
    name: str
    ulan_id: str | None
    birth_year: int | None
    death_year: int | None
    labels: dict = field(default_factory=dict)      # язык → имя
    aliases: list = field(default_factory=list)
    source: str = "wikidata"


def wikidata_query(names: list[str]) -> str:
    values = " ".join(f'"{n}"@en' for n in names)
    return f"""SELECT ?item ?name ?ulan ?birth ?death ?ru ?de ?fr
       (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases) WHERE {{
  VALUES ?name {{ {values} }}
  ?item rdfs:label ?name; wdt:P245 ?ulan.
  OPTIONAL {{ ?item wdt:P569 ?birth. }}
  OPTIONAL {{ ?item wdt:P570 ?death. }}
  OPTIONAL {{ ?item rdfs:label ?ru. FILTER(LANG(?ru) = "ru") }}
  OPTIONAL {{ ?item rdfs:label ?de. FILTER(LANG(?de) = "de") }}
  OPTIONAL {{ ?item rdfs:label ?fr. FILTER(LANG(?fr) = "fr") }}
  OPTIONAL {{ ?item skos:altLabel ?alias. FILTER(LANG(?alias) IN ("en", "de", "fr", "ru")) }}
}} GROUP BY ?item ?name ?ulan ?birth ?death ?ru ?de ?fr"""


def _year(v: str | None) -> int | None:
    m = re.match(r"^[+-]?(\d{4})", v or "")
    return int(m.group(1)) if m else None


def parse_wikidata(payload: dict) -> list[ArtistRecord]:
    out = {}
    for b in payload["results"]["bindings"]:
        get = lambda k: b.get(k, {}).get("value")  # noqa: E731
        qid = get("item").rsplit("/", 1)[-1]
        if qid in out:
            continue
        labels = {lang: get(lang) for lang in ("ru", "de", "fr") if get(lang)}
        out[qid] = ArtistRecord(qid, get("name"), get("ulan"), _year(get("birth")), _year(get("death")),
                                labels, sorted({a for a in (get("aliases") or "").split("|") if a}))
    return list(out.values())


def fetch_artists(client: PoliteClient, names: list[str], batch: int = 6) -> list[ArtistRecord]:
    records = []
    for i in range(0, len(names), batch):
        q = wikidata_query(names[i:i + batch])
        url = f"{WIKIDATA_SPARQL}?{urlencode({'query': q, 'format': 'json'})}"
        resp = client.get(url)
        if resp.status == 200:
            records += parse_wikidata(resp.json())
        else:
            print(f"Wikidata ответил {resp.status} на пакет {i // batch + 1}: {names[i:i + batch]}", file=sys.stderr)
    seen, unique = set(), []
    for r in records:
        if r.wikidata_id not in seen:
            seen.add(r.wikidata_id)
            unique.append(r)
    return unique


# ---------------- музейные API ----------------

@dataclass
class ReferenceWork:
    source: str
    source_id: str
    url: str
    artist: str | None
    title: str
    date_display: str | None
    year_from: int | None
    year_to: int | None
    medium: str | None
    dimensions_raw: str | None
    height_cm: float | None
    width_cm: float | None
    image_url: str | None
    public_domain: bool | None
    artist_ulan: str | None = None
    artist_wikidata: str | None = None

    def to_dict(self):
        return asdict(self)


ARTIC_FIELDS = ("id,title,artist_title,date_start,date_end,date_display,medium_display,dimensions,"
                "image_id,is_public_domain,classification_title")


def parse_artic(payload: dict) -> list[ReferenceWork]:
    iiif = (payload.get("config") or {}).get("iiif_url", "https://www.artic.edu/iiif/2")
    out = []
    for d in payload.get("data", []):
        h, w = parse_dimensions(d.get("dimensions"))
        out.append(ReferenceWork(
            "artic", str(d["id"]), f"https://www.artic.edu/artworks/{d['id']}", d.get("artist_title"),
            d.get("title") or "", d.get("date_display"), d.get("date_start"), d.get("date_end"),
            d.get("medium_display"), d.get("dimensions"), h, w,
            f"{iiif}/{d['image_id']}/full/843,/0/default.jpg" if d.get("image_id") else None,
            d.get("is_public_domain")))
    return out


def search_artic(client: PoliteClient, query: str, limit: int = 20) -> list[ReferenceWork]:
    url = (f"https://api.artic.edu/api/v1/artworks/search?q={quote(query)}"
           f"&fields={ARTIC_FIELDS}&limit={limit}")
    resp = client.get(url)
    return parse_artic(resp.json()) if resp.status == 200 else []


def parse_met_object(d: dict) -> ReferenceWork:
    h, w = parse_dimensions(d.get("dimensions"))
    y1, y2 = d.get("objectBeginDate"), d.get("objectEndDate")
    if not y1:
        y1, y2, _ = parse_year(d.get("objectDate"))
    artist = next((c for c in d.get("constituents") or [] if c.get("role") == "Artist"), {})
    ulan = (artist.get("constituentULAN_URL") or "").rstrip("/").rsplit("/", 1)[-1] or None
    wd = (artist.get("constituentWikidata_URL") or "").rstrip("/").rsplit("/", 1)[-1] or None
    return ReferenceWork(
        "met", str(d["objectID"]), d.get("objectURL") or "", d.get("artistDisplayName") or None,
        d.get("title") or "", d.get("objectDate"), y1, y2, d.get("medium"), d.get("dimensions"), h, w,
        d.get("primaryImageSmall") or None, d.get("isPublicDomain"), ulan, wd)


MET = "https://collectionapi.metmuseum.org/public/collection"


def search_met(client: PoliteClient, query: str, limit: int = 20) -> list[ReferenceWork]:
    # Поиск v1 закрыт музеем 2026-10-01; v1.1 работает с постраничной выдачей.
    resp = client.get(f"{MET}/v1.1/search?hasImages=true&q={quote(query)}&limit={limit}")
    if resp.status != 200:
        print(f"The Met: поиск ответил {resp.status}", file=sys.stderr)
        return []
    ids = (resp.json().get("objectIDs") or [])[:limit]
    out = []
    for oid in ids:
        r = client.get(f"{MET}/v1/objects/{oid}")
        if r.status == 200:
            out.append(parse_met_object(r.json()))
    return out


# ---------------- ECB: курсы валют ----------------

def ecb_url(currency: str, start: str) -> str:
    return (f"https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
            f"?format=csvdata&startPeriod={start}")


def parse_ecb_csv(text: str) -> dict[str, float]:
    """Дата → сколько единиц валюты за 1 евро."""
    rows = csv.DictReader(io.StringIO(text))
    return {r["TIME_PERIOD"]: float(r["OBS_VALUE"]) for r in rows if r.get("OBS_VALUE")}


def fetch_fx(client: PoliteClient, start: str = "2015-01-01") -> dict:
    """Курсы к доллару: {валюта: {дата: USD за 1 единицу}} и среднегодовые значения."""
    usd = parse_ecb_csv(client.get(ecb_url("USD", start)).text())
    gbp = parse_ecb_csv(client.get(ecb_url("GBP", start)).text())
    daily = {"EUR": dict(usd), "GBP": {d: usd[d] / gbp[d] for d in gbp if d in usd}}
    annual = {}
    for cur, series in daily.items():
        by_year = {}
        for d, v in series.items():
            by_year.setdefault(int(d[:4]), []).append(v)
        annual[cur] = {y: round(sum(v) / len(v), 4) for y, v in sorted(by_year.items())}
    return {"source": "ECB", "daily": daily, "annual": annual}


# ---------------- Банк России: курс рубля ----------------
# ECB прекратил публиковать курс рубля в 2022 году, поэтому рубль берём у ЦБ РФ.

CBR_USD = "R01235"


def cbr_url(start: str, end: str) -> str:
    d1 = "/".join(reversed(start.split("-")))
    d2 = "/".join(reversed(end.split("-")))
    return f"https://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={d1}&date_req2={d2}&VAL_NM_RQ={CBR_USD}"


def parse_cbr_xml(body: bytes) -> dict[str, float]:
    """Дата (ISO) → рублей за 1 доллар."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(body)
    out = {}
    for rec in root.iter("Record"):
        d, mth, y = rec.get("Date").split(".")
        nominal = float((rec.findtext("Nominal") or "1").replace(",", "."))
        out[f"{y}-{mth}-{d}"] = float(rec.findtext("Value").replace(",", ".")) / nominal
    return out


def fetch_rub(client: PoliteClient, start: str = "2015-01-01", end: str | None = None) -> dict:
    from datetime import date as _d
    end = end or _d.today().isoformat()
    rub_per_usd = parse_cbr_xml(client.get(cbr_url(start, end)).body)
    by_year = {}
    for d, v in rub_per_usd.items():
        by_year.setdefault(int(d[:4]), []).append(1 / v)
    annual = {y: round(sum(v) / len(v), 6) for y, v in sorted(by_year.items())}
    return {"source": "Банк России", "daily_rub_per_usd": rub_per_usd, "annual": {"RUB": annual}}


# ---------------- JSON-LD на страницах лотов ----------------

class _JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks, self.meta, self._in = [], {}, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and a.get("type") == "application/ld+json":
            self._in, self._buf = True, []
        elif tag == "meta" and (a.get("property") or a.get("name", "")).startswith("og:"):
            self.meta[a.get("property") or a.get("name")] = a.get("content")

    def handle_data(self, data):
        if self._in:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in:
            self._in = False
            try:
                self.blocks.append(json.loads("".join(self._buf)))
            except json.JSONDecodeError:
                pass


def _flatten(block):
    if isinstance(block, list):
        for b in block:
            yield from _flatten(b)
    elif isinstance(block, dict):
        if "@graph" in block:
            yield from _flatten(block["@graph"])
        yield block


def _name(v):
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        return v.get("name")
    return v


def parse_lot_page(html: str, url: str, source_id: str) -> dict | None:
    """Достаёт лот из разметки schema.org (Product / VisualArtwork / CreativeWork + Offer).

    Возвращает запись в формате сырого лота конвейера или None, если разметки нет.
    """
    p = _JsonLdParser()
    p.feed(html)
    item = None
    for b in (x for blk in p.blocks for x in _flatten(blk)):
        t = b.get("@type")
        types = set(t if isinstance(t, list) else [t])
        if types & {"Product", "VisualArtwork", "CreativeWork", "IndividualProduct"}:
            item = b
            break
    if not item:
        return None
    offers = item.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = offers.get("price") or offers.get("lowPrice")
    width, height = _name(item.get("width")), _name(item.get("height"))
    dims = None
    if isinstance(item.get("height"), dict) and isinstance(item.get("width"), dict):
        unit = (item["height"].get("unitText") or item["height"].get("unitCode") or "cm").lower()
        unit = "cm" if unit in ("cmt", "cm") else "mm" if unit in ("mmt", "mm") else unit
        dims = f"{item['height'].get('value')} x {item['width'].get('value')} {unit}"
    elif height and width:
        dims = f"{height} x {width}"
    image = item.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")
    availability = str(offers.get("availability", ""))
    return {
        "source": source_id, "url": url,
        "source_lot_id": str(item.get("sku") or item.get("productID") or item.get("identifier") or url),
        "artist_raw": _name(item.get("creator") or item.get("artist") or item.get("brand")),
        "title_raw": item.get("name") or p.meta.get("og:title"),
        "date_raw": item.get("dateCreated"),
        "medium_raw": " ".join(x for x in [_name(item.get("artMedium")), _name(item.get("artform")),
                                            item.get("description")] if x) or None,
        "dimensions_raw": dims,
        "currency": offers.get("priceCurrency"),
        "price": float(price) if price not in (None, "") else None,
        "price_kind": "sold" if "SoldOut" in availability else "offer",
        "image_url": image or p.meta.get("og:image"),
    }
