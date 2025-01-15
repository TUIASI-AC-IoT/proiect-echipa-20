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

    print(
        f"Fixed Header: Packet Type={packet_type}, Flags={flags}, Remaining Length={remaining_length}, Fixed Header Length={fixed_header_length}")
    return packet_type, flags, remaining_length, fixed_header_length


def parse_connect_packet(data):
    """Parse the CONNECT packet, including LWT fields."""
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
    will_flag = (connect_flags & 0x04) >> 2
    will_qos = (connect_flags & 0x18) >> 3
    will_retain = (connect_flags & 0x20) >> 5
    clean_session = (connect_flags & 0x02) >> 1
    print(f"Offset {offset}: Connect Flags = {bin(connect_flags)}, Clean Session = {clean_session}, Will Flag = {will_flag}")
    offset += 1

    # Keep Alive
    keep_alive = (data[offset] << 8) | data[offset + 1]
    print(f"Offset {offset}: Keep Alive = {keep_alive}")
    offset += 2

    # Properties
    property_length, property_length_size = parse_variable_byte_integer(data[offset:])
    offset += property_length_size

    will_delay_interval = 0
    user_properties = {}
    if property_length > 0:
        end_of_properties = offset + property_length
        while offset < end_of_properties:
            property_id = data[offset]
            offset += 1

            if property_id == 0x18:  # Will Delay Interval
                will_delay_interval = int.from_bytes(data[offset:offset + 4], 'big')
                offset += 4
                print(f"Will Delay Interval: {will_delay_interval}")
            elif property_id == 0x26:  # User Property
                key_len = (data[offset] << 8) | data[offset + 1]
                key = data[offset + 2:offset + 2 + key_len].decode('utf-8')
                offset += 2 + key_len
                value_len = (data[offset] << 8) | data[offset + 1]
                value = data[offset + 2:offset + 2 + value_len].decode('utf-8')
                offset += 2 + value_len
                user_properties[key] = value
                print(f"User Property: {key} = {value}")

    # Client ID
    client_id_len = (data[offset] << 8) | data[offset + 1]
    offset += 2

    if client_id_len == 0 and not clean_session:
        raise ValueError("Empty Client ID with Clean Session = 0")
    elif client_id_len > 0:
        client_id = data[offset:offset + client_id_len].decode('utf-8')
        print(f"Offset {offset}: Client ID = {client_id}")
        offset += client_id_len
    else:
        client_id = None

    # Will properties, topic, and message
    will_topic = None
    will_message = None

    if will_flag:
        # Will Properties
        will_property_length, will_property_length_size = parse_variable_byte_integer(data[offset:])
        offset += will_property_length_size
        will_properties_end = offset + will_property_length

        # Parse additional Will properties if needed (e.g., Content Type, Response Topic)
        while offset < will_properties_end:
            property_id = data[offset]
            offset += 1

            if property_id == 0x01:  # Payload Format Indicator
                payload_format = data[offset]
                offset += 1
            elif property_id == 0x02:  # Message Expiry Interval
                expiry_interval = int.from_bytes(data[offset:offset + 4], 'big')
                offset += 4

        # Will Topic
        will_topic_len = (data[offset] << 8) | data[offset + 1]
        offset += 2
        will_topic = data[offset:offset + will_topic_len].decode('utf-8')
        offset += will_topic_len

        # Will Message
        will_message_len = (data[offset] << 8) | data[offset + 1]
        offset += 2
        will_message = data[offset:offset + will_message_len].decode('utf-8')
        offset += will_message_len

        print(f"Will Topic: {will_topic}, Will Message: {will_message}")

    return {
        "protocol_name": protocol_name,
        "protocol_level": protocol_level,
        "clean_session": clean_session,
        "keep_alive": keep_alive,
        "client_id": client_id,
        "will_flag": will_flag,
        "will_qos": will_qos,
        "will_retain": will_retain,
        "will_topic": will_topic,
        "will_message": will_message,
        "will_delay_interval": will_delay_interval,
        "user_properties": user_properties,
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


def parse_unsubscribe_packet(data):
    """Parse an UNSUBSCRIBE packet with detailed logging."""
    try:
        # Parse Fixed Header
        packet_type, flags, remaining_length, fixed_header_length = parse_fixed_header(data)
        print(
            f"Fixed Header: Packet Type={packet_type}, Flags={flags}, Remaining Length={remaining_length}, Fixed Header Length={fixed_header_length}")

        # Validate Fixed Header
        if packet_type != 10:
            raise ValueError(f"Malformed UNSUBSCRIBE packet: Incorrect packet type {packet_type}.")
        if flags != 0b0010:
            raise ValueError(f"Malformed UNSUBSCRIBE packet: Incorrect flags {bin(flags)}.")

        offset = fixed_header_length

        # Read Packet Identifier
        if offset + 2 > len(data):
            raise ValueError("Incomplete UNSUBSCRIBE packet: Unable to read Packet Identifier.")
        packet_id = (data[offset] << 8) | data[offset + 1]
        print(f"Packet Identifier: {packet_id} (Offset: {offset}-{offset + 2})")
        offset += 2

        # Parse Properties
        if offset >= len(data):
            raise ValueError("Malformed UNSUBSCRIBE packet: Missing property length field.")

        property_length, property_length_size = parse_variable_byte_integer(data[offset:])
        print(f"Property Length: {property_length} (Size: {property_length_size})")
        offset += property_length_size

        # Skip Properties (if any)
        if offset + property_length > len(data):
            raise ValueError("Malformed UNSUBSCRIBE packet: Property length exceeds remaining data.")
        offset += property_length

        # Parse Topics
        topics = []
        while offset < len(data):
            print(f"Parsing topic at Offset: {offset}, Remaining Data (hex): {data[offset:].hex()}")
            if offset + 2 > len(data):
                raise ValueError("Incomplete UNSUBSCRIBE packet: Unable to read Topic Name Length.")

            # Read Topic Name Length
            topic_length = (data[offset] << 8) | data[offset + 1]
            print(f"Topic Name Length: {topic_length} (Offset: {offset}-{offset + 2})")
            offset += 2

            if topic_length == 0:
                raise ValueError("Empty topic name is not allowed.")

            if offset + topic_length > len(data):
                raise ValueError("Incomplete UNSUBSCRIBE packet: Topic Name exceeds remaining data.")

            # Read Topic Name
            topic_name = data[offset:offset + topic_length].decode('utf-8')
            print(f"Topic Name: {topic_name} (Offset: {offset}-{offset + topic_length})")
            offset += topic_length
            topics.append(topic_name)

        # Verify Remaining Length Alignment
        parsed_length = offset - fixed_header_length
        if parsed_length != remaining_length:
            raise ValueError(f"Remaining Length mismatch: Parsed {parsed_length}, Expected {remaining_length}.")

        return packet_id, topics
    except Exception as e:
        print(f"Error parsing UNSUBSCRIBE packet: {e}")
        raise


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
