import os

files = {
    'smartmarket_MQTT.py': [
        ('Gestione errore nella ricezione', 'Error handling on receive'),
        ('Gestione errore nella pubblicazione', 'Error handling on publish')
    ],
    'create_db.py': [
        ('Generiamo N scaffali per ogni categoria (max 4 prodotti diversi per scaffale o similar)', 'Generate N shelves for each category (max 4 different products per shelf)')
    ],
    'reset_sessions.py': [
        ('Errore durante la pulizia del database:', 'Error cleaning the database:')
    ],
    'AnalyticsBot.py': [
        ('Database non trovato! Devi avere catalog.db nella stessa cartella.', 'Database not found! catalog.db must be in the same directory.'),
        ('Nessuna transazione trovata nel database.', 'No transactions found in the database.'),
        ('TABELLA RIASSUNTIVA AZIENDALE', 'COMPANY SUMMARY TABLE'),
        ('Numero Transazioni', 'Number of Transactions'),
        ('Totale Articoli Venduti', 'Total Items Sold'),
        ('Ricavo Totale', 'Total Revenue'),
        ('Ricavo Medio per Transazione', 'Avg Revenue per Transaction'),
        ('PERFORMANCE SINGOLI PRODOTTI', 'INDIVIDUAL PRODUCT PERFORMANCE'),
        ('Nome Sconosciuto', 'Unknown Name'),
        ('Venduti', 'Sold'),
        ('MEDIA PERMANENZA E SPESE', 'AVERAGE DWELL TIME AND EXPENSES'),
        ('Permanenza Media nel Supermercato', 'Average Supermarket Dwell Time'),
        ('minuti', 'minutes'),
        ('Media Euro spesi al minuto', 'Average Euros spent per minute'),
        ('per utente', 'per user'),
        ('AFFLUENZA ORARIA (Acquirenti)', 'HOURLY FOOTFALL (Buyers)'),
        ('Fascia', 'Slot'),
        ('acquirenti', 'buyers'),
        ('MARKET BASKET ANALYSIS (Top 5 Abbinamenti)', 'MARKET BASKET ANALYSIS (Top 5 Pairings)'),
        ('Sconosciuto', 'Unknown'),
        ('Comprati insieme', 'Bought together'),
        ('volte', 'times'),
        ('Nessuna correlazione trovata negli acquisti passati.', 'No correlation found in past purchases.'),
        ('Dashboard UI esportata in', 'Dashboard UI exported to'),
        ('Salto le Analytics Storiche su ThingSpeak.', 'Skipping Historical Analytics on ThingSpeak.'),
        ('NOTA PER IL PROGETTO: Inserisci il TUO Channel ID dentro AnalyticsBot.py per abilitare il modulo.', 'PROJECT NOTE: Insert YOUR Channel ID inside AnalyticsBot.py to enable the module.'),
        ("In questo modo dimostrerete al professore di utilizzare l'API REST per pre-processare lo storico.", "This will demonstrate the use of REST API to pre-process the history."),
        ('Scaricando i dati storici dal Canale ThingSpeak', 'Downloading historical data from ThingSpeak Channel'),
        ('Successo: Prelevati', 'Success: Fetched'),
        ('pacchetti storici dal sensore IoT.', 'historical packets from IoT sensor.'),
        ('Nessun dato storico trovato.', 'No historical data found.'),
        ('Campi 1-7 vuoti (Heatmap non ancora popolata in ThingSpeak).', 'Fields 1-7 empty (Heatmap not yet populated in ThingSpeak).'),
        ('ANALISI CORRELAZIONE REPARTI (da Dati Storici Cloud)', 'DEPARTMENT CORRELATION ANALYSIS (from Cloud Historical Data)'),
        ('interazioni fisiche rilevate.', 'physical interactions detected.'),
        ('Pre-processing completato: il sistema ha correlato con successo lo storico!', 'Pre-processing completed: the system has successfully correlated the history!'),
        ('Errore REST API ThingSpeak: HTTP', 'ThingSpeak REST API Error: HTTP'),
        ('Chiamata a ThingSpeak fallita:', 'ThingSpeak call failed:'),
        ('Requisito del Professore: Calcolo complesso / Pre-processing sui dati ThingSpeak', 'Professor Requirement: Complex calculation / Pre-processing on ThingSpeak data'),
        ('Calcoliamo la "Zona più Calda storica" sommando le interazioni passate dei Field 1-7 (Heatmap)', 'Calculate the "Historical Hottest Zone" by summing past interactions of Fields 1-7 (Heatmap)'),
        ('e calcolando la Deviazione delle zone.', 'and calculating the Zone Deviation.'),
        ('Conta vendite per ID prodotto', 'Count sales per product ID'),
        ('Conta vendite abbinate', 'Count paired sales'),
        ('4 Fasce orarie', '4 Time slots'),
        ('come richiesto', 'as requested'),
        ('Calcolo Performance Singoli Prodotti', 'Single Products Performance Calculation'),
        ('Algoritmo di associazione per coppie frequenti', 'Association algorithm for frequent pairs'),
        ('Suddivisione transazioni per Fasce Orarie', 'Transaction split by Time Slots'),
        ('Preleviamo tutte le transazioni storiche', 'Fetch all historical transactions'),
        ('Oppure potremmo aggiungere', 'Or we could add'),
        ('per la tabella giornaliera', 'for the daily table'),
        ('Raccogliamo anche i nomi dei prodotti con una query', 'We also fetch product names with a query'),
        ('Total dwell time è in secondi', 'Total dwell time is in seconds')
    ]
}

for filename, replacements in files.items():
    if not os.path.exists(filename): continue
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    for old, new in replacements:
        content = content.replace(old, new)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
print('Translations applied.')
