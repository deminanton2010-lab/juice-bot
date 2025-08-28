# Railway: Telegram Ordering Bot × Airtable (No-Docker, Single Service)

Deploys on Railway without Docker/Compose. One service runs:
- Telegram bot (aiogram, long polling)
- Daily Airtable backup (CSV+JSON) scheduled with `schedule`

## How to deploy on Railway
1) Create a new empty repo on GitHub (web UI: New → Repository → Name it, keep it Public or Private → Create).
2) Upload these files to the repo (web UI: Add file → Upload files → select all files from this folder).
3) Go to https://railway.app → New Project → Deploy from GitHub → select your repo.
4) After the first build, open your Service → Variables and add:
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_ADMIN_CHAT_ID (optional, for reports)
   - AIRTABLE_API_KEY
   - AIRTABLE_BASE_ID
   - AIRTABLE_TABLE_SALES (e.g. "sales")
   - MENU_PRESETS (e.g. "Americano;90,Latte;130")
   - BACKUP_CRON (default "0 3 * * *")
5) In the "Start Command" field set: `python main.py` (if not auto-detected).
6) Click "Deploy".
