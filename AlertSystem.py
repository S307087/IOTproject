import time
import requests
import json
from smartmarket_MQTT import MyMQTT

REST_API_URL = "http://localhost:8080"
BROKER = "localhost"
PORT = 1883

class AlertNotifier:
    def __init__(self, system):
        self.system = system
        
    def notify(self, topic, payload):
        self.system.handle_message(topic, payload)

class AlertSystem:
    def __init__(self):
        self.notifier = AlertNotifier(self)
        self.mqtt_client = MyMQTT("AlertSystem", BROKER, PORT, self.notifier)
        
    def start(self):
        print("[AlertSystem] Listening for shelf events...")
        self.mqtt_client.mySubscribe("shelf/+/events")
        self.mqtt_client.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.mqtt_client.stop()
        
    def handle_message(self, topic, payload):
        event = payload.get("event")
        shelf_id = payload.get("shelf_id")
        
        if event == "rfid_update":
            action = payload.get("action")
            rfid = payload.get("rfid")
            self.process_inventory_update(shelf_id, rfid, action)
            
        elif event == "low_stock_shelf":
            # Smart shelf already detected low stock locally, alert system forwards it
            product_id = payload.get("product_id")
            current = payload.get("current_stock")
            thresh = payload.get("threshold")
            self.publish_staff_alert(
                level="WARNING",
                msg=f"Shelf {shelf_id} is running low on {product_id}! (Current: {current}, Min: {thresh})"
            )
            
    def process_inventory_update(self, shelf_id, rfid, action):
        print(f"[AlertSystem] Processing {action} for RFID {rfid} from {shelf_id}")
        try:
            # 1. Update Catalog
            r = requests.put(f"{REST_API_URL}/update_inventory", json={"rfid": rfid, "action": action, "shelf_id": shelf_id})
            if r.status_code == 200:
                data = r.json()
                product_id = data.get("product_id")
                
                # 2. Retrieve Product Details to check thresholds
                prod_req = requests.get(f"{REST_API_URL}/get_product_by_rfid?rfid={rfid}")
                if prod_req.status_code == 200:
                    prod_info = prod_req.json()
                    
                    product_name = prod_info.get("product_name")
                    shelf_stock = prod_info.get("shelf_stock")
                    warehouse_stock = prod_info.get("warehouse_stock")
                    
                    # 3. Check Safety Thresholds
                    # Warehouse threshold
                    WAREHOUSE_MIN = 20 # fixed rule for warehouse
                    if warehouse_stock < WAREHOUSE_MIN:
                        self.publish_staff_alert(
                            level="CRITICAL",
                            msg=f"Warehouse stock for {product_name} ({product_id}) is low! Only {warehouse_stock} left."
                        )
                    
                    # Shelf threshold (double-checked by Alert System, though smart shelf does it locally too)
                    self.check_shelf_threshold(shelf_id, product_id, product_name, shelf_stock)
                    
        except Exception as e:
            print(f"[AlertSystem] Error updating catalog or checking thresholds: {e}")
            
    def check_shelf_threshold(self, shelf_id, product_id, product_name, shelf_stock):
        try:
            prod_req = requests.get(f"{REST_API_URL}/get_product?product_id={product_id}")
            if prod_req.status_code == 200:
                prod = prod_req.json()
                max_cap = prod.get("shelf_max_capacity", 0)
                props = prod.get("shelf_proportions", {})
                
                prop = props.get(product_id, 0)
                max_allowed = int(max_cap * prop)
                min_threshold = int(max_allowed * 0.20)
                if min_threshold == 0 and max_allowed > 0: min_threshold = 1
                
                if shelf_stock < min_threshold:
                     self.publish_staff_alert(
                        level="WARNING",
                        msg=f"Shelf {shelf_id} is running low on {product_name}! (Current: {shelf_stock}, Min: {min_threshold})"
                    )
        except Exception as e:
            print(f"[AlertSystem] Error checking shelf thresholds: {e}")

    def publish_staff_alert(self, level, msg):
        print(f"[AlertSystem] Emitting Alert: {level} - {msg}")
        payload = {
            "level": level,
            "message": msg,
            "timestamp": time.time()
        }
        self.mqtt_client.myPublish("staff/alerts", payload)

if __name__ == "__main__":
    sys = AlertSystem()
    sys.start()
