"""Сервер: аккаунты, тарифы, разграничение данных, коллекция, оплата (тестовый режим), админка."""
import importlib
import json
import re

import pytest

H = {"X-Requested-With": "lotline"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTLINE_DB", str(tmp_path / "t.sqlite3"))
    monkeypatch.setenv("LOTLINE_SECRET", "test-secret")
    monkeypatch.setenv("LOTLINE_ADMIN_EMAILS", "boss@lotline.test")
    monkeypatch.setenv("LOTLINE_PAYMENTS", "demo")
    import app.config, app.db, app.auth, app.billing, app.main  # noqa: E401
    for m in (app.config, app.db, app.auth, app.billing, app.main):
        importlib.reload(m)
    from fastapi.testclient import TestClient
    with TestClient(app.main.app) as c:
        yield c


def page_data(c):
    html = c.get("/").text
    data = json.loads(re.search(r"const DATA = (.*?); const SERVER", html, re.S).group(1).replace("<\\/", "</"))
    server = json.loads(re.search(r"const SERVER = (.*?);</script>", html, re.S).group(1).replace("<\\/", "</"))
    return data, server


def register(c, email="ivan@lotline.test"):
    r = c.post("/api/register", json={"email": email, "password": "password123", "name": "Иван"}, headers=H)
    assert r.status_code == 200, r.text


def test_anonymous_gets_free_view_without_locked_numbers(client):
    data, server = page_data(client)
    assert server["me"] is None and server["plan"] == "free"
    assert all(a["liquidity"] is None and a["bias"] is None for a in data["artists"].values())
    assert all("p50" not in v["valuation"] for v in data["variants"].values())
    recent = [l for l in data["lots"] if l["d"] >= "2025-10-14" and l["s"] == "sold"]
    assert recent and all(l["tu"] is None for l in recent)
    assert server["plans"]["collector"]["durations"][3][:2] == ["12 месяцев", 11450]


def test_requests_without_header_are_rejected(client):
    r = client.post("/api/register", json={"email": "x@y.zz", "password": "password123"})
    assert r.status_code == 403


def test_register_login_and_validation(client):
    assert client.post("/api/register", json={"email": "bad", "password": "password123"}, headers=H).status_code == 400
    assert client.post("/api/register", json={"email": "a@b.cc", "password": "short"}, headers=H).status_code == 400
    register(client)
    assert client.post("/api/register", json={"email": "ivan@lotline.test", "password": "password123"}, headers=H).status_code == 400
    client.post("/api/logout", headers=H)
    assert client.post("/api/login", json={"email": "ivan@lotline.test", "password": "wrong-pass"}, headers=H).status_code == 400
    assert client.post("/api/login", json={"email": "IVAN@lotline.test", "password": "password123"}, headers=H).status_code == 200
    assert client.get("/api/me").json()["me"]["email"] == "ivan@lotline.test"


def test_free_limits_and_subscription_unlocks(client):
    register(client)
    data, _ = page_data(client)
    variants = list(data["variants"])[:5]
    for v in variants[:3]:
        r = client.post("/api/collection", json={"variant": v, "bought_on": "2019-05-01", "price": 1500000,
                                                 "currency": "RUB"}, headers=H)
        assert r.status_code == 200, r.text
    r = client.post("/api/collection", json={"variant": variants[3], "bought_on": "2019-05-01", "price": 10,
                                             "currency": "USD"}, headers=H)
    assert r.status_code == 402
    p = r = client.get("/api/me").json()["portfolio"]
    assert p["limited"] and "gain" not in p["items"][0]
    # Подписка в тестовом режиме оплаты.
    r = client.post("/api/checkout", json={"plan": "collector", "duration": "12m"}, headers=H)
    assert r.json()["status"] == "succeeded"
    me = client.get("/api/me").json()
    assert me["plan"] == "collector" and me["sub_ends"]
    assert "gain" in me["portfolio"]["items"][0] and me["portfolio"]["timeline"]
    assert client.post("/api/collection", json={"variant": variants[3], "bought_on": "2019-05-01", "price": 10,
                                                "currency": "USD"}, headers=H).status_code == 200
    data, _ = page_data(client)
    assert any(a["liquidity"] for a in data["artists"].values())  # платная версия данных
    pay = client.get("/api/payments").json()
    assert pay[0]["amount_rub"] == 11450 and pay[0]["status"] == "succeeded"


def test_renewal_extends_and_admin_grant(client):
    register(client, "boss@lotline.test")
    assert client.get("/api/me").json()["me"]["is_admin"]
    client.post("/api/checkout", json={"plan": "collector", "duration": "1m"}, headers=H)
    first = client.get("/api/me").json()["sub_ends"]
    client.post("/api/checkout", json={"plan": "collector", "duration": "1m"}, headers=H)
    from app import billing, db
    ends = db.one("SELECT MAX(ends_at) AS e FROM subscriptions")["e"]
    assert ends > first  # продление начинается после окончания текущего периода
    client.post("/api/logout", headers=H)
    register(client, "client@lotline.test")
    assert client.get("/api/admin/users").status_code == 403
    client.post("/api/logout", headers=H)
    client.post("/api/login", json={"email": "boss@lotline.test", "password": "password123"}, headers=H)
    r = client.post("/api/admin/grant", json={"email": "client@lotline.test", "plan": "pro", "days": 14}, headers=H)
    assert r.status_code == 200
    users = client.get("/api/admin/users").json()["users"]
    assert next(u for u in users if u["email"] == "client@lotline.test")["plan"] == "pro"


def test_watchlist_limits(client):
    register(client)
    for a in ["banksy", "warhol", "zverev"]:
        assert client.post("/api/watchlist", json={"kind": "artist", "ref": a}, headers=H).status_code == 200
    assert client.post("/api/watchlist", json={"kind": "artist", "ref": "kusama"}, headers=H).status_code == 402
    w = client.delete("/api/watchlist/artist/banksy", headers=H).json()
    assert w["artists"] == ["warhol", "zverev"]
