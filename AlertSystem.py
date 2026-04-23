import time
import requests
import json
from smartmarket_MQTT import MyMQTT

import os

CATALOG_API_HOST = os.environ.get("CATALOG_API_HOST", "localhost")
REST_API_URL = f"http://{CATALOG_API_HOST}:8080"
BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
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
                msg=f"Shelf {shelf_id} is running low on {product_id}! (Current: {current}, Min: {thresh})",
                event="low_stock_shelf",
                product_id=product_id,
                shelf_id=shelf_id
            )
            
    def process_inventory_update(self, shelf_id, rfid, action):
        print(f"[AlertSystem] Processing {action} for RFID {rfid} from {shelf_id}")
        try:
            # 1. Update Catalog
            r = requests.put(f"{REST_API_URL}/update_inventory", json={"rfid": rfid, "action": action, "shelf_id": shelf_id})
            if r.status_code == 200:
                data = r.json()
                product_id = data.get("product_id")
                shelf_stock_new = data.get("shelf_stock")
                warehouse_stock_new = data.get("warehouse_stock")
                
                # We always inform StaffBot of stock updates so that it can clear resolved alerts
                self.mqtt_client.myPublish("staff/alerts", {
                    "event": "stock_updated",
                    "product_id": product_id,
                    "shelf_stock": shelf_stock_new,
                    "warehouse_stock": warehouse_stock_new
                })
                
                
                # 2. Retrieve Product Details to check thresholds
                prod_req = requests.get(f"{REST_API_URL}/get_product_by_rfid?rfid={rfid}")
                if prod_req.status_code == 200:
                    prod_info = prod_req.json()
                    
                    product_name = prod_info.get("product_name")
                    shelf_stock = prod_info.get("shelf_stock")
                    warehouse_stock = prod_info.get("warehouse_stock")
                    
                    # Thresholds are now centrally evaluated by StaffBot responding to the `stock_updated` event we just published.
        except Exception as e:
            print(f"[AlertSystem] Error updating catalog or checking thresholds: {e}")

    def publish_staff_alert(self, level, msg, event=None, product_id=None, shelf_id=None):
        print(f"[AlertSystem] Emitting Alert: {level} - {msg}")
        payload = {
            "level": level,
            "message": msg,
            "timestamp": time.time()
        }
        if event: payload["event"] = event
        if product_id: payload["product_id"] = product_id
        if shelf_id: payload["shelf_id"] = shelf_id
        self.mqtt_client.myPublish("staff/alerts", payload)

if __name__ == "__main__":
    sys = AlertSystem()
    sys.start()
