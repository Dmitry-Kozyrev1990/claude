"""HTTP-сервер «Дольки» — сервиса для организаторов совместных закупок продуктов.

    uvicorn app.main:app --host 0.0.0.0 --port 8000

Страницы: / — о сервисе, /app — кабинет организатора, /z/{slug} — страница закупки для участников.
Участник заходит без регистрации: после заказа он получает личную ссылку (токен), по ней
меняет заказ и отмечает оплату. Изменяющие запросы к API требуют заголовок
X-Requested-With: dolka (защита от подделки запросов с чужих сайтов).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, billing, db
from . import purchases as pu
from .config import PAYMENTS, SECURE_COOKIES, WEB_DIR
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
            and not request.url.path.startswith("/api/payments/webhook") \
            and request.headers.get("x-requested-with") != "dolka":
        return JSONResponse({"detail": "Запрос отклонён"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


@app.exception_handler(pu.PurchaseError)
@app.exception_handler(billing.BillingError)
@app.exception_handler(auth.AuthError)
async def user_error(_request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(LookupError)
async def not_found(_request, _exc):
    return JSONResponse({"detail": "Не найдено"}, status_code=404)


# ---------- пользователь ----------

def current_user(request: Request):
    return auth.user_by_token(request.cookies.get(auth.COOKIE))


def require_user(user=Depends(current_user)):
    if not user:
        raise HTTPException(401, "Войдите в аккаунт")
    return user


def set_session(resp: Response, token: str):
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True,
                    samesite="lax", secure=SECURE_COOKIES, path="/")


def me_payload(user) -> dict:
    plan = billing.current_plan(user)
    sub = billing.active_subscription(user["id"]) if user else None
    return {
        "me": {"email": user["email"], "name": user["name"]} if user else None,
        "plan": plan, "plan_name": PLANS[plan]["name"], "sub_ends": sub["ends_at"] if sub else None,
        "trial": bool(sub and sub["source"] == "trial"),
        "limits": billing.limits(user) if user else None, "plans": public_plans(), "payments": PAYMENTS,
        "statuses": pu.STATUSES, "units": pu.UNITS,
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


@app.post("/api/logout")
def logout(request: Request):
    auth.logout(request.cookies.get(auth.COOKIE))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp


@app.get("/api/me")
def me(user=Depends(current_user)):
    return me_payload(user)


class Checkout(BaseModel):
    plan: str
    duration: str


@app.post("/api/checkout")
def checkout(body: Checkout, user=Depends(require_user)):
    return billing.checkout(user, body.plan, body.duration)


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
async def purchase_update(pid: int, request: Request, user=Depends(require_user)):
    p = pu.owned_purchase(pid, user["id"])
    data = await request.json()
    if p["status"] == "closed" and data.get("status") not in (None, "closed"):
        billing.check_can_create_purchase(user)  # переоткрытие считается как новая активная закупка
    pu.update_purchase(pid, data)
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
def item_trim(item_id: int, user=Depends(require_user)):
    item = pu.owned_item(item_id, user["id"])
    removed = pu.trim_to_packs(item)
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


@app.get("/api/purchases/{pid}/export/supplier.csv")
def export_supplier(pid: int, user=Depends(require_user)):
    p = pu.owned_purchase(pid, user["id"])
    return _csv_response(pu.supplier_csv(p), f"zakaz-postavshiku-{p['slug']}.csv")


@app.get("/api/purchases/{pid}/export/orders.csv")
def export_orders(pid: int, user=Depends(require_user)):
    p = pu.owned_purchase(pid, user["id"])
    return _csv_response(pu.orders_csv(p), f"razdacha-{p['slug']}.csv")


# ---------- страница участника ----------

@app.get("/api/z/{slug}")
def public_get(slug: str, x_order_token: str | None = Header(None)):
    p = pu.public_purchase(slug)
    return pu.participant_view(p, pu.order_by_token(p, x_order_token))


class OrderIn(BaseModel):
    name: str
    phone: str = ""
    comment: str = ""
    lines: dict[str, str | float | int | None]


@app.post("/api/z/{slug}/order")
def public_order(slug: str, body: OrderIn, x_order_token: str | None = Header(None)):
    p = pu.public_purchase(slug)
    if not pu.order_by_token(p, x_order_token):
        billing.check_can_add_order(db.one("SELECT * FROM users WHERE id = ?", p["user_id"]), p["id"])
    token = pu.save_order(p, x_order_token, body.name, body.phone, body.comment, body.lines)
    return {"token": token, **pu.participant_view(p, pu.order_by_token(p, token))}


class PaidIn(BaseModel):
    paid: bool = True


@app.post("/api/z/{slug}/paid")
def public_paid(slug: str, body: PaidIn, x_order_token: str | None = Header(None)):
    p = pu.public_purchase(slug)
    order = pu.order_by_token(p, x_order_token)
    if not order:
        raise HTTPException(404, "Заказ не найден — откройте свою личную ссылку.")
    pu.mark_says_paid(order, body.paid)
    return pu.participant_view(p, pu.order_by_token(p, x_order_token))


@app.delete("/api/z/{slug}/order")
def public_cancel(slug: str, x_order_token: str | None = Header(None)):
    p = pu.public_purchase(slug)
    order = pu.order_by_token(p, x_order_token)
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


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(WEB_DIR / "static" / "manifest.webmanifest", media_type="application/manifest+json")
