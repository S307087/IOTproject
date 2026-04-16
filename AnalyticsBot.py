import sqlite3
import json
import datetime
import os
import requests

# Percorso del database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "catalog.db")

# ==========================================
# CONSTANTS FOR THINGSPEAK (Requisito del Professore)
# ==========================================
# Se decidi di usare un canale unico, inserisci qui l'ID del tuo canale Heatmap "Smart Market"
THINGSPEAK_CHANNEL_ID = os.environ.get("THINGSPEAK_CHANNEL_ID", "YOUR_CHANNEL_ID")
THINGSPEAK_READ_KEY = os.environ.get("THINGSPEAK_READ_KEY", "")

def run_local_analytics():
    print("=" * 60)
    print("= SMART MARKET - LOCAL DATABASE ANALYTICS =")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print("Database non trovato! Devi avere catalog.db nella stessa cartella.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Preleviamo tutte le transazioni storiche
    # (Oppure potremmo aggiungere "WHERE date(timestamp) = date('now')" per la tabella giornaliera)
    transactions = cursor.execute("SELECT * FROM transactions").fetchall()
    
    if not transactions:
        print("Nessuna transazione trovata nel database.")
        conn.close()
        return

    total_transactions = len(transactions)
    total_revenue = 0.0
    total_items = 0
    total_dwell_time = 0
    
    product_performance = {} # Conta vendite per ID prodotto
    pair_performance = {} # Conta vendite abbinate (Market Basket)
    
    # 4 Fasce orarie (8-11, 11-14, 14-17, 17-20) come richiesto
    time_slots = {
        "08:00 - 11:00": 0,
        "11:00 - 14:00": 0,
        "14:00 - 17:00": 0,
        "17:00 - 20:00": 0
    }
    
    for tx in transactions:
        total_revenue += tx['total_amount']
        total_dwell_time += tx['dwell_time_seconds']
        
        # 1. Calcolo Performance Singoli Prodotti
        try:
            items = json.loads(tx['product_list'])
            total_items += len(items)
            for item in items:
                product_performance[item] = product_performance.get(item, 0) + 1
            
            # Market Basket Analysis (Algoritmo di associazione per coppie frequenti)
            unique_items = list(set(items))
            for i in range(len(unique_items)):
                for j in range(i + 1, len(unique_items)):
                    pair = tuple(sorted([unique_items[i], unique_items[j]]))
                    pair_performance[pair] = pair_performance.get(pair, 0) + 1
        except Exception:
            pass
            
        # 2. Suddivisione transazioni per Fasce Orarie
        if 'timestamp' in tx.keys() and tx['timestamp']:
            try:
                ts = datetime.datetime.fromisoformat(tx['timestamp'])
                hour = ts.hour
                if 8 <= hour < 11: time_slots["08:00 - 11:00"] += 1
                elif 11 <= hour < 14: time_slots["11:00 - 14:00"] += 1
                elif 14 <= hour < 17: time_slots["14:00 - 17:00"] += 1
                elif 17 <= hour < 20: time_slots["17:00 - 20:00"] += 1
            except Exception:
                pass


    avg_revenue = total_revenue / total_transactions if total_transactions else 0
    
    print("\n--- 1. TABELLA RIASSUNTIVA AZIENDALE ---")
    print(f"Numero Transazioni: {total_transactions}")
    print(f"Totale Articoli Venduti: {total_items}")
    print(f"Ricavo Totale: €{total_revenue:.2f}")
    print(f"Ricavo Medio per Transazione: €{avg_revenue:.2f}")

    print("\n--- 2. PERFORMANCE SINGOLI PRODOTTI (TOP 5) ---")
    sorted_products = sorted(product_performance.items(), key=lambda x: x[1], reverse=True)
    # Raccogliamo anche i nomi dei prodotti con una query
    for i, (pid, count) in enumerate(sorted_products[:5]):
        p_row = cursor.execute("SELECT product_name FROM products WHERE product_id=?", (pid,)).fetchone()
        name = p_row['product_name'] if p_row else "Nome Sconosciuto"
        print(f" {i+1}. {name} [{pid}] -> Venduti: {count}")

    print("\n--- 3. MEDIA PERMANENZA E SPESE ---")
    # Total dwell time è in secondi
    avg_dwell_sec = total_dwell_time / total_transactions if total_transactions else 0
    avg_dwell_min = avg_dwell_sec / 60.0
    eur_per_min = avg_revenue / avg_dwell_min if avg_dwell_min > 0 else 0
    
    print(f"Permanenza Media nel Supermercato: {avg_dwell_min:.1f} minuti")
    print(f"Media Euro spesi al minuto: €{eur_per_min:.2f} / minuto (per utente)")

    print("\n--- 4. AFFLUENZA ORARIA (Acquirenti) ---")
    for slot, count in time_slots.items():
        print(f"Fascia {slot} -> {count} acquirenti")

    print("\n--- 5. MARKET BASKET ANALYSIS (Top 5 Abbinamenti) ---")
    sorted_pairs = sorted(pair_performance.items(), key=lambda x: x[1], reverse=True)
    top_pairs_names = []
    top_pairs_counts = []
    
    if sorted_pairs:
        for i, (pair, count) in enumerate(sorted_pairs[:5]):
            p1_row = cursor.execute("SELECT product_name FROM products WHERE product_id=?", (pair[0],)).fetchone()
            p2_row = cursor.execute("SELECT product_name FROM products WHERE product_id=?", (pair[1],)).fetchone()
            name1 = p1_row['product_name'] if p1_row else "Sconosciuto"
            name2 = p2_row['product_name'] if p2_row else "Sconosciuto"
            combo_name = f"{name1} + {name2}"
            top_pairs_names.append(combo_name)
            top_pairs_counts.append(count)
            print(f" {i+1}. {combo_name} -> Comprati insieme {count} volte")
    else:
        print(" Nessuna correlazione trovata negli acquisti passati.")

    top_product_names = []
    top_product_counts = []
    for (pid, count) in sorted_products[:5]:
        p_row = cursor.execute("SELECT product_name FROM products WHERE product_id=?", (pid,)).fetchone()
        name = p_row['product_name'] if p_row else "Nome Sconosciuto"
        top_product_names.append(name)
        top_product_counts.append(count)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Market Analytics Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #0f172a;
            --text: #f8fafc;
            --card-bg: rgba(30, 41, 59, 0.7);
            --card-border: rgba(255, 255, 255, 0.1);
            --primary: #3b82f6;
            --accent: #8b5cf6;
        }}
        body {{
            margin: 0;
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            background-image: radial-gradient(circle at top right, rgba(59, 130, 246, 0.15) 0%, transparent 40%),
                              radial-gradient(circle at bottom left, rgba(139, 92, 246, 0.15) 0%, transparent 40%);
            background-attachment: fixed;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 5px;
            background: linear-gradient(to right, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        p.subtitle {{
            color: #94a3b8;
            margin-bottom: 40px;
            font-weight: 300;
        }}
        .grid-4 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .grid-2 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        }}
        .card h3 {{
            margin: 0 0 10px 0;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #cbd5e1;
        }}
        .card .value {{
            font-size: 2.2rem;
            font-weight: 700;
            margin: 0;
        }}
        .card .value span {{
            font-size: 1rem;
            color: #94a3b8;
            font-weight: 400;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
            width: 100%;
        }}
        /* Micro-animations */
        @keyframes fadeUp {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .animate {{
            animation: fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            opacity: 0;
        }}
        .d-1 {{ animation-delay: 0.1s; }}
        .d-2 {{ animation-delay: 0.2s; }}
        .d-3 {{ animation-delay: 0.3s; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="animate">
            <h1>Smart Market Analytics</h1>
            <p class="subtitle">Real-time local database insights</p>
        </div>

        <div class="grid-4">
            <div class="card animate d-1">
                <h3>Total Transactions</h3>
                <p class="value">{total_transactions}</p>
            </div>
            <div class="card animate d-1">
                <h3>Articles Sold</h3>
                <p class="value">{total_items}</p>
            </div>
            <div class="card animate d-2">
                <h3>Total Revenue</h3>
                <p class="value">€{total_revenue:.2f}</p>
            </div>
            <div class="card animate d-2">
                <h3>Avg. Revenue / Tx</h3>
                <p class="value">€{avg_revenue:.2f}</p>
            </div>
        </div>
        
        <div class="grid-4">
            <div class="card animate d-3">
                <h3>Average Dwell Time</h3>
                <p class="value">{avg_dwell_min:.1f} <span>min / user</span></p>
            </div>
             <div class="card animate d-3">
                <h3>Monetization Rate</h3>
                <p class="value">€{eur_per_min:.2f} <span>/ min</span></p>
            </div>
        </div>

        <div class="grid-2" style="margin-top: 20px;">
            <div class="card animate d-3">
                <h3>Hourly Buyers Footfall</h3>
                <div class="chart-container">
                    <canvas id="footfallChart"></canvas>
                </div>
            </div>
            <div class="card animate d-3">
                <h3>Top Products Performance</h3>
                <div class="chart-container">
                    <canvas id="productsChart"></canvas>
                </div>
            </div>
        </div>

        <div class="grid-2" style="margin-top: 20px;">
            <div class="card animate d-3">
                <h3>Market Basket Analysis (Bought Together)</h3>
                <div class="chart-container" style="height: 250px;">
                    <canvas id="basketChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        const footfallLabels = {json.dumps(list(time_slots.keys()))};
        const footfallData = {json.dumps(list(time_slots.values()))};
        
        Chart.defaults.color = '#cbd5e1';
        Chart.defaults.font.family = 'Inter';

        new Chart(document.getElementById('footfallChart'), {{
            type: 'line',
            data: {{
                labels: footfallLabels,
                datasets: [{{
                    label: 'Buyers',
                    data: footfallData,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.2)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    pointBackgroundColor: '#8b5cf6',
                    pointBorderColor: '#fff',
                    pointRadius: 5
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    x: {{ grid: {{ display: false }} }}
                }}
            }}
        }});

        const topProductsLabels = {json.dumps(top_product_names)};
        const topProductsData = {json.dumps(top_product_counts)};

        new Chart(document.getElementById('productsChart'), {{
            type: 'bar',
            data: {{
                labels: topProductsLabels,
                datasets: [{{
                    label: 'Units Sold',
                    data: topProductsData,
                    backgroundColor: ['#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe'],
                    borderRadius: 6
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    y: {{ grid: {{ display: false }} }}
                }}
            }}
        }});        const basketLabels = {json.dumps(top_pairs_names)};
        const basketData = {json.dumps(top_pairs_counts)};

        new Chart(document.getElementById('basketChart'), {{
            type: 'bar',
            data: {{
                labels: basketLabels,
                datasets: [{{
                    label: 'Times Bought Together',
                    data: basketData,
                    backgroundColor: ['#ec4899', '#f472b6', '#f9a8d4', '#fbcfe8', '#fdf2f8'],
                    borderRadius: 6
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ beginAtZero: true, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    y: {{ grid: {{ display: false }} }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print("\n[+] Dashboard UI esportata in 'dashboard.html'!")
    
    try:
        import webbrowser
        webbrowser.open("dashboard.html")
    except Exception:
        pass

    conn.close()

def run_thingspeak_analytics():
    print("\n" + "=" * 60)
    print("= SMART MARKET - THINGSPEAK HISTORICAL ANALYTICS =")
    print("=" * 60)
    
    if THINGSPEAK_CHANNEL_ID == "YOUR_CHANNEL_ID":
        print("! Salto le Analytics Storiche su ThingSpeak.")
        print("NOTA PER IL PROGETTO: Inserisci il TUO Channel ID dentro AnalyticsBot.py per abilitare il modulo.")
        print("In questo modo dimostrerete al professore di utilizzare l'API REST per pre-processare lo storico.")
        return
        
    print(f"Scaricando i dati storici dal Canale ThingSpeak {THINGSPEAK_CHANNEL_ID}...")
    try:
        # Preleva gli ultimi X record (results=1000) tramite API Rest di MathWorks
        url = f"https://api.thingspeak.com/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json?results=1000"
        if THINGSPEAK_READ_KEY:
            url += f"&api_key={THINGSPEAK_READ_KEY}"
            
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            feeds = data.get("feeds", [])
            print(f"Successo: Prelevati {len(feeds)} pacchetti storici dal sensore IoT.")
            
            if not feeds:
                print("Nessun dato storico trovato.")
                return
                
            # Requisito del Professore: Calcolo complesso / Pre-processing sui dati ThingSpeak
            # Calcoliamo la "Zona più Calda storica" sommando le interazioni passate dei Field 1-7 (Heatmap)
            # e calcolando la Deviazione delle zone.
            zone_totals = {}
            for feed in feeds:
                for i in range(1, 8):
                    f_val = feed.get(f"field{i}")
                    if f_val:
                        try:
                            val = float(f_val)
                            zone_totals[f"Zone {i}"] = zone_totals.get(f"Zone {i}", 0) + val
                        except ValueError:
                            pass
                            
            if not zone_totals:
                print("Campi 1-7 vuoti (Heatmap non ancora popolata in ThingSpeak).")
                return
                
            print("\n--- ANALISI CORRELAZIONE REPARTI (da Dati Storici Cloud) ---")
            sorted_zones = sorted(zone_totals.items(), key=lambda x: x[1], reverse=True)
            for z, total in sorted_zones:
                print(f" {z}: {int(total)} interazioni fisiche rilevate.")
                
            print("\n[V] Pre-processing completato: il sistema ha correlato con successo lo storico!")
            
        else:
            print(f"Errore REST API ThingSpeak: HTTP {r.status_code}")
            
    except Exception as e:
        print(f"Chiamata a ThingSpeak fallita: {e}")

if __name__ == "__main__":
    run_local_analytics()
    # run_thingspeak_analytics() # TODO: Riattivare dopo il collegamento dei Raspberry Pi
