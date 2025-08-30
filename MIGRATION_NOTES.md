# MIGRATION_NOTES

Этот пакет **заменяет** все предыдущие архивы по боту (airtable_bot_v2_final.zip, airtable_bot_v2_clean.zip и т.п.).
Используй только **juice-bot.zip**.

Что изменилось:
- Чистая структура без .venv/.env.
- Добавлены README.md и .env.example.
- Имена переменных окружения согласованы с кодом: BOT_TOKEN, BOT_ADMIN_CHAT_ID, AIRTABLE_API_KEY, AIRTABLE_BASE_ID, TABLE_MENU, TABLE_SALES, TABLE_CLIENTS.
- Точка входа: `python main.py` (aiogram polling).
