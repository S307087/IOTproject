import os
import time
import json
import threading
import random
import cherrypy
from smartmarket_MQTT import MyMQTT

BROKER = os.environ.get("MQTT_BROKER_HOST", "localhost")
PORT = 1883

class RaspberryPiConnector:
    def __init__(self):
        self.mqtt_client = MyMQTT("RaspberryPiConnector", BROKER, PORT)
        self.market_temp = 22.0
        self.market_hum = 45.0
        self.fridge_temp = 4.0
        self.fridge_hum = 60.0
        
        self.running = True

    def start(self):
        self.mqtt_client.start()
        print("[RaspberryPiConnector] Connected to MQTT Broker.")
        
        # Start simulation loop in background
        threading.Thread(target=self.simulation_loop, daemon=True).start()
        
    def stop(self):
        self.running = False
        self.mqtt_client.stop()
        
    def simulation_loop(self):
        while self.running:
            # Simulate slight environmental changes
            self.market_temp += random.uniform(-0.5, 0.5)
            self.market_hum += random.uniform(-1.0, 1.0)
            self.fridge_temp += random.uniform(-0.2, 0.2)
            self.fridge_hum += random.uniform(-0.5, 0.5)
            
            # Keep values within bounds
            self.market_temp = max(18.0, min(26.0, self.market_temp))
            self.market_hum = max(30.0, min(60.0, self.market_hum))
            self.fridge_temp = max(-2.0, min(8.0, self.fridge_temp))
            self.fridge_hum = max(50.0, min(80.0, self.fridge_hum))
            
            market_data = {
                "area": "market",
                "temperature": round(self.market_temp, 2),
                "humidity": round(self.market_hum, 2),
                "timestamp": time.time()
            }
            fridge_data = {
                "area": "fridge",
                "temperature": round(self.fridge_temp, 2),
                "humidity": round(self.fridge_hum, 2),
                "timestamp": time.time()
            }
            
            # Publish to MQTT Broker
            self.mqtt_client.myPublish("env/market", market_data)
            self.mqtt_client.myPublish("env/fridge", fridge_data)
            
            time.sleep(10) # Send data every 10 seconds

class EnvRESTProvider:
    def __init__(self, connector):
        self.connector = connector
        
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_live_data(self):
        return {
            "market": {
                "temperature": round(self.connector.market_temp, 2),
                "humidity": round(self.connector.market_hum, 2)
            },
            "fridge": {
                "temperature": round(self.connector.fridge_temp, 2),
                "humidity": round(self.connector.fridge_hum, 2)
            }
        }

if __name__ == '__main__':
    connector = RaspberryPiConnector()
    connector.start()
    
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8081,
        'log.screen': True
    })
    
    # Enable CORS
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
    
    print("Starting RaspberryPi Connector REST API on port 8081...")
    cherrypy.quickstart(EnvRESTProvider(connector), '/', conf)
