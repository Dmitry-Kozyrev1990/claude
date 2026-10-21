"""SQLite: организаторы, сессии, подписки, закупки, позиции, заказы участников.

Деньги хранятся в копейках (целые), количества — в тысячных долях единицы (qty_milli),
чтобы весовые товары (1,25 кг) считались без ошибок округления.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, pw_hash TEXT NOT NULL,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL, duration TEXT NOT NULL, amount_rub INTEGER NOT NULL, status TEXT NOT NULL,
    provider TEXT NOT NULL, provider_id TEXT, created_at TEXT NOT NULL, paid_at TEXT);
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
    source TEXT NOT NULL, payment_id INTEGER REFERENCES payments(id));
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL, supplier TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '', deadline TEXT, min_total_kop INTEGER NOT NULL DEFAULT 0,
    fee_pct REAL NOT NULL DEFAULT 0, pickup TEXT NOT NULL DEFAULT '', pay_info TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    name TEXT NOT NULL, unit TEXT NOT NULL, price_kop INTEGER NOT NULL,
    step_milli INTEGER NOT NULL DEFAULT 1000, pack_milli INTEGER NOT NULL DEFAULT 0,
    sort INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    token_hash TEXT UNIQUE NOT NULL, name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '', paid_kop INTEGER NOT NULL DEFAULT 0,
    says_paid INTEGER NOT NULL DEFAULT 0, picked_up INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS order_lines (
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    qty_milli INTEGER NOT NULL, fact_milli INTEGER,
    PRIMARY KEY (order_id, item_id));
CREATE INDEX IF NOT EXISTS subscriptions_user ON subscriptions(user_id, ends_at);
CREATE INDEX IF NOT EXISTS purchases_user ON purchases(user_id, status);
CREATE INDEX IF NOT EXISTS orders_purchase ON orders(purchase_id);
"""

_local = threading.local()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        _local.conn = c
    return c


def init():
    conn().executescript(SCHEMA)
    conn().commit()


@contextmanager
def tx():
    c = conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise


def one(sql: str, *args):
    return conn().execute(sql, args).fetchone()


def all_(sql: str, *args):
    return conn().execute(sql, args).fetchall()
