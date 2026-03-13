import json
import sqlite3
import os

DB_FILENAME = 'catalog.db'
JSON_FILENAME = 'catalog.json'

def create_db():
    # Remove existing db to start fresh if we run this multiple times
    if os.path.exists(DB_FILENAME):
        os.remove(DB_FILENAME)

    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()

    # Create table matching our schema
    cursor.execute('''
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
    ''')

    # Load JSON data
    with open(JSON_FILENAME, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Note: Depending on previous steps, the key might be 'products' or 'prodotti'
    items = data.get('products', data.get('prodotti', []))

    # Insert data
    inserted = 0
    import random
    for p in items:
        # Robust key checking for different schema versions
        pid = p.get('product_id') or p.get('productID') or p.get('id prodotto')
        name = p.get('product_name') or p.get('productName') or p.get('Nome prodotto')
        price = p.get('price') or p.get('prezzo', 0.0)
        category = p.get('category') or p.get('categoria', 'Other')
        
        # Promotion logic
        promo_bool = p.get('promotion') or p.get('promozione', False)
        # If it's already a number > 1 (percentage), keep it, otherwise assign random for existing promos
        if isinstance(promo_bool, (int, float)) and promo_bool > 1:
            promo_pct = promo_bool
        else:
            promo_pct = random.choice([10, 20, 30, 50]) if promo_bool else 0
        
        cursor.execute('''
            INSERT OR REPLACE INTO products (
                product_id, product_name, price, promotion, 
                shelf_id, shelf_stock, warehouse_stock, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pid,
            name,
            price,
            promo_pct,
            p.get('shelf_id') or f"S-{random.randint(1,10)}",
            p.get('shelf_stock', random.randint(5, 50)),
            p.get('warehouse_stock', random.randint(20, 100)),
            category
        ))
        inserted += 1

    conn.commit()

    # Verification
    cursor.execute('SELECT COUNT(*) FROM products')
    count = cursor.fetchone()[0]

    print(f"Migration complete: {inserted} items read from JSON, {count} items found in database.")

    conn.close()

if __name__ == '__main__':
    create_db()
