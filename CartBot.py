import json
import logging
import sqlite3
from datetime import datetime, timezone

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

DB_FILE = "catalog.db"
# IMPORTANT: Put your Cart Bot Token here
CART_BOT_TOKEN = "8632483838:AAF9MMJ16v6U8JCNZDMwsOSUpjef6QJLvhw"

MAIN_MENU_KBD = ReplyKeyboardMarkup(
    [["🔗 Connect User", "❤️ Show Wishlist"], ["🧾 Shopping List", "💳 Checkout QR"]],
    resize_keyboard=True,
)


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
    await update.message.reply_text(
        "🛒 Smart Cart Bot\n\n"
        "This bot represents a smart shopping cart.\n"
        "Use the menu to connect a user, view the wishlist, build the shopping list, and generate a checkout QR payload.",
        reply_markup=MAIN_MENU_KBD,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if text == "🔗 Connect User":
        context.user_data["awaiting_user_id"] = True
        await update.message.reply_text("Send the User ID to connect (e.g., USR-001).")
        return

    if context.user_data.get("awaiting_user_id"):
        context.user_data["awaiting_user_id"] = False
        await connect(update, context, user_id=text.strip().upper())
        return

    if text == "❤️ Show Wishlist":
        await show_wishlist(update, context)
    elif text == "🧾 Shopping List":
        await show_shopping_list(update, context)
    elif text == "💳 Checkout QR":
        await checkout_qr(update, context)
    else:
        await update.message.reply_text("Please use the menu buttons.", reply_markup=MAIN_MENU_KBD)


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str | None = None) -> None:
    if not user_id and context.args:
        user_id = context.args[0].strip().upper()
    if not user_id:
        await update.message.reply_text("Usage: /connect <USER_ID>")
        return

    cart_id = f"CRT-{user_id.split('-')[-1].zfill(3)}"
    conn = get_db_connection()

    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, cart_id, wish_list) VALUES (?, ?, ?)",
        (user_id, cart_id, "[]"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO carts (cart_id, user_id, shopping_list, connection_time) VALUES (?, ?, ?, ?)",
        (cart_id, user_id, "[]", _utc_now_iso()),
    )
    conn.execute("UPDATE users SET cart_id = ? WHERE user_id = ?", (cart_id, user_id))
    conn.execute("UPDATE carts SET user_id = ? WHERE cart_id = ?", (user_id, cart_id))

    conn.commit()
    conn.close()

    context.user_data["user_id"] = user_id
    context.user_data["cart_id"] = cart_id

    await update.message.reply_text(f"✅ Connected to user {user_id} on cart {cart_id}.", reply_markup=MAIN_MENU_KBD)


async def show_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = context.user_data.get("user_id")
    if not user_id:
        await update.message.reply_text("No user connected. Use 'Connect User' first.", reply_markup=MAIN_MENU_KBD)
        return

    conn = get_db_connection()
    row = conn.execute("SELECT wish_list FROM users WHERE user_id = ?", (user_id,)).fetchone()
    wishlist_ids = _load_json_list(row["wish_list"] if row else None)

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
        msg += f"- {p['product_name']} [{p['product_id']}] €{final_price:.2f}"
        if promo > 0:
            msg += f" (promo -{promo}%)"
        msg += "\n"
    msg += f"\nTotal (wishlist): €{total:.2f}"

    await update.message.reply_text(msg, reply_markup=MAIN_MENU_KBD)


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Simulates an RFID scan by product_id.
    Usage: /scan <PRODUCT_ID>
    """
    user_id = context.user_data.get("user_id")
    cart_id = context.user_data.get("cart_id")
    if not user_id or not cart_id:
        await update.message.reply_text("No user connected. Use /connect first.", reply_markup=MAIN_MENU_KBD)
        return
    if not context.args:
        await update.message.reply_text("Usage: /scan <PRODUCT_ID>")
        return

    product_id = context.args[0].strip().upper()

    conn = get_db_connection()
    prod = conn.execute(
        "SELECT product_id, product_name FROM products WHERE product_id = ?",
        (product_id,),
    ).fetchone()
    if not prod:
        conn.close()
        await update.message.reply_text(f"Product not found: {product_id}", reply_markup=MAIN_MENU_KBD)
        return

    cart_row = conn.execute(
        "SELECT shopping_list FROM carts WHERE cart_id = ?",
        (cart_id,),
    ).fetchone()
    shopping_list = _load_json_list(cart_row["shopping_list"] if cart_row else None)
    shopping_list.append(product_id)

    conn.execute(
        "UPDATE carts SET shopping_list = ? WHERE cart_id = ?",
        (_save_json_list(shopping_list), cart_id),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Added to cart: {prod['product_name']} [{product_id}]",
        reply_markup=MAIN_MENU_KBD,
    )


async def show_shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cart_id = context.user_data.get("cart_id")
    if not cart_id:
        await update.message.reply_text("No cart connected. Use 'Connect User' first.", reply_markup=MAIN_MENU_KBD)
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

    msg = "🧾 Shopping list:\n\n"
    total = 0.0
    for p in products:
        promo = int(p["promotion"] or 0)
        price = float(p["price"] or 0.0)
        final_price = price * (1 - promo / 100)
        total += final_price
        msg += f"- {p['product_name']} [{p['product_id']}] €{final_price:.2f}\n"
    msg += f"\nCurrent total: €{total:.2f}"
    await update.message.reply_text(msg, reply_markup=MAIN_MENU_KBD)


async def checkout_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Generates a QR payload (as text) containing cart_id and connection_time.
    In a real system you would encode this payload into an actual QR image.
    """
    cart_id = context.user_data.get("cart_id")
    if not cart_id:
        await update.message.reply_text("No cart connected. Use 'Connect User' first.", reply_markup=MAIN_MENU_KBD)
        return

    conn = get_db_connection()
    row = conn.execute(
        "SELECT cart_id, user_id, connection_time, shopping_list FROM carts WHERE cart_id = ?",
        (cart_id,),
    ).fetchone()
    conn.close()
    if not row:
        await update.message.reply_text("Cart not found in database.", reply_markup=MAIN_MENU_KBD)
        return

    payload = {
        "cart_id": row["cart_id"],
        "user_id": row["user_id"],
        "connection_time": row["connection_time"],
        "shopping_list": _load_json_list(row["shopping_list"]),
        "generated_at": _utc_now_iso(),
    }

    keyboard = [[InlineKeyboardButton("Copy payload", callback_data="noop")]]
    await update.message.reply_text(
        "💳 Checkout QR payload (JSON):\n\n" + json.dumps(payload, indent=2, ensure_ascii=False),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()


def main() -> None:
    if CART_BOT_TOKEN == "YOUR_CART_BOT_TOKEN_HERE":
        print("WARNING: Replace CART_BOT_TOKEN with your unique token.")

    application = ApplicationBuilder().token(CART_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("connect", connect))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(noop_callback, pattern=r"^noop$"))

    print("CartBot is starting up...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
