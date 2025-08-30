# juice-bot

Телеграм-бот на aiogram (polling), интеграция с Airtable.

## Быстрый старт (локально)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # заполни переменные
python main.py
```

## Railway
- Добавь переменные из `.env.example` в **Variables**
- Start Command: `python main.py`
- После деплоя в логах увидишь: `Bot started. Use /menu to test.`
```

