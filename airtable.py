from typing import Any, Dict, List, Optional
import httpx
from config import settings

AIRTABLE_API_URL = "https://api.airtable.com/v0"

class Airtable:
    def __init__(self, base_id: str, api_key: str):
        self.base_id = base_id
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=f"{AIRTABLE_API_URL}/{base_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )

    async def close(self):
        await self.client.aclose()

    async def list_records(self, table: str, **params) -> List[Dict[str, Any]]:
        r = await self.client.get(f"/{table}", params=params)
        r.raise_for_status()
        return r.json().get("records", [])

    async def create_record(self, table: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"fields": fields}
        r = await self.client.post(f"/{table}", json=payload)
        r.raise_for_status()
        return r.json()

    async def update_record(self, table: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"fields": fields}
        r = await self.client.patch(f"/{table}/{record_id}", json=payload)
        r.raise_for_status()
        return r.json()

    async def find_first(self, table: str, filter_formula: str) -> Optional[Dict[str, Any]]:
        recs = await self.list_records(table, filterByFormula=filter_formula, maxRecords=1)
        return recs[0] if recs else None

async def get_menu_items(at: Airtable) -> List[Dict[str, Any]]:
    recs = await at.list_records(settings.TABLE_MENU, sort=[{"field": "Item_ID"}])
    items = []
    for r in recs:
        f = r.get("fields", {})
        if "Price" in f and "Name" in f:
            items.append({
                "id": r["id"],
                "item_id": f.get("Item_ID", ""),
                "name": f["Name"],
                "price": float(f.get("Price", 0)),
                "category": f.get("Category", ""),
            })
    return items

async def ensure_client(at: Airtable, tg_user_id: int, name: str, username: str = "", phone: str = "", email: str = "") -> str:
    cid = f"tg_{tg_user_id}"
    existing = await at.find_first(settings.TABLE_CLIENTS, f"{{Client_ID}}='{cid}'")
    if existing:
        return existing["id"]
    rec = await at.create_record(settings.TABLE_CLIENTS, {
        "Client_ID": cid,
        "Name": name or username or cid,
        "Phone": phone,
        "Email": email,
        "Preferred_Channel": "Telegram",
    })
    return rec["id"]

async def create_sale(at: Airtable, *, client_record_id: str, item_id: str, quantity: int, unit_price: float, total: float, channel: str = "Telegram", payment_method: str = "Cash", schedule_iso: str = "") -> Dict[str, Any]:
    fields = {
        "Item_ID": item_id,
        "Quantity": quantity,
        "Unit_Price": unit_price,
        "Total": total,
        "Channel": channel,
        "Payment_Method": payment_method,
    }
    if client_record_id.startswith("rec"):
        fields["clients_skeleton"] = [client_record_id]
    else:
        fields["Client_ID"] = f"tg_{client_record_id}"
    if schedule_iso:
        fields["Date"] = schedule_iso
    return await at.create_record(settings.TABLE_SALES, fields)
