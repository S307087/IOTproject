import sqlite3
conn = sqlite3.connect('catalog.db')
cursor = conn.cursor()
cursor.execute('''
SELECT p.product_id, p.shelf_stock, COUNT(r.rfid_id) as rfid_count 
FROM products p 
LEFT JOIN rfid_tags r ON p.product_id = r.product_id 
GROUP BY p.product_id
HAVING p.shelf_stock != rfid_count
''')
mismatches = cursor.fetchall()
for m in mismatches:
    print(m)
