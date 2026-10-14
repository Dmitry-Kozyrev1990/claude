"""Реестр источников данных и их юридический статус.

approved        — открытая лицензия или явное разрешение; сборщик работает.
pending_review  — нужно прочитать условия использования (и при необходимости получить
                  письменное разрешение), прежде чем включать.
blocked         — не подключаем.

Аукционные сайты включаются по одному после проверки условий: домен добавляется в
config/approved_auction_sources.json с датой проверки и ссылкой на условия.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import SourcePolicy

CONFIG = Path(__file__).resolve().parents[2] / "config" / "approved_auction_sources.json"

REGISTRY: dict[str, SourcePolicy] = {p.id: p for p in [
    SourcePolicy(
        "wikidata", "Wikidata", "reference", "approved", "CC0 1.0",
        "https://www.wikidata.org/wiki/Wikidata:Licensing", ["query.wikidata.org", "www.wikidata.org"],
        min_interval=1.0, note="Художники: имена на разных языках, даты жизни, ID в Getty ULAN. Правила "
                               "сервиса запросов: https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual", documented_api=True),
    SourcePolicy(
        "artic", "Art Institute of Chicago API", "reference", "approved",
        "данные CC0; изображения public domain — CC0", "https://api.artic.edu/docs/#terms",
        ["api.artic.edu", "www.artic.edu"], min_interval=1.0,
        note="Эталонные карточки работ и изображения для сравнения.",
        extra_headers={"AIC-User-Agent": "LotlineBot (research prototype)"}, documented_api=True),
    SourcePolicy(
        "met", "The Met Collection API", "reference", "approved", "Open Access CC0 (для public domain)",
        "https://metmuseum.github.io/", ["collectionapi.metmuseum.org"], min_interval=0.5,
        note="Эталонные карточки работ и изображения для сравнения.", documented_api=True),
    SourcePolicy(
        "ecb", "ECB Data Portal", "fx", "approved", "повторное использование с указанием источника",
        "https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html",
        ["data-api.ecb.europa.eu"], min_interval=1.0, note="Ежедневные курсы валют к евро.", documented_api=True),
    SourcePolicy(
        "cbr", "Банк России: курсы валют", "fx", "approved", "официальные курсы, указание источника",
        "https://www.cbr.ru/development/sxml/", ["www.cbr.ru", "cbr.ru"], min_interval=1.0, documented_api=True,
        note="Курс рубля: ECB перестал его публиковать в 2022 году."),
    SourcePolicy(
        "artprice", "Artprice", "auction", "blocked", "платная база данных",
        "https://www.artprice.com", ["artprice.com"],
        note="Платная база: автоматическое извлечение не разрешено условиями. Используется только "
             "как образец структуры (docs/REFERENCE_STRUCTURE.md), данные не собираются."),
    *[SourcePolicy(i, n, "auction", "pending_review", "условия сайта не проверены", f"https://www.{d}/", [d],
                   min_interval=5.0, note="Найти и прочитать условия использования сайта; при запрете "
                                          "автоматического сбора — запросить разрешение.")
      for i, n, d in [
          ("christies", "Christie's", "christies.com"), ("sothebys", "Sotheby's", "sothebys.com"),
          ("phillips", "Phillips", "phillips.com"), ("bonhams", "Bonhams", "bonhams.com"),
          ("dorotheum", "Dorotheum", "dorotheum.com"), ("heritage", "Heritage Auctions", "ha.com"),
          ("invaluable", "Invaluable", "invaluable.com"), ("liveauctioneers", "LiveAuctioneers", "liveauctioneers.com"),
      ]],
    SourcePolicy(
        "artsy", "Artsy Price Database", "auction", "pending_review", "бесплатный просмотр; права на сбор не проверены",
        "https://www.artsy.net/price-database", ["artsy.net"], min_interval=5.0,
        note="Бесплатный доступ к результатам торгов — для просмотра. Перед сбором прочитать условия "
             "использования и запросить у Artsy доступ к данным для коммерческого использования."),
    SourcePolicy(
        "mutualart", "MutualArt Price Database", "auction", "pending_review",
        "бесплатный поиск, расширенные данные по премиум-подписке", "https://www.mutualart.com/price-database",
        ["mutualart.com"], min_interval=5.0,
        note="Прямой конкурент по функции Watchlist. Используется как образец структуры; данные — только "
             "после письменного разрешения или лицензии."),
    # Российский рынок: дома и агрегаторы. Лучший путь — партнёрство и архив по договору
    # (python -m arttracker.collect import-archive), а не сбор со страниц.
    # Адреса сайтов не заполнены намеренно: их нужно сверить при проверке условий.
    *[SourcePolicy(i, n, "auction", "pending_review", "условия сайта не проверены", "", [],
                   min_interval=5.0, note=f"{what}. Предложить партнёрство: архив результатов по договору "
                                          "(docs/letters/partnership_ru.md). Сайт и условия — уточнить.")
      for i, n, what in [
          ("litfond", "Литфонд", "Русская живопись и графика"),
          ("sovcom", "Совком", "Русское искусство"),
          ("vladey", "Vladey", "Неофициальное и современное искусство"),
          ("gelos", "Гелос", "Живопись и графика"),
          ("imperia", "Империя", "Русская живопись"),
      ]],
    SourcePolicy(
        "artinvestment", "ARTinvestment.RU", "auction", "blocked", "база данных под защитой ГК РФ ст. 1333–1336",
        "https://artinvestment.ru/", ["artinvestment.ru"],
        note="Конкурент. Ценовая база защищена правом изготовителя базы данных: не копируем. "
             "Возможна только лицензия по договору."),
    # Агрегаторы: через каждый доступны сотни и тысячи аукционных домов.
    *[SourcePolicy(i, n, "auction", "pending_review", "условия сайта не проверены", f"https://www.{d}/", [d],
                   min_interval=5.0, note=f"Агрегатор торгов: {what}. Проверить условия; лучше договориться о партнёрстве.")
      for i, n, d, what in [
          ("the-saleroom", "the-saleroom", "the-saleroom.com", "аукционные дома Великобритании и Европы"),
          ("lot-tissimo", "Lot-tissimo", "lot-tissimo.com", "дома Германии и Австрии"),
          ("drouot", "Drouot", "drouot.com", "французские аукционные дома"),
          ("interencheres", "Interencheres", "interencheres.com", "французские аукционные дома"),
          ("catawiki", "Catawiki", "catawiki.com", "онлайн-аукционы по всей Европе"),
          ("bidspirit", "Bidspirit", "bidspirit.com", "дома Израиля, Европы и Азии"),
      ]],
    # Музеи с открытыми данными коллекций (цен нет: эталон работ, изображения, провенанс).
    SourcePolicy(
        "cleveland", "Cleveland Museum of Art Open Access", "reference", "approved", "CC0",
        "https://openaccess-api.clevelandart.org/", ["openaccess-api.clevelandart.org"], min_interval=1.0,
        note="Открытый API коллекции. Адаптер пока не написан.", documented_api=True),
    SourcePolicy(
        "smithsonian", "Smithsonian Open Access", "reference", "approved", "CC0 (для материалов Open Access)",
        "https://www.si.edu/openaccess", ["api.si.edu"], min_interval=1.0,
        note="Нужен бесплатный ключ api.data.gov. Адаптер пока не написан.", documented_api=True),
    SourcePolicy(
        "nga", "National Gallery of Art Open Data", "reference", "approved", "CC0",
        "https://github.com/NationalGalleryOfArt/opendata", ["github.com", "raw.githubusercontent.com"],
        min_interval=1.0, note="Выгрузка коллекции в CSV на GitHub. Адаптер пока не написан."),
    SourcePolicy(
        "moma", "MoMA Collection Data", "reference", "approved", "CC0",
        "https://github.com/MuseumofModernArt/collection", ["github.com", "raw.githubusercontent.com"],
        min_interval=1.0, note="Выгрузка коллекции на GitHub, в том числе печатная графика. Адаптер пока не написан."),
    *[SourcePolicy(i, n, "reference", "pending_review", lic, u, [d], min_interval=1.0,
                   note="Нужен ключ API; проверить условия коммерческого использования. Адаптер пока не написан.")
      for i, n, d, u, lic in [
          ("rijksmuseum", "Rijksmuseum", "rijksmuseum.nl", "https://www.rijksmuseum.nl/", "метаданные открыты, условия API проверить"),
          ("europeana", "Europeana", "api.europeana.eu", "https://pro.europeana.eu/", "метаданные CC0, лицензии изображений разные"),
          ("harvard", "Harvard Art Museums", "api.harvardartmuseums.org", "https://harvardartmuseums.org/collections/api", "условия API проверить"),
          ("vam", "Victoria and Albert Museum", "api.vam.ac.uk", "https://developers.vam.ac.uk/", "условия API проверить"),
      ]],
]}


def approved_auction_sources() -> list[SourcePolicy]:
    """Аукционные сайты, которые прошли проверку условий (ведётся вручную)."""
    if not CONFIG.exists():
        return []
    items = json.loads(CONFIG.read_text(encoding="utf-8"))
    out = []
    for it in items:
        base = REGISTRY.get(it["id"])
        if base and base.status == "blocked":
            continue  # запрет в реестре сильнее конфигурации
        out.append(SourcePolicy(
            it["id"], it["name"], "auction", "approved", it.get("license", "по условиям сайта"),
            it["terms_url"], it["domains"], min_interval=max(5.0, it.get("min_interval", 5.0)),
            note=f"Условия проверены {it['reviewed_on']}: {it.get('review_note', '')}"))
    return out


CANDIDATES = Path(__file__).resolve().parents[2] / "data" / "reference" / "source_candidates.jsonl"


def discovered_candidates() -> list[dict]:
    """Кандидаты, найденные через Wikidata (python -m arttracker.collect discover). Все — pending_review."""
    if not CANDIDATES.exists():
        return []
    return [json.loads(line) for line in CANDIDATES.read_text(encoding="utf-8").splitlines() if line.strip()]


def get(source_id: str) -> SourcePolicy:
    for p in approved_auction_sources():
        if p.id == source_id:
            return p
    return REGISTRY[source_id]
