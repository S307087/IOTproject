import json
import logging
import os
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

import sqlite3
from smartmarket_MQTT import MyMQTT
import requests

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "catalog.db")
BOT_TOKEN = "8678627934:AAG9c3Jm694EzBLCBEqcoGGnQfSou3uslaY"

# In-memory storage for search context: { user_id: query_text }
search_queries = {}

class UserNotifier:
    def __init__(self):
        self.app = None
        self.chat_id = None

    def notify(self, topic, payload):
        if not self.app or not self.chat_id:
            return
            
        event = payload.get("event")
        asyncio_run = getattr(asyncio, "run_coroutine_threadsafe")
        
        if event == "checkout_complete":
            payment_id = payload.get("payment_id", "N/A")
            total = payload.get("total", 0.0)
            
            items_text = ""
            try:
                conn = get_db_connection()
                tx = conn.execute("SELECT product_list FROM transactions WHERE payment_id = ?", (payment_id,)).fetchone()
                if tx and tx['product_list']:
                    shopping_list = json.loads(tx['product_list'])
                    if shopping_list:
                        placeholders = ",".join(["?"] * len(shopping_list))
                        products = conn.execute(
                            f"SELECT product_id, product_name, price, promotion FROM products WHERE product_id IN ({placeholders})",
                            shopping_list
                        ).fetchall()
                        prod_dict = {p["product_id"]: p for p in products}
                        
                        for pid in shopping_list:
                            p = prod_dict.get(pid)
                            if p:
                                name = p["product_name"]
                                price = p["price"] or 0.0
                                promo = p["promotion"] or 0
                                curr_price = price * (1 - promo / 100)
                                items_text += f"— {name}: €{curr_price:.2f}\n"
                conn.close()
            except Exception as e:
                logger.error(f"Error fetching shopping list for receipt: {e}")
                
            items_section = f"<b>Shopping List:</b>\n{items_text}\n" if items_text else ""
            
            msg = (
                f"🧾 <b>Payment Complete!</b>\n\n"
                f"Transaction: <code>{payment_id}</code>\n"
                f"{items_section}"
                f"Total Paid: <b>€{total:.2f}</b>\n\n"
                f"Thank you for shopping with us! You have been disconnected from the cart."
            )
            asyncio_run(
                self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML', reply_markup=MAIN_MENU_KBD),
                event_loop
            )
        elif event == "user_disconnected":
            # The cart disconnected us
            msg = "🔌 <b>Remote Disconnect</b>\nThe cart has been disconnected or reset. Your session has ended."
            asyncio_run(
                self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode='HTML', reply_markup=MAIN_MENU_KBD),
                event_loop
            )

notifier = UserNotifier()
mqtt_client = MyMQTT("UserBotClient", "localhost", 1883, notifier=notifier)
event_loop = None
import asyncio

MAIN_MENU_KBD = ReplyKeyboardMarkup(
    [["🛒 Browse Market", "🔍 Search Product"], ["❤️ My Wishlist", "🔗 Connect to Cart"], ["🚪 Disconnect", "❓ Help & Info"]],
    resize_keyboard=True
)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # To access columns by name
    return conn

