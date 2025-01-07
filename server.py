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
            elif packet_type == 6:  # PUBREL (QoS 2)
                handle_pubrel(data, client_socket)
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
            log_event("GENERATED_CLIENT_ID", "Generated Client ID", client_address=client_address,
                      additional_data=client_id)

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
        log_event("SUBACK_CONSTRUCTED", "SUBACK packet constructed",
                  additional_data={"packet_id": packet_id, "granted_qos_list": granted_qos_list})
        return suback_packet
    except Exception as e:
        log_event("ERROR", f"Error constructing SUBACK packet: {e}",
                  additional_data={"packet_id": packet_id, "granted_qos_list": granted_qos_list})
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


qos2_state = {}  # Tracks the state of QoS 2 messages: {client_id: {packet_id: "state"}}

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

def encode_remaining_length(length):
    """Encode the remaining length as a Variable Byte Integer."""
    encoded_bytes = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 0x80
        encoded_bytes.append(byte)
        if length == 0:
            break
    return bytes(encoded_bytes)


def send_custom_publish(client_socket, topic_name, payload, qos_level, packet_id):
    """Send a tailored PUBLISH packet to a subscriber."""
    try:
        # Fixed Header
        flags = 0
        if qos_level == 1:
            flags |= 0b0010  # QoS 1
        elif qos_level == 2:
            flags |= 0b0100  # QoS 2

        fixed_header = bytes([(0x30 | flags)])  # PUBLISH packet type and flags

        # Variable Header
        topic_name_bytes = topic_name.encode('utf-8')
        topic_name_length = len(topic_name_bytes).to_bytes(2, 'big')

        variable_header = topic_name_length + topic_name_bytes

        # QoS 1 and 2 require Packet Identifier
        if qos_level > 0:
            variable_header += packet_id.to_bytes(2, 'big')

        # Payload
        payload_bytes = payload.encode('utf-8')

        # Remaining Length
        remaining_length = len(variable_header) + len(payload_bytes)
        remaining_length_bytes = encode_remaining_length(remaining_length)

        # Final Packet
        publish_packet = fixed_header + remaining_length_bytes + variable_header + payload_bytes

        # Send the packet
        client_socket.send(publish_packet)
        log_event("PUBLISH_SENT", f"PUBLISH sent to subscriber with QoS {qos_level}",
                  additional_data={"topic": topic_name, "qos": qos_level})
    except Exception as e:
        log_event("ERROR", f"Error sending PUBLISH to subscriber: {e}")


def handle_publish_packet(data, client_socket, client_address):
    """Handle the PUBLISH packet."""
    try:
        publish_info = parse_publish_packet(data)
        topic_name = publish_info["topic_name"]
        payload = publish_info["payload"]
        qos_level = publish_info["qos_level"]
        packet_id = publish_info.get("packet_id", None)

        log_event("PUBLISH", f"PUBLISH received for topic {topic_name} with QoS {qos_level}",
                  client_address=client_address, additional_data=payload)

        # Handle retained messages
        retain_flag = publish_info.get("retain_flag", 0)
        if retain_flag:
            retained_messages[topic_name] = payload

        # Deliver the message to subscribers
        if topic_name in subscriptions:
            for subscriber_socket in subscriptions[topic_name][:]:
                try:
                    send_custom_publish(subscriber_socket, topic_name, payload, qos_level, packet_id)
                except Exception as e:
                    subscriptions[topic_name].remove(subscriber_socket)
                    log_event("ERROR", "Failed to deliver message, subscriber removed", additional_data=topic_name)

        # Handle QoS acknowledgments for the sender
        if qos_level == 1:
            send_puback(client_socket, packet_id)
        elif qos_level == 2:
            send_pubrec(client_socket, packet_id)

    except Exception as e:
        log_event("ERROR", f"Error processing PUBLISH packet: {e}", client_address=client_address)

def send_puback(client_socket, packet_id):
    """Send PUBACK packet."""
    try:
        fixed_header = b'\x40'  # Packet Type = PUBACK
        variable_header = packet_id.to_bytes(2, 'big')
        remaining_length = len(variable_header)
        puback_packet = fixed_header + remaining_length.to_bytes(1, 'big') + variable_header
        client_socket.send(puback_packet)
        log_event("PUBACK", "PUBACK sent", additional_data={"packet_id": packet_id})
    except Exception as e:
        log_event("ERROR", f"Error sending PUBACK: {e}")

def send_pubrec(client_socket, packet_id):
    """Send PUBREC packet."""
    try:
        fixed_header = b'\x50'  # Packet Type = PUBREC
        variable_header = packet_id.to_bytes(2, 'big')
        remaining_length = len(variable_header)
        pubrec_packet = fixed_header + remaining_length.to_bytes(1, 'big') + variable_header
        client_socket.send(pubrec_packet)
        log_event("PUBREC", "PUBREC sent", additional_data={"packet_id": packet_id})
    except Exception as e:
        log_event("ERROR", f"Error sending PUBREC: {e}")

def handle_pubrel(data, client_socket):
    """Handle PUBREL packet."""
    try:
        packet_id = int.from_bytes(data[2:4], 'big')
        client_id = client_socket.getpeername()  # Identify the client by address
        log_event("PUBREL", f"PUBREL received for Packet ID {packet_id}", client_address=client_id)

        # Verify state
        if client_id in qos2_state and qos2_state[client_id].get(packet_id) == "PUBREC_SENT":
            # Transition to PUBCOMP
            send_pubcomp(client_socket, packet_id)
            qos2_state[client_id][packet_id] = "PUBCOMP_SENT"
        else:
            log_event("ERROR", f"Invalid PUBREL state for Packet ID {packet_id}", client_address=client_id)

    except Exception as e:
        log_event("ERROR", f"Error handling PUBREL: {e}")


def send_pubcomp(client_socket, packet_id):
    """Send PUBCOMP packet."""
    try:
        fixed_header = b'\x70'  # Packet Type = PUBCOMP
        variable_header = packet_id.to_bytes(2, 'big')
        remaining_length = len(variable_header)
        pubcomp_packet = fixed_header + remaining_length.to_bytes(1, 'big') + variable_header
        client_socket.send(pubcomp_packet)
        log_event("PUBCOMP", "PUBCOMP sent", additional_data={"packet_id": packet_id})
    except Exception as e:
        log_event("ERROR", f"Error sending PUBCOMP: {e}")


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
