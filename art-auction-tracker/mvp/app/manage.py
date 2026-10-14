"""Обслуживание сервера.

    python -m app.manage create-admin почта пароль     # администратор
    python -m app.manage grant почта collector 30      # выдать тариф на N дней
    python -m app.manage build                          # пересобрать данные (data/data.json)
    python -m app.manage users                          # список пользователей
    python -m app.manage backup                         # копия базы рядом с ней (/data/backup-…)
"""
from __future__ import annotations

import argparse
import sys

from . import auth, billing, db


def main(argv=None):
    ap = argparse.ArgumentParser(prog="app.manage")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("create-admin")
    a.add_argument("email")
    a.add_argument("password")
    g = sub.add_parser("grant")
    g.add_argument("email")
    g.add_argument("plan", choices=["collector", "pro"])
    g.add_argument("days", type=int)
    sub.add_parser("build")
    sub.add_parser("users")
    sub.add_parser("backup")
    args = ap.parse_args(argv)
    db.init()
    if args.cmd == "create-admin":
        row = db.one("SELECT id FROM users WHERE email = ?", args.email.lower())
        try:
            uid = row["id"] if row else auth.register(args.email, args.password)
        except auth.AuthError as e:
            sys.exit(str(e))
        with db.tx() as c:
            c.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (uid,))
        print(f"Администратор: {args.email}")
    elif args.cmd == "grant":
        row = db.one("SELECT id FROM users WHERE email = ?", args.email.lower())
        if not row:
            sys.exit("Пользователь не найден: сначала он регистрируется на сайте.")
        print("Тариф до", billing.grant(row["id"], args.plan, args.days, "admin"))
    elif args.cmd == "build":
        from arttracker import build
        data = build.run("demo")
        build.write(data)
        print("Данные пересобраны: data/data.json. Перезапустите сервер.")
    elif args.cmd == "backup":
        import sqlite3
        from datetime import datetime
        from .config import DB_PATH
        target = DB_PATH.with_name(f"backup-{datetime.now():%Y%m%d-%H%M%S}.sqlite3")
        with sqlite3.connect(target) as dst:
            db.conn().backup(dst)  # согласованная копия даже при работающем сервере
        print(f"Копия базы: {target}")
    elif args.cmd == "users":
        for r in db.all_("SELECT id, email, created_at, is_admin FROM users ORDER BY id"):
            print(r["id"], r["email"], r["created_at"], "админ" if r["is_admin"] else "",
                  billing.current_plan(r))


if __name__ == "__main__":
    main()
