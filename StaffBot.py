import logging
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_FILE = "catalog.db"
# IMPORTANT: Put your Staff Bot Token here
STAFF_BOT_TOKEN = "8668314574:AAGN3_UzpzlMmKeMRykgAnPAmdai0UlyX3A" 

# Conversation states
ID, NAME, PRICE, CATEGORY, SHELF = range(5)
STOCK_SHELF, STOCK_WAREHOUSE = range(5, 7)
PROMO_PCT = 7
CONFIRM_DELETE = 8

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    reply_keyboard = [
        ["📂 Browse Catalog", "🔍 Search Product"],
        ["➕ Add Product", "📦 Quick View"],
        ["📈 Update Stock", "🔥 Manage Promo"],
        ["❌ Delete Product"]
    ]
    
    welcome_text = (
        "🛠️ **Staff Management Menu** 🛠️\n\n"
        "Welcome Admin. Use the buttons below or the commands to manage the market catalog:\n\n"
        "✨ **Product Management**\n"
        "• /add - Follow instructions to add a new item\n"
        "• /delete <ID> - Remove an item from the database\n\n"
        "📊 **Inventory & Marketing**\n"
        "• /stock <ID> <shelf> <warehouse> - Update quantities\n"
        "• /promo <ID> <%> - Set discount percentage\n\n"
        "🔍 **Lookup**\n"
        "• /view <ID> - See full technical details"
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=False, resize_keyboard=True
        ),
    )

# --- Helper for button presses ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if text == "➕ Add Product":
        return await add_start(update, context)
    elif text == "📂 Browse Catalog":
        return await browse_categories(update, context)
    elif text == "🔍 Search Product":
        await update.message.reply_text("Type the name of the product you want to manage:")
    elif text == "📦 Quick View":
        await update.message.reply_text("Usage: /view <ID> or browse the catalog.")
    elif text == "📈 Update Stock":
        await update.message.reply_text("Usage: /stock <ID> <shelf> <warehouse> or browse to a product.")
    elif text == "🔥 Manage Promo":
        await update.message.reply_text("Usage: /promo <ID> <%> or browse to a product.")
    elif text == "❌ Delete Product":
        await update.message.reply_text("Usage: /delete <ID> or browse to a product.")
    else:
        # Treat other text as search
        if len(text) >= 2:
            return await search_staff_products(update, context)

