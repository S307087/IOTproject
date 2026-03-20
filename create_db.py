import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILENAME = os.path.join(BASE_DIR, 'catalog.db')

def create_db():
    # Remove existing db to start fresh if we run this multiple times
    if os.path.exists(DB_FILENAME):
        os.remove(DB_FILENAME)

    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()

    # --- Core catalog tables (all in English) ---

    # Products
    cursor.execute(
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
        )
        '''
    )

    # Carts
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS carts (
            cart_id TEXT PRIMARY KEY,
            user_id TEXT,
            shopping_list TEXT,         -- JSON list of product_ids
            wish_list TEXT,             -- JSON list of product_ids from User
            connection_time TEXT
        )
        '''
    )

    # Users
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            cart_id TEXT,
            wish_list TEXT              -- JSON list of product_ids
        )
        '''
    )

    # Shelves
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS shelves (
            shelf_id TEXT PRIMARY KEY,
            shelf_type TEXT,
            temperature_threshold REAL,
            product_ids TEXT            -- JSON list of product_ids
        )
        '''
    )

    # Robots
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS robots (
            robot_id TEXT PRIMARY KEY,
            in_use INTEGER NOT NULL DEFAULT 0
        )
        '''
    )

    # Transactions
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS transactions (
            payment_id TEXT PRIMARY KEY,
            user_id TEXT,
            total_amount REAL,
            product_list TEXT,          -- JSON list of product_ids
            dwell_time_seconds INTEGER
        )
        '''
    )

    # RFID tags
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS rfid_tags (
            rfid_id TEXT PRIMARY KEY,
            product_id TEXT
        )
        '''
    )

    # --- Seed products in English with multiple categories ---

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
            "warehouse_stock": 60,
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

    inserted = 0
    for p in base_products:
        cursor.execute(
            '''
            INSERT OR REPLACE INTO products (
                product_id, product_name, price, promotion,
                shelf_id, shelf_stock, warehouse_stock, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                p["product_id"],
                p["product_name"],
                p["price"],
                p["promotion"],
                p["shelf_id"],
                p["shelf_stock"],
                p["warehouse_stock"],
                p["category"],
            ),
        )
        inserted += 1

    # --- Seed other catalog entities (example data) ---

    cursor.execute(
        '''
        INSERT OR REPLACE INTO users (user_id, cart_id, wish_list)
        VALUES
            ('USR-001', NULL, '["FRU-0002", "BRK-1003", "SNK-4003"]'),
            ('USR-002', NULL, '["HYG-2002", "BEV-3002"]')
        '''
    )

    carts_values = ",\n            ".join([f"('CRT-{str(i).zfill(3)}', NULL, '[]', '[]', NULL)" for i in range(1, 16)])
    cursor.execute(
        f'''
        INSERT OR REPLACE INTO carts (cart_id, user_id, shopping_list, wish_list, connection_time)
        VALUES
            {carts_values}
        '''
    )

    cursor.execute(
        '''
        INSERT OR REPLACE INTO shelves (shelf_id, shelf_type, temperature_threshold, product_ids)
        VALUES
            ('S-FR-1', 'Fresh Produce', 8.0, '["FRU-0001", "FRU-0002"]'),
            ('S-FR-2', 'Fresh Produce', 8.0, '["FRU-0003"]'),
            ('S-BR-1', 'Dry Food', 22.0, '["BRK-1001", "BRK-1002"]'),
            ('S-BR-2', 'Dry Food', 22.0, '["BRK-1003"]'),
            ('S-HY-1', 'Hygiene', 25.0, '["HYG-2001", "HYG-2002"]'),
            ('S-HY-2', 'Hygiene', 25.0, '["HYG-2003"]'),
            ('S-BE-1', 'Beverages', 18.0, '["BEV-3001", "BEV-3002"]'),
            ('S-BE-2', 'Beverages', 18.0, '["BEV-3003"]'),
            ('S-SN-1', 'Snacks', 22.0, '["SNK-4001", "SNK-4002"]'),
            ('S-SN-2', 'Snacks', 22.0, '["SNK-4003"]'),
            ('S-FZ-1', 'Frozen', -18.0, '["FRZ-5001", "FRZ-5002"]'),
            ('S-BK-1', 'Bakery', 22.0, '["BAK-6001", "BAK-6002"]')
        '''
    )

    cursor.execute(
        '''
        INSERT OR REPLACE INTO robots (robot_id, in_use)
        VALUES
            ('ROB-001', 0),
            ('ROB-002', 1)
        '''
    )

    cursor.execute('DELETE FROM transactions')

    cursor.execute(
        '''
        INSERT OR REPLACE INTO rfid_tags (rfid_id, product_id)
        VALUES
            ('RFID-0001', 'FRU-0001'),
            ('RFID-0002', 'BRK-1001'),
            ('RFID-0003', 'HYG-2002'),
            ('RFID-0004', 'BEV-3002')
        '''
    )

    conn.commit()

    cursor.execute('SELECT COUNT(*) FROM products')
    count = cursor.fetchone()[0]

    print(f"Catalog creation complete: {count} products stored in SQL (no JSON needed).")

    conn.close()

if __name__ == '__main__':
    create_db()
