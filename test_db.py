import sqlite3

conn = sqlite3.connect('catalog.db')
stock = conn.execute("SELECT shelf_stock, warehouse_stock FROM products WHERE product_id='HYG-2003'").fetchone()
rfids = conn.execute("SELECT count(*) FROM rfid_tags WHERE product_id='HYG-2003'").fetchone()[0]
print(f"Stock: {stock}")
print(f"RFIDs: {rfids}")
conn.close()
