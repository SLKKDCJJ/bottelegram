# bot.py
import logging
import json
import os
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)

# --- إعداد التوكن و ايدي المطور ---
# يفضّل وضع التوكن في متغيّر بيئة BOT_TOKEN بدل كتابته مباشرة
BOT_TOKEN = os.getenv("BOT_TOKEN") or "7297292669:AAFXHEMDWqW-Vy9muLVyRmE6H0HDCWyiT_Y"
DEVELOPER_ID = int(os.getenv("DEVELOPER_ID") or "8296577608")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# --- ملفات التخزين البسيطة ---
PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"

def ensure_files():
    if not os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
    if not os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def load_products():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

def load_orders():
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_orders(orders):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

ensure_files()

# In-memory carts: user_id -> {product_id: qty}
CARTS = {}

# ---- مساعدة لإنشاء كيبورد المنتجات ----
def product_buttons(product):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("أضف للسلة 🛒", callback_data=f"add_{product['id']}"))
    kb.add(InlineKeyboardButton("رجوع للقائمة 🔙", callback_data="back_to_store"))
    return kb

def store_keyboard():
    kb = InlineKeyboardMarkup()
    products = load_products()
    for p in products:
        kb.add(InlineKeyboardButton(f"{p['id']}. {p['title']} — {p['price']}ج", callback_data=f"view_{p['id']}"))
    return kb

# ---- أوامر أساسية ----
@dp.message_handler(commands=["start", "help"])
async def cmd_start(message: types.Message):
    text = (
        "أهلاً! هذا بوت متجر بسيط.\n\n"
        "الأوامر:\n"
        "/store - تصفح المنتجات\n"
        "/cart - عرض السلة\n"
        "/orders - (للمطور) عرض الطلبات\n"
        "/addproduct - (للمطور) إضافة منتج\n"
        "/delproduct - (للمطور) حذف منتج\n"
    )
    await message.reply(text)

@dp.message_handler(commands=["store"])
async def cmd_store(message: types.Message):
    products = load_products()
    if not products:
        await message.reply("قائمة المنتجات فارغة حالياً. تعال لاحقًا أو اطلب من المطور إضافة منتجات.")
        return
    await message.reply("قائمة المنتجات:", reply_markup=store_keyboard())

# ---- عرض منتج، إضافة للسلة بواسطة callback_data ----
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("view_"))
async def cb_view_product(callback_query: types.CallbackQuery):
    pid = callback_query.data.split("_",1)[1]
    products = load_products()
    product = next((p for p in products if str(p["id"])==pid), None)
    if not product:
        await callback_query.answer("المنتج غير موجود.", show_alert=True)
        return
    text = f"*{product['title']}*\n\n{product.get('desc','لا يوجد وصف')} \n\nالسعر: {product['price']} ج"
    await bot.send_message(callback_query.from_user.id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=product_buttons(product))
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("add_"))
async def cb_add_to_cart(callback_query: types.CallbackQuery):
    pid = callback_query.data.split("_",1)[1]
    user = callback_query.from_user
    products = load_products()
    product = next((p for p in products if str(p["id"])==pid), None)
    if not product:
        await callback_query.answer("المنتج غير موجود.", show_alert=True)
        return
    cart = CARTS.setdefault(user.id, {})
    cart[pid] = cart.get(pid, 0) + 1
    await callback_query.answer(f"تمت الإضافة: {product['title']} (الكمية الآن: {cart[pid]})")
    await bot.send_message(user.id, "لإكمال الطلب اكتب /cart")

@dp.callback_query_handler(lambda c: c.data == "back_to_store")
async def cb_back(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "قائمة المتجر:", reply_markup=store_keyboard())
    await callback_query.answer()

