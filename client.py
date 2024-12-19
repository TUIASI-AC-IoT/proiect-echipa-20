import paho.mqtt.client as mqtt

# Callback for connection
def on_connect(client, userdata, flags, reason_code, properties=None):
    print("Connected with reason code:", reason_code)
    client.subscribe("test/topic")
    print("Subscribed to: test/topic")
    client.unsubscribe("test/topic")
    print("Unsubscribed from: test/topic")

# Callback for message receipt
def on_message(client, userdata, message):
    print(f"Message received on {message.topic}: {message.payload.decode()}")

# Callback for unsubscription
def on_unsubscribe(client, userdata, mid, properties=None):
    print(f"Unsubscribe successful for message ID: {mid}")

client = mqtt.Client(protocol=mqtt.MQTTv5)
client.on_connect = on_connect
client.on_message = on_message
client.on_unsubscribe = on_unsubscribe

client.connect("127.0.0.1", 1883)
client.loop_forever()
