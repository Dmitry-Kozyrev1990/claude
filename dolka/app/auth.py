"""Пароли (PBKDF2-SHA256) и сессии (случайный токен в cookie, в базе — только его хэш)."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from . import db
from .config import SECRET, SESSION_DAYS

ITERATIONS = 260_000
COOKIE = "dolka_session"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, it, salt, hexdk = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(it))
    return hmac.compare_digest(dk.hex(), hexdk)


def token_hash(token: str) -> str:
    """Хэш секретного токена: сессии организатора и ссылки участника хранятся только так."""
    return hmac.new(SECRET.encode(), token.encode(), hashlib.sha256).hexdigest()


def register(email: str, password: str, name: str = "") -> int:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("Проверьте адрес почты.")
    if len(password or "") < 8:
        raise AuthError("Пароль должен быть не короче 8 символов.")
    if db.one("SELECT 1 FROM users WHERE email = ?", email):
        raise AuthError("Аккаунт с этой почтой уже есть. Войдите.")
    with db.tx() as c:
        cur = c.execute("INSERT INTO users (email, name, pw_hash, created_at) VALUES (?, ?, ?, ?)",
                        (email, (name or "").strip()[:80], hash_password(password), db.now()))
        return cur.lastrowid


def login(email: str, password: str) -> str:
    row = db.one("SELECT id, pw_hash FROM users WHERE email = ?", (email or "").strip().lower())
    if not row or not verify_password(password or "", row["pw_hash"]):
        raise AuthError("Неверная почта или пароль.")
    return new_session(row["id"])


def new_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    with db.tx() as c:
        c.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                  (token_hash(token), user_id, expires))
    return token


def logout(token: str | None):
    if token:
        with db.tx() as c:
            c.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))


def user_by_token(token: str | None):
    if not token:
        return None
    return db.one("""SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
                     WHERE s.token_hash = ? AND s.expires_at > ?""", token_hash(token), db.now())
