"""Подписки и платежи.

Платёжный провайдер подключается через интерфейс Provider:
- DemoProvider — тестовая активация без списания денег (для показа инвестору);
- YooKassaProvider — место для ЮKassa: создание платежа и обработка уведомления (webhook).
Остальная логика (продление подписки, история платежей) от провайдера не зависит.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import db
from .config import PAYMENTS
from .plans import PLANS, duration


class BillingError(Exception):
    pass


def active_subscription(user_id: int):
    return db.one("""SELECT * FROM subscriptions WHERE user_id = ? AND starts_at <= ? AND ends_at > ?
                     ORDER BY CASE plan WHEN 'pro' THEN 2 WHEN 'collector' THEN 1 ELSE 0 END DESC, ends_at DESC
                     LIMIT 1""", user_id, db.now(), db.now())


def current_plan(user) -> str:
    if not user:
        return "free"
    sub = active_subscription(user["id"])
    return sub["plan"] if sub else "free"


def grant(user_id: int, plan: str, days: int, source: str, payment_id: int | None = None):
    """Продлевает подписку: новый период начинается после окончания текущей того же тарифа."""
    if plan not in PLANS or plan == "free":
        raise BillingError("Неизвестный тариф")
    last = db.one("SELECT MAX(ends_at) AS e FROM subscriptions WHERE user_id = ? AND plan = ?", user_id, plan)
    start = max(db.now(), last["e"] or "")
    start_dt = datetime.fromisoformat(start)
    end = (start_dt + timedelta(days=days)).isoformat(timespec="seconds")
    with db.tx() as c:
        c.execute("INSERT INTO subscriptions (user_id, plan, starts_at, ends_at, source, payment_id) "
                  "VALUES (?, ?, ?, ?, ?, ?)", (user_id, plan, start, end, source, payment_id))
    return end


class Provider:
    name = "base"

    def start(self, payment_id: int, amount_rub: int, description: str) -> dict:
        raise NotImplementedError


class DemoProvider(Provider):
    """Без денег: платёж сразу считается успешным. Включается LOTLINE_PAYMENTS=demo."""
    name = "demo"

    def start(self, payment_id, amount_rub, description):
        return {"status": "succeeded"}


class YooKassaProvider(Provider):
    """ЮKassa: платёж создаётся через API, пользователь уходит на страницу оплаты,
    подписка включается по уведомлению payment.succeeded (handle_webhook)."""
    name = "yookassa"

    def start(self, payment_id, amount_rub, description):
        raise BillingError("Оплата картой через ЮKassa подключается. Пока доступна тестовая активация.")


def provider() -> Provider | None:
    return {"demo": DemoProvider(), "yookassa": YooKassaProvider()}.get(PAYMENTS)


def checkout(user, plan: str, duration_id: str) -> dict:
    d = duration(plan, duration_id)
    if not d:
        raise BillingError("Выберите тариф и срок.")
    prov = provider()
    if not prov:
        raise BillingError("Оплата временно недоступна.")
    with db.tx() as c:
        pid = c.execute("INSERT INTO payments (user_id, plan, duration, amount_rub, status, provider, created_at) "
                        "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                        (user["id"], plan, duration_id, d["price_rub"], prov.name, db.now())).lastrowid
    res = prov.start(pid, d["price_rub"], f"Lotline, тариф «{PLANS[plan]['name']}», {d['label']}")
    if res.get("status") == "succeeded":
        return {"status": "succeeded", "ends_at": mark_paid(pid)}
    if res.get("confirmation_url"):
        return {"status": "redirect", "url": res["confirmation_url"]}
    return {"status": "pending"}


def mark_paid(payment_id: int, provider_id: str | None = None) -> str:
    p = db.one("SELECT * FROM payments WHERE id = ?", payment_id)
    if not p:
        raise BillingError("Платёж не найден")
    if p["status"] == "succeeded":
        sub = db.one("SELECT ends_at FROM subscriptions WHERE payment_id = ?", payment_id)
        return sub["ends_at"] if sub else ""
    with db.tx() as c:
        c.execute("UPDATE payments SET status = 'succeeded', paid_at = ?, provider_id = COALESCE(?, provider_id) "
                  "WHERE id = ?", (db.now(), provider_id, payment_id))
    return grant(p["user_id"], p["plan"], duration(p["plan"], p["duration"])["days"], p["provider"], payment_id)


def history(user_id: int) -> list[dict]:
    return [dict(r) for r in db.all_("SELECT id, plan, duration, amount_rub, status, provider, created_at, paid_at "
                                     "FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT 50", user_id)]


def utcnow():
    return datetime.now(timezone.utc)
