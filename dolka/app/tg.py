"""Telegram: проверка initData мини-приложения, вызовы Bot API, обработка вебхука,
уведомления организатору и участникам, оплата подписки звёздами (Telegram Stars).

Мини-приложение открывается по ссылке https://t.me/<бот>?startapp=<код закупки> (главное
мини-приложение бота, включается в @BotFather) или кнопкой «Открыть» в чате с ботом.
Сервер узнаёт пользователя по подписанной строке initData — ей нельзя доверять без проверки
подписи токеном бота (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qsl, quote

from . import db
from .config import PUBLIC_URL, TG_BOT_TOKEN, TG_BOT_USERNAME

log = logging.getLogger("dolka.tg")
INIT_DATA_MAX_AGE = 24 * 3600


class TgError(Exception):
    pass


def enabled() -> bool:
    return bool(TG_BOT_TOKEN)


# ---------- initData ----------

def validate_init_data(init_data: str, token: str | None = None, max_age: int = INIT_DATA_MAX_AGE,
                       now: float | None = None) -> dict:
    """Проверяет подпись initData и возвращает {"user": {...}, "start_param": ...}."""
    token = token if token is not None else TG_BOT_TOKEN
    if not token:
        raise TgError("Мини-приложение Telegram не настроено.")
    if not init_data:
        raise TgError("Откройте приложение из Telegram.")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received = pairs.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(expected, received):
        raise TgError("Подпись Telegram не прошла проверку. Перезапустите приложение.")
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    if (now or time.time()) - auth_date > max_age:
        raise TgError("Сессия Telegram устарела. Закройте и снова откройте приложение.")
    try:
        user = json.loads(pairs.get("user") or "null")
    except ValueError:
        user = None
    if not user or not isinstance(user.get("id"), int):
        raise TgError("Telegram не передал пользователя.")
    return {"user": user, "start_param": pairs.get("start_param") or ""}


def display_name(user: dict) -> str:
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x).strip()
    if user.get("username"):
        name = f"{name} (@{user['username']})" if name else "@" + user["username"]
    return name[:80] or f"id{user['id']}"


# ---------- организатор ----------

def organizer_for(tg_user: dict) -> tuple[int, bool]:
    """Находит или создаёт аккаунт организатора по Telegram id. Возвращает (user_id, создан_ли)."""
    row = db.one("SELECT id FROM users WHERE tg_id = ?", tg_user["id"])
    if row:
        return row["id"], False
    with db.tx() as c:
        # Почта-заглушка не проходит проверку формата, поэтому войти по паролю в такой аккаунт нельзя.
        uid = c.execute("INSERT INTO users (email, name, pw_hash, tg_id, created_at) VALUES (?, ?, '!', ?, ?)",
                        (f"tg:{tg_user['id']}", display_name(tg_user), tg_user["id"], db.now())).lastrowid
    return uid, True


# ---------- ссылки ----------

def start_link(slug: str) -> str | None:
    """Ссылка на закупку, которая открывает мини-приложение прямо в Telegram."""
    return f"https://t.me/{TG_BOT_USERNAME}?startapp={slug}" if TG_BOT_USERNAME else None


def webapp_url(slug: str | None = None) -> str:
    return f"{PUBLIC_URL}/tg" + (f"?z={quote(slug)}" if slug else "")


# ---------- Bot API ----------

def call(method: str, **params) -> dict:
    if not TG_BOT_TOKEN:
        raise TgError("TG_BOT_TOKEN не задан")
    req = urllib.request.Request(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/{method}",
                                 data=json.dumps(params).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        data = json.loads(e.read() or b"{}")
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise TgError(f"Telegram недоступен: {e}")
    if not data.get("ok"):
        raise TgError(data.get("description") or "Ошибка Telegram")
    return data.get("result")


def open_button(text: str, slug: str | None = None) -> dict:
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": webapp_url(slug)}}]]}


def send(chat_id: int | None, text: str, slug: str | None = None, button: str = "Открыть закупку"):
    """Отправка без гарантий: пользователь мог не разрешить боту писать или заблокировать его."""
    if not chat_id or not enabled():
        return
    try:
        call("sendMessage", chat_id=chat_id, text=text, reply_markup=open_button(button, slug),
             link_preview_options={"is_disabled": True})
    except TgError as e:
        log.info("sendMessage %s: %s", chat_id, e)


# ---------- уведомления ----------

def notify_new_order(p, order_name: str, total_kop: int, updated: bool):
    from .purchases import fmt_rub
    owner = db.one("SELECT tg_id FROM users WHERE id = ?", p["user_id"])
    verb = "изменил(а) заказ" if updated else "заказал(а)"
    send(owner and owner["tg_id"], f"🛒 «{p['title']}»: {order_name} {verb} на {fmt_rub(total_kop)}.", p["slug"])


def notify_says_paid(p, order_name: str, balance_kop: int):
    from .purchases import fmt_rub
    owner = db.one("SELECT tg_id FROM users WHERE id = ?", p["user_id"])
    send(owner and owner["tg_id"], f"💳 «{p['title']}»: {order_name} сообщает об оплате {fmt_rub(balance_kop)}. "
                                   "Проверьте поступление и отметьте в списке участников.", p["slug"])


def notify_status(pid: int, status: str):
    """Сбор закрыт — просим оплатить; приехало — зовём на раздачу и показываем итог по факту."""
    from .purchases import fmt_rub, owner_view
    p = db.one("SELECT * FROM purchases WHERE id = ?", pid)
    if not p or status not in ("stopped", "arrived"):
        return
    tg_ids = {r["id"]: r["tg_id"] for r in db.all_("SELECT id, tg_id FROM orders WHERE purchase_id = ? AND tg_id IS NOT NULL", pid)}
    if not tg_ids:
        return
    for o in owner_view(p)["orders"]:
        chat = tg_ids.get(o["id"])
        if not chat:
            continue
        if status == "stopped":
            if o["balance_kop"] <= 0:
                continue
            text = f"⏹ Сбор в «{p['title']}» закрыт. К оплате: {fmt_rub(o['balance_kop'])}."
            if p["pay_info"]:
                text += f"\nКак оплатить: {p['pay_info']}"
        else:
            text = f"✅ «{p['title']}» приехала!"
            if p["pickup"]:
                text += f"\nРаздача: {p['pickup']}"
            text += f"\nИтого по факту: {fmt_rub(o['total_kop'])}"
            if o["balance_kop"] > 0:
                text += f", доплатить {fmt_rub(o['balance_kop'])}."
            elif o["balance_kop"] < 0:
                text += f", переплата {fmt_rub(-o['balance_kop'])} — организатор вернёт."
            else:
                text += ", всё оплачено."
        send(chat, text, p["slug"])


def notify_trimmed(p, item_name: str, unit: str, removed: list[dict]):
    rows = {r["id"]: r["tg_id"] for r in db.all_("SELECT id, tg_id FROM orders WHERE purchase_id = ? AND tg_id IS NOT NULL", p["id"])}
    for r in removed:
        send(rows.get(r["order_id"]), f"📦 В «{p['title']}» коробка «{item_name}» не собралась — "
                                     f"из вашего заказа снято {r['removed']} {unit}.", p["slug"])


# ---------- оплата звёздами ----------

def create_stars_invoice(payment_id: int, title: str, description: str, stars: int) -> str:
    return call("createInvoiceLink", title=title[:32], description=description[:255], payload=f"pay:{payment_id}",
                currency="XTR", prices=[{"label": title[:32], "amount": stars}])


def _payment_id(payload: str) -> int | None:
    if not payload.startswith("pay:"):
        return None
    try:
        return int(payload[4:])
    except ValueError:
        return None


# ---------- вебхук ----------

WELCOME = ("Привет! Это «Долька» — сервис для совместных закупок продуктов.\n\n"
           "Организатор создаёт закупку и кидает ссылку в чат, участники заказывают в пару нажатий, "
           "а сервис считает коробки, оплаты, вес по факту и раздачу.")


def handle_update(update: dict):
    from . import billing
    if "pre_checkout_query" in update:
        q = update["pre_checkout_query"]
        pid = _payment_id(q.get("invoice_payload", ""))
        pay = db.one("SELECT * FROM payments WHERE id = ?", pid) if pid else None
        ok = bool(pay and pay["status"] == "pending" and q.get("currency") == "XTR")
        params = {"pre_checkout_query_id": q["id"], "ok": ok}
        if not ok:
            params["error_message"] = "Счёт устарел. Откройте тарифы в приложении и попробуйте ещё раз."
        call("answerPreCheckoutQuery", **params)
        return
    msg = update.get("message") or {}
    if "successful_payment" in msg:
        sp = msg["successful_payment"]
        pid = _payment_id(sp.get("invoice_payload", ""))
        if pid:
            ends = billing.mark_paid(pid, sp.get("telegram_payment_charge_id"))
            send(msg["chat"]["id"], f"Спасибо! Тариф «Про» действует до {ends[:10]}.", button="Открыть «Дольку»")
        return
    text = (msg.get("text") or "").strip()
    if msg.get("chat", {}).get("type") != "private" or not text.startswith("/"):
        return
    cmd, _, arg = text.partition(" ")
    if cmd.split("@")[0] == "/start" and arg:
        p = db.one("SELECT slug, title FROM purchases WHERE slug = ?", arg.strip())
        if p:
            send(msg["chat"]["id"], f"Закупка «{p['title']}». Нажмите кнопку, чтобы выбрать товары.",
                 p["slug"], button="Выбрать товары")
            return
    send(msg["chat"]["id"], WELCOME, button="Открыть «Дольку»")
