import asyncio
from typing import Union

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from airtable import Airtable, get_menu_items, ensure_client, create_sale
from payment import CashPayment, QRStaticPayment

CART: dict[int, dict[str, dict]] = {}
PAGE_SIZE = 4

def page_slice(items, page, page_size=PAGE_SIZE):
    start = page * page_size
    end = start + page_size
    return items[start:end], len(items)

def item_kb(item_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data=f"add:{item_id}")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")]
    ])

def qty_kb(item_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="−", callback_data=f"dec:{item_id}"),
         InlineKeyboardButton(text="+", callback_data=f"qty:{item_id}")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")]
    ])

def pager_kb(page: int, total_items: int) -> InlineKeyboardMarkup:
    pages = (total_items + PAGE_SIZE - 1) // PAGE_SIZE if total_items else 1
    left = InlineKeyboardButton(text="⏮", callback_data=f"page:{max(page-1,0)}")
    right = InlineKeyboardButton(text="⏭", callback_data=f"page:{min(page+1,pages-1)}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [left, right],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")]
    ])

def cart_total(cart: dict) -> float:
    return sum(v["price"] * v["qty"] for v in cart.values())

async def on_start(message: Message, at: Airtable):
    await ensure_client(
        at,
        message.from_user.id,
        message.from_user.full_name or "",
        message.from_user.username or "",
    )
    await message.answer("Привет! Я помогу оформить заказ. Нажми /menu чтобы выбрать напиток.")

async def show_menu(target: Union[Message, CallbackQuery], at: Airtable, page: int = 0):
    items = await get_menu_items(at)
    page_items, total = page_slice(items, page)
    if not items:
        text = "Меню пусто."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")]
        ])
        if isinstance(target, Message):
            await target.answer(text, reply_markup=kb)
        else:
            await target.message.edit_text(text, reply_markup=kb)
        return
    for it in page_items:
        caption = f"<b>{it['name']}</b>\n{it.get('descr','')}\n\nЦена: {it['price']:.2f}"
        kb = item_kb(it["item_id"])
        photo_url = it.get("photo") or ""
        if photo_url:
            if isinstance(target, Message):
                await target.answer_photo(photo_url, caption=caption, reply_markup=kb)
            else:
                await target.message.answer_photo(photo_url, caption=caption, reply_markup=kb)
        else:
            if isinstance(target, Message):
                await target.answer(caption, reply_markup=kb)
            else:
                await target.message.answer(caption, reply_markup=kb)
    pager = pager_kb(page, total)
    if isinstance(target, Message):
        await target.answer(f"Стр. {page+1}", reply_markup=pager)
    else:
        await target.message.answer(f"Стр. {page+1}", reply_markup=pager)

async def on_page(cb: CallbackQuery, at: Airtable):
    _, page_str = cb.data.split(":", 1)
    page = int(page_str)
    await cb.answer()
    await show_menu(cb, at, page=page)

async def add_to_cart(cb: CallbackQuery, at: Airtable):
    _, item_id = cb.data.split(":", 1)
    items = await get_menu_items(at)
    match = next((i for i in items if i["item_id"] == item_id), None)
    if not match:
        return await cb.answer("Товар не найден", show_alert=True)
    user_cart = CART.setdefault(cb.from_user.id, {})
    if item_id not in user_cart:
        user_cart[item_id] = {"name": match["name"], "price": match["price"], "qty": 0}
    user_cart[item_id]["qty"] += 1
    await cb.answer(f"Добавлено: {match['name']}")
    await cb.message.answer(
        f"В корзине {match['name']}: {user_cart[item_id]['qty']} шт. (итого корзина {cart_total(user_cart):.2f})",
        reply_markup=qty_kb(item_id)
    )

async def show_cart(cb: CallbackQuery):
    user_cart = CART.get(cb.from_user.id, {})
    if not user_cart:
        return await cb.answer("Корзина пуста", show_alert=True)
    lines = ["🧺 Корзина:"]
    for v in user_cart.values():
        lines.append(f"• {v['name']} × {v['qty']} = {v['price'] * v['qty']:.2f}")
    lines.append(f"Итого: {cart_total(user_cart):.2f}")
    actions = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♻️ Очистить", callback_data="cart:clear")],
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")]
    ])
    await cb.message.edit_text("\n".join(lines), reply_markup=actions)

async def qty_adjust(cb: CallbackQuery):
    _, item_id = cb.data.split(":", 1)
    user_cart = CART.get(cb.from_user.id, {})
    if item_id not in user_cart:
        return await cb.answer("Нет в корзине", show_alert=True)
    user_cart[item_id]["qty"] += 1
    await cb.answer("Добавлено")
    await cb.message.edit_text(
        f"В корзине {user_cart[item_id]['name']}: {user_cart[item_id]['qty']} шт.",
        reply_markup=qty_kb(item_id)
    )

