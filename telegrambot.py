import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests

# ================= CONFIGURAZIONE =================
# INCOLLA QUI IL TUO TOKEN DI BOTFATHER
TOKEN = "8546839361:AAEpKQvbAqUKA8-EkOHDFVJScO2Ri-dvnbI" 

# URL del Catalog (Microservizio A - Resource Catalog)
# Quando avrai creato l'altro script, questo sarà l'indirizzo a cui chiedere i dati
CATALOG_URL = "http://localhost:8080"

# Abilitiamo i log per vedere eventuali errori nel terminale
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inviato quando l'utente digita /start"""
    user = update.effective_user
    await update.message.reply_html(
        f"Ciao {user.mention_html()}! 👋\nBenvenuto nel <b>Smart Supermarket Bot</b>.",
    )
    
    # Creiamo la tastiera con i pulsanti (Inline Keyboard)
    keyboard = [
        [InlineKeyboardButton("🛒 Sono un Cliente", callback_data='role_client')],
        [InlineKeyboardButton("👔 Sono il Magazziniere", callback_data='role_owner')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Per iniziare, seleziona il tuo ruolo:", 
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il click sui pulsanti"""
    query = update.callback_query
    
    # È obbligatorio "rispondere" alla query per togliere l'icona di caricamento dal pulsante
    await query.answer()

    if query.data == 'role_client':
        # Modifichiamo il messaggio precedente
        await query.edit_message_text(
            text="✅ <b>Modalità Cliente Attiva</b>\n\n"
                 "Comandi disponibili:\n"
                 "/lista - Gestisci la tua lista della spesa\n"
                 "/status - Vedi lo stato del tuo carrello smart\n"
                 "/checkout - Paga e esci",
            parse_mode='HTML'
        )
        # TODO: Qui dovresti inviare una richiesta al Catalog per registrare che 
        # l'utente Telegram ID X è entrato come cliente.
        
    elif query.data == 'role_owner':
        await query.edit_message_text(
            text="✅ <b>Modalità Proprietario Attiva</b>\n\n"
                 "Ti invierò una notifica qui se le scorte scendono sotto la soglia.",
            parse_mode='HTML'
        )

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera il QR code per l'uscita"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("🔄 Sto calcolando il totale col Shopping Manager...")

    # SIMULAZIONE INTERAZIONE MICROSERVIZI
    # Nel progetto reale, qui fai una richiesta HTTP al servizio ShoppingManager
    try:
        # Esempio reale (ora commentato perché il server non esiste):
        # response = requests.get(f"{CATALOG_URL}/checkout?user_id={user_id}")
        # data = response.json()
        # totale = data['total']
        
        # Dati finti per testare il bot ora
        totale_simulato = 45.50
        
        await update.message.reply_text(
            f"🧾 <b>Scontrino Virtuale</b>\n"
            f"Totale da pagare: € {totale_simulato}\n\n"
            f"Ecco il tuo codice per la cassa veloce:",
            parse_mode='HTML'
        )
        
        # Inviamo il codice "QR" (testuale per ora)
        qr_code_text = f"SMART-CART-{user_id}-PAID"
        await update.message.reply_text(f"<code>{qr_code_text}</code>", parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Errore di connessione: {e}")
        await update.message.reply_text("⚠️ Errore: Non riesco a contattare il server del supermercato.")

def main():
    """Punto di ingresso del bot"""
    print("Avvio del bot in corso...")
    
    # Creiamo l'applicazione usando il token
    # IMPORTANTE: Sostituisci la stringa TOKEN in alto!
    application = Application.builder().token(TOKEN).build()

    # Colleghiamo i comandi alle funzioni
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkout", checkout))
    
    # Gestore generico per i pulsanti
    application.add_handler(CallbackQueryHandler(button_handler))

    print("Bot avviato! Premi Ctrl+C per fermarlo.")
    # Avvia il bot in modalità polling (ascolta continuamente i messaggi)
    application.run_polling()

if __name__ == '__main__':
    main()