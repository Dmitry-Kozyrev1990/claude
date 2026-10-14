"""Личный кабинет: аналитика коллекции пользователя.

Для каждой работы: стоимость сейчас (справедливая цена по аналогам), доходность с покупки,
годовая доходность против индекса художника, ликвидность, страховая стоимость и сигналы
(«индекс у максимума», «похожая работа на ближайших торгах»). Для портфеля: стоимость,
вложено, прибыль, структура по рынкам и сегментам, динамика стоимости по годам.

compute() работает с готовыми данными конвейера (data.json), поэтому сервер считает
коллекцию любого пользователя без повторного прогона конвейера.
"""
from __future__ import annotations

from datetime import date

# (художник, подсказка в названии, вариант) — пример коллекции на двух рынках.
EXAMPLE = [
    ("warhol", "Flowers", None), ("banksy", "Girl", "signed"), ("rembrandt", "Hundred Guilder", None),
    ("aivazovsky", None, None), ("zverev", None, None), ("deineka", None, None),
]


def _index_at(index: dict, year: int) -> float | None:
    if not index:
        return None
    keyed = {int(k): v["value"] for k, v in index.items()}
    if year in keyed:
        return keyed[year]
    return keyed[min(keyed, key=lambda y: abs(y - year))]


def _cagr(v0, v1, years):
    if not v0 or not v1 or years <= 0:
        return None
    return (v1 / v0) ** (1 / years) - 1


def example_specs(variants: dict, lots: list[dict]) -> list[dict]:
    """Пример коллекции: «покупка» — реальная для конвейера продажа экземпляра в 2016–2019."""
    by_var = {}
    for l in lots:
        if l["s"] == "sold" and l["tu"] and not l["q"] and 2016 <= int(l["d"][:4]) <= 2019:
            by_var.setdefault(l["v"], []).append(l)
    sold_count = {}
    for l in lots:
        if l["s"] == "sold":
            sold_count[l["v"]] = sold_count.get(l["v"], 0) + 1
    specs = []
    for artist, hint, key in EXAMPLE:
        cands = [vid for vid, v in variants.items() if v["artist"] == artist and vid in by_var
                 and (hint is None or hint.lower() in v["title"].lower())
                 and (key is None or v.get("variant") == key)]
        if not cands:
            continue
        vid = max(cands, key=lambda c: (sold_count.get(c, 0), c))
        buy = min(by_var[vid], key=lambda l: l["d"])
        specs.append({"variant": vid, "bought_on": buy["d"], "bought_usd": buy["tu"], "lot": buy["id"]})
    return specs


def compute(data: dict, specs: list[dict], today: date | None = None) -> dict:
    today = today or date.fromisoformat(data["meta"]["today"])
    variants, artists = data["variants"], data["artists"]
    lots = {l["id"]: l for l in data["lots"]}
    upcoming = [lots[u["lot"]] for u in data["upcoming"] if u["lot"] in lots]
    items = []
    for sp in specs:
        v = variants.get(sp["variant"])
        if not v:
            continue
        a = artists.get(v["artist"]) or {}
        val = v.get("valuation") or {}
        idx = a.get("index") or {}
        bought_on = date.fromisoformat(sp["bought_on"])
        years = max(0.1, (today - bought_on).days / 365.25)
        idx_then, idx_now = _index_at(idx, bought_on.year), _index_at(idx, today.year)
        p50 = val.get("p50")
        # Нет аналогов — оцениваем по индексу художника от цены покупки.
        if not p50 and idx_then and idx_now:
            p50 = round(sp["bought_usd"] * idx_now / idx_then, -2)
            val = {"p10": round(p50 * 0.75, -2), "p50": p50, "p90": round(p50 * 1.3, -2), "n": 0}
        if not p50:
            p50 = sp["bought_usd"]
            val = {"p10": p50, "p50": p50, "p90": p50, "n": 0}
        same = [l for l in upcoming if l["v"] == sp["variant"] and not l["q"]]
        similar = [l for l in upcoming if l["a"] == v["artist"] and not l["q"]]
        signals = []
        if idx and idx_now and idx_now >= max(x["value"] for x in idx.values()) * 0.97:
            signals.append({"kind": "peak", "text": "Индекс художника у исторического максимума"})
        if same:
            signals.append({"kind": "same", "text": "Такая же работа выставлена на ближайших торгах"})
        elif similar:
            signals.append({"kind": "similar", "text": f"Работы художника на ближайших торгах: {len(similar)}"})
        liq = (a.get("liquidity") or {}).get("score")
        if liq is not None and liq < 65:
            signals.append({"kind": "illiquid", "text": "Низкая ликвидность: продажа может занять больше года"})
        span = max(1, today.year - bought_on.year)
        drift = p50 / (sp["bought_usd"] * idx_now / idx_then) if idx_then and idx_now else 1.0
        timeline = {y: round(sp["bought_usd"] * ((_index_at(idx, y) / idx_then) if idx_then else 1)
                             * drift ** ((y - bought_on.year) / span))
                    for y in range(bought_on.year, today.year + 1)}
        work_cagr, index_cagr = _cagr(sp["bought_usd"], p50, years), _cagr(idx_then, idx_now, years)
        items.append({
            "id": sp.get("id"), "variant": sp["variant"], "artist": v["artist"], "market": a.get("market"),
            "segment": a.get("segment"), "bought_on": sp["bought_on"], "bought_usd": sp["bought_usd"],
            "note": sp.get("note"), "value": {"p10": val["p10"], "p50": p50, "p90": val["p90"]},
            "comps": val.get("n", 0), "gain": round(p50 / sp["bought_usd"] - 1, 4), "years": round(years, 1),
            "cagr": round(work_cagr, 4) if work_cagr is not None else None,
            "index_cagr": round(index_cagr, 4) if index_cagr is not None else None,
            "liquidity": liq, "insurance": val["p90"], "timeline": timeline, "signals": signals,
        })
    invested = sum(i["bought_usd"] for i in items)
    value = sum(i["value"]["p50"] for i in items)
    first = min((int(i["bought_on"][:4]) for i in items), default=today.year)
    timeline = [{"year": y, "value": sum(i["timeline"].get(y, 0) for i in items),
                 "invested": sum(i["bought_usd"] for i in items if int(i["bought_on"][:4]) <= y)}
                for y in range(first, today.year + 1)]

    def by(k):
        out = {}
        for i in items:
            out[i[k] or "—"] = out.get(i[k] or "—", 0) + i["value"]["p50"]
        return out
    liq_items = [i for i in items if i["liquidity"] is not None]
    liq_value = sum(i["value"]["p50"] for i in liq_items)
    return {
        "items": items, "invested": invested, "value": value,
        "value_lo": sum(i["value"]["p10"] for i in items), "value_hi": sum(i["value"]["p90"] for i in items),
        "gain": round(value / invested - 1, 4) if invested else None,
        "insurance": sum(i["insurance"] for i in items),
        "liquidity": round(sum(i["liquidity"] * i["value"]["p50"] for i in liq_items) / liq_value) if liq_value else None,
        "by_market": by("market"), "by_segment": by("segment"), "timeline": timeline,
        "signals": sum(len(i["signals"]) for i in items),
    }
