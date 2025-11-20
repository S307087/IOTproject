import logging
import json
import random
import os
import qrcode
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# ==========================================
# CONFIGURAZIONE
# ==========================================
BOT_TOKEN = "8546839361:AAEpKQvbAqUKA8-EkOHDFVJScO2Ri-dvnbI"
CATALOG_FILE = "catalog.json"
PAGE_SIZE = 6

# SESSIONS = { chat_id: { 
#    'target_list': { pid: {'qty': int, 'data': obj} }, 
#    'cart_items': [obj, obj, ...],
#    ...
# }}
SESSIONS = {}
CATALOG_DB = []

# ==========================================
# GESTIONE CATALOGO
# ==========================================
def load_catalog():
    global CATALOG_DB
    if not os.path.exists(CATALOG_FILE):
        print(f"❌ Errore: {CATALOG_FILE} non trovato.")
        return False
    with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
        CATALOG_DB = json.load(f).get("products", [])
    print(f"✅ Catalogo caricato: {len(CATALOG_DB)} prodotti.")
    return True

def get_categories():
    return sorted(list(set(p['category'] for p in CATALOG_DB)))

def get_products_by_category(category):
    return [p for p in CATALOG_DB if p['category'] == category]

def get_product_by_id(pid):
    for p in CATALOG_DB:
        if str(p['productID']) == str(pid):
            return p
    return None

# ==========================================
# HELPERS TASTIERA
# ==========================================
def build_catalog_keyboard(category, page, target_dict):
    products = get_products_by_category(category)
    total_pages = (len(products) + PAGE_SIZE - 1) // PAGE_SIZE
    
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    current_batch = products[start:end]
    
    keyboard = []
    
    for p in current_batch:
        pid = str(p['productID'])
        qty = target_dict.get(pid, {}).get('qty', 0)
        
        icon = "✅" if qty > 0 else "⬜️"
        qty_label = f"(x{qty})" if qty > 0 else ""
        
        label = f"{icon} {p['productName']} {qty_label} - €{p['price']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"add_{pid}")])
    
    # Navigazione
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prec", callback_data=f"nav_prev"))
    nav_row.append(InlineKeyboardButton(f"Pag {page+1}/{total_pages}", callback_data="noop"))
    if end < len(products):
        nav_row.append(InlineKeyboardButton("Succ ➡️", callback_data=f"nav_next"))
    
    keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🔙 Reparti", callback_data='menu_categories')])
    
    return keyboard

