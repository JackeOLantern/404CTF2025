import csv

def read_i2c_csv(file_path):
    with open(file_path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)  # skip header
        data = [(int(row[0]), int(row[1])) for row in reader]
    return data

def write_filtered_csv(filtered_data, output_path):
    """
    Écrit la séquence filtrée SDA/SCL dans un fichier CSV.
    
    :param filtered_data: liste de tuples [(scl, sda), ...]
    :param output_path: chemin du fichier de sortie CSV
    """
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["scl", "sda"])  # entête
        for scl, sda in filtered_data:
            writer.writerow([scl, sda])


def stable_transitions(data, min_stable=3):
    cleaned = []
    i = 0
    while i < len(data):
        current = data[i]
        count = 1
        while i + count < len(data) and data[i + count] == current:
            count += 1
        if count >= min_stable:
            cleaned.extend([current] * count)
        i += count
    return cleaned

def detect_i2c_messages(data):
    messages = []
    state = "IDLE"
    current_message = []
    scl_last, sda_last = 1, 1

    byte_buffer = []
    bit_buffer = []

    command = "NONE"
    for i, (scl, sda) in enumerate(data):
        if scl == scl_last and sda == sda_last:
            #current_message.append(f"    # [{i}] repeat: {scl}, {sda}  <- {scl_last}, {sda_last}")
            continue# repeat
        #current_message.append(f"[{i}] read: {scl}, {sda}  <- {scl_last}, {sda_last}")
        # Detect START
        if scl == 1 and sda_last == 1 and sda == 0:
            if state != "IDLE":
                current_message.append(f"[{i}] Unexpected START (previous STOP missing?)")
                if byte_buffer:
                    current_message.append(f"[{i}] BYTES: {byte_buffer}")
                    messages.append({"type": "MESSAGE", "data": byte_buffer, "trace": current_message})
            state = "READING"
            current_message = [f"[{i}] START"]
            byte_buffer = []
            bit_buffer = []

        # Detect STOP
        elif scl == 1 and sda_last == 0 and sda == 1:
            if len(bit_buffer) == 9:
                byte = int("".join(str(b) for b in bit_buffer[:8]), 2)
                ack = bit_buffer[8]
                byte_buffer.append(byte)
                current_message.append(f"[{i}] BYTE: 0x{byte:02X}, ACK={ack==0}")
            elif len(bit_buffer) > 0:
                current_message.append(f"[{i}] Incomplete byte ignored (only {len(bit_buffer)} bits)")
            current_message.append(f"[{i}] STOP")
            if byte_buffer:
                current_message.append(f"[{i}] BYTES: {byte_buffer}")
                messages.append({"type": "MESSAGE", "data": byte_buffer, "trace": current_message})
                ### commande 
                if byte_buffer[0] == 0x88 and len(byte_buffer) > 1:
                    if byte_buffer[1] == 0x89:
                        command = "SERIAL"
                        current_message.append(f"[{i}] COMMAND=SERIAL")
                    elif byte_buffer[1] == 0xFD:
                        command = "MESURE"
                        current_message.append(f"[{i}] COMMAND=MESURE")
                    else:
                        command = "NONE"
                ### reponse
                if byte_buffer[0] == 0x89:
                    if command == "SERIAL":
                        serial = decode_serial_number(byte_buffer)
                        current_message.append(f"[{i}] SERIAL: {serial}")
                    elif command == "MESURE":
                        mesure = decode_measurement(byte_buffer)
                        current_message.append(f"[{i}] MESURE: {mesure}")
                    else:
                        current_message.append(f"[{i}] UNKNOWN COMMAND")

            else:
                current_message.append(f"[{i}] No valid bytes detected")
                messages.append({"type": "EMPTY", "data": [], "trace": current_message})
            state = "IDLE"
            bit_buffer = []
            byte_buffer = []

        # Read bits only during active message (after START)
        elif state == "READING":
            scl_rising = scl_last == 0 and scl == 1
            if scl_rising:
                bit_buffer.append(sda)
                #current_message.append(f"[{i}] BIT {sda}")

                if len(bit_buffer) == 9:
                    byte = int("".join(str(b) for b in bit_buffer[:8]), 2)
                    ack = bit_buffer[8]
                    byte_buffer.append(byte)
                    current_message.append(f"[{i}] BYTE: 0x{byte:02X}, ACK={ack==0}")
                    bit_buffer = []

        scl_last, sda_last = scl, sda

    return messages

