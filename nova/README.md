# Нова — контент-фабрика

Исходники робота Новы (t.me/nova_family_ai). Посты, тексты и расписание — здесь; рендер и публикация — в облачной песочнице Composio по запланированным задачам.

- `content/cards.json` — HTML карточек (Telegram 1280×720, Instagram 1080×1350)
- `content/texts.json` — тексты постов (HTML для Telegram)
- `content/schedule.json` — что и когда публиковать
- `content/guide.html` — гайд «Безопасный ИИ дома: 8 правил»
- `studio/` — генераторы: персонаж (`nova_svg.py`) и сборщики карточек
- `publish.py` — рендер + публикация одного дня