async def qty_dec(cb: CallbackQuery):
    _, item_id = cb.data.split(":", 1)
    user_cart = CART.get(cb.from_user.id, {})
    if item_id not in user_cart:
        return await cb.answer("Нет в корзине", show_alert=True)
    user_cart[item_id]["qty"] = max(0, user_cart[item_id]["qty"] - 1)
    await cb.answer("Убрано")
    await cb.message.edit_text(
        f"В корзине {user_cart[item_id]['name']}: {user_cart[item_id]['qty']} шт.",
        reply_markup=qty_kb(item_id)
    )

async def checkout(cb: CallbackQuery, at: Airtable):
    user_cart = CART.get(cb.from_user.id, {})
    if not user_cart:
        return await cb.answer("Корзина пуста", show_alert=True)
    total = cart_total(user_cart)
    kb = InlineKeyboardBuilder()
    kb.button(text="💵 Наличные", callback_data="pay:cash")
    kb.button(text="📷 QR", callback_data="pay:qr")
    kb.adjust(2)
    await cb.message.edit_text(
        f"Сумма к оплате: {total:.2f}. Выберите способ оплаты:",
        reply_markup=kb.as_markup(),
    )

async def pay(cb: CallbackQuery, at: Airtable):
    method = cb.data.split(":", 1)[1]
    user_id = cb.from_user.id
    cart = CART.get(user_id, {})
    if not cart:
        return await cb.answer("Корзина пуста", show_alert=True)
    total = cart_total(cart)
    client_rec_id = await ensure_client(
        at, user_id, cb.from_user.full_name or "", cb.from_user.username or ""
    )
    for item_id, info in cart.items():
        await create_sale(
            at,
            client_record_id=client_rec_id,
            item_id=item_id,
            quantity=info["qty"],
            unit_price=info["price"],
            total=info["price"] * info["qty"],
            channel="Telegram",
            payment_method="Cash" if method == "cash" else "QR",
        )
    if method == "cash":
        provider = CashPayment()
        res = await provider.create_invoice(f"order-{user_id}", total, "Оплата наличными")
        CART[user_id] = {}
        await cb.message.edit_text(f"Заказ оформлен. {res.description}\\nСумма: {total:.2f}")
    else:
        provider = QRStaticPayment("PAY")
        res = await provider.create_invoice(f"order-{user_id}", total, "QR оплата")
        CART[user_id] = {}
        if res.qr_png:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(res.qr_png); tmp.flush()
            await cb.message.answer_photo(FSInputFile(tmp.name), caption=f"Отсканируйте QR. Сумма: {total:.2f}")
        else:
            await cb.message.edit_text("Оплата создана.")

def h_on_start(at: Airtable):
    async def _h(m: Message): return await on_start(m, at)
    return _h
def h_show_menu(at: Airtable):
    async def _h(obj: Union[Message, CallbackQuery]): return await show_menu(obj, at, page=0)
    return _h
def h_page(at: Airtable):
    async def _h(cb: CallbackQuery): return await on_page(cb, at)
    return _h
def h_add_to_cart(at: Airtable):
    async def _h(cb: CallbackQuery): return await add_to_cart(cb, at)
    return _h
def h_checkout(at: Airtable):
    async def _h(cb: CallbackQuery): return await checkout(cb, at)
    return _h
def h_pay(at: Airtable):
    async def _h(cb: CallbackQuery): return await pay(cb, at)
    return _h

async def main():
    bot = Bot(settings.BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()
    at = Airtable(settings.AIRTABLE_BASE_ID, settings.AIRTABLE_API_KEY)
    dp.message.register(h_on_start(at), CommandStart())
    dp.message.register(h_show_menu(at), Command("menu"))
    dp.callback_query.register(h_show_menu(at), F.data == "menu")
    dp.callback_query.register(h_page(at), F.data.startswith("page:"))
    dp.callback_query.register(h_add_to_cart(at), F.data.startswith("add:"))
    dp.callback_query.register(show_cart, F.data == "cart")
    dp.callback_query.register(qty_adjust, F.data.startswith("qty:"))
    dp.callback_query.register(qty_dec, F.data.startswith("dec:"))
    dp.callback_query.register(h_checkout(at), F.data == "checkout")
    dp.callback_query.register(h_pay(at), F.data.startswith("pay:"))
    print("Bot started. Use /menu to test.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
