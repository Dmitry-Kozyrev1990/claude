"""Личный кабинет: аналитика коллекции пользователя.

Для каждой работы: стоимость сейчас (справедливая цена по аналогам), доходность с покупки,
годовая доходность против индекса художника, ликвидность, страховая стоимость и сигналы
(«индекс у максимума», «похожая работа на ближайших торгах»). Для портфеля: стоимость,
вложено, прибыль, структура по рынкам и сегментам, динамика стоимости по годам.

В демо пример коллекции собран из реальных для конвейера лотов: «покупка» — продажа
этого экземпляра в 2016–2019 годах.
"""
from __future__ import annotations

from datetime import date

from .analytics import cagr, index_at
from .catalog import ARTISTS

# (художник, подсказка в названии, вариант) — пример коллекции на двух рынках.
EXAMPLE = [
    ("warhol", "Flowers", None), ("banksy", "Girl", "signed"), ("rembrandt", "Hundred Guilder", None),
    ("aivazovsky", None, None), ("zverev", None, None), ("deineka", None, None),
]


def _pick_variant(variants, lots_by_variant, artist, hint, key):
    cands = [vid for vid, v in variants.items() if v["artist"] == artist
             and (hint is None or hint.lower() in v["title"].lower())
             and (key is None or v.get("variant") == key)]

    def purchases(vid):
        return [l for l in lots_by_variant[vid] if l.status == "sold" and 2016 <= l.year <= 2019 and l.total_usd]
    cands = [c for c in cands if purchases(c)]
    if not cands:
        return None, None
    best = max(cands, key=lambda vid: (len([l for l in lots_by_variant[vid] if l.status == "sold"]),
                                       -min(l.year for l in purchases(vid))))
    return best, min(purchases(best), key=lambda l: l.sale_date)


def _timeline(buy, idx, idx_then, idx_now, p50, now_year) -> dict:
    """Стоимость по годам: путь индекса художника, плавно приведённый к текущей оценке по
    аналогам (в год покупки — цена покупки, сейчас — справедливая цена)."""
    span = max(1, now_year - buy.year)
    drift = p50 / (buy.total_usd * idx_now / idx_then)
    return {y: round(buy.total_usd * index_at(idx, y) / idx_then * drift ** ((y - buy.year) / span))
            for y in range(buy.year, now_year + 1)}


def build_portfolio(variants, lots_by_variant, artists_out, upcoming, match, today: date) -> dict:
    items = []
    for artist, hint, key in EXAMPLE:
        vid, buy = _pick_variant(variants, lots_by_variant, artist, hint, key)
        if not vid:
            continue
        v, a = variants[vid], artists_out[artist]
        val = v.get("valuation") or {}
        idx = a["index"]
        if not val.get("p50") or not idx:
            continue
        years = (today - date.fromisoformat(buy.sale_date)).days / 365.25
        idx_then, idx_now = index_at(idx, buy.year), index_at(idx, today.year)
        work_cagr = cagr(buy.total_usd, val["p50"], years)
        index_cagr = cagr(idx_then, idx_now, years)
        similar = [l for l in upcoming if not l.qualifier and match.variant_of[l.lot_id] == vid
                   or (l.artist_id == artist and not l.qualifier)]
        signals = []
        peak = max(p["value"] for p in idx.values())
        if idx_now >= peak * 0.97:
            signals.append({"kind": "peak", "text": "Индекс художника у исторического максимума"})
        if any(match.variant_of[l.lot_id] == vid for l in similar):
            signals.append({"kind": "same", "text": "Такая же работа выставлена на ближайших торгах"})
        elif similar:
            signals.append({"kind": "similar", "text": f"Работы художника на ближайших торгах: {len(similar)}"})
        if a["liquidity"]["score"] < 65:
            signals.append({"kind": "illiquid", "text": "Низкая ликвидность: продажа может занять больше года"})
        items.append({
            "variant": vid, "artist": artist, "market": ARTISTS[artist]["market"],
            "segment": ARTISTS[artist]["segment"], "bought_lot": buy.lot_id, "bought_on": buy.sale_date,
            "bought_usd": buy.total_usd, "value": {"p10": val["p10"], "p50": val["p50"], "p90": val["p90"]},
            "gain": round(val["p50"] / buy.total_usd - 1, 4), "years": round(years, 1),
            "cagr": round(work_cagr, 4) if work_cagr is not None else None,
            "index_cagr": round(index_cagr, 4) if index_cagr is not None else None,
            "liquidity": a["liquidity"]["score"], "insurance": val["p90"],
            "timeline": _timeline(buy, idx, idx_then, idx_now, val["p50"], today.year),
            "signals": signals,
        })
    invested = sum(i["bought_usd"] for i in items)
    value = sum(i["value"]["p50"] for i in items)
    years = range(min((int(i["bought_on"][:4]) for i in items), default=today.year), today.year + 1)
    timeline = [{"year": y,
                 "value": sum(i["timeline"].get(y, 0) for i in items),
                 "invested": sum(i["bought_usd"] for i in items if int(i["bought_on"][:4]) <= y)} for y in years]
    by = lambda k: {g: sum(i["value"]["p50"] for i in items if i[k] == g) for g in {i[k] for i in items}}  # noqa: E731
    liq = sum(i["liquidity"] * i["value"]["p50"] for i in items) / value if value else None
    return {
        "items": items, "invested": invested, "value": value,
        "value_lo": sum(i["value"]["p10"] for i in items), "value_hi": sum(i["value"]["p90"] for i in items),
        "gain": round(value / invested - 1, 4) if invested else None,
        "insurance": sum(i["insurance"] for i in items),
        "liquidity": round(liq) if liq else None,
        "by_market": by("market"), "by_segment": by("segment"),
        "timeline": timeline,
        "signals": sum(len(i["signals"]) for i in items),
    }
