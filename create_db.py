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
            category TEXT,
            min_threshold INTEGER DEFAULT 1
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
            product_id TEXT,
            status TEXT DEFAULT 'SH'
        );

        CREATE TABLE IF NOT EXISTS temperatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shelf_id TEXT,
            temperature REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        '''
    )

def generate_100_products():
    categories = {
        "Fruit and Vegetables": [("Bananas 1kg", 1.99), ("Apples Gala 1kg", 2.49), ("Cherry Tomatoes 500g", 1.79), ("Carrots 1kg", 1.20), ("Potatoes 2kg", 2.50), ("Strawberries 250g", 3.50), ("Oranges 1.5kg", 2.80), ("Lettuce Iceberg", 1.10), ("Broccoli 500g", 1.60), ("Onions 1kg", 1.30), ("Garlic 200g", 0.99), ("Lemon 500g", 1.50)],
        "Breakfast": [("Wholegrain Cereal 500g", 3.49), ("Honey 500g", 4.99), ("Ground Coffee 250g", 3.89), ("Oats 1kg", 2.20), ("Tea 50 bags", 2.50), ("Fruit Jam 300g", 2.70), ("Croissant 6-pack", 3.00), ("Pancake Mix 400g", 2.80), ("Cocoa Powder 250g", 3.10), ("Muesli 500g", 3.60)],
        "Hygiene": [("Shower Gel 500ml", 2.59), ("Toothpaste Fresh Mint", 1.99), ("Laundry Detergent 2L", 6.49), ("Shampoo 400ml", 3.20), ("Conditioner 400ml", 3.20), ("Deodorant 150ml", 2.80), ("Liquid Soap 300ml", 1.80), ("Toilet Paper 8 rolls", 4.50), ("Sponges 3-pack", 1.20), ("Dishwasher Tablets 30", 5.99)],
        "Beverages": [("Still Water 1.5L", 0.39), ("Cola Zero 1L", 1.19), ("Orange Juice 1L", 1.49), ("Sparkling Water 1.5L", 0.45), ("Apple Juice 1L", 1.60), ("Lemonade 1.5L", 1.30), ("Energy Drink 250ml", 1.20), ("Beer 500ml", 1.10), ("Red Wine 750ml", 5.50), ("White Wine 750ml", 4.80)],
        "Snacks": [("Classic Potato Chips 200g", 1.79), ("Salted Peanuts 300g", 2.39), ("Protein Bar Chocolate", 2.29), ("Tortilla Chips 200g", 1.99), ("Popcorn 100g", 1.10), ("Dark Chocolate 100g", 1.50), ("Milk Chocolate 100g", 1.40), ("Mixed Nuts 200g", 3.50), ("Crackers 250g", 1.20), ("Cookies 300g", 2.10)],
        "Frozen Food": [("Frozen Margherita Pizza", 3.79), ("Frozen Mixed Vegetables 1kg", 2.89), ("Ice Cream Vanilla 500g", 3.50), ("Fish Sticks 300g", 4.20), ("Frozen French Fries 1kg", 2.50), ("Frozen Peas 500g", 1.80), ("Frozen Blueberries 300g", 3.90), ("Pizza Pepperoni", 4.10), ("Frozen Spinach 450g", 1.60)],
        "Bakery": [("Wholemeal Bread 500g", 1.99), ("Butter Croissant 4 pcs", 2.59), ("Baguette 250g", 1.10), ("Toast Bread 400g", 1.50), ("Donut Chocolate", 1.20), ("Muffins 4-pack", 2.80), ("Sourdough Loaf 400g", 2.90), ("Burger Buns 4 pcs", 1.60)],
        "Meat & Poultry": [("Chicken Breast 500g", 5.99), ("Beef Steak 300g", 7.50), ("Ground Beef 400g", 4.50), ("Pork Chops 400g", 4.80), ("Bacon 200g", 2.90), ("Sausages 400g", 3.50), ("Chicken Wings 500g", 4.20), ("Turkey Deli 150g", 2.20)],
        "Dairy": [("Milk 1L", 1.10), ("Butter 250g", 2.50), ("Cheddar Cheese 200g", 3.20), ("Eggs 10 pcs", 2.80), ("Yoghurt Natural 500g", 1.50), ("Greek Yoghurt 400g", 2.20), ("Parmesan 150g", 4.50), ("Mozzarella 125g", 1.20), ("Cream Cheese 200g", 1.90)],
        "Pantry": [("Pasta Spaghetti 500g", 0.99), ("Rice 1kg", 2.10), ("Tomato Sauce 400g", 1.20), ("Olive Oil 500ml", 5.50), ("Sunflower Oil 1L", 2.80), ("Flour 1kg", 1.10), ("Sugar 1kg", 1.20), ("Salt 1kg", 0.80), ("Pepper 50g", 1.50), ("Canned Tuna 3x80g", 3.50), ("Canned Beans 400g", 0.90), ("Canned Corn 300g", 1.10)]
    }

    products = []
    pid_counter = 1
    
    for category, items in categories.items():
        prefix = "".join([c.upper() for c in category if c.isalpha()])[:3]
        for name, price in items:
            promotion = random.choices([0, 5, 10, 20, 30], weights=[70, 10, 10, 5, 5])[0]
            shelf_stock = random.randint(20, 50)
            warehouse_stock = random.randint(50, 150)
            products.append({
                "product_id": f"{prefix}-{pid_counter:04d}",
                "product_name": name,
                "price": price,
                "promotion": promotion,
                "shelf_stock": shelf_stock,
                "warehouse_stock": warehouse_stock,
                "category": category,
            })
            pid_counter += 1
            
    return products

ALL_PRODUCTS = generate_100_products()
SHELVES_CONFIG = []

def seed_products(conn):
    """Inizializza il catalogo prodotti, genera le etichette RFID e la mappa scaffali."""
    products_data = []
    rfids_data = []
    
    # Raggruppa i prodotti per categoria per generare gli scaffali in automatico
    from collections import defaultdict
    category_products = defaultdict(list)
    
    for p in ALL_PRODUCTS:
        category_products[p["category"]].append(p)
        
    for category, prods in category_products.items():
        cat_prefix = "".join([c.upper() for c in category if c.isalpha()])[:2]
        # Per backwards compatibility con Docker (SmartShelf S-FR-1)
        if category == "Fruit and Vegetables":
            cat_prefix = "FR"
            
        # Generate N shelves for each category (max 4 different products per shelf)
        chunk_size = 4
        for i in range(0, len(prods), chunk_size):
            chunk = prods[i:i+chunk_size]
            shelf_id = f"S-{cat_prefix}-{i//chunk_size + 1}"
            
            shelf_product_ids = [p["product_id"] for p in chunk]
            max_capacity = sum(p["shelf_stock"] for p in chunk) + random.randint(10, 50)
            
            # 20% of equally distributed capacity
            max_allocation = max_capacity // max(1, len(chunk))
            min_threshold = int(max_allocation * 0.20)
            if min_threshold == 0 and max_allocation > 0:
                min_threshold = 1
            
            SHELVES_CONFIG.append({
                "shelf_id": shelf_id,
                "shelf_type": category,
                "temperature": -18.0 if category == "Frozen Food" else (4.0 if category in ["Meat & Poultry", "Dairy"] else 20.0),
                "product_ids": json.dumps(shelf_product_ids),
                "max_capacity": max_capacity,
                "proportions": "{}"
            })
            
            # Update product dict with generated shelf_id and min_threshold
            for p in chunk:
                p["shelf_id"] = shelf_id
                p["min_threshold"] = min_threshold

    for p in ALL_PRODUCTS:
        products_data.append((
            p["product_id"], p["product_name"], p["price"], p["promotion"],
            p["shelf_id"], p["shelf_stock"], p["warehouse_stock"], p["category"], p["min_threshold"]
        ))
        
        for _ in range(p["shelf_stock"]):
            rfid = f"RFID-{uuid.uuid4().hex[:8].upper()}"
            rfids_data.append((rfid, p["product_id"]))

    conn.executemany(
        '''
        INSERT OR REPLACE INTO products (
            product_id, product_name, price, promotion,
            shelf_id, shelf_stock, warehouse_stock, category, min_threshold
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', products_data
    )
    conn.executemany(
        "INSERT OR REPLACE INTO rfid_tags (rfid_id, product_id) VALUES (?, ?)", 
        rfids_data
    )