@dp.message_handler(commands=["cart"])
async def cmd_cart(message: types.Message):
    cart = CARTS.get(message.from_user.id, {})
    if not cart:
        await message.reply("سلتك فارغة.")
        return
    products = load_products()
    lines = []
    total = 0
    for pid, qty in cart.items():
        p = next((x for x in products if str(x["id"])==pid), None)
        if not p:
            continue
        subtotal = p["price"] * qty
        total += subtotal
        lines.append(f"{p['title']} × {qty} = {subtotal}ج")
    lines.append(f"\nالمجموع: {total} ج")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("تأكيد الطلب ✅", callback_data="checkout"))
    kb.add(InlineKeyboardButton("مسح السلة 🗑️", callback_data="clear_cart"))
    await message.reply("\n".join(lines), reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "clear_cart")
async def cb_clear_cart(callback_query: types.CallbackQuery):
    CARTS.pop(callback_query.from_user.id, None)
    await callback_query.answer("تم مسح السلة.")
    await bot.send_message(callback_query.from_user.id, "سلتك الآن فارغة.")

@dp.callback_query_handler(lambda c: c.data == "checkout")
async def cb_checkout(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    cart = CARTS.get(user.id, {})
    if not cart:
        await callback_query.answer("سلتك فارغة.", show_alert=True)
        return
    products = load_products()
    order_items = []
    total = 0
    for pid, qty in cart.items():
        p = next((x for x in products if str(x["id"])==pid), None)
        if not p:
            continue
        order_items.append({"id": p["id"], "title": p["title"], "qty": qty, "price": p["price"]})
        total += p["price"] * qty
    orders = load_orders()
    order_id = len(orders) + 1
    order = {
        "order_id": order_id,
        "user_id": user.id,
        "username": user.username,
        "name": user.full_name,
        "items": order_items,
        "total": total,
        "status": "pending"
    }
    orders.append(order)
    save_orders(orders)
    CARTS.pop(user.id, None)

    # ارسال اشعار للمستخدم
    await bot.send_message(user.id, f"تم إنشاء الطلب #{order_id} — المجموع: {total} ج\nسيرد عليك المطور للتواصل.", parse_mode=ParseMode.MARKDOWN)
    # ارسال للمطور مع تفاصيل وازرار لتغيير الحالة
    text = f"🆕 طلب جديد #{order_id}\nمن: {user.full_name} (@{user.username})\nالمعرف: `{user.id}`\nالمجموع: {total} ج\n\nالعناصر:\n"
    for it in order_items:
        text += f"- {it['title']} × {it['qty']} = {it['price'] * it['qty']}ج\n"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("وضع قيد الشحن 🚚", callback_data=f"mark_ship_{order_id}"))
    kb.add(InlineKeyboardButton("وضع مكتمل ✅", callback_data=f"mark_done_{order_id}"))
    kb.add(InlineKeyboardButton("أرسل رسالة للمشتري ✉️", callback_data=f"msg_user_{order_id}"))
    await bot.send_message(DEVELOPER_ID, text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    await callback_query.answer("تم إنشاء الطلب وأُرسِل للمطور.")

# ---- تفاعلات المطور مع الطلب ----
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("mark_ship_"))
async def cb_mark_ship(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DEVELOPER_ID:
        await callback_query.answer("غير مسموح.", show_alert=True)
        return
    order_id = int(callback_query.data.split("_")[-1])
    orders = load_orders()
    order = next((o for o in orders if o["order_id"]==order_id), None)
    if not order:
        await callback_query.answer("الطلب غير موجود.", show_alert=True)
        return
    order["status"] = "shipped"
    save_orders(orders)
    await callback_query.answer("تم تغيير الحالة إلى: قيد الشحن.")
    try:
        await bot.send_message(order["user_id"], f"تم تحديث حالة طلبك #{order_id}: قيد الشحن 🚚")
    except Exception:
        pass

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("mark_done_"))
async def cb_mark_done(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DEVELOPER_ID:
        await callback_query.answer("غير مسموح.", show_alert=True)
        return
    order_id = int(callback_query.data.split("_")[-1])
    orders = load_orders()
    order = next((o for o in orders if o["order_id"]==order_id), None)
    if not order:
        await callback_query.answer("الطلب غير موجود.", show_alert=True)
        return
    order["status"] = "done"
    save_orders(orders)
    await callback_query.answer("تم وضع الطلب كمكتمل.")
    try:
        await bot.send_message(order["user_id"], f"تم تسليم الطلب #{order_id} ✅\nشكراً لطلبك!")
    except Exception:
        pass

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("msg_user_"))
async def cb_msg_user(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != DEVELOPER_ID:
        await callback_query.answer("غير مسموح.", show_alert=True)
        return
    order_id = int(callback_query.data.split("_")[-1])
    orders = load_orders()
    order = next((o for o in orders if o["order_id"]==order_id), None)
    if not order:
        await callback_query.answer("الطلب غير موجود.", show_alert=True)
        return
    # يطلب من المطور كتابة الرسالة في نفس الدردشة مع البوت
    await callback_query.answer()
    await bot.send_message(DEVELOPER_ID, f"أرسل الرسالة التي تريد إرسالها للمشتري #{order_id} الآن.\n(سيتم إرسالها مباشرةً للمشتري.)")

    # ننتظر رسالة من المطور ثم نرسلها للمشتري — نستخدم فلتر بسيط عبر حالة
    @dp.message_handler(lambda m: m.from_user.id == DEVELOPER_ID, content_types=types.ContentTypes.TEXT)
    async def forward_from_dev(m: types.Message):
        try:
            await bot.send_message(order["user_id"], f"رسالة من المطور بخصوص طلب #{order_id}:\n\n{m.text}")
            await m.reply("تم الإرسال للمشتري.")
        except Exception as e:
            await m.reply("فشل الإرسال: " + str(e))

# ---- أوامر إدارية للمطور لإدارة المنتجات والطلبات ----
@dp.message_handler(commands=["addproduct"])
async def cmd_addproduct(message: types.Message):
    if message.from_user.id != DEVELOPER_ID:
        await message.reply("غير مسموح.")
        return
    # صيغة بسيطة: /addproduct عنوان | وصف | سعر
    payload = message.get_args()
    if not payload:
        await message.reply("استخدم: /addproduct عنوان | وصف | سعر")
        return
    try:
        title, desc, price = [x.strip() for x in payload.split("|", 2)]
        price = int(price)
    except Exception:
        await message.reply("صيغة غير صحيحة. مثال:\n/addproduct هاتف سامسونج | موبايل نظيف | 2500")
        return
    products = load_products()
    new_id = (max([p["id"] for p in products]) + 1) if products else 1
    products.append({"id": new_id, "title": title, "desc": desc, "price": price})
    save_products(products)
    await message.reply(f"تمت إضافة المنتج #{new_id} — {title}")

@dp.message_handler(commands=["delproduct"])
async def cmd_delproduct(message: types.Message):
    if message.from_user.id != DEVELOPER_ID:
        await message.reply("غير مسموح.")
        return
    pid = message.get_args().strip()
    if not pid:
        await message.reply("استخدم: /delproduct <id>")
        return
    products = load_products()
    products = [p for p in products if str(p["id"]) != pid]
    save_products(products)
    await message.reply(f"تم حذف المنتج {pid} إن وجد.")

@dp.message_handler(commands=["orders"])
async def cmd_orders(message: types.Message):
    if message.from_user.id != DEVELOPER_ID:
        await message.reply("غير مسموح.")
        return
    orders = load_orders()
    if not orders:
        await message.reply("لا توجد طلبات بعد.")
        return
    text = "قائمة الطلبات:\n"
    for o in orders:
        text += f"#{o['order_id']} — {o['name']} ({o['user_id']}) — {o['total']}ج — {o['status']}\n"
    await message.reply(text)

# ---- بدأ البوت ----
if __name__ == "__main__":
    print("Bot is starting ...")
    executor.start_polling(dp, skip_updates=True)
