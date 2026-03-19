import sqlite3

DB_FILENAME = 'catalog.db'

def reset_sessions():
    try:
        conn = sqlite3.connect(DB_FILENAME)
        cursor = conn.cursor()
        
        # 1. Rimuovi tutti gli utenti creati durante le simulazioni
        cursor.execute('DELETE FROM users')
        deleted_users = cursor.rowcount
        
        # 2. Resetta tutti i carrelli allo stato "Scollegato e Vuoto"
        cursor.execute('''
            UPDATE carts 
            SET user_id = NULL, 
                shopping_list = '[]', 
                wish_list = '[]', 
                connection_time = NULL
        ''')
        reset_carts = cursor.rowcount
        
        conn.commit()
        
        print("Database ripulito con successo per le nuove simulazioni!")
        print(f"Utenti eliminati: {deleted_users}")
        print(f"Carrelli svuotati e scollegati: {reset_carts}")
        
    except sqlite3.Error as e:
        print(f"Errore durante la pulizia del database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    reset_sessions()
