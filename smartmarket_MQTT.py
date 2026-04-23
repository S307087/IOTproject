import json
import paho.mqtt.client as PahoMQTT
import os


class MyMQTT:
    # Classe che gestisce connessione, publish e subscribe MQTT
    def __init__(self, clientID, broker, port, notifier=None,
                 service_name=None, keepalive=60, clean_session=True):

        # Salvo i parametri principali del client
        if broker is None or broker == "localhost":
            broker = os.environ.get("MQTT_BROKER_HOST", "localhost")
        self.broker = broker
        self.port = port
        self.notifier = notifier
        self.clientID = clientID
        self.service_name = service_name if service_name is not None else clientID
        self.keepalive = keepalive
        self.clean_session = clean_session

        # Insieme dei topic sottoscritti
        self._topics = set()

        # Indica se il client è subscriber
        self._isSubscriber = False

        # Creo il client MQTT
        self._paho_mqtt = PahoMQTT.Client(
            client_id=self.clientID,
            clean_session=self.clean_session
        )

        # Collego le callback ai metodi della classe
        self._paho_mqtt.on_connect = self.myOnConnect
        self._paho_mqtt.on_message = self.myOnMessageReceived
        self._paho_mqtt.on_disconnect = self.myOnDisconnect

    def myOnConnect(self, paho_mqtt, userdata, flags, rc):
        # Viene eseguita quando il client si connette al broker
        print(f"[{self.service_name}] Connected to {self.broker}:{self.port} with result code {rc}")
        for topic in self._topics:
            print(f"[{self.service_name}] Auto-subscribing to {topic} after connect...")
            self._paho_mqtt.subscribe(topic, 1)

    def myOnDisconnect(self, paho_mqtt, userdata, rc):
        # Viene eseguita quando il client si disconnette
        print(f"[{self.service_name}] Disconnected from broker with result code {rc}")

    def myOnMessageReceived(self, paho_mqtt, userdata, msg):
        # Viene eseguita quando arriva un messaggio
        try:
            # Converto il payload da bytes a stringa
            payload = msg.payload.decode("utf-8")

            # Se il payload è JSON, lo trasformo in dizionario
            try:
                payload = json.loads(payload)
            except Exception:
                pass

            # Stampo il messaggio ricevuto
            print(f"[{self.service_name}] Message received on topic '{msg.topic}': {payload}")

            # Passo il messaggio al notifier, se esiste
            if self.notifier is not None:
                self.notifier.notify(msg.topic, payload)

        except Exception as e:
            # Error handling on receive
            print(f"[{self.service_name}] Error while processing received message: {e}")

    def myPublish(self, topic, msg, qos=1, retain=False):
        # Pubblica un messaggio su un topic
        try:
            # Se il messaggio è un dict, lo converto in JSON
            if isinstance(msg, dict):
                msg = json.dumps(msg)

            # Stampo cosa sto inviando
            print(f"[{self.service_name}] Publishing on topic '{topic}': {msg}")

            # Invio il messaggio al broker
            self._paho_mqtt.publish(topic, msg, qos=qos, retain=retain)

        except Exception as e:
            # Error handling on publish
            print(f"[{self.service_name}] Publish error: {e}")

    def mySubscribe(self, topic, qos=1):
        # Mi iscrivo a un topic
        print(f"[{self.service_name}] Subscribing to topic '{topic}' with QoS {qos}")

        # Invio la richiesta di subscribe
        self._paho_mqtt.subscribe(topic, qos)

        # Salvo il topic tra quelli sottoscritti
        self._topics.add(topic)
        self._isSubscriber = True

    def myUnsubscribe(self, topic):
        # Mi cancello da un topic
        if topic in self._topics:
            print(f"[{self.service_name}] Unsubscribing from topic '{topic}'")

            # Invio la richiesta di unsubscribe
            self._paho_mqtt.unsubscribe(topic)

            # Tolgo il topic dalla lista interna
            self._topics.remove(topic)

        # Se non ci sono più topic, non sono più subscriber
        if len(self._topics) == 0:
            self._isSubscriber = False

    def start(self):
        # Avvio il client MQTT
        print(f"[{self.service_name}] Starting MQTT client...")

        # Mi connetto al broker
        self._paho_mqtt.connect(self.broker, self.port, self.keepalive)

        # Avvio il loop di ascolto
        self._paho_mqtt.loop_start()

    def stop(self):
        # Chiudo il client MQTT
        print(f"[{self.service_name}] Stopping MQTT client...")

        # Faccio unsubscribe da tutti i topic
        if self._isSubscriber:
            for topic in list(self._topics):
                self.myUnsubscribe(topic)

        # Fermo il loop MQTT
        self._paho_mqtt.loop_stop()

        # Mi disconnetto dal broker
        self._paho_mqtt.disconnect()