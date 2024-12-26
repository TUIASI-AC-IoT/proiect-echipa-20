import socket
import threading
import uuid
import logging
import json

from mqtt_parser import parse_fixed_header, parse_connect_packet, PACKET_TYPES, parse_publish_packet, \
    parse_variable_byte_integer, parse_subscribe_properties, parse_unsubscribe_packet

# Server configuration
HOST = '127.0.0.1'  # Localhost for testing
PORT = 1883  # Default MQTT port

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler("mqtt_server.log"),  # Logs to file
        logging.StreamHandler()  # Logs to console
    ]
)

def log_event(event_type, message, client_address=None, additional_data=None):
    """Log an event with structured data."""
    log_entry = {
        "event": event_type,
        "message": message,
        "client_address": client_address,
        "additional_data": additional_data,
    }
    logging.info(json.dumps(log_entry))

# Subscription registry
subscriptions = {}  # Dictionary to track subscribers: {topic: [client_sockets]}
retained_messages = {}  # Dictionary to store retained messages: {topic: payload}

def handle_client(client_socket, client_address):
    """Handle an individual MQTT client."""
    log_event("CONNECTION", "New connection established", client_address=client_address)
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                log_event("DISCONNECTION", "Client disconnected", client_address=client_address)
                break

            # Parse the fixed header
            packet_type, flags, remaining_length, fixed_header_length = parse_fixed_header(data)
            packet_name = PACKET_TYPES.get(packet_type, "UNKNOWN")
            log_event("PACKET_RECEIVED", f"Received {packet_name} packet", client_address=client_address)

            # Handle packets

            if packet_type == 1:  # CONNECT
                handle_connect_packet(data, client_socket, client_address)
            elif packet_type == 3:  # PUBLISH
                handle_publish_packet(data, client_socket, client_address)
            elif packet_type == 8:  # SUBSCRIBE
                handle_subscribe_packet(data, client_socket, client_address)
            elif packet_type == 10:  # UNSUBSCRIBE
                handle_unsubscribe_packet(data, client_socket, client_address)
            elif packet_type == 12:  # PINGREQ
                handle_pingreq_packet(client_socket, client_address)
            elif packet_type == 14:  # DISCONNECT
                handle_disconnect_packet(client_socket, client_address)

    except Exception as e:
        log_event("ERROR", f"Error with client: {e}", client_address=client_address)
    finally:
        client_socket.close()

def handle_connect_packet(data, client_socket, client_address):
    """Handle the CONNECT packet."""
    try:
        connect_info = parse_connect_packet(data[2:])  # Skip fixed header
        client_id = connect_info.get("client_id")

        if not client_id:
            client_id = f"auto-{uuid.uuid4().hex[:8]}"
            log_event("GENERATED_CLIENT_ID", "Generated Client ID", client_address=client_address, additional_data=client_id)

        log_event("CONNECT", f"CONNECT received. Client ID: {client_id}", client_address=client_address)

        # Construct CONNACK packet (MQTT v5 compliant)
        fixed_header = b'\x20'  # Packet Type = CONNACK
        variable_header = b'\x00\x00'  # Connect Acknowledge Flags and Return Code
        properties = b'\x00'  # Properties Length (no properties)

        remaining_length = len(variable_header) + len(properties)
        connack_packet = fixed_header + remaining_length.to_bytes(1, 'big') + variable_header + properties

        client_socket.send(connack_packet)
        log_event("CONNACK", "CONNACK sent", client_address=client_address, additional_data=client_id)
    except Exception as e:
        log_event("ERROR", f"Error processing CONNECT packet: {e}", client_address=client_address)

def construct_suback_packet(packet_id, granted_qos_list):
    """Construct a SUBACK packet."""
    try:
        fixed_header = b'\x90'  # Packet Type = SUBACK
        variable_header = packet_id.to_bytes(2, 'big')  # Packet Identifier
        payload = bytes(granted_qos_list)  # Granted QoS for each topic

        remaining_length = len(variable_header) + len(payload)
        suback_packet = fixed_header + remaining_length.to_bytes(1, 'big') + variable_header + payload
        log_event("SUBACK_CONSTRUCTED", "SUBACK packet constructed", additional_data={"packet_id": packet_id, "granted_qos_list": granted_qos_list})
        return suback_packet
    except Exception as e:
        log_event("ERROR", f"Error constructing SUBACK packet: {e}", additional_data={"packet_id": packet_id, "granted_qos_list": granted_qos_list})
        raise

