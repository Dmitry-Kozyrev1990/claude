"""Подписка организатора: пробный период, оплата тарифа «Про», лимиты бесплатного тарифа.

Платёжный провайдер подключается через интерфейс Provider:
- DemoProvider — тестовая активация без списания денег;
- YooKassaProvider — место для ЮKassa (создание платежа и webhook payment.succeeded);
- StarsProvider — Telegram Stars внутри мини-приложения (по правилам Telegram цифровые товары
  в мини-приложениях продаются только за звёзды); подписка включается по successful_payment в app/tg.py.
Деньги участников закупок через сервис не проходят: они платят организатору напрямую.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import db
from .config import PAYMENTS
from .plans import FREE_LIMITS, PLANS, TRIAL_DAYS, duration


class BillingError(Exception):
    pass


def active_subscription(user_id: int):
    return db.one("SELECT * FROM subscriptions WHERE user_id = ? AND starts_at <= ? AND ends_at > ? "
                  "ORDER BY ends_at DESC LIMIT 1", user_id, db.now(), db.now())


def paid_until(user_id: int) -> tuple[str | None, bool]:
    """До какой даты действует «Про» с учётом оплаченных наперёд периодов и идёт ли сейчас только пробный."""
    rows = db.all_("SELECT source, ends_at FROM subscriptions WHERE user_id = ? AND ends_at > ?", user_id, db.now())
    if not rows:
        return None, False
    return max(r["ends_at"] for r in rows), all(r["source"] == "trial" for r in rows)


def current_plan(user) -> str:
    if not user:
        return "free"
    return "pro" if active_subscription(user["id"]) else "free"


def grant(user_id: int, plan: str, days: int, source: str, payment_id: int | None = None) -> str:
    """Продлевает подписку: новый период начинается после окончания текущего."""
    if plan not in PLANS or plan == "free":
        raise BillingError("Неизвестный тариф")
    last = db.one("SELECT MAX(ends_at) AS e FROM subscriptions WHERE user_id = ?", user_id)
    start = max(db.now(), last["e"] or "")
    end = (datetime.fromisoformat(start) + timedelta(days=days)).isoformat(timespec="seconds")
    with db.tx() as c:
        c.execute("INSERT INTO subscriptions (user_id, plan, starts_at, ends_at, source, payment_id) "
                  "VALUES (?, ?, ?, ?, ?, ?)", (user_id, plan, start, end, source, payment_id))
    return end


def start_trial(user_id: int) -> str:
    return grant(user_id, "pro", TRIAL_DAYS, "trial")


def limits(user) -> dict | None:
    """None — без ограничений (тариф «Про» или пробный период)."""
    return None if current_plan(user) == "pro" else FREE_LIMITS


def check_can_create_purchase(user):
    lim = limits(user)
    if lim is None:
        return
    active = db.one("SELECT COUNT(*) AS n FROM purchases WHERE user_id = ? AND status != 'closed'", user["id"])["n"]
    if active >= lim["active_purchases"]:
        raise BillingError(f"На бесплатном тарифе — {lim['active_purchases']} незакрытая закупка. "
                           "Закройте текущую или подключите «Про» за 500 ₽ в месяц.")


def check_can_add_order(owner, purchase_id: int):
    lim = limits(owner)
    if lim is None:
        return
    n = db.one("SELECT COUNT(*) AS n FROM orders WHERE purchase_id = ?", purchase_id)["n"]
    if n >= lim["orders_per_purchase"]:
        raise BillingError("В закупке закончились места. Напишите организатору.")


class Provider:
    name = "base"

    def start(self, payment_id: int, amount_rub: int, description: str) -> dict:
        raise NotImplementedError


class DemoProvider(Provider):
    """Без денег: платёж сразу считается успешным. Включается DOLKA_PAYMENTS=demo."""
    name = "demo"

    def start(self, payment_id, amount_rub, description):
        return {"status": "succeeded"}


class YooKassaProvider(Provider):
    """ЮKassa: платёж создаётся через API, пользователь уходит на страницу оплаты,
    подписка включается по уведомлению payment.succeeded."""
    name = "yookassa"

    def start(self, payment_id, amount_rub, description):
        raise BillingError("Оплата картой через ЮKassa подключается. Пока доступна тестовая активация.")


class StarsProvider(Provider):
    name = "stars"

    def __init__(self, stars: int):
        self.stars = stars

    def start(self, payment_id, amount_rub, description):
        from . import tg
        try:
            return {"invoice_url": tg.create_stars_invoice(payment_id, "Долька Про", description, self.stars)}
        except tg.TgError as e:
            raise BillingError(f"Не удалось выставить счёт в Telegram: {e}")


def provider(channel: str = "web", d: dict | None = None) -> Provider | None:
    if channel == "tg":
        from . import tg
        # В тестовом режиме (demo) звёзды не списываются — так же, как в веб-версии.
        if PAYMENTS == "demo":
            return DemoProvider()
        return StarsProvider(d["stars"]) if tg.enabled() and d and d.get("stars") else None
    return {"demo": DemoProvider(), "yookassa": YooKassaProvider()}.get(PAYMENTS)


def checkout(user, plan: str, duration_id: str, channel: str = "web") -> dict:
    d = duration(plan, duration_id)
    if not d:
        raise BillingError("Выберите тариф и срок.")
    prov = provider(channel, d)
    if not prov:
        raise BillingError("Оплата временно недоступна.")
    with db.tx() as c:
        pid = c.execute("INSERT INTO payments (user_id, plan, duration, amount_rub, status, provider, created_at) "
                        "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                        (user["id"], plan, duration_id, d["price_rub"], prov.name, db.now())).lastrowid
    res = prov.start(pid, d["price_rub"], f"Долька, тариф «{PLANS[plan]['name']}», {d['label']}")
    if res.get("status") == "succeeded":
        return {"status": "succeeded", "ends_at": mark_paid(pid)}
    if res.get("confirmation_url"):
        return {"status": "redirect", "url": res["confirmation_url"]}
    if res.get("invoice_url"):
        return {"status": "invoice", "url": res["invoice_url"]}
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
