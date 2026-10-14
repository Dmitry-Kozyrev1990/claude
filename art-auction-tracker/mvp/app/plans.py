"""Тарифы — единственный источник цен для сервера и интерфейса."""
from __future__ import annotations

PLANS = {
    "free": {"name": "Обзор", "rank": 0, "durations": []},
    # «Коллекционер»: безлимитный доступ вдвое дешевле конкурента (docs/MONETIZATION.md).
    "collector": {"name": "Коллекционер", "rank": 1, "durations": [
        {"id": "1d", "label": "1 день", "price_rub": 890, "days": 1, "months": 1 / 30},
        {"id": "1m", "label": "1 месяц", "price_rub": 3690, "days": 30, "months": 1},
        {"id": "6m", "label": "6 месяцев", "price_rub": 8490, "days": 182, "months": 6},
        {"id": "12m", "label": "12 месяцев", "price_rub": 11450, "days": 365, "months": 12},
    ]},
    "pro": {"name": "Профи", "rank": 2, "durations": [
        {"id": "1m", "label": "1 месяц", "price_rub": 7490, "days": 30, "months": 1},
        {"id": "12m", "label": "12 месяцев", "price_rub": 49900, "days": 365, "months": 12},
    ]},
}
FREE_LIMITS = {"collection": 3, "watch_artists": 3, "watch_works": 3}


def duration(plan: str, duration_id: str) -> dict | None:
    return next((d for d in PLANS.get(plan, {}).get("durations", []) if d["id"] == duration_id), None)


def public_plans() -> dict:
    return {k: {"name": v["name"], "rank": v["rank"],
                "durations": [[d["label"], d["price_rub"], d["months"], d["id"]] for d in v["durations"]]}
            for k, v in PLANS.items()}
