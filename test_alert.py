import time
from smartmarket_MQTT import MyMQTT

def run():
    class Dummy:
        def notify(self, t, p): pass
    client = MyMQTT("TestPublisher", "localhost", 1883, Dummy())
    client.start()
    time.sleep(1)
    print("Publishing RFID update...")
    
    payload = {
        "event": "rfid_update",
        "action": "removed",
        "rfid": "HYG-2003-T1",
        "shelf_id": "S-HY-2"
    }
    client.myPublish("shelf/S-HY-2/events", payload)
    
    time.sleep(2)
    client.stop()
    print("Done")

if __name__ == "__main__":
    run()