def handle_subscribe_packet(data, client_socket, client_address):
    """Handle the SUBSCRIBE packet."""
    try:
        packet_type, flags, remaining_length, fixed_header_length = parse_fixed_header(data)
        offset = fixed_header_length

        packet_id = (data[offset] << 8) | data[offset + 1]
        offset += 2

        property_length, property_length_size = parse_variable_byte_integer(data[offset:])
        offset += property_length_size

        properties = parse_subscribe_properties(data[offset:offset + property_length])
        offset += property_length

        topics = []
        while offset - fixed_header_length < remaining_length:
            topic_name_len = (data[offset] << 8) | data[offset + 1]
            offset += 2
            topic_name = data[offset:offset + topic_name_len].decode('utf-8')
            offset += topic_name_len

            subscription_options = data[offset]
            qos = subscription_options & 0b11
            offset += 1

            topics.append((topic_name, qos))

            if topic_name not in subscriptions:
                subscriptions[topic_name] = []
            if client_socket not in subscriptions[topic_name]:
                subscriptions[topic_name].append(client_socket)

            # Send retained message if available
            if topic_name in retained_messages:
                retained_payload = retained_messages[topic_name]
                client_socket.send(retained_payload.encode('utf-8'))

        suback_packet = construct_suback_packet(packet_id, [qos for _, qos in topics])
        client_socket.send(suback_packet)

        log_event("SUBSCRIBE", "Subscription successful", client_address=client_address, additional_data=topics)

    except Exception as e:
        log_event("ERROR", f"Error processing SUBSCRIBE packet: {e}", client_address=client_address)

def construct_unsuback_packet(packet_id):
    """Construct an UNSUBACK packet."""
    fixed_header = b'\xB0'  # Packet Type = UNSUBACK
    variable_header = packet_id.to_bytes(2, 'big')  # Packet Identifier
    remaining_length = len(variable_header)
    return fixed_header + remaining_length.to_bytes(1, 'big') + variable_header


def handle_unsubscribe_packet(data, client_socket, client_address):
    """Handle the UNSUBSCRIBE packet."""
    try:
        # Call parse_unsubscribe_packet to get packet_id and topics
        packet_id, topics = parse_unsubscribe_packet(data)

        for topic in topics:
            if topic in subscriptions:
                if client_socket in subscriptions[topic]:
                    subscriptions[topic].remove(client_socket)
                    log_event(
                        "UNSUBSCRIBE",
                        f"Client unsubscribed from topic: {topic}",
                        client_address=client_address
                    )
                    if not subscriptions[topic]:  # Cleanup empty topic
                        del subscriptions[topic]

        # Construct and send UNSUBACK
        unsuback_packet = construct_unsuback_packet(packet_id)
        client_socket.send(unsuback_packet)
        log_event("UNSUBACK", "UNSUBACK sent", client_address=client_address, additional_data={"packet_id": packet_id})

    except ValueError as ve:
        log_event("ERROR", f"Error processing UNSUBSCRIBE packet: {ve}", client_address=client_address)
    except Exception as e:
        log_event("ERROR", f"Unexpected error processing UNSUBSCRIBE packet: {e}", client_address=client_address)


def handle_publish_packet(data, client_socket, client_address):
    """Handle the PUBLISH packet."""
    try:
        publish_info = parse_publish_packet(data)
        topic_name = publish_info["topic_name"]
        payload = publish_info["payload"]

        log_event("PUBLISH", f"PUBLISH received for topic {topic_name}", client_address=client_address, additional_data=payload)

        retain_flag = publish_info.get("retain_flag", 0)
        if retain_flag:
            retained_messages[topic_name] = payload

        if topic_name in subscriptions:
            for subscriber_socket in subscriptions[topic_name][:]:
                try:
                    subscriber_socket.send(data)
                except Exception as e:
                    subscriptions[topic_name].remove(subscriber_socket)
                    log_event("ERROR", "Failed to deliver message, subscriber removed", additional_data=topic_name)

    except Exception as e:
        log_event("ERROR", f"Error processing PUBLISH packet: {e}", client_address=client_address)

def handle_pingreq_packet(client_socket, client_address):
    """Handle the PINGREQ packet."""
    try:
        # Construct PINGRESP (Type 13) packet
        fixed_header = b'\xD0'  # Packet Type = PINGRESP
        remaining_length = b'\x00'  # No additional data
        pingresp_packet = fixed_header + remaining_length

        # Send PINGRESP
        client_socket.send(pingresp_packet)
        log_event("PINGRESP", "PINGRESP sent", client_address=client_address)
    except Exception as e:
        log_event("ERROR", f"Error processing PINGREQ packet: {e}", client_address=client_address)


def handle_disconnect_packet(client_socket, client_address):
    """Handle the DISCONNECT packet."""
    try:
        # Simply log and close the connection
        log_event("DISCONNECT", "Client requested disconnection", client_address=client_address)
        client_socket.close()
    except Exception as e:
        log_event("ERROR", f"Error processing DISCONNECT packet: {e}", client_address=client_address)


def start_server():
    """Start the MQTT server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    log_event("SERVER_START", f"MQTT server running on {HOST}:{PORT}")

    try:
        while True:
            client_socket, client_address = server_socket.accept()
            threading.Thread(target=handle_client, args=(client_socket, client_address)).start()
    except KeyboardInterrupt:
        log_event("SERVER_STOP", "Server shutting down...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()
