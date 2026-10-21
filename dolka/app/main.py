"""HTTP-сервер «Дольки» — сервиса для организаторов совместных закупок продуктов.

    uvicorn app.main:app --host 0.0.0.0 --port 8000

Страницы: / — о сервисе, /app — кабинет организатора, /z/{slug} — страница закупки для участников.
Участник заходит без регистрации: после заказа он получает личную ссылку (токен), по ней
меняет заказ и отмечает оплату. Изменяющие запросы к API требуют заголовок
X-Requested-With: dolka (защита от подделки запросов с чужих сайтов).

Мини-приложение Telegram (/tg) — те же страницы: организатор входит по подписанной initData
и дальше передаёт сессию заголовком Authorization (cookie в Telegram Web живут в чужом iframe
и браузеры их режут), участник передаёт initData заголовком X-Tg-Init-Data — заказ привязан
к его Telegram-аккаунту, а бот присылает уведомления.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import hashlib
import hmac
import logging
import time

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, billing, db, tg
from . import purchases as pu
from .config import PAYMENTS, PUBLIC_URL, SECRET, SECURE_COOKIES, TG_BOT_USERNAME, TG_WEBHOOK_SECRET, WEB_DIR
from .plans import PLANS, public_plans


@asynccontextmanager
async def lifespan(_app):
    db.init()
    yield


app = FastAPI(title="Долька", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE") and request.url.path.startswith("/api/") \
            and not request.url.path.startswith(("/api/payments/webhook", "/api/tg/webhook")) \
            and request.headers.get("x-requested-with") != "dolka":
        return JSONResponse({"detail": "Запрос отклонён"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


@app.exception_handler(tg.TgError)
@app.exception_handler(pu.PurchaseError)
@app.exception_handler(billing.BillingError)
@app.exception_handler(auth.AuthError)
async def user_error(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(LookupError)
async def not_found(_request, _exc):
    return JSONResponse({"detail": "Не найдено"}, status_code=404)


# ---------- пользователь ----------

def session_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(auth.COOKIE)


def current_user(request: Request):
    return auth.user_by_token(session_token(request))


def require_user(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "Войдите в аккаунт")
    return user


def set_session(resp: Response, token: str):
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True,
                    samesite="lax", secure=SECURE_COOKIES, path="/")


def me_payload(user) -> dict:
    plan = billing.current_plan(user)
    sub_ends, trial = billing.paid_until(user["id"]) if user else (None, False)
    return {
        "me": {"email": user["email"], "name": user["name"]} if user else None,
        "plan": plan, "plan_name": PLANS[plan]["name"], "sub_ends": sub_ends, "trial": trial,
        "limits": billing.limits(user) if user else None, "plans": public_plans(), "payments": PAYMENTS,
        "statuses": pu.STATUSES, "units": pu.UNITS,
        "tg": {"enabled": tg.enabled(), "bot": TG_BOT_USERNAME or None},
    }


class Credentials(BaseModel):
    email: str
    password: str
    name: str = ""


@app.post("/api/register")
def register(body: Credentials):
    uid = auth.register(body.email, body.password, body.name)
    billing.start_trial(uid)
    resp = JSONResponse(me_payload(db.one("SELECT * FROM users WHERE id = ?", uid)))
    set_session(resp, auth.new_session(uid))
    return resp


@app.post("/api/login")
def login(body: Credentials):
    token = auth.login(body.email, body.password)
    resp = JSONResponse(me_payload(auth.user_by_token(token)))
    set_session(resp, token)
    return resp


class TgAuth(BaseModel):
    init_data: str


@app.post("/api/tg/auth")
def tg_auth(body: TgAuth):
    """Вход организатора из мини-приложения: аккаунт создаётся по Telegram id, с пробным периодом."""
    data = tg.validate_init_data(body.init_data)
    uid, created = tg.organizer_for(data["user"])
    if created:
        billing.start_trial(uid)
    token = auth.new_session(uid)
    return {"session": token, "start_param": data["start_param"],
            **me_payload(db.one("SELECT * FROM users WHERE id = ?", uid))}


@app.post("/api/tg/webhook")
async def tg_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
    if not TG_WEBHOOK_SECRET or x_telegram_bot_api_secret_token != TG_WEBHOOK_SECRET:
        raise HTTPException(403, "Запрос отклонён")
    try:
        tg.handle_update(await request.json())
    except Exception:  # Telegram повторяет запрос при ошибке — не зацикливаем его на сломанном апдейте
        logging.getLogger("dolka.tg").exception("Ошибка обработки апдейта Telegram")
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request):
    auth.logout(session_token(request))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


@app.get("/api/me")
def me(user=Depends(current_user)):
    return me_payload(user)


class Checkout(BaseModel):
    plan: str
    duration: str
    channel: str = "web"   # tg — оплата звёздами внутри мини-приложения


@app.post("/api/checkout")
def checkout(body: Checkout, user=Depends(require_user)):
    return billing.checkout(user, body.plan, body.duration, "tg" if body.channel == "tg" else "web")


# ---------- кабинет организатора ----------

@app.get("/api/purchases")
def purchases_list(user=Depends(require_user)):
    return pu.list_purchases(user["id"])


@app.post("/api/purchases")
async def purchase_create(request: Request, user=Depends(require_user)):
    billing.check_can_create_purchase(user)
    pid = pu.create_purchase(user["id"], await request.json())
    return pu.owner_view(pu.owned_purchase(pid, user["id"]))


@app.get("/api/purchases/{pid}")
def purchase_get(pid: int, user=Depends(require_user)):
    return pu.owner_view(pu.owned_purchase(pid, user["id"]))


@app.put("/api/purchases/{pid}")
async def purchase_update(pid: int, request: Request, background: BackgroundTasks, user=Depends(require_user)):
    p = pu.owned_purchase(pid, user["id"])
    data = await request.json()
    if p["status"] == "closed" and data.get("status") not in (None, "closed"):
        billing.check_can_create_purchase(user)  # переоткрытие считается как новая активная закупка
    pu.update_purchase(pid, data)
    if data.get("status") in ("stopped", "arrived") and data["status"] != p["status"]:
        background.add_task(tg.notify_status, pid, data["status"])
    return pu.owner_view(pu.owned_purchase(pid, user["id"]))


@app.delete("/api/purchases/{pid}")
def purchase_delete(pid: int, user=Depends(require_user)):
    pu.owned_purchase(pid, user["id"])
    with db.tx() as c:
        c.execute("DELETE FROM purchases WHERE id = ?", (pid,))
    return {"ok": True}


@app.post("/api/purchases/{pid}/copy")
def purchase_copy(pid: int, user=Depends(require_user)):
    p = pu.owned_purchase(pid, user["id"])
    billing.check_can_create_purchase(user)
    return pu.owner_view(pu.owned_purchase(pu.copy_purchase(p, user["id"]), user["id"]))


@app.post("/api/purchases/{pid}/items")
async def item_add(pid: int, request: Request, user=Depends(require_user)):
    pu.owned_purchase(pid, user["id"])
    pu.add_item(pid, await request.json())
    return pu.owner_view(pu.owned_purchase(pid, user["id"]))


@app.put("/api/items/{item_id}")
async def item_update(item_id: int, request: Request, user=Depends(require_user)):
    item = pu.owned_item(item_id, user["id"])
    pu.update_item(item_id, await request.json())
    return pu.owner_view(pu.owned_purchase(item["purchase_id"], user["id"]))


@app.delete("/api/items/{item_id}")
def item_delete(item_id: int, user=Depends(require_user)):
    item = pu.owned_item(item_id, user["id"])
    pu.delete_item(item_id)
    return pu.owner_view(pu.owned_purchase(item["purchase_id"], user["id"]))


@app.post("/api/items/{item_id}/trim")
def item_trim(item_id: int, background: BackgroundTasks, user=Depends(require_user)):
    item = pu.owned_item(item_id, user["id"])
    removed = pu.trim_to_packs(item)
    background.add_task(tg.notify_trimmed, pu.owned_purchase(item["purchase_id"], user["id"]),
                        item["name"], item["unit"], removed)
    return {"removed": removed, "purchase": pu.owner_view(pu.owned_purchase(item["purchase_id"], user["id"]))}


@app.put("/api/orders/{order_id}")
async def order_admin_update(order_id: int, request: Request, user=Depends(require_user)):
    order = pu.owned_order(order_id, user["id"])
    pu.update_order_admin(order, await request.json())
    return pu.owner_view(pu.owned_purchase(order["purchase_id"], user["id"]))


@app.delete("/api/orders/{order_id}")
def order_admin_delete(order_id: int, user=Depends(require_user)):
    order = pu.owned_order(order_id, user["id"])
    pu.delete_order(order)
    return pu.owner_view(pu.owned_purchase(order["purchase_id"], user["id"]))


def _csv_response(text: str, name: str) -> Response:
    return Response(text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=\"{name}\""})


EXPORTS = {"supplier": (pu.supplier_csv, "zakaz-postavshiku"), "orders": (pu.orders_csv, "razdacha")}
EXPORT_LINK_SECONDS = 600


def _export_sig(pid: int, kind: str, exp: int) -> str:
    return hmac.new(SECRET.encode(), f"export:{pid}:{kind}:{exp}".encode(), hashlib.sha256).hexdigest()


@app.post("/api/purchases/{pid}/export/{kind}/link")
def export_link(pid: int, kind: str, user=Depends(require_user)):
    """Ссылка на файл, которая работает без cookie: Telegram скачивает файлы отдельным запросом."""
    p = pu.owned_purchase(pid, user["id"])
    if kind not in EXPORTS:
        raise HTTPException(404, "Не найдено")
    exp = int(time.time()) + EXPORT_LINK_SECONDS
    name = f"{EXPORTS[kind][1]}-{p['slug']}.csv"
    return {"url": f"{PUBLIC_URL}/api/purchases/{pid}/export/{kind}.csv?exp={exp}&sig={_export_sig(pid, kind, exp)}",
            "file_name": name}


@app.get("/api/purchases/{pid}/export/{kind}.csv")
def export_csv(pid: int, kind: str, request: Request, exp: int = 0, sig: str = ""):
    if kind not in EXPORTS:
        raise HTTPException(404, "Не найдено")
    if sig:
        if exp < time.time() or not hmac.compare_digest(sig, _export_sig(pid, kind, exp)):
            raise HTTPException(403, "Ссылка устарела. Скачайте файл заново.")
        p = db.one("SELECT * FROM purchases WHERE id = ?", pid)
        if not p:
            raise HTTPException(404, "Не найдено")
    else:
        user = current_user(request)
        if not user:
            raise HTTPException(401, "Войдите в аккаунт")
        p = pu.owned_purchase(pid, user["id"])
    build, prefix = EXPORTS[kind]
    return _csv_response(build(p), f"{prefix}-{p['slug']}.csv")


# ---------- страница участника ----------

def participant(p, token: str | None, init_data: str | None):
    """Заказ участника: в Telegram — по аккаунту (подпись initData), в браузере — по личной ссылке."""
    if init_data:
        user = tg.validate_init_data(init_data)["user"]
        return pu.order_by_tg(p, user["id"]), user
    return pu.order_by_token(p, token), None


@app.get("/api/z/{slug}")
def public_get(slug: str, x_order_token: str | None = Header(None), x_tg_init_data: str | None = Header(None)):
    p = pu.public_purchase(slug)
    order, _ = participant(p, x_order_token, x_tg_init_data)
    return pu.participant_view(p, order)


class OrderIn(BaseModel):
    name: str
    phone: str = ""
    comment: str = ""
    lines: dict[str, str | float | int | None]


@app.post("/api/z/{slug}/order")
def public_order(slug: str, body: OrderIn, background: BackgroundTasks,
                 x_order_token: str | None = Header(None), x_tg_init_data: str | None = Header(None)):
    p = pu.public_purchase(slug)
    existing, tg_user = participant(p, x_order_token, x_tg_init_data)
    if not existing:
        billing.check_can_add_order(db.one("SELECT * FROM users WHERE id = ?", p["user_id"]), p["id"])
    oid, token = pu.save_order(p, existing, body.name, body.phone, body.comment, body.lines,
                               tg_id=tg_user["id"] if tg_user else None)
    order = db.one("SELECT * FROM orders WHERE id = ?", oid)
    view = pu.participant_view(p, order)
    background.add_task(tg.notify_new_order, p, order["name"], view["my_order"]["total_kop"], bool(existing))
    return {"token": token or x_order_token, **view}


class PaidIn(BaseModel):
    paid: bool = True


@app.post("/api/z/{slug}/paid")
def public_paid(slug: str, body: PaidIn, background: BackgroundTasks,
                x_order_token: str | None = Header(None), x_tg_init_data: str | None = Header(None)):
    p = pu.public_purchase(slug)
    order, _ = participant(p, x_order_token, x_tg_init_data)
    if not order:
        raise HTTPException(404, "Заказ не найден — откройте свою личную ссылку.")
    pu.mark_says_paid(order, body.paid)
    view = pu.participant_view(p, db.one("SELECT * FROM orders WHERE id = ?", order["id"]))
    if body.paid:
        background.add_task(tg.notify_says_paid, p, order["name"], view["my_order"]["balance_kop"])
    return view


@app.delete("/api/z/{slug}/order")
def public_cancel(slug: str, x_order_token: str | None = Header(None), x_tg_init_data: str | None = Header(None)):
    p = pu.public_purchase(slug)
    order, _ = participant(p, x_order_token, x_tg_init_data)
    if not order:
        raise HTTPException(404, "Заказ не найден.")
    pu.cancel_order(p, order)
    return pu.participant_view(p)


# ---------- страницы ----------

@app.get("/")
def landing():
    return FileResponse(WEB_DIR / "landing.html")


@app.get("/app")
def organizer_app():
    return FileResponse(WEB_DIR / "app.html")


@app.get("/z/{slug}")
def participant_page(slug: str):
    return FileResponse(WEB_DIR / "join.html")


@app.get("/tg")
def telegram_app():
    """Точка входа мини-приложения: кабинет организатора или закупка (по start_param / ?z=)."""
    return FileResponse(WEB_DIR / "tg.html")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(WEB_DIR / "static" / "manifest.webmanifest", media_type="application/manifest+json")
