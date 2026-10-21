"""Закупки: позиции, заказы участников, коробки («ряды»), факт по весу, оплаты и раздача.

Термины совместных покупок:
- коробка (ряд) — упаковка поставщика, которую надо набрать целиком (pack_milli), 0 — без коробок;
- шаг — сколько минимум и кратно чему заказывает участник (step_milli): 1 шт, 0,5 кг;
- оргсбор — процент организатора сверху суммы товара;
- факт — сколько реально приехало участнику (весовой товар), по нему пересчитывается сумма.
"""
from __future__ import annotations

import csv
import io
import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from . import auth, db, tg

TZ = ZoneInfo("Europe/Moscow")
STATUSES = {
    "open": "Сбор заказов",
    "stopped": "Стоп, ждём оплату",
    "ordered": "Заказано у поставщика",
    "arrived": "Приехало, раздача",
    "closed": "Закрыта",
}
UNITS = ("шт", "кг", "г", "л", "уп", "пачка", "банка", "бут", "мешок", "коробка")
MAX_MILLI = 1_000_000 * 1000
SLUG_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


class PurchaseError(Exception):
    pass


# ---------- числа ----------

def to_milli(value, field: str = "Количество") -> int:
    """'1,5' / 1.5 / '2' → 1500 / 1500 / 2000. Больше трёх знаков после запятой не принимаем."""
    if value is None or value == "":
        return 0
    try:
        d = Decimal(str(value).replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        raise PurchaseError(f"{field}: не число.")
    milli = d * 1000
    if milli != milli.to_integral_value():
        raise PurchaseError(f"{field}: не больше трёх знаков после запятой.")
    milli = int(milli)
    if milli < 0 or milli > MAX_MILLI:
        raise PurchaseError(f"{field}: недопустимое значение.")
    return milli


def to_kop(value, field: str = "Цена") -> int:
    try:
        d = Decimal(str(value).replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        raise PurchaseError(f"{field}: не число.")
    kop = d * 100
    if kop != kop.to_integral_value() or kop < 0 or kop > 100_000_000_00:
        raise PurchaseError(f"{field}: укажите сумму в рублях, до копеек.")
    return int(kop)


def line_kop(price_kop: int, milli: int) -> int:
    """Стоимость строки, округление до копейки «половина вверх»."""
    return (price_kop * milli + 500) // 1000


def fee_kop(goods_kop: int, fee_pct: float) -> int:
    return int((Decimal(goods_kop) * Decimal(str(fee_pct)) / 100).quantize(Decimal(1), rounding="ROUND_HALF_UP"))


def fmt_milli(milli: int) -> str:
    s = f"{Decimal(milli) / 1000:f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def fmt_rub(kop: int) -> str:
    rub, k = divmod(abs(kop), 100)
    s = f"{rub:,}".replace(",", " ") + (f",{k:02d}" if k else "")
    return ("−" if kop < 0 else "") + s + " ₽"


# ---------- закупка ----------

def new_slug() -> str:
    while True:
        slug = "".join(secrets.choice(SLUG_ALPHABET) for _ in range(8))
        if not db.one("SELECT 1 FROM purchases WHERE slug = ?", slug):
            return slug


def parse_deadline(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        raise PurchaseError("Стоп: укажите дату и время.")
    return dt.replace(tzinfo=None).isoformat(timespec="minutes")


def deadline_passed(p) -> bool:
    if not p["deadline"]:
        return False
    return datetime.now(TZ).replace(tzinfo=None) > datetime.fromisoformat(p["deadline"])


def accepting_orders(p) -> bool:
    return p["status"] == "open" and not deadline_passed(p)


def clean_purchase_fields(data: dict) -> dict:
    out = {}
    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            raise PurchaseError("Назовите закупку.")
        out["title"] = title[:120]
    for key, limit in (("supplier", 200), ("description", 4000), ("pickup", 1000), ("pay_info", 1000)):
        if key in data:
            out[key] = (data[key] or "").strip()[:limit]
    if "deadline" in data:
        out["deadline"] = parse_deadline(data["deadline"])
    if "min_total" in data:
        out["min_total_kop"] = to_kop(data["min_total"] or 0, "Минимальная сумма заказа")
    if "fee_pct" in data:
        fee = Decimal(str(data["fee_pct"] or 0).replace(",", "."))
        if fee < 0 or fee > 50:
            raise PurchaseError("Оргсбор — от 0 до 50%.")
        out["fee_pct"] = float(fee)
    if "status" in data:
        if data["status"] not in STATUSES:
            raise PurchaseError("Неизвестный статус.")
        out["status"] = data["status"]
    return out


def create_purchase(user_id: int, data: dict) -> int:
    fields = clean_purchase_fields({"title": data.get("title", ""), **data})
    fields.pop("status", None)
    cols = ["user_id", "slug", "created_at", *fields]
    vals = [user_id, new_slug(), db.now(), *fields.values()]
    with db.tx() as c:
        return c.execute(f"INSERT INTO purchases ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                         vals).lastrowid


def update_purchase(pid: int, data: dict):
    fields = clean_purchase_fields(data)
    if not fields:
        return
    with db.tx() as c:
        c.execute(f"UPDATE purchases SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                  (*fields.values(), pid))


def copy_purchase(p, user_id: int) -> int:
    """«Повторить закупку»: те же поставщик, позиции и условия, новые заказы и стоп."""
    new_id = create_purchase(user_id, {
        "title": p["title"], "supplier": p["supplier"], "description": p["description"],
        "pickup": p["pickup"], "pay_info": p["pay_info"],
        "min_total": Decimal(p["min_total_kop"]) / 100, "fee_pct": p["fee_pct"]})
    with db.tx() as c:
        c.execute("""INSERT INTO items (purchase_id, name, unit, price_kop, step_milli, pack_milli, sort)
                     SELECT ?, name, unit, price_kop, step_milli, pack_milli, sort FROM items WHERE purchase_id = ?""",
                  (new_id, p["id"]))
    return new_id


def owned_purchase(pid: int, user_id: int):
    p = db.one("SELECT * FROM purchases WHERE id = ? AND user_id = ?", pid, user_id)
    if not p:
        raise LookupError
    return p


# ---------- позиции ----------

def clean_item(data: dict) -> dict:
    name = (data.get("name") or "").strip()[:200]
    if not name:
        raise PurchaseError("Назовите позицию.")
    unit = (data.get("unit") or "шт").strip()[:20] or "шт"
    price = to_kop(data.get("price"), "Цена")
    if price <= 0:
        raise PurchaseError("Цена должна быть больше нуля.")
    step = to_milli(data.get("step") or 1, "Шаг заказа")
    if step <= 0:
        raise PurchaseError("Шаг заказа должен быть больше нуля.")
    pack = to_milli(data.get("pack") or 0, "Коробка")
    if pack and pack % step:
        raise PurchaseError("Коробка должна делиться на шаг заказа без остатка.")
    return {"name": name, "unit": unit, "price_kop": price, "step_milli": step, "pack_milli": pack}


def add_item(pid: int, data: dict) -> int:
    item = clean_item(data)
    sort = db.one("SELECT COALESCE(MAX(sort), 0) + 1 AS s FROM items WHERE purchase_id = ?", pid)["s"]
    with db.tx() as c:
        return c.execute("INSERT INTO items (purchase_id, name, unit, price_kop, step_milli, pack_milli, sort) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (pid, *item.values(), sort)).lastrowid


def update_item(item_id: int, data: dict):
    item = clean_item(data)
    bad = db.one("SELECT 1 FROM order_lines WHERE item_id = ? AND qty_milli % ? != 0", item_id, item["step_milli"])
    if bad:
        raise PurchaseError("Уже есть заказы, которые не делятся на новый шаг. Оставьте прежний шаг.")
    with db.tx() as c:
        c.execute("UPDATE items SET name = ?, unit = ?, price_kop = ?, step_milli = ?, pack_milli = ? WHERE id = ?",
                  (*item.values(), item_id))


def owned_item(item_id: int, user_id: int):
    row = db.one("""SELECT i.*, p.user_id, p.status FROM items i JOIN purchases p ON p.id = i.purchase_id
                    WHERE i.id = ? AND p.user_id = ?""", item_id, user_id)
    if not row:
        raise LookupError
    return row


def delete_item(item_id: int):
    with db.tx() as c:
        c.execute("DELETE FROM items WHERE id = ?", (item_id,))


def trim_to_packs(item) -> list[dict]:
    """Не набралась коробка: снимаем остаток с самых поздних заказов (как принято в СП)."""
    pack = item["pack_milli"]
    if not pack:
        raise PurchaseError("У позиции нет коробки — обрезать нечего.")
    lines = db.all_("""SELECT l.order_id, l.qty_milli, o.name FROM order_lines l JOIN orders o ON o.id = l.order_id
                       WHERE l.item_id = ? ORDER BY o.created_at DESC, o.id DESC""", item["id"])
    left = sum(r["qty_milli"] for r in lines) % pack
    removed = []
    with db.tx() as c:
        for r in lines:
            if not left:
                break
            take = min(r["qty_milli"], left)
            left -= take
            if take == r["qty_milli"]:
                c.execute("DELETE FROM order_lines WHERE order_id = ? AND item_id = ?", (r["order_id"], item["id"]))
            else:
                c.execute("UPDATE order_lines SET qty_milli = qty_milli - ? WHERE order_id = ? AND item_id = ?",
                          (take, r["order_id"], item["id"]))
            removed.append({"order_id": r["order_id"], "name": r["name"], "removed": fmt_milli(take)})
    return removed


# ---------- заказы участников ----------

def public_purchase(slug: str):
    p = db.one("SELECT * FROM purchases WHERE slug = ?", slug)
    if not p:
        raise LookupError
    return p


def order_by_token(p, token: str | None):
    if not token:
        return None
    return db.one("SELECT * FROM orders WHERE purchase_id = ? AND token_hash = ?", p["id"], auth.token_hash(token))


def order_by_tg(p, tg_id: int | None):
    """В мини-приложении Telegram заказ привязан к аккаунту участника, а не к личной ссылке."""
    if not tg_id:
        return None
    return db.one("SELECT * FROM orders WHERE purchase_id = ? AND tg_id = ?", p["id"], tg_id)


def clean_lines(p, raw: dict) -> dict[int, int]:
    items = {r["id"]: r for r in db.all_("SELECT * FROM items WHERE purchase_id = ?", p["id"])}
    lines = {}
    for key, value in (raw or {}).items():
        try:
            item = items[int(key)]
        except (KeyError, ValueError):
            raise PurchaseError("Позиция не найдена — обновите страницу.")
        milli = to_milli(value, item["name"])
        if not milli:
            continue
        if milli % item["step_milli"]:
            raise PurchaseError(f"«{item['name']}»: заказ кратен {fmt_milli(item['step_milli'])} {item['unit']}.")
        lines[item["id"]] = milli
    return lines


def save_order(p, existing, name: str, phone: str, comment: str, raw_lines: dict,
               tg_id: int | None = None) -> tuple[int, str | None]:
    """Создаёт или меняет заказ участника. Возвращает (id заказа, токен личной ссылки — только для нового)."""
    if not accepting_orders(p):
        raise PurchaseError("Сбор заказов закрыт.")
    name = (name or "").strip()[:80]
    if not name:
        raise PurchaseError("Укажите имя или ник, как в чате.")
    phone = (phone or "").strip()[:30]
    comment = (comment or "").strip()[:500]
    lines = clean_lines(p, raw_lines)
    if not lines:
        raise PurchaseError("Выберите хотя бы одну позицию.")
    token = None
    with db.tx() as c:
        if existing:
            oid = existing["id"]
            c.execute("UPDATE orders SET name = ?, phone = ?, comment = ?, updated_at = ? WHERE id = ?",
                      (name, phone, comment, db.now(), oid))
            c.execute("DELETE FROM order_lines WHERE order_id = ?", (oid,))
        else:
            token = secrets.token_urlsafe(18)
            oid = c.execute("INSERT INTO orders (purchase_id, token_hash, name, phone, comment, tg_id, created_at, "
                            "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (p["id"], auth.token_hash(token), name, phone, comment, tg_id, db.now(), db.now())).lastrowid
        c.executemany("INSERT INTO order_lines (order_id, item_id, qty_milli) VALUES (?, ?, ?)",
                      [(oid, i, q) for i, q in lines.items()])
    return oid, token


def cancel_order(p, order):
    if not accepting_orders(p):
        raise PurchaseError("Сбор закрыт — отменить заказ может только организатор.")
    with db.tx() as c:
        c.execute("DELETE FROM orders WHERE id = ?", (order["id"],))


def mark_says_paid(order, value: bool):
    with db.tx() as c:
        c.execute("UPDATE orders SET says_paid = ?, updated_at = ? WHERE id = ?", (int(value), db.now(), order["id"]))


def owned_order(order_id: int, user_id: int):
    row = db.one("""SELECT o.* FROM orders o JOIN purchases p ON p.id = o.purchase_id
                    WHERE o.id = ? AND p.user_id = ?""", order_id, user_id)
    if not row:
        raise LookupError
    return row


def update_order_admin(order, data: dict):
    """Организатор: сколько заплатил, выдан ли заказ, факт по весу, правка количества."""
    with db.tx() as c:
        if "paid" in data:
            c.execute("UPDATE orders SET paid_kop = ? WHERE id = ?", (to_kop(data["paid"] or 0, "Оплачено"), order["id"]))
        if "picked_up" in data:
            c.execute("UPDATE orders SET picked_up = ? WHERE id = ?", (int(bool(data["picked_up"])), order["id"]))
        for key, value in (data.get("facts") or {}).items():
            fact = None if value in (None, "") else to_milli(value, "Факт")
            c.execute("UPDATE order_lines SET fact_milli = ? WHERE order_id = ? AND item_id = ?",
                      (fact, order["id"], int(key)))
        for key, value in (data.get("qty") or {}).items():
            item = db.one("SELECT * FROM items WHERE id = ? AND purchase_id = ?", int(key), order["purchase_id"])
            if not item:
                raise PurchaseError("Позиция не найдена.")
            milli = to_milli(value, item["name"])
            if milli % item["step_milli"]:
                raise PurchaseError(f"«{item['name']}»: количество кратно {fmt_milli(item['step_milli'])} {item['unit']}.")
            if milli:
                c.execute("INSERT INTO order_lines (order_id, item_id, qty_milli) VALUES (?, ?, ?) "
                          "ON CONFLICT (order_id, item_id) DO UPDATE SET qty_milli = excluded.qty_milli",
                          (order["id"], int(key), milli))
            else:
                c.execute("DELETE FROM order_lines WHERE order_id = ? AND item_id = ?", (order["id"], int(key)))
        c.execute("UPDATE orders SET updated_at = ? WHERE id = ?", (db.now(), order["id"]))


def delete_order(order):
    with db.tx() as c:
        c.execute("DELETE FROM orders WHERE id = ?", (order["id"],))


# ---------- расчёты и представления ----------

def _items(pid: int) -> list:
    return db.all_("SELECT * FROM items WHERE purchase_id = ? ORDER BY sort, id", pid)


def _lines(pid: int) -> list:
    return db.all_("""SELECT l.* FROM order_lines l JOIN orders o ON o.id = l.order_id
                      WHERE o.purchase_id = ?""", pid)


def item_stats(item, total_milli: int) -> dict:
    pack = item["pack_milli"]
    d = {"id": item["id"], "name": item["name"], "unit": item["unit"], "price_kop": item["price_kop"],
         "step": fmt_milli(item["step_milli"]), "pack": fmt_milli(pack) if pack else "",
         "total": fmt_milli(total_milli), "total_milli": total_milli,
         "sum_kop": line_kop(item["price_kop"], total_milli)}
    if pack:
        rest = total_milli % pack
        d.update(packs=total_milli // pack, missing=fmt_milli(pack - rest) if rest else "",
                 missing_milli=pack - rest if rest else 0)
    return d


def order_totals(lines: list[dict], items: dict, fee_pct: float) -> dict:
    goods = sum(line_kop(items[l["item_id"]]["price_kop"],
                         l["fact_milli"] if l["fact_milli"] is not None else l["qty_milli"]) for l in lines)
    fee = fee_kop(goods, fee_pct)
    return {"goods_kop": goods, "fee_kop": fee, "total_kop": goods + fee}


def _order_dict(o, lines: list, items: dict, fee_pct: float) -> dict:
    tot = order_totals(lines, items, fee_pct)
    return {
        "id": o["id"], "name": o["name"], "phone": o["phone"], "comment": o["comment"],
        "paid_kop": o["paid_kop"], "says_paid": bool(o["says_paid"]), "picked_up": bool(o["picked_up"]),
        "created_at": o["created_at"], **tot, "balance_kop": tot["total_kop"] - o["paid_kop"],
        "lines": [{"item_id": l["item_id"], "qty": fmt_milli(l["qty_milli"]),
                   "fact": fmt_milli(l["fact_milli"]) if l["fact_milli"] is not None else "",
                   "sum_kop": line_kop(items[l["item_id"]]["price_kop"],
                                       l["fact_milli"] if l["fact_milli"] is not None else l["qty_milli"])}
                  for l in lines],
    }


def _base(p) -> dict:
    return {"slug": p["slug"], "title": p["title"], "supplier": p["supplier"], "description": p["description"],
            "deadline": p["deadline"], "min_total_kop": p["min_total_kop"], "fee_pct": p["fee_pct"],
            "pickup": p["pickup"], "pay_info": p["pay_info"], "status": p["status"],
            "status_name": STATUSES[p["status"]], "accepting": accepting_orders(p), "tg_link": tg.start_link(p["slug"])}


def owner_view(p) -> dict:
    items = _items(p["id"])
    by_id = {i["id"]: i for i in items}
    lines = [dict(l) for l in _lines(p["id"])]
    by_order: dict[int, list] = {}
    totals: dict[int, int] = {}
    for l in lines:
        by_order.setdefault(l["order_id"], []).append(l)
        totals[l["item_id"]] = totals.get(l["item_id"], 0) + l["qty_milli"]
    orders = [_order_dict(o, by_order.get(o["id"], []), by_id, p["fee_pct"])
              for o in db.all_("SELECT * FROM orders WHERE purchase_id = ? ORDER BY created_at, id", p["id"])]
    stats = [item_stats(i, totals.get(i["id"], 0)) for i in items]
    supplier_kop = sum(s["sum_kop"] for s in stats)
    return {
        **_base(p), "id": p["id"], "created_at": p["created_at"],
        "items": [{**s, "step_milli": i["step_milli"], "pack_milli": i["pack_milli"]} for s, i in zip(stats, items)],
        "orders": orders,
        "summary": {
            "participants": len(orders), "supplier_kop": supplier_kop,
            "goods_kop": sum(o["goods_kop"] for o in orders), "fee_kop": sum(o["fee_kop"] for o in orders),
            "total_kop": sum(o["total_kop"] for o in orders), "paid_kop": sum(o["paid_kop"] for o in orders),
            "debt_kop": sum(max(o["balance_kop"], 0) for o in orders),
            "unpaid": sum(1 for o in orders if o["balance_kop"] > 0),
            "picked_up": sum(1 for o in orders if o["picked_up"]),
            "min_reached": supplier_kop >= p["min_total_kop"],
            "packs_open": sum(1 for s in stats if s.get("missing_milli")),
        },
    }


def participant_view(p, order=None) -> dict:
    """Публичная страница: позиции, заполнение коробок, прогресс к минималке — без чужих имён."""
    items = _items(p["id"])
    by_id = {i["id"]: i for i in items}
    totals: dict[int, int] = {}
    for l in _lines(p["id"]):
        totals[l["item_id"]] = totals.get(l["item_id"], 0) + l["qty_milli"]
    stats = [item_stats(i, totals.get(i["id"], 0)) for i in items]
    supplier_kop = sum(s["sum_kop"] for s in stats)
    count = db.one("SELECT COUNT(*) AS n FROM orders WHERE purchase_id = ?", p["id"])["n"]
    mine = None
    if order:
        mine = _order_dict(order, [dict(l) for l in db.all_("SELECT * FROM order_lines WHERE order_id = ?", order["id"])],
                           by_id, p["fee_pct"])
    return {**_base(p), "items": stats, "participants": count,
            "progress_kop": supplier_kop, "min_reached": supplier_kop >= p["min_total_kop"], "my_order": mine}


def list_purchases(user_id: int) -> list[dict]:
    rows = db.all_("""SELECT p.*, (SELECT COUNT(*) FROM orders o WHERE o.purchase_id = p.id) AS participants
                      FROM purchases p WHERE user_id = ? ORDER BY (status = 'closed'), created_at DESC""", user_id)
    return [{**_base(r), "id": r["id"], "participants": r["participants"], "created_at": r["created_at"]} for r in rows]


# ---------- выгрузки ----------

def _csv(rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerows(rows)
    return "﻿" + buf.getvalue()  # BOM — чтобы Excel открыл кириллицу


def supplier_csv(p) -> str:
    v = owner_view(p)
    rows = [["Позиция", "Ед.", "Количество", "Коробок", "Не хватает до коробки", "Цена, ₽", "Сумма, ₽"]]
    for i in v["items"]:
        if i["total_milli"]:
            rows.append([i["name"], i["unit"], i["total"], i.get("packs", ""), i.get("missing", ""),
                         f"{i['price_kop'] / 100:.2f}".replace(".", ","), f"{i['sum_kop'] / 100:.2f}".replace(".", ",")])
    rows.append(["Итого", "", "", "", "", "", f"{v['summary']['supplier_kop'] / 100:.2f}".replace(".", ",")])
    return _csv(rows)


def orders_csv(p) -> str:
    v = owner_view(p)
    names = {i["id"]: i for i in v["items"]}
    rows = [["Участник", "Телефон", "Позиция", "Заказано", "Факт", "Сумма, ₽", "Итого с оргсбором, ₽",
             "Оплачено, ₽", "Долг, ₽", "Выдано"]]
    for o in v["orders"]:
        for n, l in enumerate(o["lines"]):
            it = names[l["item_id"]]
            first = n == 0
            rows.append([o["name"] if first else "", o["phone"] if first else "", it["name"],
                         f"{l['qty']} {it['unit']}", l["fact"], f"{l['sum_kop'] / 100:.2f}".replace(".", ","),
                         f"{o['total_kop'] / 100:.2f}".replace(".", ",") if first else "",
                         f"{o['paid_kop'] / 100:.2f}".replace(".", ",") if first else "",
                         f"{o['balance_kop'] / 100:.2f}".replace(".", ",") if first else "",
                         ("да" if o["picked_up"] else "нет") if first else ""])
    return _csv(rows)
