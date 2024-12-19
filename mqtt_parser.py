def parse_fixed_header(data):
    """Parse the fixed header of an MQTT packet."""
    byte1 = data[0]
    packet_type = (byte1 & 0xF0) >> 4
    flags = byte1 & 0x0F

    # Parse Remaining Length (Variable Byte Integer)
    remaining_length = 0
    multiplier = 1
    fixed_header_length = 1

    for i in range(1, 5):  # Remaining Length can be up to 4 bytes
        byte = data[fixed_header_length]
        fixed_header_length += 1
        remaining_length += (byte & 127) * multiplier
        if (byte & 128) == 0:
            break
        multiplier *= 128

    print(f"Fixed Header: Packet Type={packet_type}, Flags={flags}, Remaining Length={remaining_length}, Fixed Header Length={fixed_header_length}")
    return packet_type, flags, remaining_length, fixed_header_length


def parse_connect_packet(data):
    """Parse the CONNECT packet."""
    offset = 0
    print(f"Raw data (hex): {data.hex()}")

    # Protocol name
    protocol_name_len = (data[offset] << 8) | data[offset + 1]
    offset += 2
    protocol_name = data[offset:offset + protocol_name_len].decode('utf-8')
    offset += protocol_name_len

    if protocol_name != "MQTT":
        raise ValueError("Invalid protocol name")

    # Protocol level
    protocol_level = data[offset]
    offset += 1

    if protocol_level != 5:
        raise ValueError(f"Unsupported protocol level: {protocol_level}")

    # Connect flags
    connect_flags = data[offset]
    clean_session = (connect_flags & 0x02) >> 1
    print(f"Offset {offset}: Connect Flags = {bin(connect_flags)}, Clean Session = {clean_session}")
    offset += 1

    # Keep Alive
    keep_alive = (data[offset] << 8) | data[offset + 1]
    print(f"Offset {offset}: Keep Alive = {keep_alive}")
    offset += 2

    # Client ID Length
    client_id_len = (data[offset] << 8) | data[offset + 1]
    if client_id_len == 0 and len(data[offset + 2:]) > 0:
        # Skip extra byte before Client ID
        print(f"Adjusting offset due to unexpected data: {data[offset + 2:].hex()}")
        offset += 1  # Skip unexpected byte
        client_id_len = (data[offset] << 8) | data[offset + 1]
    offset += 2


    # Client ID
    if client_id_len == 0 and not clean_session:
        raise ValueError("Empty Client ID with Clean Session = 0")
    elif client_id_len > 0:
        client_id = data[offset:offset + client_id_len].decode('utf-8')
        print(f"Offset {offset}: Client ID = {client_id}")
        offset += client_id_len
    else:
        client_id = None

    print(f"Final Offset {offset}: Remaining Data = {data[offset:].hex()}")

    return {
        "protocol_name": protocol_name,
        "protocol_level": protocol_level,
        "clean_session": clean_session,
        "keep_alive": keep_alive,
        "client_id": client_id,
    }


def parse_publish_packet(data):
    """Parse the PUBLISH packet."""
    offset = 0

    # Extract flags (QoS and Dup flag are in the fixed header flags)
    flags = data[0] & 0x0F
    dup_flag = (flags & 0x08) >> 3
    qos_level = (flags & 0x06) >> 1
    retain_flag = flags & 0x01
    print(f"PUBLISH Flags: Dup={dup_flag}, QoS={qos_level}, Retain={retain_flag}")

    # Remaining Length (multi-byte)
    remaining_length = 0
    multiplier = 1
    while True:
        byte = data[offset + 1]
        remaining_length += (byte & 127) * multiplier
        offset += 1
        if (byte & 128) == 0:
            break
        multiplier *= 128

    # Topic Name
    topic_name_len = (data[offset + 1] << 8) | data[offset + 2]
    offset += 2
    topic_name = data[offset + 1:offset + 1 + topic_name_len].decode('utf-8')
    offset += topic_name_len
    print(f"Topic Name: {topic_name}")

    # Packet Identifier for QoS 1 and 2
    packet_id = None
    if qos_level > 0:
        packet_id = (data[offset + 1] << 8) | data[offset + 2]
        offset += 2
        print(f"Packet ID: {packet_id}")

    # Payload
    payload = data[offset + 1:offset + remaining_length].decode('utf-8')
    print(f"Payload: {payload}")

    return {
        "topic_name": topic_name,
        "qos_level": qos_level,
        "retain_flag": retain_flag,
        "packet_id": packet_id,
        "payload": payload,
    }

def parse_variable_byte_integer(data):
    """Parse a Variable Byte Integer."""
    value = 0
    multiplier = 1
    bytes_read = 0
    for byte in data:
        value += (byte & 127) * multiplier
        bytes_read += 1
        if (byte & 128) == 0:
            break
        multiplier *= 128
    return value, bytes_read

def parse_subscribe_properties(data):
    """Parse properties of the SUBSCRIBE packet."""
    properties = {}
    offset = 0
    while offset < len(data):
        prop_id = data[offset]
        offset += 1
        if prop_id == 0x0B:  # Subscription Identifier
            sub_id, sub_id_len = parse_variable_byte_integer(data[offset:])
            offset += sub_id_len
            properties["subscription_identifier"] = sub_id
        elif prop_id == 0x26:  # User Property
            key_len = (data[offset] << 8) | data[offset + 1]
            key = data[offset + 2:offset + 2 + key_len].decode("utf-8")
            offset += 2 + key_len
            value_len = (data[offset] << 8) | data[offset + 1]
            value = data[offset + 2:offset + 2 + value_len].decode("utf-8")
            offset += 2 + value_len
            if "user_properties" not in properties:
                properties["user_properties"] = []
            properties["user_properties"].append((key, value))
        else:
            raise ValueError(f"Unknown property ID: {prop_id}")
    return properties

PACKET_TYPES = {
    1: "CONNECT",
    2: "CONNACK",
    3: "PUBLISH",
    4: "PUBACK",
    8: "SUBSCRIBE",
    9: "SUBACK",
    10: "UNSUBSCRIBE",
    11: "UNSUBACK",
    12: "PINGREQ",
    13: "PINGRESP",
    14: "DISCONNECT",
}
