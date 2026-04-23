import os
import time
import requests
import threading
import cherrypy
from smartmarket_MQTT import MyMQTT

BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
PORT = 1883

THINGSPEAK_API_KEY = os.environ.get("THINGSPEAK_WRITE_KEY", "MOCK_KEY")
THINGSPEAK_URL = "https://api.thingspeak.com/update"

class ThingSpeakNotifier:
    def __init__(self, adaptor):
        self.adaptor = adaptor
        
    def notify(self, topic, payload):
        self.adaptor.handle_message(topic, payload)

class ThingSpeakAdaptor:
    def __init__(self):
        self.notifier = ThingSpeakNotifier(self)
        self.mqtt_client = MyMQTT("ThingSpeakAdaptor", BROKER, PORT, self.notifier)
        
        self.history = []

    def start(self):
        print("[ThingSpeakAdaptor] Starting and subscribing to env/# ...")
        self.mqtt_client.mySubscribe("env/#")
        self.mqtt_client.start()
        
    def stop(self):
        self.mqtt_client.stop()
        
    def handle_message(self, topic, payload):
        area = payload.get("area")
        temp = payload.get("temperature")
        hum = payload.get("humidity")
        timestamp = payload.get("timestamp")
        
        # Store locally for Node-RED historical provider
        self.history.append(payload)
        if len(self.history) > 1000:
            self.history.pop(0)
            
        # Push to ThingSpeak (Simulated or Real)
        if THINGSPEAK_API_KEY != "MOCK_KEY":
            try:
                # Field1: Market Temp, Field2: Market Hum, Field3: Fridge Temp, Field4: Fridge Hum
                field_temp = 1 if area == "market" else 3
                field_hum = 2 if area == "market" else 4
                
                params = {
                    "api_key": THINGSPEAK_API_KEY,
                    f"field{field_temp}": temp,
                    f"field{field_hum}": hum
                }
                requests.get(THINGSPEAK_URL, params=params)
                print(f"[ThingSpeakAdaptor] Pushed {area} data to ThingSpeak.")
            except Exception as e:
                print(f"[ThingSpeakAdaptor] Failed to push to ThingSpeak: {e}")
        else:
            # print(f"[ThingSpeakAdaptor] MOCK push to ThingSpeak for {area}: Temp={temp}, Hum={hum}")
            pass

class HistoryRESTProvider:
    def __init__(self, adaptor):
        self.adaptor = adaptor
        
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_history(self):
        return {"status": "success", "history": self.adaptor.history}

if __name__ == '__main__':
    adaptor = ThingSpeakAdaptor()
    adaptor.start()
    
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8082,
        'log.screen': True
    })
    
    def cors():
        cherrypy.response.headers["Access-Control-Allow-Origin"] = "*"
        cherrypy.response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        cherrypy.response.headers["Access-Control-Allow-Headers"] = "Content-Type"

    cherrypy.tools.cors = cherrypy.Tool('before_handler', cors)
    
    conf = {
        '/': {
            'tools.cors.on': True
        }
    }
    
    print("Starting ThingSpeakAdaptor REST API on port 8082...")
    cherrypy.quickstart(HistoryRESTProvider(adaptor), '/', conf)
