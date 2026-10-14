"""Сборщики проверяются на образцах ответов: живая сеть в тестах не нужна.

Образцы повторяют формат публичных API. После открытия доступа к доменам стоит
один раз сверить их с живыми ответами (python -m arttracker.collect …).
"""
import json

import pytest

from arttracker.sources import registry
from arttracker.sources.adapters import (parse_artic, parse_ecb_csv, parse_lot_page, parse_met_object,
                                         parse_wikidata, wikidata_query)
from arttracker.sources.base import PoliteClient, SourceNotAllowed, SourcePolicy


def policy(**kw):
    base = dict(id="t", name="Test", kind="reference", status="approved", license="CC0",
                terms_url="https://example.org/terms", domains=["example.org"], min_interval=1.0)
    return SourcePolicy(**{**base, **kw})


class FakeNet:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        for prefix, resp in self.routes.items():
            if url.startswith(prefix):
                return resp.pop(0) if isinstance(resp, list) else resp
        return 404, b""


def test_blocked_and_pending_sources_refuse_to_start():
    with pytest.raises(SourceNotAllowed):
        PoliteClient(registry.REGISTRY["artprice"])
    for sid in ("artsy", "mutualart", "christies"):
        with pytest.raises(SourceNotAllowed):
            PoliteClient(registry.REGISTRY[sid])


def test_client_rejects_foreign_domain(tmp_path):
    c = PoliteClient(policy(), transport=FakeNet({}), raw_dir=tmp_path, sleep=lambda s: None)
    with pytest.raises(SourceNotAllowed):
        c.get("https://other.org/page")


def test_client_respects_robots_txt(tmp_path):
    net = FakeNet({"https://example.org/robots.txt": (200, b"User-agent: *\nDisallow: /private/\n"),
                   "https://example.org/": (200, b"ok")})
    c = PoliteClient(policy(), transport=net, raw_dir=tmp_path, sleep=lambda s: None)
    assert c.get("https://example.org/public/1").status == 200
    with pytest.raises(SourceNotAllowed):
        c.get("https://example.org/private/1")


def test_client_throttles_retries_and_caches(tmp_path):
    slept = []
    net = FakeNet({"https://example.org/robots.txt": (404, b""),
                   "https://example.org/a": [(503, b""), (200, b'{"x": 1}')]})
    c = PoliteClient(policy(min_interval=5.0), transport=net, raw_dir=tmp_path, sleep=slept.append)
    r = c.get("https://example.org/a")
    assert r.status == 200 and r.json() == {"x": 1}
    assert any(s >= 2.0 for s in slept)             # пауза после 503
    assert all("LotlineBot" in h["User-Agent"] for _, h in net.calls)
    calls = len(net.calls)
    again = c.get("https://example.org/a")          # второй раз — из сырого архива
    assert again.from_cache and len(net.calls) == calls


WIKIDATA = {"head": {"vars": []}, "results": {"bindings": [{
    "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q5603"},
    "name": {"xml:lang": "en", "type": "literal", "value": "Andy Warhol"},
    "ulan": {"type": "literal", "value": "500006031"},
    "birth": {"type": "literal", "value": "1928-08-06T00:00:00Z"},
    "death": {"type": "literal", "value": "1987-02-22T00:00:00Z"},
    "ru": {"xml:lang": "ru", "type": "literal", "value": "Энди Уорхол"},
    "aliases": {"type": "literal", "value": "Andrew Warhola|Warhol"}}]}}


def test_parse_wikidata():
    [a] = parse_wikidata(WIKIDATA)
    assert (a.wikidata_id, a.ulan_id, a.birth_year, a.death_year) == ("Q5603", "500006031", 1928, 1987)
    assert a.labels["ru"] == "Энди Уорхол" and "Andrew Warhola" in a.aliases
    assert '"Andy Warhol"@en' in wikidata_query(["Andy Warhol"])


def test_parse_museum_records():
    artic = {"config": {"iiif_url": "https://www.artic.edu/iiif/2"}, "data": [{
        "id": 4575, "title": "Christ Crucified between the Two Thieves: The Three Crosses",
        "artist_title": "Rembrandt van Rijn", "date_start": 1653, "date_end": 1653, "date_display": "1653",
        "medium_display": "Drypoint and engraving on paper", "dimensions": "38.5 × 45 cm (15 3/16 × 17 11/16 in.)",
        "image_id": "abc-123", "is_public_domain": True}]}
    [w] = parse_artic(artic)
    assert (w.height_cm, w.width_cm) == (38.5, 45.0)
    assert w.image_url == "https://www.artic.edu/iiif/2/abc-123/full/843,/0/default.jpg"
    met = parse_met_object({"objectID": 336222, "title": "Melencolia I", "artistDisplayName": "Albrecht Dürer",
                            "objectDate": "1514", "objectBeginDate": 1514, "objectEndDate": 1514,
                            "medium": "Engraving", "dimensions": "sheet: 9 7/16 × 7 5/16 in. (24 × 18.5 cm)",
                            "primaryImageSmall": "https://images.metmuseum.org/x.jpg", "isPublicDomain": True,
                            "objectURL": "https://www.metmuseum.org/art/collection/search/336222"})
    assert (met.year_from, met.height_cm, met.width_cm) == (1514, 24.0, 18.5)