async def search_staff_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query_text = update.message.text
    conn = get_db_connection()
    results = conn.execute(
        "SELECT product_id, product_name, price, promotion FROM products WHERE product_name LIKE ? LIMIT 10", 
        (f"%{query_text}%",)
    ).fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text(f"No products found matching '{query_text}'.")
        return
        
    keyboard = []
    for p in results:
        promo_tag = f" 🔥 (-{p['promotion']}%)" if p['promotion'] > 0 else ""
        keyboard.append([InlineKeyboardButton(f"{p['product_name']} [{p['product_id']}]{promo_tag}", callback_data=f"staff_prod_{p['product_id']}")])
    
    await update.message.reply_text(f"Search results for '{query_text}':", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Browsing & Interaction ---

async def browse_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_db_connection()
    categories = [row['category'] for row in conn.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL').fetchall()]
    conn.close()

    if not categories:
        await update.message.reply_text("The catalog is empty!")
        return

    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"staff_cat_{cat}_0")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a category to manage:", reply_markup=reply_markup)

async def staff_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("staff_cat_"):
        parts = data.split("_")
        cat = parts[2]
        page = int(parts[3])
        limit = 10
        offset = page * limit
        
        conn = get_db_connection()
        products = conn.execute(
            'SELECT product_id, product_name, price, promotion FROM products WHERE category = ? LIMIT ? OFFSET ?', 
            (cat, limit, offset)
        ).fetchall()
        
        next_prod = conn.execute(
            'SELECT product_id FROM products WHERE category = ? LIMIT 1 OFFSET ?', 
            (cat, offset + limit)
        ).fetchone()
        conn.close()
        
        keyboard = []
        for p in products:
            promo_info = f" 🔥 (-{p['promotion']}%)" if p['promotion'] > 0 else ""
            keyboard.append([InlineKeyboardButton(f"{p['product_name']} [{p['product_id']}]{promo_info}", callback_data=f"staff_prod_{p['product_id']}")])
            
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"staff_cat_{cat}_{page-1}"))
        if next_prod:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"staff_cat_{cat}_{page+1}"))
        if nav_row: keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton("« Back to Categories", callback_data="staff_back_cats")])
        await query.edit_message_text(f"Products in {cat} (Page {page+1}):\nPick one to edit:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "staff_back_cats":
        conn = get_db_connection()
        categories = [row['category'] for row in conn.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL').fetchall()]
        conn.close()
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"staff_cat_{cat}_0")] for cat in categories]
        await query.edit_message_text("Select a category to manage:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("staff_prod_"):
        pid = data.split("_")[2]
        await show_staff_product_view(query, pid)

    elif data.startswith("edit_stock_"):
        pid = data.split("_")[2]
        context.user_data['pid'] = pid
        await query.message.reply_text(f"Updating Stock for **{pid}**.\nEnter new Shelf Stock:")
        return STOCK_SHELF # This will trigger the ConversationHandler if it's an entry point

async def show_staff_product_view(query_or_update, pid):
    conn = get_db_connection()
    prod = conn.execute('SELECT * FROM products WHERE product_id = ?', (pid,)).fetchone()
    conn.close()
    
    if prod:
        msg = (
            f"🛠️ **Management: {prod['product_name']}**\n"
            f"ID: `{prod['product_id']}`\n"
            f"Price: €{prod['price']:.2f} | Promo: {prod['promotion']}%\n"
            f"Category: {prod['category']}\n"
            f"--- Inventory ---\n"
            f"📍 Shelf: {prod['shelf_id']} (Stock: {prod['shelf_stock']})\n"
            f"📦 Warehouse Stock: {prod['warehouse_stock']}"
        )
        keyboard = [
            [InlineKeyboardButton("📈 Edit Stock", callback_data=f"edit_stock_{pid}"),
             InlineKeyboardButton("🔥 Edit Promo", callback_data=f"edit_promo_{pid}")],
            [InlineKeyboardButton("❌ Delete Product", callback_data=f"staff_del_{pid}")],
            [InlineKeyboardButton("« Back to List", callback_data=f"staff_cat_{prod['category']}_0")]
        ]
        
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query_or_update.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # Fallback if product deleted
        if hasattr(query_or_update, 'edit_message_text'):
            await query_or_update.edit_message_text("Error: Product not found.")

# --- Edit Stock Conversation ---

async def edit_stock_start_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pid = query.data.split("_")[2]
    context.user_data['pid'] = pid
    await query.message.reply_text(f"Updating Stock for `{pid}`.\nEnter new Shelf Stock:")
    return STOCK_SHELF

async def edit_stock_shelf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['shelf'] = int(update.message.text)
        await update.message.reply_text("Enter new Warehouse Stock:")
        return STOCK_WAREHOUSE
    except ValueError:
        await update.message.reply_text("Invalid number. Please enter an integer:")
        return STOCK_SHELF

async def edit_stock_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        warehouse = int(update.message.text)
        shelf = context.user_data['shelf']
        pid = context.user_data['pid']
        
        conn = get_db_connection()
        conn.execute('UPDATE products SET shelf_stock = ?, warehouse_stock = ? WHERE product_id = ?', (shelf, warehouse, pid))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Stock updated for {pid}!")
        # Return to product view
        await show_staff_product_view(update, pid)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid number. Please enter an integer:")
        return STOCK_WAREHOUSE

# --- Edit Promo Conversation ---

async def edit_promo_start_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pid = query.data.split("_")[2]
    context.user_data['pid'] = pid
    await query.message.reply_text(f"Setting promotion for `{pid}`.\nEnter discount percentage (0-100):")
    return PROMO_PCT

async def edit_promo_pct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        pct = int(update.message.text)
        pid = context.user_data['pid']
        
        conn = get_db_connection()
        conn.execute('UPDATE products SET promotion = ? WHERE product_id = ?', (pct, pid))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Promotion set to {pct}% for {pid}!")
        # Return to product view
        await show_staff_product_view(update, pid)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid number. Enter a percentage (0-100):")
        return PROMO_PCT

# --- Delete Confirmation ---

async def delete_confirm_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pid = query.data.split("_")[2]
    context.user_data['pid'] = pid
    
    keyboard = [[InlineKeyboardButton("⚠️ YES, DELETE", callback_data=f"staff_del_confirm"),
                 InlineKeyboardButton("Cancel", callback_data=f"staff_prod_{pid}")]]
    await query.edit_message_text(f"ARE YOU SURE you want to delete product `{pid}`? This cannot be undone.", 
                                  reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CONFIRM_DELETE

async def delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This is slightly tricky with buttons in conversation. 
    # Usually we handle buttons in a specific state.
    query = update.callback_query
    await query.answer()
    
    if query.data == "staff_del_confirm":
        pid = context.user_data['pid']
        conn = get_db_connection()
        conn.execute('DELETE FROM products WHERE product_id = ?', (pid,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"🗑️ Product `{pid}` has been permanently deleted.")
    else:
        # Cancelled via "staff_prod_PID" button which is handled by staff_button_callback
        # but since we are in a state, we need to end it.
        pass
    
    return ConversationHandler.END

# --- Add Product Conversation ---

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add product conversation."""
    await update.message.reply_text("Enter the Product ID (e.g., FRU-1234):")
    return ID

async def add_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['pid'] = update.message.text.upper()
    await update.message.reply_text("Enter the Product Name:")
    return NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Enter the Price (e.g., 2.50):")
    return PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        context.user_data['price'] = float(update.message.text.replace(',', '.'))
        await update.message.reply_text("Enter the Category (e.g., Colazione):")
        return CATEGORY
    except ValueError:
        await update.message.reply_text("Invalid price. Please enter a number (e.g., 4.99):")
        return PRICE

async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['category'] = update.message.text
    await update.message.reply_text("Enter the Shelf ID (e.g., S-1):")
    return SHELF

async def add_shelf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    shelf_id = update.message.text.upper()
    data = context.user_data
    
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO products (product_id, product_name, price, category, shelf_id, shelf_stock, warehouse_stock, promotion)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0)
        ''', (data['pid'], data['name'], data['price'], data['category'], shelf_id))
        conn.commit()
        await update.message.reply_text(f"✅ Product {data['name']} added successfully!")
    except sqlite3.IntegrityError:
        await update.message.reply_text(f"❌ Error: Product ID {data['pid']} already exists.")
    finally:
        conn.close()
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Quick Admin Commands ---

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /delete <ID>")
        return
    
    pid = context.args[0].upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE product_id = ?', (pid,))
    conn.commit()
    
    if cursor.rowcount > 0:
        await update.message.reply_text(f"✅ Product {pid} deleted.")
    else:
        await update.message.reply_text(f"❓ Product {pid} not found.")
    conn.close()

async def update_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /stock <ID> <shelf_count> <warehouse_count>")
        return
    
    try:
        pid = context.args[0].upper()
        shelf = int(context.args[1])
        warehouse = int(context.args[2])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE products SET shelf_stock = ?, warehouse_stock = ? WHERE product_id = ?', (shelf, warehouse, pid))
        conn.commit()
        
        if cursor.rowcount > 0:
            await update.message.reply_text(f"✅ Stock updated for {pid}.")
        else:
            await update.message.reply_text(f"❓ Product {pid} not found.")
        conn.close()
    except ValueError:
        await update.message.reply_text("Error: Stock counts must be integers.")

async def update_promo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /promo <ID> <percentage>")
        return
    
    try:
        pid = context.args[0].upper()
        pct = int(context.args[1])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE products SET promotion = ? WHERE product_id = ?', (pct, pid))
        conn.commit()
        
        if cursor.rowcount > 0:
            await update.message.reply_text(f"✅ Promotion set to {pct}% for {pid}.")
        else:
            await update.message.reply_text(f"❓ Product {pid} not found.")
        conn.close()
    except ValueError:
        await update.message.reply_text("Error: Percentage must be an integer.")

async def view_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /view <ID>")
        return
    
    pid = context.args[0].upper()
    conn = get_db_connection()
    prod = conn.execute('SELECT * FROM products WHERE product_id = ?', (pid,)).fetchone()
    conn.close()
    
    if prod:
        await show_staff_product_view(update, pid)
    else:
        await update.message.reply_text(f"❓ Product {pid} not found.")

def main() -> None:
    """Start the bot."""
    if STAFF_BOT_TOKEN == "YOUR_STAFF_BOT_TOKEN_HERE":
        print("WARNING: Replace STAFF_BOT_TOKEN with your unique token.")
        
    application = ApplicationBuilder().token(STAFF_BOT_TOKEN).build()

    # Combined Administrative Management Conversation
    admin_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start),
            CallbackQueryHandler(edit_stock_start_btn, pattern=r"^edit_stock_"),
            CallbackQueryHandler(edit_promo_start_btn, pattern=r"^edit_promo_"),
            CallbackQueryHandler(delete_confirm_start, pattern=r"^staff_del_")
        ],
        states={
            ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_id)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_category)],
            SHELF: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_shelf)],
            STOCK_SHELF: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_stock_shelf)],
            STOCK_WAREHOUSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_stock_warehouse)],
            PROMO_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_promo_pct)],
            CONFIRM_DELETE: [CallbackQueryHandler(delete_execute, pattern=r"^staff_del_confirm$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(admin_conv)
    application.add_handler(CommandHandler("delete", delete_product))
    application.add_handler(CommandHandler("stock", update_stock))
    application.add_handler(CommandHandler("promo", update_promo))
    application.add_handler(CommandHandler("view", view_product))
    
    # Callback queries for browsing (that don't start a conversation)
    application.add_handler(CallbackQueryHandler(staff_button_callback, pattern=r"^staff_"))
    
    # Handle button clicks from the persistent menu
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("StaffBot is starting up...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
