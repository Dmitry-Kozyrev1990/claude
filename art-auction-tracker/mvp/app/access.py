"""Что видит каждый тариф. Закрытые данные вырезаются на сервере и не попадают в браузер."""
from __future__ import annotations

import copy
import json
from datetime import date

from arttracker.portfolio import compute

from .plans import FREE_LIMITS, PLANS


def is_paid(plan: str) -> bool:
    return PLANS[plan]["rank"] >= PLANS["collector"]["rank"]


def free_view(data: dict) -> dict:
    """Версия данных для бесплатного тарифа «Обзор»."""
    d = copy.deepcopy(data)
    today = date.fromisoformat(d["meta"]["today"])
    recent = date(today.year - 1, today.month, today.day).isoformat()
    for l in d["lots"]:  # цены продаж последних 12 месяцев
        if l["d"] >= recent:
            l["tu"] = l["hu"] = l["pr"] = None
    for a in d["artists"].values():  # ликвидность, точность эстимейтов, доходность перепродаж
        a["liquidity"] = a["bias"] = a["repeat"] = None
    for v in d["variants"].values():  # справедливая цена и аналоги
        v["valuation"] = {"n": (v.get("valuation") or {}).get("n", 0)}
    d["repeat_pairs"] = []
    for u in d["upcoming"]:
        u["signal"] = None
    for n in d["alerts"]["notifications"]:
        n["signal"] = None
        n["fair"] = ""
    d["portfolio"] = free_portfolio(d["portfolio"])
    return d


def free_portfolio(p: dict) -> dict:
    items = p["items"][:FREE_LIMITS["collection"]]
    keep = {"id", "variant", "artist", "market", "segment", "bought_on", "bought_usd", "note", "value"}
    items = [{k: v for k, v in i.items() if k in keep} for i in items]
    return {"items": items, "invested": sum(i["bought_usd"] for i in items),
            "value": sum(i["value"]["p50"] for i in items),
            "value_lo": sum(i["value"]["p10"] for i in items),
            "value_hi": sum(i["value"]["p90"] for i in items),
            "limited": True, "total_items": len(p["items"])}


class DataViews:
    """Готовые JSON-версии данных по тарифам: считаются один раз при старте."""

    def __init__(self, data: dict):
        self.data = data
        self.json = {"paid": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                     "free": json.dumps(free_view(data), ensure_ascii=False, separators=(",", ":"))}

    def for_plan(self, plan: str) -> str:
        return self.json["paid" if is_paid(plan) else "free"]

    def portfolio(self, specs: list[dict], plan: str) -> dict:
        p = compute(self.data, specs)
        return p if is_paid(plan) else free_portfolio(p)
