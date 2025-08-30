from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    BOT_ADMIN_CHAT_ID: int = int(os.getenv("BOT_ADMIN_CHAT_ID", "0"))
    AIRTABLE_API_KEY: str = os.getenv("AIRTABLE_API_KEY", "")
    AIRTABLE_BASE_ID: str = os.getenv("AIRTABLE_BASE_ID", "")
    TABLE_MENU: str = os.getenv("TABLE_MENU", "menu_all")
    TABLE_SALES: str = os.getenv("TABLE_SALES", "sales_skeleton")
    TABLE_CLIENTS: str = os.getenv("TABLE_CLIENTS", "clients_skeleton")
    PUBLIC_WEBHOOK_URL: str = os.getenv("PUBLIC_WEBHOOK_URL", "")
    WEBHOOK_SECRET_TOKEN: str = os.getenv("WEBHOOK_SECRET_TOKEN", "")

settings = Settings()
