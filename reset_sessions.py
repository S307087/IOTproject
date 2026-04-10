import sqlite3
import json
import uuid

DB_FILENAME = 'catalog.db'

def reset_sessions():
    try:
        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()
        
        # 1. Rimuovi tutti gli utenti creati durante le simulazioni
        cursor.execute('DELETE FROM users')
        deleted_users = cursor.rowcount
        
        # 2a. Ripristina lo stock per i prodotti che erano nei carrelli prima di svuotarli
        cursor.execute("SELECT shopping_list FROM carts WHERE shopping_list != '[]' AND shopping_list IS NOT NULL")
        carts = cursor.fetchall()
        restored_items = 0
        for cart in carts:
            try:
                items = json.loads(cart[0])
                for item_id in items:
                    cursor.execute("UPDATE products SET shelf_stock = shelf_stock + 1 WHERE product_id = ?", (item_id,))
                    restored_items += 1
            except json.JSONDecodeError:
                pass
                
        # 2b. Resetta tutti i carrelli allo stato "Scollegato e Vuoto"
        cursor.execute('''
            UPDATE carts 
            SET user_id = NULL, 
                shopping_list = '[]', 
                wish_list = '[]', 
                scanned_rfids = '[]',
                connection_time = NULL
        ''')
        reset_carts = cursor.rowcount

        # 3. Allinea il numero di rfid_tags allo stock effettivo (shelf_stock)
        cursor.execute('SELECT product_id, shelf_stock FROM products')
        products = cursor.fetchall()
        tags_added = 0
        tags_removed = 0
        for p_id, stock in products:
            cursor.execute('SELECT rfid_id FROM rfid_tags WHERE product_id = ?', (p_id,))
            current_tags = cursor.fetchall()
            current_count = len(current_tags)
            
            if current_count > stock:
                excess = current_count - stock
                to_delete = [t[0] for t in current_tags[:excess]]
                for tag_id in to_delete:
                    cursor.execute('DELETE FROM rfid_tags WHERE rfid_id = ?', (tag_id,))
                tags_removed += excess
            elif current_count < stock:
                missing = stock - current_count
                for _ in range(missing):
                    new_rfid = f"RFID-{uuid.uuid4().hex[:8].upper()}"
                    cursor.execute('INSERT INTO rfid_tags (rfid_id, product_id) VALUES (?, ?)', (new_rfid, p_id))
                tags_added += missing
        
        conn.commit()
        
        print("Database ripulito con successo per le nuove simulazioni!")
        print(f"Utenti eliminati: {deleted_users}")
        print(f"Prodotti non pagati rimessi in stock: {restored_items}")
        print(f"Carrelli svuotati e scollegati: {reset_carts}")
        print(f"RFID tags allineati (aggiunti: {tags_added}, rimossi: {tags_removed})")
        
    except sqlite3.Error as e:
        print(f"Errore durante la pulizia del database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    reset_sessions()
