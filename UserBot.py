import json
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

import sqlite3

DB_FILE = "catalog.db"
BOT_TOKEN = "8678627934:AAG9c3Jm694EzBLCBEqcoGGnQfSou3uslaY" # Replace with your actual token

# In-memory storage for user wishlists: { user_id: [product_id, ...] }
wishlists = {}

# In-memory storage for search context: { user_id: query_text }
search_queries = {}

MAIN_MENU_KBD = ReplyKeyboardMarkup(
    [["🛒 Browse Market", "🔍 Search Product"], ["❤️ My Wishlist"]],
    resize_keyboard=True
)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # To access columns by name
    return conn

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
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
    if text == "🛒 Browse Market":
        await market(update, context)
    elif text == "❤️ My Wishlist":
        await view_wishlist(update, context)
    elif text == "🔍 Search Product":
        await update.message.reply_text("Type the name of the product you are looking for:")
    else:
        # Treat other text as search query
        await search_products(update, context)

async def search_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for products by name."""
    query_text = update.message.text
    if len(query_text) < 2:
        return # Ignore very short messages if they aren't commands
        
    conn = get_db_connection()
    results = conn.execute(
        "SELECT product_id, product_name, price, promotion FROM products WHERE product_name LIKE ? LIMIT 10", 
        (f"%{query_text}%",)
    ).fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text(f"No products found matching '{query_text}'. Try another name!")
        return
        
    keyboard = []
    for p in results:
        promo_tag = f" 🔥 (-{p['promotion']}%)" if p['promotion'] > 0 else ""
        keyboard.append([InlineKeyboardButton(f"{p['product_name']} (€{p['price']}){promo_tag}", callback_data=f"prod_{p['product_id']}")])
    
    await update.message.reply_text(f"Search results for '{query_text}':", reply_markup=InlineKeyboardMarkup(keyboard))

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
    user_id = update.effective_user.id
    user_wishlist = wishlists.get(user_id, [])
    
    if not user_wishlist:
        await update.message.reply_text("Your wish list is empty. Use /market to find products.")
        return
    
    msg = "Your Wishlist ❤️:\n\n"
    total_cost = 0.0
    
    conn = get_db_connection()
    
    for item_id in user_wishlist:
        # Find product details
        prod = conn.execute('SELECT product_name, price, promotion FROM products WHERE product_id = ?', (item_id,)).fetchone()
        if prod:
            original_price = prod['price'] or 0.0
            promotion = prod['promotion'] or 0
            current_price = original_price * (1 - promotion / 100)
            
            msg += f"- {prod['product_name']} (€{current_price:.2f})"
            if promotion > 0:
                msg += f" (<s>€{original_price:.2f}</s> -{promotion}%)"
            msg += "\n"
            total_cost += current_price
        else:
            msg += f"- Unknown Product ({item_id})\n"
            
    conn.close()
            
    msg += f"\n<b>Total Cost:</b> €{total_cost:.2f}"
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
        if user_id not in wishlists:
            wishlists[user_id] = []
            
        conn = get_db_connection()
        prod = conn.execute('SELECT product_name, category FROM products WHERE product_id = ?', (prod_id,)).fetchone()
        conn.close()
        
        cat = prod['category'] if prod else "Other"
        
        keyboard = [
            [InlineKeyboardButton(f"« Back to {cat}", callback_data=f"cat_{cat}_0")],
            [InlineKeyboardButton("🛒 Market", callback_data="back_categories"), InlineKeyboardButton("❤️ Wishlist", callback_data="view_wish_inline")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if prod_id not in wishlists[user_id]:
            wishlists[user_id].append(prod_id)
            await query.edit_message_text(text=f"✅ Added <b>{prod['product_name']}</b> to your wishlist! ❤️", parse_mode='HTML', reply_markup=reply_markup)
        else:
            await query.edit_message_text(text=f"ℹ️ <b>{prod['product_name']}</b> is already in your wishlist.", parse_mode='HTML', reply_markup=reply_markup)

    elif data == "back_categories" or data == "view_wish_inline":
        if data == "view_wish_inline":
             # We can't easily call view_wishlist here because it expects an Update with a certain format
             # but we can just implement a simplified version or redirect
             user_wishlist = wishlists.get(user_id, [])
             if not user_wishlist:
                 await query.edit_message_text("Your wishlist is empty!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="back_categories")]]))
                 return
             
             msg = "Your Wishlist ❤️:\n\n"
             total = 0
             conn = get_db_connection()
             for item_id in user_wishlist:
                 p = conn.execute('SELECT product_name, price, promotion FROM products WHERE product_id = ?', (item_id,)).fetchone()
                 if p:
                     price = p['price'] * (1 - p['promotion']/100)
                     msg += f"- {p['product_name']} (€{price:.2f})\n"
                     total += price
             conn.close()
             msg += f"\n<b>Total: €{total:.2f}</b>"
             await query.edit_message_text(msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="back_categories")]]))
             return

        conn = get_db_connection()
        categories = [row['category'] for row in conn.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL').fetchall()]
        conn.close()
        
        keyboard = []
        for cat in categories:
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}_0")])  # Send to page 0
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Please choose a category:", reply_markup=reply_markup)

def main() -> None:
    """Start the bot."""
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("WARNING: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual Telegram Bot Token.")
        # Proceeding without immediate crash so the structure is valid Python, but Telegram will raise an error.
        
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register commands for the bot menu
    from telegram import BotCommand
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("market", market))
    application.add_handler(CommandHandler("wishlist", view_wishlist))
    
    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handle button clicks from the persistent menu
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Set command list in the Telegram UI
    async def set_commands(app):
        await app.bot.set_my_commands([
            BotCommand("start", "Start the bot"),
            BotCommand("market", "Browse the market"),
            BotCommand("wishlist", "View your wishlist")
        ])
    
    # We can use post_init for this
    application.post_init = set_commands

    # Run the bot until user presses Ctrl-C
    print("Bot is starting up...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