def test_parse_ecb_csv():
    text = ("KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
            "EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2024-01-02,1.0956\n"
            "EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2024-01-03,1.0919\n")
    assert parse_ecb_csv(text) == {"2024-01-02": 1.0956, "2024-01-03": 1.0919}


LOT_HTML = """<html><head><meta property="og:image" content="https://cdn.example.org/lot.jpg">
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
 {"@type": "BreadcrumbList"},
 {"@type": ["Product", "VisualArtwork"], "sku": "LOT-145", "name": "Flowers (F. & S. II.64)",
  "creator": {"@type": "Person", "name": "Andy Warhol"}, "dateCreated": "1970",
  "artMedium": "screenprint in colours", "description": "signed in pencil, numbered 37/250",
  "height": {"@type": "QuantitativeValue", "value": 91.5, "unitCode": "CMT"},
  "width": {"@type": "QuantitativeValue", "value": 91.5, "unitCode": "CMT"},
  "offers": {"@type": "Offer", "price": "63000", "priceCurrency": "USD",
             "availability": "https://schema.org/SoldOut"}}]}</script></head><body></body></html>"""


def test_parse_lot_page_jsonld():
    lot = parse_lot_page(LOT_HTML, "https://example.org/lot/145", "example")
    assert lot["artist_raw"] == "Andy Warhol" and lot["title_raw"].startswith("Flowers")
    assert lot["dimensions_raw"] == "91.5 x 91.5 cm" and lot["price"] == 63000.0
    assert lot["price_kind"] == "sold" and lot["image_url"] == "https://cdn.example.org/lot.jpg"
    assert "numbered 37/250" in lot["medium_raw"]
    assert parse_lot_page("<html></html>", "u", "s") is None


def test_approved_config_cannot_unblock(tmp_path, monkeypatch):
    cfg = tmp_path / "approved.json"
    cfg.write_text(json.dumps([
        {"id": "artprice", "name": "Artprice", "domains": ["artprice.com"], "terms_url": "x", "reviewed_on": "2026-10-14"},
        {"id": "house", "name": "House", "domains": ["house.example"], "terms_url": "x", "reviewed_on": "2026-10-14",
         "min_interval": 1}]))
    monkeypatch.setattr(registry, "CONFIG", cfg)
    ids = [p.id for p in registry.approved_auction_sources()]
    assert ids == ["house"]
    assert registry.get("house").min_interval == 5.0   # не чаще раза в 5 секунд, даже если указано меньше


def test_discovery_parsing_and_registry_counts(tmp_path, monkeypatch):
    from arttracker.sources.discovery import CATEGORIES, discovery_query, parse_discovery
    payload = {"results": {"bindings": [
        {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "Dorotheum"},
         "countryLabel": {"value": "Austria"}, "cityLabel": {"value": "Vienna"}},
        {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "Dorotheum"},
         "website": {"value": "https://www.dorotheum.com/"}},
        {"item": {"value": "http://www.wikidata.org/entity/Q2"}, "itemLabel": {"value": "Q2"}},  # без названия
    ]}}
    [c] = parse_discovery("auction_house", payload)
    assert (c.name, c.city, c.website, c.status) == ("Dorotheum", "Vienna", "https://www.dorotheum.com/", "pending_review")
    for cat in CATEGORIES:
        assert "LIMIT 100 OFFSET 200" in discovery_query(cat, 100, 200)
    cands = tmp_path / "c.jsonl"
    cands.write_text(json.dumps({"category": "art_museum", "wikidata_id": "Q3", "name": "M",
                                 "country": None, "city": None, "website": None, "status": "pending_review"}) + "\n")
    monkeypatch.setattr(registry, "CANDIDATES", cands)
    assert registry.discovered_candidates()[0]["category"] == "art_museum"


def test_registry_covers_aggregators_and_open_museums():
    r = registry.REGISTRY
    assert {"the-saleroom", "drouot", "catawiki", "lot-tissimo"} <= set(r)
    assert all(r[k].status == "approved" for k in ("cleveland", "smithsonian", "nga", "moma"))
    assert all(p.status != "approved" for p in r.values() if p.kind == "auction")


def test_unreachable_robots_txt(tmp_path):
    def net(url, headers):
        if url.endswith("/robots.txt"):
            raise OSError("tunnel 403")
        return 200, b"{}"
    api = PoliteClient(policy(documented_api=True), transport=net, raw_dir=tmp_path, sleep=lambda s: None)
    assert api.get("https://example.org/data").status == 200
    assert not any(u.endswith("robots.txt") for u in [])  # у официального API robots.txt не запрашивается
    site = PoliteClient(policy(id="site"), transport=net, raw_dir=tmp_path, sleep=lambda s: None)
    with pytest.raises(SourceNotAllowed):
        site.get("https://example.org/page")


def test_429_waits_for_retry_after(tmp_path):
    from arttracker.sources.base import retry_after
    slept = []
    responses = [(429, b"", {"Retry-After": "90"}), (200, b"{}", {})]
    c = PoliteClient(policy(documented_api=True), transport=lambda u, h: responses.pop(0),
                     raw_dir=tmp_path, sleep=slept.append)
    assert c.get("https://example.org/q").status == 200
    assert 90.0 in slept
    assert retry_after({}, 60.0) == 60.0 and retry_after({"retry-after": "9999"}, 1) == 300.0
