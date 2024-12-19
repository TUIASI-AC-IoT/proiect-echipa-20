import paho.mqtt.client as mqtt
import time

# Callback for connection
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected successfully to MQTT server!")
        # Subscribe to a topic
        client.subscribe("test/topic", qos=0)
        print("Subscribed to topic: test/topic")
    else:
        print(f"Connection failed with reason code {reason_code}")

# Callback for message receipt
def on_message(client, userdata, message):
    print(f"Received message: '{message.payload.decode()}' on topic '{message.topic}' with QoS {message.qos}")

# Callback for publish acknowledgment (QoS 1 and QoS 2)
def on_publish(client, userdata, mid):
    print(f"Message published with message ID: {mid}")

# Callback for SUBACK (subscription acknowledgment)
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print(f"Subscription acknowledged with message ID: {mid}, Granted QoS: {granted_qos}")

# Create client instance
client = mqtt.Client(client_id="TestSubscriber", protocol=mqtt.MQTTv5)
client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish
client.on_subscribe = on_subscribe

# Connect to the MQTT server
try:
    client.connect("127.0.0.1", 1883)
except Exception as e:
    print(f"Failed to connect: {e}")
    exit(1)

# Publish a test message
def publish_test_messages():
    try:
        # Publish messages with different QoS levels
        client.publish("test/topic", payload="Test message with QoS 0", qos=0)
        time.sleep(1)  # Give time to process QoS 0
    except Exception as e:
        print(f"Error during publishing: {e}")

# Start the loop in a separate thread
client.loop_start()

# Publish test messages
publish_test_messages()

# Keep the script running to test receive functionality
time.sleep(5)

# Stop the loop and disconnect
client.loop_stop()
client.disconnect()
