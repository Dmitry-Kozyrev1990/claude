"""Общие настройки тестов: временная база и чистые таблицы перед каждым тестом."""
from __future__ import annotations

import os
import tempfile

os.environ["DOLKA_DB"] = os.path.join(tempfile.mkdtemp(), "test.sqlite3")
os.environ["DOLKA_SECRET"] = "test"
os.environ["DOLKA_PAYMENTS"] = "demo"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402

H = {"X-Requested-With": "dolka"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        with db.tx() as conn:
            for t in ("order_lines", "orders", "items", "purchases", "subscriptions", "payments", "sessions", "users"):
                conn.execute(f"DELETE FROM {t}")
        yield c
