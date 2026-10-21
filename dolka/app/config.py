"""Настройки из переменных окружения (см. .env.example)."""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


SECRET = _env("DOLKA_SECRET")
if not SECRET:
    SECRET = secrets.token_hex(32)
    print("ВНИМАНИЕ: DOLKA_SECRET не задан — сессии сбросятся при перезапуске.", file=sys.stderr)

DB_PATH = Path(_env("DOLKA_DB", str(ROOT / "data" / "dolka.sqlite3")))
WEB_DIR = ROOT / "web"
# demo — тестовая активация без списания денег; yookassa — оплата через ЮKassa; off — оплата выключена.
PAYMENTS = _env("DOLKA_PAYMENTS", "demo").lower()
SECURE_COOKIES = _env("DOLKA_SECURE_COOKIES", "0") == "1"
PUBLIC_URL = _env("DOLKA_PUBLIC_URL", "http://localhost:8000").rstrip("/")
YOOKASSA_SHOP_ID = _env("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = _env("YOOKASSA_SECRET_KEY")
SESSION_DAYS = 60

# Telegram-бот и мини-приложение (см. README, раздел «Telegram»). Без токена мини-приложение выключено.
TG_BOT_TOKEN = _env("TG_BOT_TOKEN")
TG_BOT_USERNAME = _env("TG_BOT_USERNAME").lstrip("@")
TG_WEBHOOK_SECRET = _env("TG_WEBHOOK_SECRET")
