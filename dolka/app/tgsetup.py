"""Настройка бота одной командой (после того как сервер доступен по HTTPS):

    python -m app.tgsetup

Ставит вебхук с секретом, кнопку меню «Открыть» с мини-приложением, команды и описание.
Главное мини-приложение (ссылки t.me/<бот>?startapp=...) включается вручную в @BotFather —
см. README, раздел «Telegram».
"""
from __future__ import annotations

import sys

from . import tg
from .config import PUBLIC_URL, TG_BOT_USERNAME, TG_WEBHOOK_SECRET


def main() -> int:
    if not tg.enabled() or not TG_WEBHOOK_SECRET:
        print("Задайте TG_BOT_TOKEN и TG_WEBHOOK_SECRET в .env", file=sys.stderr)
        return 1
    if not PUBLIC_URL.startswith("https://"):
        print("DOLKA_PUBLIC_URL должен быть https:// — Telegram открывает мини-приложения только по HTTPS",
              file=sys.stderr)
        return 1
    me = tg.call("getMe")
    print(f"Бот: @{me['username']}")
    if TG_BOT_USERNAME and TG_BOT_USERNAME.lower() != me["username"].lower():
        print(f"ВНИМАНИЕ: TG_BOT_USERNAME={TG_BOT_USERNAME}, а токен от @{me['username']}", file=sys.stderr)
    tg.call("setWebhook", url=f"{PUBLIC_URL}/api/tg/webhook", secret_token=TG_WEBHOOK_SECRET,
            allowed_updates=["message", "pre_checkout_query"], drop_pending_updates=True)
    tg.call("setChatMenuButton", menu_button={"type": "web_app", "text": "Открыть",
                                              "web_app": {"url": tg.webapp_url()}})
    tg.call("setMyCommands", commands=[{"command": "start", "description": "Открыть «Дольку»"}])
    tg.call("setMyShortDescription", short_description="Совместные закупки продуктов: заказы, коробки, оплаты, раздача.")
    tg.call("setMyDescription", description=tg.WELCOME)
    print(f"Вебхук: {PUBLIC_URL}/api/tg/webhook\nМини-приложение: {tg.webapp_url()}")
    print("Осталось в @BotFather: /mybots → бот → Bot Settings → Configure Mini App → Enable Mini App, "
          f"URL: {tg.webapp_url()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
