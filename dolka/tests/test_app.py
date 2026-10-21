"""Сквозные сценарии: организатор создаёт закупку, участники заказывают, коробки, оплаты, факт, лимиты."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app import purchases as pu
from app.main import app

from .conftest import H


def organizer(client, email="org@example.com"):
    r = client.post("/api/register", json={"email": email, "password": "password1", "name": "Оля"}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def make_purchase(client, **extra):
    body = {"title": "Крупы, октябрь", "supplier": "База №1", "fee_pct": "10", "min_total": "1000",
            "pay_info": "СБП +7 900 000-00-00", **extra}
    p = client.post("/api/purchases", json=body, headers=H).json()
    p = client.post(f"/api/purchases/{p['id']}/items",
                    json={"name": "Гречка", "unit": "кг", "price": "80", "step": "1", "pack": "10"}, headers=H).json()
    p = client.post(f"/api/purchases/{p['id']}/items",
                    json={"name": "Масло", "unit": "бут", "price": "149.90", "step": "1"}, headers=H).json()
    p = client.post(f"/api/purchases/{p['id']}/items",
                    json={"name": "Сыр", "unit": "кг", "price": "650", "step": "0.5"}, headers=H).json()
    return p


def order(client, slug, name, lines, token=None):
    h = {**H, **({"X-Order-Token": token} if token else {})}
    return client.post(f"/api/z/{slug}/order", json={"name": name, "phone": "", "lines": lines}, headers=h)


# ---------- расчёты ----------

def test_money_and_quantities():
    assert pu.to_milli("1,5") == 1500
    assert pu.to_milli(2) == 2000
    with pytest.raises(pu.PurchaseError):
        pu.to_milli("0,0005")
    assert pu.to_kop("149.90") == 14990
    assert pu.line_kop(14990, 3000) == 44970
    assert pu.line_kop(65000, 1930) == 125450  # 1,93 кг сыра по 650 ₽
    assert pu.fee_kop(125450, 10) == 12545
    assert pu.fee_kop(5, 10) == 1  # 0,5 коп. → вверх
    assert pu.fmt_milli(1500) == "1,5"
    assert pu.fmt_rub(125450) == "1 254,50 ₽"


# ---------- сценарии ----------

def test_full_purchase_flow(client):
    me = organizer(client)
    assert me["plan"] == "pro" and me["trial"]
    p = make_purchase(client)
    slug, ids = p["slug"], [i["id"] for i in p["items"]]

    # участник видит позиции без чужих имён и без авторизации
    anon = TestClient(app)
    pub = anon.get(f"/api/z/{slug}").json()
    assert pub["accepting"] and len(pub["items"]) == 3 and pub["my_order"] is None

    r = order(anon, slug, "Ира", {str(ids[0]): "6", str(ids[1]): "2"})
    assert r.status_code == 200, r.text
    ira = r.json()["token"]
    mine = r.json()["my_order"]
    assert mine["goods_kop"] == 6 * 8000 + 2 * 14990 and mine["fee_kop"] == round(mine["goods_kop"] * 0.1)

    r = order(anon, slug, "Петя", {str(ids[0]): "7", str(ids[2]): "1,5"})
    petya = r.json()["token"]
    # шаг 0,5 кг: 1,2 кг сыра заказать нельзя
    assert order(anon, slug, "Вася", {str(ids[2]): "1.2"}).status_code == 400

    # участник меняет свой заказ по личной ссылке
    r = order(anon, slug, "Ира", {str(ids[0]): "5", str(ids[1]): "2"}, token=ira)
    assert r.json()["token"] == ira

    view = client.get(f"/api/purchases/{p['id']}").json()
    grecha = view["items"][0]
    assert grecha["total"] == "12" and grecha["packs"] == 1 and grecha["missing"] == "8"
    assert view["summary"]["participants"] == 2

    # коробка не собралась: снимаем 2 кг с последнего заказа (Петя)
    res = client.post(f"/api/items/{ids[0]}/trim", headers=H).json()
    assert res["removed"] == [{"order_id": res["removed"][0]["order_id"], "name": "Петя", "removed": "2"}]
    assert res["purchase"]["items"][0]["total"] == "10" and res["purchase"]["items"][0]["missing"] == ""

    # стоп: участники больше не меняют заказы
    client.put(f"/api/purchases/{p['id']}", json={"status": "stopped"}, headers=H)
    assert order(anon, slug, "Ира", {str(ids[0]): "1"}, token=ira).status_code == 400

    # участник отмечает оплату, организатор сверяет; факт по весу пересчитывает сумму
    pub = anon.post(f"/api/z/{slug}/paid", json={"paid": True}, headers={**H, "X-Order-Token": petya}).json()
    assert pub["my_order"]["says_paid"]
    view = client.get(f"/api/purchases/{p['id']}").json()
    po = next(o for o in view["orders"] if o["name"] == "Петя")
    client.put(f"/api/orders/{po['id']}", json={"paid": po["total_kop"] / 100}, headers=H)
    view = client.put(f"/api/orders/{po['id']}", json={"facts": {str(ids[2]): "1,43"}}, headers=H).json()
    po = next(o for o in view["orders"] if o["name"] == "Петя")
    # 5 кг гречки × 80 + 1,43 кг сыра × 650 = 400 + 929,50 = 1329,50 ₽, оргсбор 132,95 ₽
    assert po["goods_kop"] == 132950 and po["fee_kop"] == 13295
    assert po["balance_kop"] < 0  # переплата: платил за 1,5 кг, приехало 1,43

    view = client.put(f"/api/orders/{po['id']}", json={"picked_up": True}, headers=H).json()
    assert view["summary"]["picked_up"] == 1

    sup = client.get(f"/api/purchases/{p['id']}/export/supplier.csv")
    assert sup.status_code == 200 and "Гречка" in sup.text and sup.text.startswith("﻿")
    raz = client.get(f"/api/purchases/{p['id']}/export/orders.csv")
    assert "Петя" in raz.text and "да" in raz.text


def test_access_control(client):
    organizer(client)
    p = make_purchase(client)
    other = TestClient(app)
    organizer(other, "other@example.com")
    assert other.get(f"/api/purchases/{p['id']}").status_code == 404
    assert other.put(f"/api/items/{p['items'][0]['id']}", json={"name": "x", "price": "1"}, headers=H).status_code == 404
    # без заголовка X-Requested-With изменяющие запросы отклоняются
    assert client.post("/api/purchases", json={"title": "x"}).status_code == 403
    # чужой токен заказа не даёт доступа к заказу
    assert other.post(f"/api/z/{p['slug']}/paid", json={"paid": True},
                      headers={**H, "X-Order-Token": "fake"}).status_code == 404


def test_free_limits_and_upgrade(client):
    organizer(client)
    with db.tx() as c:  # пробный период закончился
        c.execute("DELETE FROM subscriptions")
    me = client.get("/api/me").json()
    assert me["plan"] == "free"
    p = make_purchase(client)
    assert client.post("/api/purchases", json={"title": "Вторая"}, headers=H).status_code == 400
    anon = TestClient(app)
    for n in range(15):
        assert order(anon, p["slug"], f"У{n}", {str(p["items"][1]["id"]): "1"}).status_code == 200
    assert order(anon, p["slug"], "Лишний", {str(p["items"][1]["id"]): "1"}).status_code == 400

    r = client.post("/api/checkout", json={"plan": "pro", "duration": "1m"}, headers=H).json()
    assert r["status"] == "succeeded"
    assert client.get("/api/me").json()["plan"] == "pro"
    assert order(anon, p["slug"], "Лишний", {str(p["items"][1]["id"]): "1"}).status_code == 200
    assert client.post("/api/purchases", json={"title": "Вторая"}, headers=H).status_code == 200


def test_copy_and_deadline(client):
    organizer(client)
    p = make_purchase(client, deadline="2020-01-01T10:00")
    anon = TestClient(app)
    assert anon.get(f"/api/z/{p['slug']}").json()["accepting"] is False
    assert order(anon, p["slug"], "Поздно", {str(p["items"][0]["id"]): "1"}).status_code == 400
    copy = client.post(f"/api/purchases/{p['id']}/copy", headers=H).json()
    assert copy["slug"] != p["slug"] and len(copy["items"]) == 3 and copy["orders"] == []
    assert copy["deadline"] is None and copy["fee_pct"] == 10


def test_pages_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/app").status_code == 200
    assert client.get("/z/abc").status_code == 200
    assert client.get("/static/app.js").status_code == 200
