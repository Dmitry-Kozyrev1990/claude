"""HTTP-сервер Lotline.

    uvicorn app.main:app --host 0.0.0.0 --port 8000

Страница — тот же интерфейс, что в демо (web/template.html), но данные в неё подставляет
сервер: по тарифу пользователя, с его коллекцией и избранным. Изменяющие запросы к API
требуют заголовок X-Requested-With: lotline (защита от подделки запросов с чужих сайтов).
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from arttracker.catalog import FX_TO_USD, fx

from . import auth, billing, db
from .access import DataViews, is_paid
from .config import DATA_PATH, PAYMENTS, SECURE_COOKIES, TEMPLATE_PATH
from .plans import FREE_LIMITS, PLANS, public_plans

STATE: dict = {}


def load_data() -> dict:
    if not DATA_PATH.exists():
        from arttracker import build
        data = build.run("demo")
        build.write(data)
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@asynccontextmanager
async def lifespan(_app):
    db.init()
    STATE["views"] = DataViews(load_data())
    STATE["template"] = TEMPLATE_PATH.read_text(encoding="utf-8")
    yield


app = FastAPI(title="Lotline", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE") and request.url.path.startswith("/api/") \
            and not request.url.path.startswith("/api/payments/webhook") \
            and request.headers.get("x-requested-with") != "lotline":
        return JSONResponse({"detail": "Запрос отклонён"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


# ---------- пользователь ----------

def current_user(request: Request):
    return auth.user_by_token(request.cookies.get(auth.COOKIE))


def require_user(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "Войдите в аккаунт")
    return user


def require_admin(user=Depends(require_user)):
    if not user["is_admin"]:
        raise HTTPException(403, "Только для администратора")
    return user


def watchlist(user_id: int) -> dict:
    rows = db.all_("SELECT kind, ref FROM watchlist WHERE user_id = ? ORDER BY created_at", user_id)
    return {"artists": [r["ref"] for r in rows if r["kind"] == "artist"],
            "works": [r["ref"] for r in rows if r["kind"] == "work"]}


def collection_specs(user_id: int) -> list[dict]:
    rows = db.all_("SELECT * FROM collection WHERE user_id = ? ORDER BY bought_on", user_id)
    return [{"id": r["id"], "variant": r["variant"], "bought_on": r["bought_on"], "bought_usd": r["bought_usd"],
             "note": r["note"], "price": r["price"], "currency": r["currency"]} for r in rows]


def me_payload(user) -> dict:
    plan = billing.current_plan(user)
    sub = billing.active_subscription(user["id"]) if user else None
    return {
        "me": {"email": user["email"], "name": user["name"], "is_admin": bool(user["is_admin"])} if user else None,
        "plan": plan, "plan_name": PLANS[plan]["name"], "sub_ends": sub["ends_at"] if sub else None,
        "plans": public_plans(), "payments": PAYMENTS, "limits": FREE_LIMITS,
        "watchlist": watchlist(user["id"]) if user else None,
        "portfolio": STATE["views"].portfolio(collection_specs(user["id"]), plan) if user else None,
    }


def set_session(resp, token: str):
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True,
                    samesite="lax", secure=SECURE_COOKIES, path="/")


# ---------- страница ----------

@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def page(user=Depends(current_user)):
    plan = billing.current_plan(user)
    data = STATE["views"].for_plan(plan).replace("</", "<\\/")
    server = json.dumps(me_payload(user), ensure_ascii=False).replace("</", "<\\/")
    html = STATE["template"].replace("/*__DATA__*/null", data, 1).replace("/*__SERVER__*/null", server, 1)
    return HTMLResponse("<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\">"
                        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
                        "</head><body>" + html + "</body></html>", headers={"Cache-Control": "no-store"})


@app.get("/healthz")
def healthz():
    return {"ok": True, "lots": len(STATE["views"].data["lots"])}


# ---------- аккаунт ----------

class Credentials(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)
    name: str = Field(default="", max_length=80)


@app.post("/api/register")
def register(body: Credentials):
    try:
        uid = auth.register(body.email, body.password, body.name)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    resp = JSONResponse({"ok": True})
    set_session(resp, auth.new_session(uid))
    return resp


@app.post("/api/login")
def login(body: Credentials):
    try:
        token = auth.login(body.email, body.password)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    resp = JSONResponse({"ok": True})
    set_session(resp, token)
    return resp


@app.post("/api/logout")
def logout(request: Request):
    auth.logout(request.cookies.get(auth.COOKIE))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


@app.get("/api/me")
def me(user=Depends(current_user)):
    return me_payload(user)


# ---------- коллекция и избранное ----------

class CollectionItem(BaseModel):
    variant: str = Field(max_length=200)
    bought_on: date
    price: float = Field(gt=0, lt=1e12)
    currency: str = Field(pattern="^(RUB|USD|EUR|GBP)$")
    note: str = Field(default="", max_length=200)


@app.post("/api/collection")
def add_to_collection(item: CollectionItem, user=Depends(require_user)):
    if item.variant not in STATE["views"].data["variants"]:
        raise HTTPException(400, "Работа не найдена в базе")
    if item.bought_on > date.today() or item.bought_on.year < 1950:
        raise HTTPException(400, "Проверьте дату покупки")
    plan = billing.current_plan(user)
    count = db.one("SELECT COUNT(*) AS n FROM collection WHERE user_id = ?", user["id"])["n"]
    if not is_paid(plan) and count >= FREE_LIMITS["collection"]:
        raise HTTPException(402, f"В бесплатном тарифе — до {FREE_LIMITS['collection']} работ. "
                                 "В подписке коллекция без ограничений.")
    table = FX_TO_USD[item.currency]
    year = min(max(item.bought_on.year, min(table)), max(table))  # до 2015 года — курс 2015 года
    usd = item.price * fx(item.currency, year)
    with db.tx() as c:
        c.execute("INSERT INTO collection (user_id, variant, bought_on, price, currency, bought_usd, note, created_at) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (user["id"], item.variant, item.bought_on.isoformat(),
                                                      item.price, item.currency, round(usd, 2), item.note, db.now()))
    return me_payload(user)


@app.delete("/api/collection/{item_id}")
def delete_from_collection(item_id: int, user=Depends(require_user)):
    with db.tx() as c:
        c.execute("DELETE FROM collection WHERE id = ? AND user_id = ?", (item_id, user["id"]))
    return me_payload(user)


class WatchItem(BaseModel):
    kind: str = Field(pattern="^(artist|work)$")
    ref: str = Field(max_length=200)


@app.post("/api/watchlist")
def watch(item: WatchItem, user=Depends(require_user)):
    data = STATE["views"].data
    if (item.kind == "artist" and item.ref not in data["artists"]) or (item.kind == "work" and item.ref not in data["variants"]):
        raise HTTPException(400, "Не найдено")
    plan = billing.current_plan(user)
    count = db.one("SELECT COUNT(*) AS n FROM watchlist WHERE user_id = ? AND kind = ?", user["id"], item.kind)["n"]
    limit = FREE_LIMITS["watch_artists" if item.kind == "artist" else "watch_works"]
    if not is_paid(plan) and count >= limit:
        raise HTTPException(402, f"В бесплатном тарифе — до {limit} в избранном. В подписке — без ограничений.")
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO watchlist (user_id, kind, ref, created_at) VALUES (?, ?, ?, ?)",
                  (user["id"], item.kind, item.ref, db.now()))
    return watchlist(user["id"])


@app.delete("/api/watchlist/{kind}/{ref:path}")
def unwatch(kind: str, ref: str, user=Depends(require_user)):
    with db.tx() as c:
        c.execute("DELETE FROM watchlist WHERE user_id = ? AND kind = ? AND ref = ?", (user["id"], kind, ref))
    return watchlist(user["id"])


# ---------- тарифы и оплата ----------

@app.get("/api/plans")
def plans():
    return {"plans": public_plans(), "payments": PAYMENTS}


class Checkout(BaseModel):
    plan: str = Field(pattern="^(collector|pro)$")
    duration: str = Field(max_length=10)


@app.post("/api/checkout")
def checkout(body: Checkout, user=Depends(require_user)):
    try:
        return billing.checkout(user, body.plan, body.duration)
    except billing.BillingError as e:
        raise HTTPException(400, str(e))


@app.get("/api/payments")
def payments(user=Depends(require_user)):
    return billing.history(user["id"])


@app.post("/api/payments/webhook/yookassa")
def yookassa_webhook():
    # Уведомления ЮKassa о платежах: обработка появится вместе с подключением ЮKassa.
    raise HTTPException(501, "ЮKassa ещё не подключена")


# ---------- администратор ----------

@app.get("/api/admin/users")
def admin_users(_=Depends(require_admin)):
    rows = db.all_("""SELECT u.id, u.email, u.name, u.created_at, u.is_admin,
                      (SELECT COUNT(*) FROM collection c WHERE c.user_id = u.id) AS works,
                      (SELECT plan || '|' || ends_at FROM subscriptions s WHERE s.user_id = u.id AND s.ends_at > ?
                       ORDER BY ends_at DESC LIMIT 1) AS sub
                      FROM users u ORDER BY u.id DESC LIMIT 500""", db.now())
    out = []
    for r in rows:
        plan, ends = (r["sub"].split("|") if r["sub"] else ("free", None))
        out.append({"id": r["id"], "email": r["email"], "name": r["name"], "created_at": r["created_at"],
                    "is_admin": bool(r["is_admin"]), "works": r["works"], "plan": plan, "ends_at": ends})
    revenue = db.one("SELECT COUNT(*) AS n, COALESCE(SUM(amount_rub), 0) AS s FROM payments "
                     "WHERE status = 'succeeded' AND provider != 'demo'")
    return {"users": out, "paid_payments": revenue["n"], "revenue_rub": revenue["s"]}


class Grant(BaseModel):
    email: str
    plan: str = Field(pattern="^(collector|pro)$")
    days: int = Field(gt=0, le=3660)


@app.post("/api/admin/grant")
def admin_grant(body: Grant, _=Depends(require_admin)):
    u = db.one("SELECT id FROM users WHERE email = ?", body.email.strip().lower())
    if not u:
        raise HTTPException(404, "Пользователь не найден")
    return {"ends_at": billing.grant(u["id"], body.plan, body.days, "admin")}