def crc8_sht(data):
    """
    CRC-8 algorithm used by Sensirion (polynomial 0x31, init 0xFF).
    Accepts a bytes-like object of 2 bytes.
    """
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x31
            else:
                crc <<= 1
            crc &= 0xFF  # Ensure 8-bit result
    return crc


def decode_serial_number(byte_input):
    """
    Decode a serial number from 6 bytes + 2 CRCs (8 bytes total).
    byte_list: list of 8 integers from the I2C reply.
    Returns a tuple (serial_number, is_valid, details)
    """
    if byte_input[0] == 0x89:
        byte_list = byte_input[1:]
    else:
        byte_list = byte_input[1:]
    if len(byte_list) < 6:
        raise ValueError("Not enough data for serial number")

    parts = []
    valid = True
    details = []

    for i in range(0, 6, 3):
        word = byte_list[i:i+2]
        crc = byte_list[i+2]
        calc_crc = crc8_sht(word)
        is_ok = (crc == calc_crc)
        details.append(f"{word[0]:02X}{word[1]:02X} CRC={crc:02X} {'OK' if is_ok else 'FAIL'}")
        valid &= is_ok
        parts.append((word[0] << 8) | word[1])

    serial_hex = ''.join(f"{w:04X}" for w in parts)
    return serial_hex, valid, details


def decode_measurement(byte_input, check_crc=True):
    """
    Décode les 6 octets renvoyés par le capteur après une commande de mesure.
    Format attendu : [T_MSB, T_LSB, T_CRC, RH_MSB, RH_LSB, RH_CRC]
    
    :param byte_list: liste de 6 entiers (octets bruts)
    :param check_crc: True pour vérifier les CRCs
    :return: dict avec température (°C), humidité (%), CRC status
    """
    if byte_input[0] == 0x89:
        byte_list = byte_input[1:]
    else:
        byte_list = byte_input[1:]
    if len(byte_list) < 6:
        raise ValueError("Il faut exactement 6 octets pour décoder la mesure.")
    #temp_raw = (byte_list[0] << 8) | byte_list[1]
    temp_raw = (byte_list[0] << 8) | byte_list[1]
    temp_crc = byte_list[2]
    rh_raw = (byte_list[3] << 8) | byte_list[4]
    rh_crc = byte_list[5]

    temp_crc_ok = (crc8_sht(byte_list[0:2]) == temp_crc)
    rh_crc_ok = (crc8_sht(byte_list[3:5]) == rh_crc)
    ##convertion page 12 spec
    temperature = -45 + 175 * (temp_raw / 65535.0)
    humidity = -6 + 125 * (rh_raw / 65535.0)

    return {
        "temperature_c": round(temperature, 2),
        "temperature_raw": temp_raw,
        "humidity_percent": round(humidity, 2),
        "temp_crc_ok": temp_crc_ok,
        "rh_crc_ok": rh_crc_ok
    }

def main():
    file_path = "challenge.csv"  # Change this to your CSV file path
    data = read_i2c_csv(file_path)
    stable = data #stable_transitions(data)
    write_filtered_csv(stable, "stable.csv")

    messages = detect_i2c_messages(stable)

    for i, msg in enumerate(messages):
        print(f"\n--- Message {i+1} ---")
        for line in msg["trace"]:
            print(line)

if __name__ == "__main__":
    main()