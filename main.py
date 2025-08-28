import os, asyncio, time, csv, json, tarfile, datetime, io, requests
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import Command
from pyairtable import Table
from dotenv import load_dotenv
import schedule

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
AIRTABLE_API_KEY = os.environ["AIRTABLE_API_KEY"]
AIRTABLE_BASE_ID = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE_SALES = os.environ.get("AIRTABLE_TABLE_SALES","sales")
MENU_PRESETS = [x.strip() for x in os.environ.get("MENU_PRESETS","").split(",") if x.strip()]
BACKUP_TABLES = [x.strip() for x in os.environ.get("BACKUP_TABLES", AIRTABLE_TABLE_SALES).split(",")]
BACKUP_CRON = os.environ.get("BACKUP_CRON","0 3 * * *").strip()

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

sales_tbl = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_SALES)

def menu_kb():
    if not MENU_PRESETS: return None
    rows, row = [], []
    for item in MENU_PRESETS:
        if ";" in item:
            name, price = item.split(";",1)
        else:
            name, price = item, "0"
        row.append(KeyboardButton(text=f"{name} ({price})"))
        if len(row)==2:
            rows.append(row); row=[]
    if row: rows.append(row)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

@dp.message(Command("start"))
async def start(m: Message):
    txt = ("Hello! This is an order bot.\n"
           "Use `/order Name;Qty;Price`.\n"
           "Example: `/order Americano;2;90`")
    await m.answer(txt, reply_markup=menu_kb(), parse_mode="Markdown")

@dp.message(Command("order"))
async def order(m: Message):
    text = m.text[len("/order"):].strip()
    if text.startswith("@"):
        text = text.split(" ",1)[1] if " " in text else ""
    parts = [p.strip() for p in text.split(";")]
    if len(parts)!=3:
        return await m.reply("Format: /order Name;Qty;Price")
    name, qty_s, price_s = parts
    try:
        qty=float(qty_s.replace(",",".")); price=float(price_s.replace(",","."))
    except ValueError:
        return await m.reply("Qty and Price must be numbers.")
    total = round(qty*price,2)
    rec = {"timestamp": datetime.datetime.utcnow().isoformat(),
           "user_id": str(m.from_user.id), "item": name, "qty": qty, "price": price, "sum": total}
    try:
        sales_tbl.create(rec)
    except Exception as e:
        return await m.reply(f"Write error: {e}")
    await m.reply(f"Order received: {name} × {qty} @ {price} = {total}")
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(ADMIN_CHAT_ID, f"New order: {rec}")
        except Exception:
            pass

@dp.message(F.text)
async def buttons(m: Message):
    t=m.text.strip()
    if "(" in t and t.endswith(")"):
        name=t[:t.rfind("(")].strip()
        price=t[t.rfind("(")+1:-1].strip()
        m.text=f"/order {name};1;{price}"
        return await order(m)
    await m.reply("Use /order or preset buttons.")

# -------- Backup job (runs in background via schedule) --------
def airtable_export_and_send():
    day = datetime.date.today().isoformat()
    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode="w:gz") as tar:
        for tname in BACKUP_TABLES:
            tbl = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, tname)
            rows = tbl.all()
            fields = sorted(set().union(*[r["fields"].keys() for r in rows])) if rows else []
            csv_buf = io.StringIO()
            w = csv.DictWriter(csv_buf, fieldnames=["id"]+fields)
            w.writeheader()
            for r in rows:
                data={"id": r["id"]}; data.update(r["fields"]); w.writerow(data)
            csv_bytes = csv_buf.getvalue().encode("utf-8")
            info = tarfile.TarInfo(name=f"{day}/{tname}.csv"); info.size=len(csv_bytes)
            tar.addfile(info, io.BytesIO(csv_bytes))
            json_bytes = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
            info = tarfile.TarInfo(name=f"{day}/{tname}.json"); info.size=len(json_bytes)
            tar.addfile(info, io.BytesIO(json_bytes))
    tar_bytes.seek(0)
    if ADMIN_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            files = {"document": ("airtable_backup_%s.tar.gz" % day, tar_bytes, "application/gzip")}
            data = {"chat_id": ADMIN_CHAT_ID, "caption": f"Airtable backup {day}"}
            requests.post(url, data=data, files=files, timeout=60)
        except Exception as e:
            print("Backup send failed:", e)

def schedule_parse(expr: str):
    parts = expr.split()
    if len(parts)==5 and parts[2]==parts[3]==parts[4]=="*":
        return int(parts[1]), int(parts[0])
    return 3,0

def run_scheduler():
    h,m = schedule_parse(BACKUP_CRON)
    schedule.every().day.at(f"{h:02d}:{m:02d}").do(airtable_export_and_send)
    print(f"[scheduler] daily backup at {h:02d}:{m:02d}")
    while True:
        schedule.run_pending()
        time.sleep(1)

async def main():
    import threading
    threading.Thread(target=run_scheduler, daemon=True).start()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
