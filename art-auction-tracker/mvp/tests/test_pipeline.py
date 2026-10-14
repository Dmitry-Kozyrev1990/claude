import math

import pytest

from arttracker.catalog import fx
from arttracker.analytics import cagr, estimate_bias, hedonic_index
from arttracker.matching import pairwise_quality, title_similarity
from arttracker.normalize import (normalize, parse_artist, parse_dimensions, parse_edition, parse_ref,
                                  parse_state, parse_year)


@pytest.mark.parametrize("raw, expected", [
    ("REMBRANDT HARMENSZ. VAN RIJN (1606–1669)", ("rembrandt", None)),
    ("Rijn, Rembrandt Harmensz. van", ("rembrandt", None)),
    ("Kusama, Yayoi", ("kusama", None)),
    ("Lichtenstein (American, 1923-1997)", ("lichtenstein", None)),
    ("AFTER ANDY WARHOL", ("warhol", "after")),
    ("Nach Albrecht Dürer", ("durer", "after")),
    ("Unknown Master", (None, None)),
])
def test_parse_artist(raw, expected):
    assert parse_artist(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("Sheet: 385 x 450 mm.", (38.5, 45.0)),
    ("15 1/8 by 17 3/4 in. (385 by 450 mm)", (38.5, 45.0)),
    ("37-5/8 x 27-1/2 inches (95.6 x 70.0 cm)", (95.6, 70.0)),
    ("38,5 : 45 cm", (38.5, 45.0)),
    ("36 x 36in", (91.4, 91.4)),
    (None, (None, None)),
])
def test_parse_dimensions(raw, expected):
    assert parse_dimensions(raw) == expected


def test_parse_year_variants():
    assert parse_year("circa 1653") == (1653, 1653, True)
    assert parse_year("1797-99") == (1797, 1799, False)
    assert parse_year("um 1648") == (1648, 1648, True)


def test_parse_state_ref_edition():
    assert parse_state("The Three Crosses, State IV") == "IV"
    assert parse_state("a fine impression of the fourth state (of five)") == "IV"
    assert parse_state("Kaltnadel, IV. Zustand") == "IV"
    assert parse_state("Radierung, 1. Ausgabe") == "1st edition"
    assert parse_ref("Marilyn (F. & S. II.31)") == "F&S II.31"
    assert parse_ref("drypoint; B. 78") == "B.78"
    assert parse_edition("signiert, nummeriert 23/250") == (23, 250)
    assert parse_edition("Ed. 10/200") == (10, 200)


def test_normalize_converts_to_usd_and_splits_premium():
    raw = {"source": "dorotheum", "sale_id": "DOR201801", "sale_title": "Druckgraphik", "sale_date": "2018-05-02",
           "lot_number": "12", "source_lot_id": "DOR201801-12", "currency": "EUR", "image_ref": "x",
           "artist_raw": "Andy Warhol", "title_raw": "Mao", "date_raw": "1972",
           "medium_raw": "Farbserigraphie, signiert, nummeriert 12/250, F. & S. II.91",
           "dimensions_raw": "91,5 x 91,5 cm", "estimate_raw": "Schätzwert EUR 80.000 bis EUR 120.000",
           "price_raw": "Zuschlag EUR 100.000", "status_raw": "sold"}
    lot = normalize(raw)
    assert (lot.est_low, lot.est_high) == (80000, 120000)
    assert lot.hammer_local == 100000
    rate = fx("EUR", 2018)                    # приближённый курс или ECB, если собран
    assert lot.hammer_usd == round(100000 * rate)
    assert lot.total_usd == round(100000 * 1.28 * rate)  # + премия 28%
    assert lot.edition_number == 12 and lot.catalogue_ref == "F&S II.91"


def test_title_similarity():
    assert title_similarity("The Three Crosses", "Christ Crucified between the Two Thieves: The Three Crosses") > 0.5
    assert title_similarity("Pumpkin", "Kate Moss") < 0.2


def test_pairwise_quality():
    truth = {"a": 1, "b": 1, "c": 2, "d": 2}
    assert pairwise_quality(truth, truth)["f1"] == 1.0
    split = {"a": 1, "b": 3, "c": 2, "d": 2}
    q = pairwise_quality(split, truth)
    assert q["precision"] == 1.0 and q["recall"] == 0.5


def test_cagr():
    assert cagr(100, 200, 1) == pytest.approx(1.0)
    assert cagr(100, 121, 2) == pytest.approx(0.1)
    assert cagr(0, 100, 1) is None


class FakeLot:
    def __init__(self, lot_id, year, price, status="sold", est=(None, None), hammer=None, qualifier=None):
        self.lot_id, self.year, self.total_usd, self.status = lot_id, year, price, status
        self.est_low, self.est_high, self.hammer_local, self.qualifier = est[0], est[1], hammer, qualifier


def test_hedonic_index_recovers_growth():
    # Три экземпляра разного уровня цен, рынок растёт на 10% в год.
    lots, group = [], {}
    for obj, base in enumerate([10_000, 50_000, 200_000]):
        for y in range(2015, 2020):
            lid = f"{obj}-{y}"
            lots.append(FakeLot(lid, y, base * 1.1 ** (y - 2015)))
            group[lid] = obj
    idx = hedonic_index(lots, group)
    assert idx[2015]["value"] == 100
    assert idx[2019]["value"] == pytest.approx(100 * 1.1 ** 4, rel=1e-3)


def test_estimate_bias():
    lots = [FakeLot("1", 2020, 1, est=(100, 200), hammer=250), FakeLot("2", 2020, 1, est=(100, 200), hammer=150),
            FakeLot("3", 2020, 1, est=(100, 200), hammer=90), FakeLot("4", 2020, None, "bought_in", est=(100, 200))]
    b = estimate_bias(lots)
    assert (b["above"], b["within"], b["below"], b["unsold"]) == (0.25, 0.25, 0.25, 0.25)


def test_full_pipeline_quality(tmp_path):
    """Сквозной прогон на сгенерированных данных: качество сопоставления не ниже порога."""
    import json
    from arttracker import generate
    from arttracker.matching import match
    generate.generate(tmp_path)
    raws = [json.loads(l) for l in open(tmp_path / "raw_lots.jsonl", encoding="utf-8")]
    truth = {json.loads(l)["source_lot_id"]: json.loads(l) for l in open(tmp_path / "truth.jsonl", encoding="utf-8")}
    emb = json.loads((tmp_path / "image_embeddings.json").read_text())
    lots = [normalize(r) for r in raws]
    m = match(lots, emb)
    work = pairwise_quality(m.work_of, {k: v["work_id"] for k, v in truth.items()})
    obj = pairwise_quality(m.object_of, {k: v["object_id"] for k, v in truth.items()})
    assert work["precision"] > 0.98 and work["recall"] > 0.95
    assert obj["precision"] > 0.97 and obj["recall"] > 0.85
    assert not math.isnan(obj["f1"])
