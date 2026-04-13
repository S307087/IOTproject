import sqlite3
import os
import uuid
import random
import datetime
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILENAME = os.path.join(BASE_DIR, 'catalog.db')

def create_schema(conn):
    """Crea la struttura delle tabelle (DDL) nel database."""
    # executemany o executescript sono best practice per eseguire blocchi massivi
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            promotion INTEGER NOT NULL DEFAULT 0,
            shelf_id TEXT,
            shelf_stock INTEGER DEFAULT 0,
            warehouse_stock INTEGER DEFAULT 0,
            category TEXT
        );

        CREATE TABLE IF NOT EXISTS carts (
            cart_id TEXT PRIMARY KEY,
            user_id TEXT,
            shopping_list TEXT,         -- JSON list of product_ids
            wish_list TEXT,             -- JSON list of product_ids from User
            scanned_rfids TEXT,         -- JSON list of rfid_ids scanned into cart
            connection_time TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            cart_id TEXT,
            wish_list TEXT              -- JSON list of product_ids
        );

        CREATE TABLE IF NOT EXISTS shelves (
            shelf_id TEXT PRIMARY KEY,
            shelf_type TEXT,
            temperature_threshold REAL,
            product_ids TEXT,           -- JSON list of product_ids
            max_capacity INTEGER,       -- Max items this shelf can hold
            proportions TEXT            -- JSON mapping: product_id -> proportion e.g. {"ID1": 0.5, "ID2": 0.5}
        );

        CREATE TABLE IF NOT EXISTS robots (
            robot_id TEXT PRIMARY KEY,
            in_use INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS transactions (
            payment_id TEXT PRIMARY KEY,
            user_id TEXT,
            total_amount REAL,
            product_list TEXT,          -- JSON list of product_ids
            dwell_time_seconds INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS rfid_tags (
            rfid_id TEXT PRIMARY KEY,
            product_id TEXT
        );
        '''
    )

def seed_products(conn):
    """Inizializza il catalogo prodotti e i rispettivi tag RFID."""
    base_products = [
        # Fruits & Vegetables
        {
            "product_id": "FRU-0001",
            "product_name": "Bananas 1kg",
            "price": 1.99,
            "promotion": 0,
            "shelf_id": "S-FR-1",
            "shelf_stock": 40,
            "warehouse_stock": 120,
            "category": "Fruit and Vegetables",
        },
        {
            "product_id": "FRU-0002",
            "product_name": "Apples Gala 1kg",
            "price": 2.49,
            "promotion": 10,
            "shelf_id": "S-FR-1",
            "shelf_stock": 35,
            "warehouse_stock": 90,
            "category": "Fruit and Vegetables",
        },
        {
            "product_id": "FRU-0003",
            "product_name": "Cherry Tomatoes 500g",
            "price": 1.79,
            "promotion": 0,
            "shelf_id": "S-FR-2",
            "shelf_stock": 28,
            "warehouse_stock": 60,
            "category": "Fruit and Vegetables",
        },
        # Breakfast
        {
            "product_id": "BRK-1001",
            "product_name": "Wholegrain Cereal 500g",
            "price": 3.49,
            "promotion": 15,
            "shelf_id": "S-BR-1",
            "shelf_stock": 25,
            "warehouse_stock": 80,
            "category": "Breakfast",
        },
        {
            "product_id": "BRK-1002",
            "product_name": "Honey 500g",
            "price": 4.99,
            "promotion": 0,
            "shelf_id": "S-BR-1",
            "shelf_stock": 18,
            "warehouse_stock": 50,
            "category": "Breakfast",
        },
        {
            "product_id": "BRK-1003",
            "product_name": "Ground Coffee 250g",
            "price": 3.89,
            "promotion": 20,
            "shelf_id": "S-BR-2",
            "shelf_stock": 30,
            "warehouse_stock": 100,
            "category": "Breakfast",
        },
        # Hygiene
        {
            "product_id": "HYG-2001",
            "product_name": "Shower Gel 500ml",
            "price": 2.59,
            "promotion": 0,
            "shelf_id": "S-HY-1",
            "shelf_stock": 22,
            "warehouse_stock": 70,
            "category": "Hygiene",
        },
        {
            "product_id": "HYG-2002",
            "product_name": "Toothpaste Fresh Mint",
            "price": 1.99,
            "promotion": 5,
            "shelf_id": "S-HY-1",
            "shelf_stock": 40,
            "warehouse_stock": 150,
            "category": "Hygiene",
        },
        {
            "product_id": "HYG-2003",
            "product_name": "Laundry Detergent 2L",
            "price": 6.49,
            "promotion": 0,
            "shelf_id": "S-HY-2",
            "shelf_stock": 15,
            "warehouse_stock": 19,
            "category": "Hygiene",
        },
        # Beverages
        {
            "product_id": "BEV-3001",
            "product_name": "Still Water 1.5L",
            "price": 0.39,
            "promotion": 0,
            "shelf_id": "S-BE-1",
            "shelf_stock": 80,
            "warehouse_stock": 300,
            "category": "Beverages",
        },
        {
            "product_id": "BEV-3002",
            "product_name": "Cola Zero 1L",
            "price": 1.19,
            "promotion": 10,
            "shelf_id": "S-BE-1",
            "shelf_stock": 50,
            "warehouse_stock": 200,
            "category": "Beverages",
        },
        {
            "product_id": "BEV-3003",
            "product_name": "Orange Juice 1L",
            "price": 1.49,
            "promotion": 0,
            "shelf_id": "S-BE-2",
            "shelf_stock": 32,
            "warehouse_stock": 90,
            "category": "Beverages",
        },
        # Snacks
        {
            "product_id": "SNK-4001",
            "product_name": "Classic Potato Chips 200g",
            "price": 1.79,
            "promotion": 0,
            "shelf_id": "S-SN-1",
            "shelf_stock": 34,
            "warehouse_stock": 110,
            "category": "Snacks",
        },
        {
            "product_id": "SNK-4002",
            "product_name": "Salted Peanuts 300g",
            "price": 2.39,
            "promotion": 10,
            "shelf_id": "S-SN-1",
            "shelf_stock": 27,
            "warehouse_stock": 75,
            "category": "Snacks",
        },
        {
            "product_id": "SNK-4003",
            "product_name": "Protein Bar Chocolate",
            "price": 2.29,
            "promotion": 15,
            "shelf_id": "S-SN-2",
            "shelf_stock": 20,
            "warehouse_stock": 60,
            "category": "Snacks",
        },
        # Frozen
        {
            "product_id": "FRZ-5001",
            "product_name": "Frozen Margherita Pizza",
            "price": 3.79,
            "promotion": 0,
            "shelf_id": "S-FZ-1",
            "shelf_stock": 18,
            "warehouse_stock": 55,
            "category": "Frozen Food",
        },
        {
            "product_id": "FRZ-5002",
            "product_name": "Frozen Mixed Vegetables 1kg",
            "price": 2.89,
            "promotion": 0,
            "shelf_id": "S-FZ-1",
            "shelf_stock": 24,
            "warehouse_stock": 70,
            "category": "Frozen Food",
        },
        # Bakery
        {
            "product_id": "BAK-6001",
            "product_name": "Wholemeal Bread 500g",
            "price": 1.99,
            "promotion": 5,
            "shelf_id": "S-BK-1",
            "shelf_stock": 20,
            "warehouse_stock": 40,
            "category": "Bakery",
        },
        {
            "product_id": "BAK-6002",
            "product_name": "Butter Croissant 4 pcs",
            "price": 2.59,
            "promotion": 0,
            "shelf_id": "S-BK-1",
            "shelf_stock": 16,
            "warehouse_stock": 32,
            "category": "Bakery",
        },
    ]

    # Prepara le tuple per l'inserimento bulk (batching), pedagogicamente più ottimizzato
    products_data = []
    rfids_data = []

    for p in base_products:
        products_data.append((
            p["product_id"], p["product_name"], p["price"], p["promotion"],
            p["shelf_id"], p["shelf_stock"], p["warehouse_stock"], p["category"]
        ))
        for _ in range(p["shelf_stock"]):
            rfid = f"RFID-{uuid.uuid4().hex[:8].upper()}"
            rfids_data.append((rfid, p["product_id"]))

    conn.executemany(
        '''
        INSERT OR REPLACE INTO products (
            product_id, product_name, price, promotion,
            shelf_id, shelf_stock, warehouse_stock, category
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', products_data
    )
    conn.executemany(
        "INSERT OR REPLACE INTO rfid_tags (rfid_id, product_id) VALUES (?, ?)", 
        rfids_data
    )

def seed_other_entities(conn):
    """Inizializza entità aggiuntive tramite query parametrizzate, per scongiurare SQL Injection."""
    users_data = [
        ('USR-001', None, '["FRU-0002", "BRK-1003", "SNK-4003"]'),
        ('USR-002', None, '["HYG-2002", "BEV-3002"]')
    ]
    conn.executemany("INSERT OR REPLACE INTO users (user_id, cart_id, wish_list) VALUES (?, ?, ?)", users_data)

    carts_data = [(f"CRT-{str(i).zfill(3)}", None, "[]", "[]", "[]", None) for i in range(1, 16)]
    conn.executemany("INSERT OR REPLACE INTO carts (cart_id, user_id, shopping_list, wish_list, scanned_rfids, connection_time) VALUES (?, ?, ?, ?, ?, ?)", carts_data)

    shelves_data = [
        ('S-FR-1', 'Fresh Produce', 8.0, '["FRU-0001", "FRU-0002"]', 100, '{"FRU-0001": 0.5, "FRU-0002": 0.5}'),
        ('S-FR-2', 'Fresh Produce', 8.0, '["FRU-0003"]', 50, '{"FRU-0003": 1.0}'),
        ('S-BR-1', 'Dry Food', 22.0, '["BRK-1001", "BRK-1002"]', 60, '{"BRK-1001": 0.6, "BRK-1002": 0.4}'),
        ('S-BR-2', 'Dry Food', 22.0, '["BRK-1003"]', 40, '{"BRK-1003": 1.0}'),
        ('S-HY-1', 'Hygiene', 25.0, '["HYG-2001", "HYG-2002"]', 80, '{"HYG-2001": 0.5, "HYG-2002": 0.5}'),
        ('S-HY-2', 'Hygiene', 25.0, '["HYG-2003"]', 75, '{"HYG-2003": 1.0}'),
        ('S-BE-1', 'Beverages', 18.0, '["BEV-3001", "BEV-3002"]', 150, '{"BEV-3001": 0.6, "BEV-3002": 0.4}'),
        ('S-BE-2', 'Beverages', 18.0, '["BEV-3003"]', 50, '{"BEV-3003": 1.0}'),
        ('S-SN-1', 'Snacks', 22.0, '["SNK-4001", "SNK-4002"]', 80, '{"SNK-4001": 0.5, "SNK-4002": 0.5}'),
        ('S-SN-2', 'Snacks', 22.0, '["SNK-4003"]', 40, '{"SNK-4003": 1.0}'),
        ('S-FZ-1', 'Frozen', -18.0, '["FRZ-5001", "FRZ-5002"]', 60, '{"FRZ-5001": 0.5, "FRZ-5002": 0.5}'),
        ('S-BK-1', 'Bakery', 22.0, '["BAK-6001", "BAK-6002"]', 50, '{"BAK-6001": 0.5, "BAK-6002": 0.5}')
    ]
    conn.executemany("INSERT OR REPLACE INTO shelves (shelf_id, shelf_type, temperature_threshold, product_ids, max_capacity, proportions) VALUES (?, ?, ?, ?, ?, ?)", shelves_data)

    robots_data = [
        ('ROB-001', 0),
        ('ROB-002', 0),
        ('ROB-003', 0)
    ]
    conn.executemany("INSERT OR REPLACE INTO robots (robot_id, in_use) VALUES (?, ?)", robots_data)

def seed_realistic_transactions(conn):
    """Seed historical realistic transactions data if empty."""
    transactions_data = []
    base_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=30)
    
    products = [
        ("FRU-0001", 1.99), ("FRU-0002", 2.24), ("FRU-0003", 1.79),
        ("BRK-1001", 2.97), ("BRK-1002", 4.99), ("BRK-1003", 3.11),
        ("HYG-2001", 2.59), ("HYG-2002", 1.89), ("HYG-2003", 6.49),
        ("BEV-3001", 0.39), ("BEV-3002", 1.07), ("BEV-3003", 1.49),
        ("SNK-4001", 1.79), ("SNK-4002", 2.15), ("SNK-4003", 1.95),
        ("FRZ-5001", 3.79), ("FRZ-5002", 2.89),
        ("BAK-6001", 1.89), ("BAK-6002", 2.59)
    ]

    for _ in range(1000):
        t_date = base_date + datetime.timedelta(days=random.randint(0, 30), hours=random.randint(8, 19), minutes=random.randint(0, 59))
        num_items = random.randint(1, 8)
        purchased_items = random.choices(products, k=num_items)
        
        total_amount = sum(item[1] for item in purchased_items)
        product_ids = [item[0] for item in purchased_items]
        
        payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        user_id = f"USR-{random.randint(100, 999)}" if random.random() > 0.3 else "GUEST"
        dwell_time = random.randint(120, 1800) # 2 mins to 30 mins
        
        transactions_data.append((
            payment_id,
            user_id,
            round(total_amount, 2),
            json.dumps(product_ids),
            dwell_time,
            t_date.strftime("%Y-%m-%d %H:%M:%S")
        ))
        
    conn.executemany(
        '''
        INSERT INTO transactions (payment_id, user_id, total_amount, product_list, dwell_time_seconds, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', transactions_data
    )

def create_db():
    """Punto di ingresso che orchestra la creazione."""
    existing_transactions = []
    if os.path.exists(DB_FILENAME):
        try:
            with sqlite3.connect(DB_FILENAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT payment_id, user_id, total_amount, product_list, dwell_time_seconds, timestamp FROM transactions")
                existing_transactions = cursor.fetchall()
        except sqlite3.Error:
            pass
        try:
            with sqlite3.connect(DB_FILENAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")
                tables = cursor.fetchall()
                for table_name in tables:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name[0]}")
        except sqlite3.Error as e:
            print(f"Error dropping existing tables: {e}")

    # Il context manager "with" esegue automaticamente il commit e chiude la 
    # connessione anche in caso di eccezioni (best practice Python).
    with sqlite3.connect(DB_FILENAME) as conn:
        create_schema(conn)
        seed_products(conn)
        seed_other_entities(conn)

        if existing_transactions:
            conn.executemany('''
                INSERT INTO transactions (payment_id, user_id, total_amount, product_list, dwell_time_seconds, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', existing_transactions)
            print(f"Restored {len(existing_transactions)} existing transactions.")
        else:
            seed_realistic_transactions(conn)
            print("Generated realistic transactions.")

        count = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
        print(f"Catalog creation complete: {count} products stored in SQL (no JSON needed).")

if __name__ == '__main__':
    create_db()
