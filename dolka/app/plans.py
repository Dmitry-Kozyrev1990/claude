"""Тарифы — единственный источник цен и лимитов для сервера и интерфейса."""
from __future__ import annotations

PLANS = {
    "free": {"name": "Бесплатный", "durations": []},
    # 500 ₽/мес — цена, которую организаторы назвали приемлемой (research/food-bulk-app-market-research.md).
    "pro": {"name": "Про", "durations": [
        # stars — цена в мини-приложении Telegram: цифровые товары там продаются только за Telegram Stars.
        # 300 ⭐ — около 500 ₽ по цене покупки звёзд; разработчик получает меньше (комиссия Telegram).
        {"id": "1m", "label": "1 месяц", "price_rub": 500, "stars": 300, "days": 30},
        {"id": "12m", "label": "12 месяцев", "price_rub": 5000, "stars": 3000, "days": 365},
    ]},
}
# Бесплатно: одна незакрытая закупка и до 15 участников в ней — хватает, чтобы попробовать на своём чате.
FREE_LIMITS = {"active_purchases": 1, "orders_per_purchase": 15}
TRIAL_DAYS = 14


def duration(plan: str, duration_id: str) -> dict | None:
    return next((d for d in PLANS.get(plan, {}).get("durations", []) if d["id"] == duration_id), None)


def public_plans() -> dict:
    return {k: {"name": v["name"], "durations": v["durations"]} for k, v in PLANS.items()}
