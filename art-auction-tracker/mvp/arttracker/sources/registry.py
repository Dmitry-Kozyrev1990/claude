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
        min_interval=1.0, note="Художники: имена на разных языках, даты жизни, ID в Getty ULAN."),
    SourcePolicy(
        "artic", "Art Institute of Chicago API", "reference", "approved",
        "данные CC0; изображения public domain — CC0", "https://api.artic.edu/docs/#terms",
        ["api.artic.edu", "www.artic.edu"], min_interval=1.0,
        note="Эталонные карточки работ и изображения для сравнения.",
        extra_headers={"AIC-User-Agent": "LotlineBot (research prototype)"}),
    SourcePolicy(
        "met", "The Met Collection API", "reference", "approved", "Open Access CC0 (для public domain)",
        "https://metmuseum.github.io/", ["collectionapi.metmuseum.org"], min_interval=0.5,
        note="Эталонные карточки работ и изображения для сравнения."),
    SourcePolicy(
        "ecb", "ECB Data Portal", "fx", "approved", "повторное использование с указанием источника",
        "https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html",
        ["data-api.ecb.europa.eu"], min_interval=1.0, note="Ежедневные курсы валют к евро."),
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


def get(source_id: str) -> SourcePolicy:
    for p in approved_auction_sources():
        if p.id == source_id:
            return p
    return REGISTRY[source_id]
