"""Настройки из переменных окружения (см. .env.example)."""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


SECRET = _env("LOTLINE_SECRET")
if not SECRET:
    SECRET = secrets.token_hex(32)
    print("ВНИМАНИЕ: LOTLINE_SECRET не задан — сессии сбросятся при перезапуске.", file=sys.stderr)

DB_PATH = Path(_env("LOTLINE_DB", str(ROOT / "data" / "lotline.sqlite3")))
DATA_PATH = Path(_env("LOTLINE_DATA", str(ROOT / "data" / "data.json")))
TEMPLATE_PATH = ROOT / "web" / "template.html"
ADMIN_EMAILS = {e.strip().lower() for e in _env("LOTLINE_ADMIN_EMAILS").split(",") if e.strip()}
# demo — тестовая активация без списания денег; yookassa — оплата через ЮKassa; off — оплата выключена.
PAYMENTS = _env("LOTLINE_PAYMENTS", "demo").lower()
SECURE_COOKIES = _env("LOTLINE_SECURE_COOKIES", "0") == "1"
PUBLIC_URL = _env("LOTLINE_PUBLIC_URL", "http://localhost:8000").rstrip("/")
YOOKASSA_SHOP_ID = _env("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = _env("YOOKASSA_SECRET_KEY")
SESSION_DAYS = 30
