"""Российский рынок: разбор русских каталогов, импорт архивов по договору, сборка на них."""
import csv
import json

import pytest

from arttracker.archive import ArchiveError, convert, import_archive, load_mapping
from arttracker.normalize import normalize, parse_artist, parse_dimensions, parse_medium_class


@pytest.mark.parametrize("raw, expected", [
    ("И.К. Айвазовский", ("aivazovsky", None)),
    ("АЙВАЗОВСКИЙ Иван Константинович. 1817–1900", ("aivazovsky", None)),
    ("Зверев Анатолий Тимофеевич (1931–1986)", ("zverev", None)),
    ("ANATOLY ZVEREV (1931-1986)", ("zverev", None)),
    ("Круг И.К. Айвазовского", ("aivazovsky", "circle")),
    ("Копия с работы И.И. Шишкина", ("shishkin", "after")),
    ("Последователь Н.К. Рериха", ("roerich", "after")),
])
def test_russian_artist_names(raw, expected):
    assert parse_artist(raw) == expected


def test_russian_catalogue_formats():
    assert parse_dimensions("60 х 80 см") == (60.0, 80.0)        # кириллическая «х»
    assert parse_dimensions("67,5 х 101") == (67.5, 101.0)        # без единиц — сантиметры
    assert parse_medium_class("Х., м.") == "painting"
    assert parse_medium_class("Б., акв.") == "drawing"
    assert parse_medium_class("Бумага, литография") == "lithograph"
    lot = normalize({"source": "gelos", "sale_id": "G1", "sale_date": "2023-03-10", "lot_number": "5",
                     "source_lot_id": "G1-5", "currency": "RUB", "image_ref": "x",
                     "artist_raw": "ЗВЕРЕВ Анатолий Тимофеевич. 1931–1986", "title_raw": "Портрет девушки",
                     "date_raw": "1983", "medium_raw": "Х., м.", "dimensions_raw": "67,5 х 101",
                     "estimate_raw": "Оценка: 1 500 000 – 2 500 000 руб.", "price_raw": "Продано: 3 750 000 руб.",
                     "status_raw": "sold"})
    assert (lot.artist_id, lot.medium_class, lot.est_low, lot.hammer_local) == ("zverev", "painting", 1500000, 3750000)
    assert lot.hammer_usd and lot.total_usd > lot.hammer_usd


def mapping(tmp_path, license=True):
    m = json.load(open("config/archive_mapping.example.json", encoding="utf-8"))
    m["source_id"] = "partner_test"
    if license:
        m["license"] = {"agreement": "Т-1", "signed_on": "2026-10-14", "scope": "тест", "attribution": "тест"}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return p


def test_import_requires_license(tmp_path):
    with pytest.raises(ArchiveError):
        load_mapping(mapping(tmp_path, license=False))


def test_import_template_archive(tmp_path):
    rep = import_archive("config/archive_template.csv", mapping(tmp_path), out_dir=tmp_path / "imp")
    assert rep["accepted"] == 2 and rep["rejected"] == 0
    rows = [json.loads(l) for l in (tmp_path / "imp" / "partner_test.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["sale_date"] == "2019-05-14" and rows[0]["status_raw"] == "sold"
    assert rows[1]["status_raw"] == "bought_in" and rows[0]["license"] == "Т-1"
    assert rep["coverage"]["художник узнан"] == 1.0


def test_convert_rejects_duplicates_and_missing(tmp_path):
    m = load_mapping(mapping(tmp_path))
    with open("config/archive_template.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    rows += [dict(rows[0]), {**rows[1], "Автор": ""}]
    ok, rejected = convert(rows, m)
    assert len(ok) == 2 and sorted(r["reason"] for r in rejected) == ["дубль лота", "нет обязательных полей"]


def test_build_on_imported_archive(tmp_path, monkeypatch):
    from arttracker import archive, build
    import_archive("config/archive_template.csv", mapping(tmp_path), out_dir=tmp_path / "imp")
    monkeypatch.setattr(archive, "IMPORTED", tmp_path / "imp")
    data = build.run("imported")
    assert data["meta"]["synthetic"] is False and data["pipeline"]["quality"] is None
    assert data["meta"]["licenses"] == ["Т-1"] and data["meta"]["counts"]["raw"] == 2
