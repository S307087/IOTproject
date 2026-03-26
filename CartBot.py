import json
import logging
import sqlite3
import asyncio
from datetime import datetime, timezone

from smartmarket_MQTT import MyMQTT
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "catalog.db")
# IMPORTANT: Put your Cart Bot Token here
CART_BOT_TOKEN = "8632483838:AAF9MMJ16v6U8JCNZDMwsOSUpjef6QJLvhw"

MAIN_MENU_KBD = ReplyKeyboardMarkup(
    [["⚙️ Set Cart ID", "💳 Show Pairing Code"], ["❤️ Show Wishlist", "🧾 Shopping List"], ["🏁 Finish Shopping", "🚪 Disconnect"]],
    resize_keyboard=True,
)

event_loop = None

class CartNotifier:
    def __init__(self):
        self.app = None
        self.chat_id = None
        
    def notify(self, topic, payload):
        if not self.app or not self.chat_id or not event_loop:
            return
        if not payload:
            return
            
        event = payload.get("event")
        if event in ["user_connected", "wishlist_updated"]:
            user_id = payload.get("user_id")
            user_name = payload.get("user_name", "User")
            wish_list = payload.get("wish_list", [])
            
            if event == "user_connected":
                header = f"✅ <b>Connection Established!</b>\nWelcome <b>{user_name}</b> (<code>{user_id}</code>) to this cart.\n\n"
            else:
                header = f"🔔 <b>Wishlist Update</b>\nUser <b>{user_name}</b> updated their wishlist.\n\n"
                
            msg = header
            if wish_list:
                msg += "❤️ <b>Current Wishlist:</b>\n"
                conn = get_db_connection()
                
                # Try to get cart_id to handle strikethrough logic correctly
                cart_id = self.app.bot_data.get("cart_id") if self.app else None
                shopping_ids = []
                if cart_id:
                     row = conn.execute("SELECT shopping_list FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
                     if row and row['shopping_list']:
                         shopping_ids = _load_json_list(row['shopping_list'])
                     
                products = conn.execute(f"SELECT product_id, product_name, price, promotion FROM products WHERE product_id IN ({','.join(['?']*len(wish_list))})", wish_list).fetchall()
                conn.close()
                for p in products:
                    promo = int(p["promotion"] or 0)
                    price = float(p["price"] or 0.0)
                    final_price = price * (1 - promo / 100)
                    
                    is_scanned = p['product_id'] in shopping_ids
                    line = f"- <s>{p['product_name']}</s>" if is_scanned else f"- {p['product_name']}"
                    line += f" [<code>{p['product_id']}</code>]"
                    
                    if promo > 0:
                        line += f" <s>€{price:.2f}</s> €{final_price:.2f}"
                    else:
                        line += f" €{final_price:.2f}"
                    
                    msg += f"{line}\n"
            else:
                msg += "Wishlist is empty."
                
            asyncio.run_coroutine_threadsafe(
                self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML'),
                event_loop
            )
        elif event == "checkout_complete":
            msg = "✅ <b>Checkout Complete!</b>\nPayment registered successfully. The cart is now free for a new user."
            asyncio.run_coroutine_threadsafe(
                self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML', reply_markup=MAIN_MENU_KBD),
                event_loop
            )
        elif event == "user_disconnected":
            msg = "🔌 <b>User Disconnected</b>\nThe cart has been reset and is ready for a new user."
            asyncio.run_coroutine_threadsafe(
                self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML', reply_markup=MAIN_MENU_KBD),
                event_loop
            )

notifier = CartNotifier()
mqtt_client = MyMQTT("CartBotClient", "localhost", 1883, notifier=notifier)


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_json_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global event_loop
    # capture the running loop so the MQTT thread can schedule coroutines
    if event_loop is None:
        event_loop = asyncio.get_running_loop()
    
    # Store app and chat_id in notifier so it can send messages to this chat
    notifier.app = context.application
    notifier.chat_id = update.effective_chat.id
    
    await update.message.reply_text(
        "🛒 Smart Cart Bot\n\n"
        "This bot represents a smart shopping cart.\n"
        "Use ⚙️ Set Cart ID to define this cart's ID, then use 💳 Show Pairing Code to let a user pair.",
        reply_markup=MAIN_MENU_KBD,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if text == "⚙️ Set Cart ID":
        context.user_data["awaiting_set_cart_id"] = True
        await update.message.reply_text("Enter the Cart ID this bot represents (e.g. CRT-001).")
        return

    if context.user_data.get("awaiting_set_cart_id"):
        context.user_data["awaiting_set_cart_id"] = False
        cart_id = text.strip().upper()
        
        # Subscribe to MQTT
        old_cart = context.bot_data.get("cart_id")
        if old_cart:
            mqtt_client.myUnsubscribe(f"cart/{old_cart}/data")
            
        context.bot_data["cart_id"] = cart_id
        mqtt_client.mySubscribe(f"cart/{cart_id}/data")
        
        await update.message.reply_text(f"✅ Active Cart set to: {cart_id}", reply_markup=MAIN_MENU_KBD)
        return

    if text == "💳 Show Pairing Code":
        cart_id = context.bot_data.get("cart_id")
        if not cart_id:
            await update.message.reply_text("Cart ID not set! Use ⚙️ Set Cart ID first.", reply_markup=MAIN_MENU_KBD)
            return
            
        # Deep link URL for the UserBot (UsersMarketBot)
        # Scan with phone -> opens telegram -> sends /start CRT-XXX
        deep_link = f"https://t.me/UsersMarketBot?start={cart_id}"
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={deep_link}"
        
        await update.message.reply_photo(
            photo=qr_url, 
            caption=(
                f"🔑 <b>Cart Pairing QR Code</b>\n\n"
                f"Code: <code>{cart_id}</code>\n\n"
                f"📸 <b>Scan this with your phone camera</b> to connect directly, or manually type the code in the User Bot."
            ), 
            parse_mode='HTML', 
            reply_markup=MAIN_MENU_KBD
        )
        return

    if text == "❤️ Show Wishlist":
        await show_wishlist(update, context)
    elif text == "🧾 Shopping List":
        await show_shopping_list(update, context)
    elif text == "🏁 Finish Shopping":
        await checkout_qr(update, context)
    elif text == "🚪 Disconnect":
        await disconnect_cart(update, context)
    else:
        await update.message.reply_text("Please use the menu buttons.", reply_markup=MAIN_MENU_KBD)

async def disconnect_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cart_id = context.bot_data.get("cart_id")
    if not cart_id:
        await update.message.reply_text("No cart connected.", reply_markup=MAIN_MENU_KBD)
        return
    
    conn = get_db_connection()
    cart_row = conn.execute("SELECT user_id FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
    user_id = cart_row["user_id"] if cart_row else None
    
    if user_id:
        conn.execute("UPDATE users SET cart_id = NULL WHERE user_id = ?", (user_id,))
    
    # Restore shelf stock for all items in the shopping list
    cart_row = conn.execute("SELECT shopping_list FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
    if cart_row and cart_row["shopping_list"]:
        items = _load_json_list(cart_row["shopping_list"])
        for item_id in items:
            conn.execute("UPDATE products SET shelf_stock = shelf_stock + 1 WHERE product_id = ?", (item_id,))

    conn.execute("UPDATE carts SET user_id=NULL, shopping_list='[]', wish_list='[]', scanned_rfids='[]', connection_time=NULL WHERE cart_id=?", (cart_id,))
    conn.commit()
    conn.close()
    
    # Send MQTT
    try:
        payload = {"event": "user_disconnected", "cart_id": cart_id, "user_id": user_id}
        mqtt_client.myPublish(f"cart/{cart_id}/data", payload)
    except Exception:
        pass
    
    await update.message.reply_text("🔌 Disconnected! The cart has been reset and all items returned to stock. The user's wishlist was preserved.", reply_markup=MAIN_MENU_KBD)


async def show_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cart_id = context.bot_data.get("cart_id")
    if not cart_id:
        await update.message.reply_text("Cart ID not set. Use 'Set Cart ID' first.", reply_markup=MAIN_MENU_KBD)
        return

    conn = get_db_connection()
    row = conn.execute("SELECT wish_list, shopping_list, user_id FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
    
    if not row or not row["user_id"]:
        conn.close()
        await update.message.reply_text("No user is connected to this cart.", reply_markup=MAIN_MENU_KBD)
        return
        
    wishlist_ids = _load_json_list(row["wish_list"] if row else None)
    shopping_ids = _load_json_list(row["shopping_list"] if row else None)

    if not wishlist_ids:
        conn.close()
        await update.message.reply_text("Wishlist is empty.", reply_markup=MAIN_MENU_KBD)
        return

    products = conn.execute(
        f"SELECT product_id, product_name, price, promotion FROM products WHERE product_id IN ({','.join(['?'] * len(wishlist_ids))})",
        wishlist_ids,
    ).fetchall()
    conn.close()

    msg = "❤️ Wishlist:\n\n"
    total = 0.0
    for p in products:
        promo = int(p["promotion"] or 0)
        price = float(p["price"] or 0.0)
        final_price = price * (1 - promo / 100)
        total += final_price
        
        is_scanned = p['product_id'] in shopping_ids
        line = f"- <s>{p['product_name']}</s>" if is_scanned else f"- {p['product_name']}"
        line += f" [<code>{p['product_id']}</code>]"
        
        if promo > 0:
            line += f" <s>€{price:.2f}</s> €{final_price:.2f}"
        else:
            line += f" €{final_price:.2f}"
            
        msg += f"{line}\n"
        
    msg += f"\nTotal (wishlist): €{total:.2f}"

    await update.message.reply_text(msg, parse_mode='HTML', reply_markup=MAIN_MENU_KBD)


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Simulates an RFID scan to add a product to the cart.
    Usage: /scan <RFID_ID>
    """
    cart_id = context.bot_data.get("cart_id")
    if not cart_id:
        await update.message.reply_text("No cart connected. Use ⚙️ Set Cart ID first.", reply_markup=MAIN_MENU_KBD)
        return
    if not context.args:
        await update.message.reply_text("Usage: /scan <RFID_ID>")
        return

    rfid_id = context.args[0].strip().upper()

    conn = get_db_connection()
    # Find the product associated with this RFID
    rfid_row = conn.execute("SELECT product_id FROM rfid_tags WHERE rfid_id = ?", (rfid_id,)).fetchone()
    
    if not rfid_row:
        conn.close()
        await update.message.reply_text(f"❌ Invalid RFID or unassigned tag: {rfid_id}", reply_markup=MAIN_MENU_KBD)
        return
        
    product_id = rfid_row["product_id"]

    prod = conn.execute(
        "SELECT product_id, product_name, shelf_stock FROM products WHERE product_id = ?",
        (product_id,),
    ).fetchone()
    
    if not prod:
        conn.close()
        await update.message.reply_text(f"Product not found for this RFID: {product_id}", reply_markup=MAIN_MENU_KBD)
        return
        
    if prod["shelf_stock"] <= 0:
        conn.close()
        await update.message.reply_text(f"❌ Product {product_id} is out of stock on the shelf!", reply_markup=MAIN_MENU_KBD)
        return

    cart_row = conn.execute(
        "SELECT shopping_list, wish_list, scanned_rfids, user_id FROM carts WHERE cart_id = ?",
        (cart_id,),
    ).fetchone()
    
    scanned_rfids = _load_json_list(cart_row["scanned_rfids"] if cart_row else None)
    if rfid_id in scanned_rfids:
        conn.close()
        await update.message.reply_text(f"⚠️ This exact item ({rfid_id}) has already been scanned into the cart!", reply_markup=MAIN_MENU_KBD)
        return
        
    scanned_rfids.append(rfid_id)

    shopping_list = _load_json_list(cart_row["shopping_list"] if cart_row else None)
    shopping_list.append(product_id)

    conn.execute("UPDATE products SET shelf_stock = shelf_stock - 1 WHERE product_id = ?", (product_id,))
    conn.execute(
        "UPDATE carts SET shopping_list = ?, scanned_rfids = ? WHERE cart_id = ?",
        (_save_json_list(shopping_list), _save_json_list(scanned_rfids), cart_id),
    )
    
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Added to cart: {prod['product_name']} [RFID: {rfid_id}] (Stock -1)",
        reply_markup=MAIN_MENU_KBD,
    )

async def unscan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Simulates removing an item from the cart.
    Usage: /unscan <RFID_ID>
    """
    cart_id = context.bot_data.get("cart_id")
    if not cart_id:
        await update.message.reply_text("No cart connected. Use ⚙️ Set Cart ID first.", reply_markup=MAIN_MENU_KBD)
        return
    if not context.args:
        await update.message.reply_text("Usage: /unscan <RFID_ID>")
        return

    rfid_id = context.args[0].strip().upper()

    conn = get_db_connection()
    cart_row = conn.execute("SELECT shopping_list, scanned_rfids FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
    
    scanned_rfids = _load_json_list(cart_row["scanned_rfids"] if cart_row else None)

    if rfid_id not in scanned_rfids:
        conn.close()
        await update.message.reply_text(f"❌ RFID {rfid_id} is not in your cart.", reply_markup=MAIN_MENU_KBD)
        return

    # Find the product associated with this RFID
    rfid_row = conn.execute("SELECT product_id FROM rfid_tags WHERE rfid_id = ?", (rfid_id,)).fetchone()
    product_id = rfid_row["product_id"] if rfid_row else None

    scanned_rfids.remove(rfid_id)
    
    shopping_list = _load_json_list(cart_row["shopping_list"] if cart_row else None)
    if product_id and product_id in shopping_list:
        shopping_list.remove(product_id)

    if product_id:
        conn.execute("UPDATE products SET shelf_stock = shelf_stock + 1 WHERE product_id = ?", (product_id,))
        
    conn.execute(
        "UPDATE carts SET shopping_list = ?, scanned_rfids = ? WHERE cart_id = ?",
        (_save_json_list(shopping_list), _save_json_list(scanned_rfids), cart_id),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Removed from cart: [RFID: {rfid_id}] (Stock +1)",
        reply_markup=MAIN_MENU_KBD,
    )


async def show_shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cart_id = context.bot_data.get("cart_id")
    if not cart_id:
        await update.message.reply_text("No cart connected. Use 'Set Cart ID' first.", reply_markup=MAIN_MENU_KBD)
        return

    conn = get_db_connection()
    cart_row = conn.execute("SELECT shopping_list FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
    product_ids = _load_json_list(cart_row["shopping_list"] if cart_row else None)
    if not product_ids:
        conn.close()
        await update.message.reply_text("Shopping list is empty. Use /scan <PRODUCT_ID>.", reply_markup=MAIN_MENU_KBD)
        return

    products = conn.execute(
        f"SELECT product_id, product_name, price, promotion FROM products WHERE product_id IN ({','.join(['?'] * len(product_ids))})",
        product_ids,
    ).fetchall()
    conn.close()

    prod_dict = {p["product_id"]: p for p in products}

    msg = "🧾 Shopping list:\n\n"
    total = 0.0
    for pid in product_ids:
        p = prod_dict.get(pid)
        if p:
            promo = int(p["promotion"] or 0)
            price = float(p["price"] or 0.0)
            final_price = price * (1 - promo / 100)
            total += final_price
            msg += f"- {p['product_name']} [{p['product_id']}] €{final_price:.2f}\n"
    msg += f"\nCurrent total: €{total:.2f}"
    await update.message.reply_text(msg, reply_markup=MAIN_MENU_KBD)


async def checkout_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generates a QR code for checkout that StaffBot can scan.
    """
    cart_id = context.bot_data.get("cart_id")
    if not cart_id:
        await update.message.reply_text("No cart connected. Use ⚙️ Set Cart ID first.", reply_markup=MAIN_MENU_KBD)
        return

    conn = get_db_connection()
    row = conn.execute(
        "SELECT user_id, shopping_list FROM carts WHERE cart_id = ?",
        (cart_id,),
    ).fetchone()
    conn.close()
    if not row or not row["user_id"]:
        await update.message.reply_text("No user is currently connected to this cart.", reply_markup=MAIN_MENU_KBD)
        return

    shopping_list = _load_json_list(row["shopping_list"])
    if not shopping_list:
        await update.message.reply_text("Your shopping cart is empty! Scan some products first.", reply_markup=MAIN_MENU_KBD)
        return

    # Generate QR Code URL
    payload = f"https://t.me/StaffsMarketBot?start=CHK-{cart_id}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={payload}"

    await update.message.reply_photo(
        photo=qr_url, 
        caption=(
            f"🏁 <b>Checkout per Cart: {cart_id}</b>\n\n"
            f"Show this QR code to the Staff to complete the payment and finish shopping.\n"
            
        ), 
        parse_mode='HTML', 
        reply_markup=MAIN_MENU_KBD
    )


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()


def main() -> None:
    if CART_BOT_TOKEN == "YOUR_CART_BOT_TOKEN_HERE":
        print("WARNING: Replace CART_BOT_TOKEN with your unique token.")

    try:
        mqtt_client.start()
    except Exception as e:
        logger.error(f"Failed to start MQTT Client: {e}")

    application = ApplicationBuilder().token(CART_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("unscan", unscan))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))

    print("CartBot is starting up...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
