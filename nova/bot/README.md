# Нова: бот для продажи курсов

Telegram-бот на Cloudflare Workers (бесплатный тариф): сегментация, каталог,
оплата через ЮKassa (карта и СБП), автоматическая выдача доступа, прогрев и
напоминания о неоплаченных заказах. ИИ внутри нет, платных зависимостей нет.

## Структура

- `src/content.ts` — все тексты, курсы и цены (правится здесь)
- `src/bot.ts` — сценарии бота, обработка платежей, фоновые задачи
- `src/yookassa.ts` — клиент ЮKassa
- `src/db.ts`, `schema.sql` — база D1
- `wrangler.toml` — конфигурация Worker

## Запуск (один раз)

1. Telegram: создайте бота в @BotFather, получите токен.
2. Cloudflare: зарегистрируйтесь (бесплатно), затем в `nova/bot`:
   ```
   npm install
   npx wrangler login
   npx wrangler d1 create nova-bot      # id вставьте в wrangler.toml
   npm run db:init
   ```
3. Заполните в `wrangler.toml` `BOT_USERNAME` и `SUPPORT_USERNAME`,
   а в `src/content.ts` замените все `REPLACE`.
4. Секреты (вводятся в терминале, в репозиторий не попадают):
   ```
   npx wrangler secret put BOT_TOKEN
   npx wrangler secret put WEBHOOK_SECRET   # длинная случайная строка
   npx wrangler secret put YK_SHOP_ID
   npx wrangler secret put YK_SECRET_KEY
   npx wrangler secret put ADMIN_ID         # ваш Telegram id
   npm run deploy
   ```
5. Подключите вебхуки (адрес Worker выведет `deploy`):
   - Telegram:
     `https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<worker>.workers.dev/tg/<WEBHOOK_SECRET>`
   - ЮKassa: личный кабинет → Интеграция → HTTP-уведомления →
     `https://<worker>.workers.dev/yookassa/<WEBHOOK_SECRET>`, события
     `payment.succeeded` и `payment.canceled`.
6. Закрытый канал курса: добавьте бота админом с правом приглашать, укажите
   `accessChatId` курса в `src/content.ts`. Тогда каждому покупателю выдаётся
   одноразовая ссылка.

## Автодеплой из GitHub

Добавьте в Settings → Secrets репозитория `CLOUDFLARE_API_TOKEN` и
`CLOUDFLARE_ACCOUNT_ID`. Дальше каждый пуш в `main`, затрагивающий `nova/bot/`,
деплоит бота (`.github/workflows/deploy-bot.yml`).

## Как это защищено

- Вебхуки ЮKassa не подписаны, поэтому бот перепроверяет платёж запросом к API
  и сверяет заказ и сумму. Доступ выдаётся только после этого.
- Повторный вебхук не выдаёт доступ дважды.
- Адреса вебхуков содержат секрет, а токены хранятся только в секретах Cloudflare.

## Перед запуском проверьте

- В ЮKassa включена оплата по СБП и настроены чеки (54-ФЗ). `VAT_CODE` в
  `wrangler.toml` соответствует вашей системе налогообложения.
- Есть оферта и политика возврата (ссылки в `src/content.ts`).
- Бот хранит только Telegram id, email и заказы; email нужен для чека.
  Если это персональные данные российских пользователей, учтите 152-ФЗ.