def seed_other_entities(conn):
    """Inizializza entità aggiuntive tramite query parametrizzate."""
    users_data = [
        ('USR-001', None, json.dumps([ALL_PRODUCTS[0]["product_id"], ALL_PRODUCTS[10]["product_id"]])),
        ('USR-002', None, json.dumps([ALL_PRODUCTS[5]["product_id"], ALL_PRODUCTS[20]["product_id"]]))
    ]
    conn.executemany("INSERT OR REPLACE INTO users (user_id, cart_id, wish_list) VALUES (?, ?, ?)", users_data)

    carts_data = [(f"CRT-{str(i).zfill(3)}", None, "[]", "[]", "[]", None) for i in range(1, 16)]
    conn.executemany("INSERT OR REPLACE INTO carts (cart_id, user_id, shopping_list, wish_list, scanned_rfids, connection_time) VALUES (?, ?, ?, ?, ?, ?)", carts_data)
    
    shelves_data = [
        (s["shelf_id"], s["shelf_type"], s["temperature"], s["product_ids"], s["max_capacity"], s["proportions"])
        for s in SHELVES_CONFIG
    ]
    conn.executemany("INSERT OR REPLACE INTO shelves (shelf_id, shelf_type, temperature_threshold, product_ids, max_capacity, proportions) VALUES (?, ?, ?, ?, ?, ?)", shelves_data)

    robots_data = [('ROB-001', 0), ('ROB-002', 0), ('ROB-003', 0)]
    conn.executemany("INSERT OR REPLACE INTO robots (robot_id, in_use) VALUES (?, ?)", robots_data)

def seed_realistic_transactions(conn):
    """Seed historical realistic transactions data using SQLite's newly seeded products."""
    transactions_data = []
    base_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=30)
    
    # We map ALL_PRODUCTS into a tuple structure for random choices
    tx_products = [(p["product_id"], p["price"] * (1 - p["promotion"]/100)) for p in ALL_PRODUCTS]

    for _ in range(1000):
        t_date = base_date + datetime.timedelta(days=random.randint(0, 30), hours=random.randint(8, 19), minutes=random.randint(0, 59))
        num_items = random.randint(1, 15)
        purchased_items = random.choices(tx_products, k=num_items)
        
        total_amount = sum(item[1] for item in purchased_items)
        product_ids = [item[0] for item in purchased_items]
        
        payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        user_id = f"USR-{random.randint(100, 999)}" if random.random() > 0.3 else "GUEST"
        dwell_time = random.randint(120, 2400) # 2 mins to 40 mins
        
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