def get_user_wishlist(user_id):
    conn = get_db_connection()
    row = conn.execute("SELECT wish_list FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row or not row['wish_list']:
        return []
    return json.loads(row['wish_list'])

def add_to_user_wishlist(user_id, prod_id, user_name="User"):
    conn = get_db_connection()
    conn.execute("INSERT OR IGNORE INTO users (user_id, cart_id, wish_list) VALUES (?, NULL, '[]')", (user_id,))
    row = conn.execute("SELECT wish_list, cart_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
    wishlist = json.loads(row['wish_list']) if row and row['wish_list'] else []
    if prod_id not in wishlist:
        wishlist.append(prod_id)
        conn.execute("UPDATE users SET wish_list = ? WHERE user_id = ?", (json.dumps(wishlist), user_id))
        if row and row['cart_id']:
            conn.execute("UPDATE carts SET wish_list = ? WHERE cart_id = ?", (json.dumps(wishlist), row['cart_id']))
            try:
                # Include user_name if possible (placeholder as we don't have update/context here easy, but we can pass it if we refactor)
                # For now, we'll refactor add_to_user_wishlist to accept user_name
                payload = {"event": "wishlist_updated", "user_id": user_id, "user_name": user_name, "wish_list": wishlist}
                mqtt_client.myPublish(f"cart/{row['cart_id']}/data", payload)
            except Exception as e:
                logger.error(f"MQTT Publish error: {e}")
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    global event_loop
    if event_loop is None:
        event_loop = asyncio.get_running_loop()
        
    notifier.app = context.application
    notifier.chat_id = update.effective_chat.id
    
    user = update.effective_user
    
    # Check for deep-link parameters (e.g. /start CRT-001)
    if context.args:
        param = context.args[0].upper()
        logger.info(f"Start parameter detected: {param}")
        if param.startswith("CRT-"):
            await perform_pairing(param, update, context)
            return

    welcome_text = (
        f"👋 <b>Hi {user.mention_html()}!</b>\n\n"
        "Welcome to the <b>Market Bot</b>! 🛒✨\n\n"
        "How can I help you today?\n"
        "• Click <b>Browse Market</b> to see categories\n"
        "• Click <b>Search Product</b> to find something specific\n"
        "• Click <b>My Wishlist</b> to see your saved items\n\n"
        "<i>Enjoy your shopping!</i>"
    )
    await update.message.reply_html(welcome_text, reply_markup=MAIN_MENU_KBD)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle menu button clicks."""
    text = update.message.text
    
    # Reset search state on any valid menu button press
    if text in ["🛒 Browse Market", "❤️ My Wishlist", "❓ Help & Info", "🔍 Search Product", "🔗 Connect to Cart", "🚪 Disconnect"]:
        context.user_data['awaiting_search'] = False
        context.user_data['awaiting_cart_id'] = False

    if text == "🛒 Browse Market":
        await market(update, context)
    elif text == "❤️ My Wishlist":
        await view_wishlist(update, context)
    elif text == "🔍 Search Product":
        context.user_data['awaiting_search'] = True
        await update.message.reply_text("🔍 <b>Search Mode Active</b>\n\nType the name of the product you are looking for, or click another menu button to cancel.", parse_mode='HTML')
    elif text == "🔗 Connect to Cart":
        context.user_data['awaiting_cart_id'] = True
        await update.message.reply_text("🔗 <b>Connect to Cart</b>\n\nPlease enter the Cart Pairing Code (e.g. CRT-001) or scan the QR code to link your wishlist:", parse_mode='HTML')
    elif text == "🚪 Disconnect":
        await disconnect_user(update, context)
    elif text == "❓ Help & Info":
        await help_command(update, context)
    elif context.user_data.get('awaiting_search'):
        # Only treat other text as search if explicitly awaiting search
        await search_products(update, context)
    elif context.user_data.get('awaiting_cart_id'):
        await connect_to_cart(update, context)
    else:
        # Unexpected text, suggest using the menu
        # Ensure we are subscribed to our own cart updates if we are connected
        user_id = f"USR-{update.effective_user.id}"
        conn = get_db_connection()
        user_row = conn.execute("SELECT cart_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if user_row and user_row['cart_id']:
             mqtt_client.mySubscribe(f"cart/{user_row['cart_id']}/data")
        conn.close()
        await update.message.reply_text("Sorry, I didn't quite catch that. Please use the menu buttons below! 🛒")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photos sent to the bot, specifically for QR scanning."""
    if not context.user_data.get('awaiting_cart_id'):
        await update.message.reply_text("If you want to connect to a cart, please click '🔗 Connect to Cart' first!")
        return
        
    # Get the photo
    photo_file = await update.message.photo[-1].get_file()
    photo_url = photo_file.file_path # This is a temporary URL from Telegram
    
    # Use QRServer API to read the QR code from the URL
    try:
        response = requests.get(f"https://api.qrserver.com/v1/read-qr-code/?fileurl={photo_url}")
        data = response.json()
        
        # Result format: [{"type":"qrcode","symbol":[{"seq":0,"data":"CRT-001","error":null}]}]
        qr_data = data[0]['symbol'][0]['data']
        
        if qr_data:
            # Simulate a text message with the QR data
            update.message.text = qr_data
            await connect_to_cart(update, context)
        else:
            await update.message.reply_text("❌ No QR code found in this photo. Please make sure the code is clearly visible and try again.")
            
    except Exception as e:
        logger.error(f"QR Reading error: {e}")
        await update.message.reply_text("❌ Sorry, there was an error processing the QR code. Please try typing the code manually.")


async def connect_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cart_id = update.message.text.strip().upper()
    await perform_pairing(cart_id, update, context)

async def perform_pairing(cart_id: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = f"USR-{update.effective_user.id}"
    
    conn = get_db_connection()
    cart = conn.execute("SELECT cart_id FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
    if not cart:
        conn.close()
        await update.message.reply_text(f"❌ Invalid Cart Pairing Code: <b>{cart_id}</b>\nPlease try again or use the menu.", parse_mode='HTML', reply_markup=MAIN_MENU_KBD)
        context.user_data['awaiting_cart_id'] = False
        return
        
    conn.execute("INSERT OR IGNORE INTO users (user_id, cart_id, wish_list) VALUES (?, NULL, '[]')", (user_id,))
    user_row = conn.execute("SELECT wish_list FROM users WHERE user_id = ?", (user_id,)).fetchone()
    wish_list = user_row['wish_list'] if user_row else "[]"
    
    # Link cart
    conn.execute("UPDATE users SET cart_id = ? WHERE user_id = ?", (cart_id, user_id))
    conn.execute("UPDATE carts SET user_id = ?, wish_list = ?, connection_time = ? WHERE cart_id = ?", (user_id, wish_list, datetime.datetime.now().isoformat(), cart_id))
    conn.commit()
    conn.close()
    
    context.user_data['awaiting_cart_id'] = False
    
    # Notify via MQTT
    try:
        mqtt_client.mySubscribe(f"cart/{cart_id}/data")
        payload = {
            "event": "user_connected",
            "user_id": user_id,
            "user_name": update.effective_user.first_name,
            "wish_list": json.loads(wish_list)
        }
        mqtt_client.myPublish(f"cart/{cart_id}/data", payload)
    except Exception as e:
         logger.error(f"MQTT Publish error: {e}")
    
    await update.message.reply_text(f"✅ Successfully paired with Cart <b>{cart_id}</b>!\nYour wishlist has been sent to the cart.", parse_mode='HTML', reply_markup=MAIN_MENU_KBD)

async def disconnect_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = f"USR-{update.effective_user.id}"
    conn = get_db_connection()
    user_row = conn.execute("SELECT cart_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not user_row:
        conn.close()
        await update.message.reply_text("You are not connected to any cart.", reply_markup=MAIN_MENU_KBD)
        return
        
    cart_id = user_row['cart_id']
    
    # Unlink cart from user (preserve wishlist)
    conn.execute("UPDATE users SET cart_id = NULL WHERE user_id = ?", (user_id,))
    
    # If connected to a cart, reset it and restore stock
    if cart_id:
        # Restore shelf stock for all items in the shopping list
        cart_row = conn.execute("SELECT shopping_list FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
        if cart_row and cart_row["shopping_list"]:
            items = json.loads(cart_row["shopping_list"])
            for item_id in items:
                conn.execute("UPDATE products SET shelf_stock = shelf_stock + 1 WHERE product_id = ?", (item_id,))

        conn.execute("UPDATE carts SET user_id=NULL, shopping_list='[]', wish_list='[]', connection_time=NULL WHERE cart_id=?", (cart_id,))
        # Send MQTT notification
        try:
            payload = {"event": "user_disconnected", "user_id": user_id}
            mqtt_client.myPublish(f"cart/{cart_id}/data", payload)
        except Exception:
            pass

    conn.commit()
    conn.close()
    
    await update.message.reply_text("🔌 Disconnected! Your wishlist has been saved, but the cart has been reset and items returned to stock.", reply_markup=MAIN_MENU_KBD)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show an interactive help menu."""
    help_text = (
        "❓ <b>Market Bot Help Menu</b>\n\n"
        "Here are the available features:\n\n"
        "🛒 <b>Market</b>: Browse categories and products.\n"
        "🔍 <b>Search</b>: Find products by typing their name.\n"
        "❤️ <b>Wishlist</b>: Save products you like and see the total cost.\n"
        "🔥 <b>Promos</b>: Look for the '🔥' icon for special discounts!\n\n"
        "Click a button below for more details on a specific feature:"
    )
    keyboard = [
        [InlineKeyboardButton("How to Buy? 🛒", callback_data="help_buy"),
         InlineKeyboardButton("How to Search? 🔍", callback_data="help_search")],
        [InlineKeyboardButton("Wishlist Info ❤️", callback_data="help_wishlist")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_html(help_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(help_text, parse_mode='HTML', reply_markup=reply_markup)

async def search_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for products by name."""
    query_text = update.message.text
    
    if len(query_text) < 2:
        await update.message.reply_text("⚠️ <b>Query too short!</b>\nPlease type at least 2 characters to search.", parse_mode='HTML')
        return
        
    conn = get_db_connection()
    results = conn.execute(
        "SELECT product_id, product_name, price, promotion FROM products WHERE product_name LIKE ? LIMIT 10", 
        (f"%{query_text}%",)
    ).fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text(f"❌ No products found matching '<b>{query_text}</b>'.\nTry another name or check your spelling!", parse_mode='HTML')
        return
        
    keyboard = []
    for p in results:
        promo_tag = f" 🔥 (-{p['promotion']}%)" if p['promotion'] > 0 else ""
        keyboard.append([InlineKeyboardButton(f"{p['product_name']} (€{p['price']}){promo_tag}", callback_data=f"prod_{p['product_id']}")])
    
    await update.message.reply_text(f"✅ Found {len(results)} results for '<b>{query_text}</b>':", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show market categories."""
    conn = get_db_connection()
    categories = [row['category'] for row in conn.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL').fetchall()]
    conn.close()

    if not categories:
        await update.message.reply_text("The market is currently empty!")
        return

    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}_0")])  # Added page 0 suffix

    reply_markup = InlineKeyboardMarkup(keyboard)
    # The persistent keyboard stays visible, so we just send the categories
    await update.message.reply_text("Please choose a category to browse:", reply_markup=reply_markup)

async def view_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View the user's wish list."""
    user_id = f"USR-{update.effective_user.id}"
    user_wishlist = get_user_wishlist(user_id)
    
    if not user_wishlist:
        await update.message.reply_text("Your wish list is empty. Use /market to find products.")
        return
    
    msg = "Your Wishlist ❤️:\n\n"
    total_cost = 0.0
    
    conn = get_db_connection()
    
    # Check if connected to a cart to strike through items
    user_row = conn.execute("SELECT cart_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
    cart_id = user_row['cart_id'] if user_row else None
    scanned_items = []
    if cart_id:
        cart_row = conn.execute("SELECT shopping_list FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
        if cart_row and cart_row['shopping_list']:
            scanned_items = json.loads(cart_row['shopping_list'])

    for item_id in user_wishlist:
        # Find product details
        prod = conn.execute('SELECT product_name, price, promotion FROM products WHERE product_id = ?', (item_id,)).fetchone()
        if prod:
            original_price = prod['price'] or 0.0
            promotion = prod['promotion'] or 0
            current_price = original_price * (1 - promotion / 100)
            
            is_scanned = item_id in scanned_items
            item_name = f"<s>{prod['product_name']}</s>" if is_scanned else prod['product_name']
            
            msg += f"- {item_name} (€{current_price:.2f})"
            if promotion > 0:
                msg += f" (<s>€{original_price:.2f}</s> -{promotion}%)"
            msg += "\n"
            total_cost += current_price
        else:
            msg += f"- Unknown Product ({item_id})\n"
            
    conn.close()
            
    msg += f"\n<b>Total Cost:</b> €{total_cost:.2f}"
    if cart_id:
        msg += f"\n<i>(Items in your cart {cart_id} are struck through)</i>"
        
    await update.message.reply_text(msg, parse_mode='HTML', reply_markup=MAIN_MENU_KBD)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses Callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data

    if data.startswith("cat_"):
        # Show products in this category with pagination (10 per page)
        parts = data.split("_")
        cat = parts[1]
        page = int(parts[2]) if len(parts) > 2 else 0
        limit = 10
        offset = page * limit
        
        conn = get_db_connection()
        # Fetch current page products
        cat_products = conn.execute(
            'SELECT product_id, product_name, price, promotion FROM products WHERE category = ? LIMIT ? OFFSET ?', 
            (cat, limit, offset)
        ).fetchall()
        
        # Check if there is a next page
        next_prod = conn.execute(
            'SELECT product_id FROM products WHERE category = ? LIMIT 1 OFFSET ?', 
            (cat, offset + limit)
        ).fetchone()
        conn.close()
        
        keyboard = []
        for p in cat_products:
            promo_tag = f" 🔥 (-{p['promotion']}%)" if p['promotion'] > 0 else ""
            keyboard.append([InlineKeyboardButton(f"{p['product_name']} (€{p['price']}){promo_tag}", callback_data=f"prod_{p['product_id']}")])
            
        # Navigation buttons
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"cat_{cat}_{page-1}"))
        if next_prod:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"cat_{cat}_{page+1}"))
        
        if nav_row:
            keyboard.append(nav_row)
            
        keyboard.append([InlineKeyboardButton("« Back to Categories", callback_data="back_categories")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text=f"Products in {cat} (Page {page+1}):", reply_markup=reply_markup)
        
    elif data.startswith("prod_"):
        # Show product details and add to wishlist button
        prod_id = data.split("prod_")[1]
        
        conn = get_db_connection()
        prod = conn.execute('SELECT * FROM products WHERE product_id = ?', (prod_id,)).fetchone()
        conn.close()
        
        if prod:
            promotion = prod['promotion'] or 0
            original_price = prod['price']
            
            if promotion > 0:
                discounted_price = original_price * (1 - promotion / 100)
                promo_text = f"🔥 <b>PROMO! -{promotion}%</b> 🔥\n"
                price_text = f"Price: <s>€{original_price:.2f}</s> <b>€{discounted_price:.2f}</b>"
            else:
                promo_text = ""
                price_text = f"Price: €{original_price:.2f}"
                
            text = f"{promo_text}<b>{prod['product_name']}</b>\nCategory: {prod['category'] or 'N/D'}\n{price_text}\nShelf: {prod['shelf_id']} (Stock: {prod['shelf_stock']})"
            keyboard = [
                [InlineKeyboardButton("Add to Wishlist ❤️", callback_data=f"addwish_{prod_id}")],
                [InlineKeyboardButton("« Back to Categories", callback_data="back_categories")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=reply_markup)
            
    elif data.startswith("addwish_"):
        # Add to wishlist
        prod_id = data.split("addwish_")[1]
        user_id = f"USR-{update.effective_user.id}"
            
        conn = get_db_connection()
        prod = conn.execute('SELECT product_name, category FROM products WHERE product_id = ?', (prod_id,)).fetchone()
        conn.close()
        
        cat = prod['category'] if prod else "Other"
        
        keyboard = [
            [InlineKeyboardButton(f"« Back to {cat}", callback_data=f"cat_{cat}_0")],
            [InlineKeyboardButton("🛒 Market", callback_data="back_categories"), InlineKeyboardButton("❤️ Wishlist", callback_data="view_wish_inline")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        added = add_to_user_wishlist(user_id, prod_id, update.effective_user.first_name)
        if added:
            await query.edit_message_text(text=f"✅ Added <b>{prod['product_name']}</b> to your wishlist! ❤️", parse_mode='HTML', reply_markup=reply_markup)
        else:
            await query.edit_message_text(text=f"ℹ️ <b>{prod['product_name']}</b> is already in your wishlist.", parse_mode='HTML', reply_markup=reply_markup)

    elif data == "back_categories" or data == "view_wish_inline":
        if data == "view_wish_inline":
             # Simplified wishlist view for inline button
             user_id = f"USR-{update.effective_user.id}"
             user_wishlist = get_user_wishlist(user_id)
             if not user_wishlist:
                 await query.edit_message_text("Your wishlist is empty!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="back_categories")]]))
                 return
             
             msg = "Your Wishlist ❤️:\n\n"
             total = 0
             conn = get_db_connection()
             
             # Check if connected to a cart
             user_row = conn.execute("SELECT cart_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
             cart_id = user_row['cart_id'] if user_row else None
             scanned_items = []
             if cart_id:
                 cart_row = conn.execute("SELECT shopping_list FROM carts WHERE cart_id = ?", (cart_id,)).fetchone()
                 if cart_row and cart_row['shopping_list']:
                     scanned_items = json.loads(cart_row['shopping_list'])

             for item_id in user_wishlist:
                 p = conn.execute('SELECT product_name, price, promotion FROM products WHERE product_id = ?', (item_id,)).fetchone()
                 if p:
                     original_price = p['price'] or 0.0
                     promo = p['promotion'] or 0
                     price = original_price * (1 - promo/100)
                     
                     is_scanned = item_id in scanned_items
                     item_name = f"<s>{p['product_name']}</s>" if is_scanned else p['product_name']
                     
                     line = f"- {item_name} (€{price:.2f})"
                     if promo > 0:
                         line += f" (<s>€{original_price:.2f}</s>)"
                     msg += line + "\n"
                     total += price
             conn.close()
             msg += f"\n<b>Total: €{total:.2f}</b>"
             if cart_id:
                 msg += f"\n<i>Linked: {cart_id}</i>"
             await query.edit_message_text(msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="back_categories")]]))
             return

        conn = get_db_connection()
        categories = [row['category'] for row in conn.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL').fetchall()]
        conn.close()
        
        keyboard = []
        for cat in categories:
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}_0")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Please choose a category:", reply_markup=reply_markup)

    elif data.startswith("help_"):
        # Interactive help responses
        help_responses = {
            "help_buy": "🛒 <b>How to Buy</b>\n\n1. Use /market or the button.\n2. Choose a category.\n3. Click on a product to see details.\n4. Add it to your wishlist! ❤️",
            "help_search": "🔍 <b>How to Search</b>\n\nYou can search in two ways:\n1. Click 'Search Product' and type a name.\n2. Simply type any product name (e.g., 'Apple') at any time!",
            "help_wishlist": "❤️ <b>Wishlist Info</b>\n\nYour wishlist stores items you like. It automatically calculates the <b>total cost</b>, including any active discounts! 🔥"
        }
        text = help_responses.get(data, "Unknown help topic.")
        keyboard = [[InlineKeyboardButton("« Back to Help", callback_data="back_help")]]
        await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back_help":
        await help_command(update, context)

def main() -> None:
    """Start the bot."""
    
    try:
        mqtt_client.start()
    except Exception as e:
        logger.error(f"Failed to start MQTT Client: {e}")
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("WARNING: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual Telegram Bot Token.")
        # Proceeding without immediate crash so the structure is valid Python, but Telegram will raise an error.
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    from telegram import BotCommand
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("market", market))
    application.add_handler(CommandHandler("wishlist", view_wishlist))
    application.add_handler(CommandHandler("help", help_command))
    
    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handle button clicks from the persistent menu
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Handle photo scans
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Set command list in the Telegram UI
    async def set_commands(app):
        await app.bot.set_my_commands([
            BotCommand("start", "Start the bot"),
            BotCommand("market", "Browse the market"),
            BotCommand("wishlist", "View your wishlist"),
            BotCommand("help", "How to use the bot")
        ])
    
    # We can use post_init for this
    application.post_init = set_commands

    # Run the bot until user presses Ctrl-C
    print("Bot is starting up...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
