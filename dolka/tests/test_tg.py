"""Мини-приложение Telegram: подпись initData, вход организатора, заказ участника по аккаунту,
вебхук (оплата звёздами, /start), уведомления, подписанные ссылки на выгрузку."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app import main, tg
from app.main import app

from .conftest import H

TOKEN = "123456:TEST-token"


def sign(user: dict, start_param: str = "", token: str = TOKEN, auth_date: int | None = None) -> str:
    """Собирает initData так же, как Telegram: поля по алфавиту, HMAC от ключа WebAppData."""
    fields = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAH",
              "user": json.dumps(user, separators=(",", ":"), ensure_ascii=False)}
    if start_param:
        fields["start_param"] = start_param
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


ORG = {"id": 1001, "first_name": "Оля", "username": "olya_sp", "allows_write_to_pm": True}
IRA = {"id": 2002, "first_name": "Ира", "last_name": "К."}


@pytest.fixture()
def bot(monkeypatch):
    """Включает Telegram и перехватывает вызовы Bot API."""
    calls = []

    def fake_call(method, **params):
        calls.append((method, params))
        if method == "createInvoiceLink":
            return "https://t.me/$invoice123"
        return True

    monkeypatch.setattr(tg, "TG_BOT_TOKEN", TOKEN)
    monkeypatch.setattr(tg, "TG_BOT_USERNAME", "dolka_bot")
    monkeypatch.setattr(main, "TG_BOT_USERNAME", "dolka_bot")
    monkeypatch.setattr(main, "TG_WEBHOOK_SECRET", "hooksecret")
    monkeypatch.setattr(tg, "call", fake_call)
    return calls


def tg_login(client, user=ORG):
    r = client.post("/api/tg/auth", json={"init_data": sign(user)}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def test_init_data_validation():
    data = tg.validate_init_data(sign(IRA, "abcd2345"), TOKEN)
    assert data["user"]["id"] == 2002 and data["start_param"] == "abcd2345"
    with pytest.raises(tg.TgError):  # чужой токен — подпись не сходится
        tg.validate_init_data(sign(IRA), "999:other")
    with pytest.raises(tg.TgError):  # подменили пользователя
        tg.validate_init_data(sign(IRA).replace("2002", "2003"), TOKEN)
    with pytest.raises(tg.TgError):  # устаревшая сессия
        tg.validate_init_data(sign(IRA, auth_date=int(time.time()) - 3 * 86400), TOKEN)
    assert tg.display_name(ORG) == "Оля (@olya_sp)"


def test_tg_organizer_and_participant_flow(client, bot):
    me = tg_login(client)
    assert me["me"]["name"] == "Оля (@olya_sp)" and me["plan"] == "pro" and me["tg"]["bot"] == "dolka_bot"
    session = {**H, "Authorization": "Bearer " + me["session"]}
    # повторный вход — тот же аккаунт, без нового пробного периода
    assert tg_login(client)["session"] != me["session"]
    org = TestClient(app)  # без cookie: в Telegram Web сессия идёт только заголовком
    p = org.post("/api/purchases", json={"title": "Мёд", "pay_info": "СБП +7 900", "pickup": "Двор"}, headers=session).json()
    p = org.post(f"/api/purchases/{p['id']}/items", json={"name": "Мёд", "unit": "банка", "price": "450"},
                 headers=session).json()
    assert p["tg_link"] == f"https://t.me/dolka_bot?startapp={p['slug']}"
    item = str(p["items"][0]["id"])

    # участник: заказ привязан к Telegram-аккаунту, токен не нужен
    ira = TestClient(app)
    ih = {**H, "X-Tg-Init-Data": sign(IRA, p["slug"])}
    r = ira.post(f"/api/z/{p['slug']}/order", json={"name": "Ира К.", "lines": {item: "2"}}, headers=ih)
    assert r.status_code == 200, r.text
    assert ira.get(f"/api/z/{p['slug']}", headers=ih).json()["my_order"]["goods_kop"] == 90000
    # второй заказ с того же аккаунта меняет первый, а не создаёт новый
    ira.post(f"/api/z/{p['slug']}/order", json={"name": "Ира К.", "lines": {item: "3"}}, headers=ih)
    view = org.get(f"/api/purchases/{p['id']}", headers=session).json()
    assert view["summary"]["participants"] == 1 and view["orders"][0]["lines"][0]["qty"] == "3"
    sent = [c for c in bot if c[0] == "sendMessage"]
    assert sent[0][1]["chat_id"] == 1001 and "заказал(а)" in sent[0][1]["text"]
    assert "изменил(а)" in sent[1][1]["text"]

    # «Я оплатил(а)» → организатору приходит сообщение
    ira.post(f"/api/z/{p['slug']}/paid", json={"paid": True}, headers=ih)
    assert "сообщает об оплате" in bot[-1][1]["text"]

    # стоп → участнику с долгом пишет бот, с кнопкой открыть закупку
    bot.clear()
    org.put(f"/api/purchases/{p['id']}", json={"status": "stopped"}, headers=session)
    msg = next(c[1] for c in bot if c[0] == "sendMessage")
    assert msg["chat_id"] == 2002 and "К оплате: 1 350 ₽" in msg["text"]
    assert msg["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"].endswith(f"/tg?z={p['slug']}")

    # приехало → итог по факту и место раздачи
    bot.clear()
    org.put(f"/api/purchases/{p['id']}", json={"status": "arrived"}, headers=session)
    assert "Раздача: Двор" in bot[0][1]["text"]

    # чужой initData не открывает заказ Иры
    other = {**H, "X-Tg-Init-Data": sign({"id": 3003, "first_name": "Петя"})}
    assert ira.get(f"/api/z/{p['slug']}", headers=other).json()["my_order"] is None
    bad = {**H, "X-Tg-Init-Data": sign(IRA, token="999:other")}
    assert ira.get(f"/api/z/{p['slug']}", headers=bad).status_code == 400


def test_export_link_works_without_cookie(client, bot):
    session = {**H, "Authorization": "Bearer " + tg_login(client)["session"]}
    org = TestClient(app)
    p = org.post("/api/purchases", json={"title": "Крупы"}, headers=session).json()
    link = org.post(f"/api/purchases/{p['id']}/export/supplier/link", headers=session).json()
    path = link["url"].split("://", 1)[1].split("/", 1)[1]
    anon = TestClient(app)
    assert anon.get("/" + path).status_code == 200
    assert anon.get("/" + path.replace("sig=", "sig=0")).status_code == 403
    assert anon.get(f"/api/purchases/{p['id']}/export/supplier.csv").status_code == 401


def test_stars_payment_via_webhook(client, monkeypatch, bot):
    monkeypatch.setattr("app.billing.PAYMENTS", "yookassa")  # не тестовый режим — платим звёздами
    session = {**H, "Authorization": "Bearer " + tg_login(client)["session"]}
    org = TestClient(app)
    res = org.post("/api/checkout", json={"plan": "pro", "duration": "1m", "channel": "tg"}, headers=session).json()
    assert res == {"status": "invoice", "url": "https://t.me/$invoice123"}
    inv = next(c[1] for c in bot if c[0] == "createInvoiceLink")
    assert inv["currency"] == "XTR" and inv["prices"][0]["amount"] == 300
    payload = inv["payload"]

    hook = {"X-Telegram-Bot-Api-Secret-Token": "hooksecret"}
    assert client.post("/api/tg/webhook", json={}, headers={"X-Telegram-Bot-Api-Secret-Token": "x"}).status_code == 403
    client.post("/api/tg/webhook", headers=hook, json={"update_id": 1, "pre_checkout_query": {
        "id": "q1", "currency": "XTR", "total_amount": 300, "invoice_payload": payload, "from": {"id": 1001}}})
    assert ("answerPreCheckoutQuery", {"pre_checkout_query_id": "q1", "ok": True}) in bot

    before = org.get("/api/me", headers=session).json()["sub_ends"]
    client.post("/api/tg/webhook", headers=hook, json={"update_id": 2, "message": {
        "message_id": 5, "chat": {"id": 1001, "type": "private"}, "from": {"id": 1001},
        "successful_payment": {"currency": "XTR", "total_amount": 300, "invoice_payload": payload,
                               "telegram_payment_charge_id": "ch_1"}}})
    after = org.get("/api/me", headers=session).json()["sub_ends"]
    assert after > before  # 30 дней добавились после пробного периода
    # повтор того же апдейта не продлевает подписку второй раз
    client.post("/api/tg/webhook", headers=hook, json={"update_id": 2, "message": {
        "message_id": 5, "chat": {"id": 1001, "type": "private"},
        "successful_payment": {"currency": "XTR", "total_amount": 300, "invoice_payload": payload}}})
    assert org.get("/api/me", headers=session).json()["sub_ends"] == after


def test_start_command_opens_purchase(client, bot):
    session = {**H, "Authorization": "Bearer " + tg_login(client)["session"]}
    p = TestClient(app).post("/api/purchases", json={"title": "Сыр"}, headers=session).json()
    hook = {"X-Telegram-Bot-Api-Secret-Token": "hooksecret"}
    bot.clear()
    client.post("/api/tg/webhook", headers=hook, json={"update_id": 3, "message": {
        "message_id": 1, "chat": {"id": 2002, "type": "private"}, "text": f"/start {p['slug']}"}})
    msg = bot[0][1]
    assert "Сыр" in msg["text"] and msg["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"].endswith(p["slug"])


def test_tg_page_served(client):
    r = client.get("/tg")
    assert r.status_code == 200 and "telegram-web-app.js" in r.text
