import os
import time
import json
import sqlite3
import threading
import uuid
from smartmarket_MQTT import MyMQTT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "catalog.db")
BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
PORT = 1883

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

class RobotNotifier:
    def __init__(self, system):
        self.system = system
        
    def notify(self, topic, payload):
        self.system.handle_message(topic, payload)

class RobotBot:
    def __init__(self):
        self.notifier = RobotNotifier(self)
        self.mqtt_client = MyMQTT("RobotBot", BROKER, PORT, self.notifier)
        
        # Track active restocks by shelf_id to prevent duplicate assignments
        self.active_restocks = set()
        self.lock = threading.Lock()

    def start(self):
        print("[RobotBot] Starting and listening for alerts...")
        self.mqtt_client.mySubscribe("staff/alerts")
        self.mqtt_client.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.mqtt_client.stop()

    def handle_message(self, topic, payload):
        if topic == "staff/alerts":
            event = payload.get("event")
            # We are interested in low stock alerts
            if event == "low_stock_shelf":
                product_id = payload.get("product_id")
                shelf_id = payload.get("shelf_id")
                
                if not product_id or not shelf_id:
                    return

                with self.lock:
                    # Removed the active_restocks check to ensure the robot
                    # starts EVERY time the stock is modified.
                    
                    # Try to find an available robot
                    conn = get_db_connection()
                    robot = conn.execute("SELECT robot_id FROM robots WHERE in_use = 0 LIMIT 1").fetchone()
                    if not robot:
                        print(f"[RobotBot] No robots available to restock {product_id} on {shelf_id}!")
                        conn.close()
                        return
                    
                    robot_id = robot["robot_id"]
                    
                    # Mark robot as in_use
                    conn.execute("UPDATE robots SET in_use = 1 WHERE robot_id = ?", (robot_id,))
                    conn.commit()
                    conn.close()
                    
                    self.active_restocks.add(shelf_id)
                    print(f"[RobotBot] Assigned {robot_id} to restock {product_id} on {shelf_id}.")
                    
                    # Start restock process in a separate thread to not block MQTT callback
                    threading.Thread(target=self.execute_restock, args=(robot_id, product_id, shelf_id)).start()

    def execute_restock(self, robot_id, product_id, shelf_id):
        # Simulate time taken for robot to move to warehouse, grab items, and return to shelf
        print(f"[RobotBot] {robot_id} is moving to warehouse and restocking...")
        time.sleep(5)
        
        conn = get_db_connection()
        try:
            prod = conn.execute(
                "SELECT p.product_name, p.shelf_stock, p.warehouse_stock "
                "FROM products p "
                "WHERE p.product_id = ?", (product_id,)
            ).fetchone()
            
            if not prod:
                print(f"[RobotBot] Product {product_id} not found in DB.")
                return

            product_name = prod["product_name"]
            shelf_stock = prod["shelf_stock"]
            warehouse_stock = prod["warehouse_stock"]
            
            count = conn.execute("SELECT COUNT(*) FROM products WHERE shelf_id = ?", (shelf_id,)).fetchone()[0]
            max_capacity = conn.execute("SELECT max_capacity FROM shelves WHERE shelf_id = ?", (shelf_id,)).fetchone()[0]
            
            max_allowed = max_capacity // max(1, count)
            
            items_needed = max_allowed - shelf_stock
            if items_needed <= 0:
                print(f"[RobotBot] Shelf {shelf_id} is already full. No restock needed.")
                return
                
            items_to_take = min(items_needed, warehouse_stock)
            if items_to_take <= 0:
                print(f"[RobotBot] No {product_id} available in warehouse to restock!")
                return
                
            new_shelf_stock = shelf_stock + items_to_take
            new_warehouse_stock = warehouse_stock - items_to_take
            
            # Generate RFIDs for new items
            new_rfids = [f"RFID-{uuid.uuid4().hex[:8].upper()}" for _ in range(items_to_take)]
            for rfid in new_rfids:
                conn.execute("INSERT OR REPLACE INTO rfid_tags (rfid_id, product_id, status) VALUES (?, ?, 'SH')", (rfid, product_id))
            
            # Update stock in DB
            conn.execute(
                "UPDATE products SET shelf_stock = ?, warehouse_stock = ? WHERE product_id = ?", 
                (new_shelf_stock, new_warehouse_stock, product_id)
            )
            conn.commit()
            
            print(f"[RobotBot] {robot_id} successfully added {items_to_take} of {product_id} to {shelf_id}.")
            
            # Publish stock_updated event so StaffBot clears the warning alert
            self.mqtt_client.myPublish("staff/alerts", {
                "event": "stock_updated",
                "product_id": product_id,
                "shelf_stock": new_shelf_stock,
                "warehouse_stock": new_warehouse_stock
            })
            
            # Publish standard notification to staff
            if items_to_take < items_needed:
                shortage_msg = f"⚠️ Warehouse Alert: Not enough items in warehouse! Restocked {items_to_take} but needed {items_needed}."
            else:
                shortage_msg = "✅ Warehouse sufficiently stocked."
                
            self.mqtt_client.myPublish("staff/alerts", {
                "level": "INFO",
                "message": f"🤖 Robot {robot_id} completed restocking: added {items_to_take}x {product_name} to shelf {shelf_id}. (New shelf stock: {new_shelf_stock}/{max_allowed})\n{shortage_msg}",
                "timestamp": time.time()
            })
            
        except Exception as e:
            print(f"[RobotBot] Error during restocking: {e}")
        finally:
            # Mark robot as available and remove from active restocks
            conn.execute("UPDATE robots SET in_use = 0 WHERE robot_id = ?", (robot_id,))
            conn.commit()
            conn.close()
            
            with self.lock:
                if shelf_id in self.active_restocks:
                    self.active_restocks.remove(shelf_id)

if __name__ == "__main__":
    bot = RobotBot()
    bot.start()