# ==========================================
# LOGICA BOT
# ==========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    SESSIONS[chat_id] = {
        "target_list": {},
        "cart_items": [],
        "status": "planning",
        "view": {"cat": None, "page": 0}
    }

    msg = (
        f"👋 Ciao {user.first_name}!\n"
        f"Benvenuto in **Smart Market V6**.\n\n"
        f"1. Prepara la lista (puoi mettere più quantità per lo stesso prodotto).\n"
        f"2. Simula la spesa.\n"
        f"3. Al checkout vedrai le differenze e il QR Code."
    )
    kb = [[InlineKeyboardButton("📝 Crea Lista", callback_data='menu_categories')]]
    await update.message.reply_markdown(msg, reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    
    if chat_id not in SESSIONS:
        await query.answer("Sessione scaduta")
        await query.edit_message_text("⚠️ Sessione scaduta. /start")
        return

    session = SESSIONS[chat_id]
    data = query.data

    # --- MENU CATEGORIE ---
    if data == 'menu_categories':
        await query.answer()
        session['view']['cat'] = None
        
        keyboard = []
        for cat in get_categories():
            keyboard.append([InlineKeyboardButton(f"📂 {cat}", callback_data=f"cat_{cat}")])
        
        total_qty = sum(i['qty'] for i in session['target_list'].values())
        keyboard.append([InlineKeyboardButton(f"✅ VAI ALLA LISTA ({total_qty})", callback_data='view_list')])
        
        await query.edit_message_text("📂 **Seleziona Reparto**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # --- NAVIGAZIONE PRODOTTI ---
    elif data.startswith('cat_'):
        await query.answer()
        cat_name = data.split('_')[1]
        session['view']['cat'] = cat_name
        session['view']['page'] = 0
        kb = build_catalog_keyboard(cat_name, 0, session['target_list'])
        await query.edit_message_text(f"📂 Reparto: **{cat_name}**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data in ['nav_prev', 'nav_next']:
        await query.answer()
        if data == 'nav_prev': session['view']['page'] = max(0, session['view']['page'] - 1)
        else: session['view']['page'] += 1
        
        cat = session['view']['cat']
        kb = build_catalog_keyboard(cat, session['view']['page'], session['target_list'])
        await query.edit_message_text(f"📂 Reparto: **{cat}**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    # --- ADD QUANTITY ---
    elif data.startswith('add_'):
        pid = data.split('_')[1]
        product = get_product_by_id(pid)
        
        if product:
            if pid not in session['target_list']:
                session['target_list'][pid] = {'qty': 0, 'data': product}
            
            session['target_list'][pid]['qty'] += 1
            new_qty = session['target_list'][pid]['qty']
            
            await query.answer(f"Aggiunto! Ora: {new_qty}")
            
            # Refresh Tastiera
            cat = session['view']['cat']
            page = session['view']['page']
            kb = build_catalog_keyboard(cat, page, session['target_list'])
            try:
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
            except:
                pass

    # --- VIEW LIST ---
    elif data == 'view_list':
        await query.answer()
        items = session['target_list']
        if not items:
            await query.edit_message_text("📭 Lista vuota.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Indietro", callback_data='menu_categories')]]))
            return

        text = "📝 **LA TUA LISTA**\n\n"
        tot_eur = 0
        for pid, info in items.items():
            p = info['data']
            q = info['qty']
            subtot = p['price'] * q
            text += f"• {q}x {p['productName']} (€{subtot:.2f})\n"
            tot_eur += subtot
            
        text += f"\n💰 **Budget Stimato: €{tot_eur:.2f}**"
        
        kb = [
            [InlineKeyboardButton("🗑️ Svuota", callback_data='clear_list')],
            [InlineKeyboardButton("➕ Aggiungi altro", callback_data='menu_categories')],
            [InlineKeyboardButton("🛒 VAI IN NEGOZIO", callback_data='start_shopping')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data == 'clear_list':
        session['target_list'] = {}
        await query.answer("Lista svuotata!")
        await button_handler(update, context)

    # --- SHOPPING ---
    elif data == 'start_shopping':
        await query.answer()
        msg = "🛒 **Sei nel negozio.**\nSimula scansione prodotti:"
        kb = [
            [InlineKeyboardButton("📷 Simula Scansione", callback_data='scan_random')],
            [InlineKeyboardButton("💳 Vai in Cassa", callback_data='checkout')]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data == 'scan_random':
        await query.answer()
        item = random.choice(CATALOG_DB)
        session['cart_items'].append(item)
        
        # Feedback "Smart"
        pid = str(item['productID'])
        planned_info = session['target_list'].get(pid)
        planned_qty = planned_info['qty'] if planned_info else 0
        
        # Quante ne ho nel carrello?
        cart_qty = sum(1 for x in session['cart_items'] if str(x['productID']) == pid)
        
        if planned_qty == 0:
            status = "⚠️ EXTRA (Non in lista)"
        elif cart_qty <= planned_qty:
            status = f"✅ In Lista ({cart_qty}/{planned_qty})"
        else:
            status = f"⚠️ Eccesso ({cart_qty}/{planned_qty})"
            
        msg = (
            f"📷 **BIP!** {item['productName']}\n"
            f"Prezzo: €{item['price']} | Peso: {item['weight']}g\n"
            f"Stato: {status}\n\n"
            f"Carrello: {len(session['cart_items'])} articoli"
        )
        kb = [
            [InlineKeyboardButton("📷 Scansiona ancora", callback_data='scan_random')],
            [InlineKeyboardButton("💳 Vai in Cassa", callback_data='checkout')]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    # --- CHECKOUT CON CONFRONTO ---
    elif data == 'checkout':
        await query.answer()
        cart = session['cart_items']
        target = session['target_list']
        
        # Calcola conteggi carrello
        cart_counts = {}
        total_price = 0
        for p in cart:
            pid = str(p['productID'])
            cart_counts[pid] = cart_counts.get(pid, 0) + 1
            total_price += p['price']

        report = f"🧾 **SCONTRINO SMART**\n\n"
        
        # 1. Analisi Lista
        ok_items = []
        missing_items = []
        extra_planned_items = [] # Presi più del previsto ma erano in lista

        for pid, info in target.items():
            p_name = info['data']['productName']
            plan_q = info['qty']
            real_q = cart_counts.get(pid, 0)
            
            if real_q == 0:
                missing_items.append(f"- {p_name} (x{plan_q})")
            elif real_q < plan_q:
                missing_items.append(f"- {p_name} (Presi {real_q}/{plan_q})")
            elif real_q == plan_q:
                ok_items.append(f"✅ {p_name} (x{plan_q})")
            else: # real > plan
                ok_items.append(f"✅ {p_name} (x{plan_q})")
                extra_planned_items.append(f"⚠️ + {p_name} (Extra x{real_q - plan_q})")

        # 2. Analisi Extra puri (non in lista)
        pure_extra = []
        for pid, qty in cart_counts.items():
            if pid not in target:
                # Trova nome
                p_obj = next((x for x in cart if str(x['productID']) == pid), None)
                name = p_obj['productName'] if p_obj else "???"
                pure_extra.append(f"⚠️ + {name} (x{qty})")

        # Costruzione Testo
        if ok_items:
            report += "**PRESI CORRETTAMENTE:**\n" + "\n".join(ok_items) + "\n\n"
        
        if missing_items:
            report += "❌ **DIMENTICATI:**\n" + "\n".join(missing_items) + "\n\n"
            
        if extra_planned_items or pure_extra:
            report += "⚠️ **EXTRA:**\n"
            if extra_planned_items: report += "\n".join(extra_planned_items) + "\n"
            if pure_extra: report += "\n".join(pure_extra) + "\n"
            report += "\n"
            
        report += f"💰 **TOTALE: €{total_price:.2f}**"

        kb = [[InlineKeyboardButton("📲 Genera QR Code", callback_data='gen_qr')]]
        await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data == 'gen_qr':
        total = sum(p['price'] for p in session['cart_items'])
        if total == 0:
            await query.answer("Totale zero!")
            return
            
        url = f"https://pay.smartmarket.it/v1/checkout?amt={total:.2f}"
        
        qr = qrcode.QRCode(box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        
        await context.bot.send_photo(chat_id, photo=bio, caption=f"💳 **Paga €{total:.2f}**\nGrazie!")
        
        kb = [[InlineKeyboardButton("🏠 Nuova Spesa", callback_data='menu_categories')]]
        await context.bot.send_message(chat_id, "Sessione terminata.", reply_markup=InlineKeyboardMarkup(kb))

if __name__ == '__main__':
    if load_catalog():
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        print("🤖 Bot V6 (Smart Comparison + MultiQty) running...")
        app.run_polling()