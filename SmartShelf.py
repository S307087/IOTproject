import json
import time
import requests
import sys
import os
from smartmarket_MQTT import MyMQTT

CATALOG_API_HOST = os.environ.get("CATALOG_API_HOST", "localhost")
REST_API_URL = f"http://{CATALOG_API_HOST}:8080"
BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
PORT = 1883

class SmartShelf:
    def __init__(self, shelf_id):
        self.shelf_id = shelf_id
        self.mqtt_client = MyMQTT(f"SmartShelf-{shelf_id}", BROKER, PORT)
        self.mqtt_client.start()
        
        self.product_configurations = {}
        self.max_capacity = 0
        self.proportions = {}
        self.authorized_products = []
        
        self.current_tags = [] # T-1
        self.product_counts = {}
        self.register()

    def register(self):
        print(f"[{self.shelf_id}] Registering with Market Catalog REST API...")
        try:
            r = requests.post(f"{REST_API_URL}/register_shelf", json={"shelf_id": self.shelf_id})
            if r.status_code == 200:
                data = r.json()
                self.max_capacity = data.get("max_capacity", 0)
                self.proportions = data.get("proportions", {})
                self.authorized_products = data.get("product_ids", [])
                
                print(f"[{self.shelf_id}] Successfully registered! Max Capacity: {self.max_capacity}")
                print(f"[{self.shelf_id}] Authorized Products: {self.authorized_products}")
                print(f"[{self.shelf_id}] Proportions: {self.proportions}")
            else:
                print(f"[{self.shelf_id}] Failed to register shelf: Http {r.status_code}")
                sys.exit(1)
        except Exception as e:
            print(f"[{self.shelf_id}] Could not connect to Catalog REST API: {e}")
            sys.exit(1)

    def interactive_loop(self):
        print("\n--- Smart Shelf Interactive Console ---")
        print("Commands:")
        print("  add <rfid>")
        print("  remove <rfid>")
        print("  status")
        print("  exit")
        
        while True:
            cmd = input(f"[{self.shelf_id}] > ").strip().split()
            if not cmd:
                continue
                
            command = cmd[0].lower()
            
            if command == "exit":
                break
            elif command == "status":
                print(f"Current Tags: {self.current_tags}")
                print(f"Product Counts: {self.product_counts}")
            elif command in ["add", "remove"] and len(cmd) > 1:
                rfid = cmd[1].upper()
                self.simulate_poll(command, rfid)
            else:
                print("Unknown command or missing RFID.")

    def simulate_poll(self, action, rfid):
        # We simulate the local poller reading a new list of tags at time T
        simulated_time_t_tags = self.current_tags.copy()
        
        if action == "add":
            if rfid not in simulated_time_t_tags:
                simulated_time_t_tags.append(rfid)
            else:
                print(f"RFID {rfid} is already on the shelf.")
                return
        elif action == "remove":
            if rfid in simulated_time_t_tags:
                simulated_time_t_tags.remove(rfid)
            else:
                print(f"RFID {rfid} is not on the shelf.")
                return
                
        # Compare T with T-1
        self.report_by_exception(simulated_time_t_tags)

    def report_by_exception(self, new_tags):
        added = set(new_tags) - set(self.current_tags)
        removed = set(self.current_tags) - set(new_tags)
        
        self.current_tags = new_tags
        
        if added or removed:
            print(f"[{self.shelf_id}] State changed! Added: {added}, Removed: {removed}")
            
            # For each change, identify the product via REST (simulating the shelf checking tag associations)
            # and publish the MQTT event
            for rfid in added:
                self.process_rfid_change(rfid, "added")
                
            for rfid in removed:
                self.process_rfid_change(rfid, "removed")
                
    def process_rfid_change(self, rfid, action):
        try:
            r = requests.get(f"{REST_API_URL}/get_product_by_rfid?rfid={rfid}")
            if r.status_code == 200:
                prod = r.json()
                product_id = prod["product_id"]
                
                # Update local counts
                if product_id not in self.product_counts:
                    self.product_counts[product_id] = 0
                    
                if action == "added":
                    self.product_counts[product_id] += 1
                elif action == "removed":
                    self.product_counts[product_id] = max(0, self.product_counts[product_id] - 1)
                    
                # Publish event to Broker to notify Alert System
                event_payload = {
                    "event": "rfid_update",
                    "shelf_id": self.shelf_id,
                    "rfid": rfid,
                    "action": action,
                    "product_id": product_id
                }
                self.mqtt_client.myPublish(f"shelf/{self.shelf_id}/events", event_payload)
                
                # Check low stock thresholds locally
                self.check_local_threshold(product_id)
                
            else:
                print(f"[{self.shelf_id}] Warning: Unknown RFID {rfid} ({action})")
        except Exception as e:
            print(f"[{self.shelf_id}] Error accessing REST API: {e}")
            
    def check_local_threshold(self, product_id):
        if self.max_capacity <= 0: return
        
        prop = self.proportions.get(product_id, 0.0)
        # Calculate max allowed for this specific product
        max_allowed = int(self.max_capacity * prop)
        
        # 20% minimum threshold dynamically
        min_threshold = int(max_allowed * 0.20)
        
        # If min_threshold is 0, we default to 1 so we get alerts for items that reach 0
        if min_threshold == 0 and max_allowed > 0:
            min_threshold = 1
            
        current = self.product_counts.get(product_id, 0)
        
        if current < min_threshold:
            print(f"[{self.shelf_id}] 🚨 LOCAL ALERT: {product_id} stock is low! ({current} < {min_threshold})")
            alert_payload = {
                "event": "low_stock_shelf",
                "shelf_id": self.shelf_id,
                "product_id": product_id,
                "current_stock": current,
                "threshold": min_threshold
            }
            self.mqtt_client.myPublish(f"shelf/{self.shelf_id}/events", alert_payload)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python SmartShelf.py <SHELF_ID> (e.g. S-FR-1)")
        sys.exit(1)
        
    shelf_id = sys.argv[1].upper()
    shelf = SmartShelf(shelf_id)
    try:
        shelf.interactive_loop()
    except KeyboardInterrupt:
        pass
    finally:
        shelf.mqtt_client.stop()
