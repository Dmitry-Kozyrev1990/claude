"""SQLite: пользователи, сессии, подписки, платежи, коллекции, избранное.

Для пилота с инвестором SQLite достаточно; файл базы лежит в томе Docker. Переход на
PostgreSQL — замена этого модуля (схема переносится как есть).
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
    is_admin INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
    source TEXT NOT NULL, payment_id INTEGER REFERENCES payments(id));
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL, duration TEXT NOT NULL, amount_rub INTEGER NOT NULL, status TEXT NOT NULL,
    provider TEXT NOT NULL, provider_id TEXT, created_at TEXT NOT NULL, paid_at TEXT);
CREATE TABLE IF NOT EXISTS collection (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    variant TEXT NOT NULL, bought_on TEXT NOT NULL, price REAL NOT NULL, currency TEXT NOT NULL,
    bought_usd REAL NOT NULL, note TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS watchlist (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, kind TEXT NOT NULL, ref TEXT NOT NULL,
    created_at TEXT NOT NULL, PRIMARY KEY (user_id, kind, ref));
CREATE INDEX IF NOT EXISTS subscriptions_user ON subscriptions(user_id, ends_at);
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
