import numpy as np
import matplotlib.pyplot as plt
from itertools import dropwhile
# Lire les fichiers correctement comme float64
d_plus = np.fromfile("USB1_D_plus.raw", dtype=np.float64)
d_neg = np.fromfile("USB1_D_neg.raw", dtype=np.float64)
assert len(d_plus) == len(d_neg), "Les fichiers n'ont pas la même taille."
print("Taille D+ :", len(d_plus))
print("Taille D− :", len(d_neg))

# on cherche 00010010 0x12
DESCRIPTOR_TYPES = {
    0x01: "Device",
    0x02: "Configuration",
    0x03: "String",
    0x04: "Interface",
    0x05: "Endpoint",
}
USB_PID_TYPES = {
    0xE1: "OUT",
    0x69: "IN",
    0x2D: "SOF",
    0xA5: "SETUP",
    0xB4: "OUT",
    0x96: "IN",
    0xC3: "DATA0",
    0x4B: "DATA1",
    0xD2: "PRE/ERR",
    0x87: "ACK",
    0x1B: "NAK",
    0x5A: "STALL"
}
def get_pid_type(pid_hex):
    try:
        pid_val = int(pid_hex, 16)
        return USB_PID_TYPES.get(pid_val, f"Unknown (0x{pid_val:02X})")
    except:
        return "Invalid PID"
def detectPeriod(dataFlow):
    threshold = 30  # ajustable selon amplitude observée
    transitions = []
    for i in range(1, len(dataFlow)):
        delta = dataFlow[i] - dataFlow[i-1]
        if abs(delta) > threshold:
            transitions.append(i)

    # Période estimée entre transitions
    periods = np.diff(transitions)
    # moyenne des 10 premieres
    s = 0
    n =0
    for i in range(10):
        n = n + 1
        s = s + periods[i]
    average = s / n
    print("average:", average, " Periods:", periods[:50])
    return average

def classify(diff):
    if diff > 50:
        return 'J'
    elif diff < -50:
        return 'K'
    elif abs(diff) < 20:
        return 'SE0'
    else:
        return '-'  # flou ou transition


def extract_logical_states(d_diff, threshold=40, transition_window=10):
    trames = []
    states = []
    offest_search=4
    i = 0
    section = 0
    last_state = "IDLE"
    state = "IDLE"
    while i < len(d_diff) - transition_window:
        window = d_diff[i:i+transition_window+offest_search]
        print(f"[{section}] i:({i} -> {i + transition_window})", window)

        #min et max sur la window
        minW = 100
        maxW = -100
        jMin = 0
        jMax = 0
        for j in range(transition_window + offest_search):
            if minW > window[j]:
                minW = window[j]
                jMin = j
            if maxW < window[j]:
                maxW = window[j]
                jMax = j
        print(f"[{section}] min:({jMin}, {minW}) max:({jMax}, {maxW})")
        
        if minW > 50 and state == "IDLE":
            state='IDLE'
            print(f"[{section}] STAY IDLE :({last_state} -> {state})")
        elif maxW > 50 and state == "SE0":
            state='IDLE'
            # next trame
            section = 0
            trames.append(states)
            states=[]
            print(f"[{section}] SE0 to IDLE :({last_state} -> {state})")
            print("\n--------------------------------------------------\n")
        elif maxW - minW < threshold or (maxW < -50) or (minW > 50):
            state = last_state
            print(f"[{section}] stable :({last_state} -> {state})")
        elif maxW - minW > 60:
            deltaI = 0
            if jMin > jMax:
                state = classify(minW)
                deltaI = jMin
            else:
                state = classify(maxW)
                deltaI = jMax
            #if last_state == "IDLE":
            print(f"[{section}] transition :({last_state} -> {state})  i: {i} + {deltaI} - {transition_window}-> {i + deltaI - transition_window}")
            i = i + deltaI - transition_window
            #else:
            #    print(f"[{section}] transition :({last_state} -> {state})")

        else:
            print(f"********************* UNDEFINED TRANSITION")
            
        if (state != "SE0" or last_state != "SE0") and state != 'IDLE' and last_state !="IDLE": #http://esd.cs.ucr.edu/webres/usb11.pdf p 121 1srt bit starts AFTER exit of IDLE state
            states.append(state)#+"_"+str(section))
        last_state = state
        section = section +1
        i += transition_window  # avancer à la prochaine fenêtre
        print("\n\n")
    if len(states) > 0:
        print(" ** STATE incomplet sur trame : ", len(states))
        trames.append(state)
    return trames


def find_sync_with_repeat(states):
    patterns = [
        ['J', 'K', 'J', 'K', 'J', 'K', 'J', 'K', 'K'],
        ['K', 'J', 'K', 'J', 'K', 'J', 'K', 'J', 'J'],
    ]
    
    for i in range(len(states) - 8):  # 9 états => len - 8
        window = states[i:i+9]
        if window in patterns:
            print(f"[✓] SYNC détecté à l'indice {i} : {window}")
            return i + 8, i  # début des données utiles
    print("[✗] Aucun SYNC détecté")
    return None

def find_sync_pattern(nrzi_bits):
    sync_pattern = "00000001"
    bit_str = "".join(nrzi_bits)

    for i in range(len(bit_str) - 7):
        if bit_str[i:i+8] == sync_pattern:
            print(f"[✓] SYNC (00000001) found at bit index {i}")
            return i + 8  # start of actual packet data
    print("[✗] No SYNC pattern found")
    return None


# Bit unstuffing (retire les 0 insérés après 6x 1)
def unstuff(bits):
    result = []
    count = 0
    for b in bits:
        if b == '1':
            count += 1
            result.append(b)
            if count == 6:
                count = 0  # skip next stuffed 0
        else:
            result.append(b)
            count = 0
    return result

# Bits → octets
#def bits_to_bytes(bits):
#    bytes_ = [int("".join(bits[i:i+8]), 2) for i in range(0, len(bits) - 7, 8)]
#    print("[hex] :", " ".join(f"{b:02X}" for b in bytes_))
#    return bytes_
def bits_to_bytes(bits):
    bytes_ = []
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        if len(chunk) < 8:
            print(f"bit incomplet {i} : {bits}")
            break  # ignore chunk incomplet
        byte = int("".join(chunk), 2)
        bytes_.append(byte)
    print("[hex] :", " ".join(f"{b:02X}" for b in bytes_))
    return bytes_

def decode_descriptor(packet):
    if len(packet) < 2:
        return "Trame trop courte"
    try:
        length = int(packet[0], 16)
        dtype = int(packet[1], 16)
        dtype_name = DESCRIPTOR_TYPES.get(dtype, f"Unknown (0x{dtype:02X})")
        return f"Descriptor: {dtype_name}, Length={length}, Raw={packet}"
    except:
        return f"Erreur de parsing: {packet}"

def print_data(packet):
    s=""
    for n in packet:
        c = chr(int(n, 16))
        s = s + c
    print(s)

LIMIT = 500

transition_window = detectPeriod(d_plus)
d_diff = d_plus - d_neg
# 500 970 DATA0 1900 2330 IN 2780 PRE ERR 3300 DATA (missing) 3670 EE CODE 4200
D=970
F=1900
d_plus = d_plus[D:F]
d_neg = d_neg[D:F]
#d_diff = d_diff[D:F]
trames = extract_logical_states(d_diff)
print(trames)
plt.plot(d_plus[:1500], label="D+")
plt.plot(d_neg[:1500], label="D−")
plt.plot(d_diff[:1500], label="D+ - D−")
plt.legend()
#plt.show()

#exit()

if not trames:
    print("Aucun état logique J/K détecté.")
    exit()

decoded = []
for logical_states in trames:    
    print("logical_states : ", logical_states[:LIMIT])

    print("logical_states", logical_states)
    # NRZI decoding : transition = 0, stable = 1
    decoded_bits = []
    last = logical_states[0]
    pos = 1
    for current in logical_states[1:]:
        if current == 'SE0':
            break
        #  In NRZI encoding, a “1” is represented by no change in level and a “0” is represented by a change in level p123
        bit = '1' if current == last else '0' 
        #bit = '0' if current == last else '1'
        decoded_bits.append(bit)
        #print(f"[{pos}] {last}/{current} : {bit}  total: {decoded_bits}")
        last = current
        pos = pos + 1

    sync = find_sync_pattern(decoded_bits)
    print("Bits décodés :", "".join(decoded_bits[:256]), len(decoded_bits), "sync :", sync)
    signifiant_bits = decoded_bits[sync:]

    print("Bits significatifs :", "".join(signifiant_bits[:256]), len(signifiant_bits))

    unstuffed_bits = unstuff(signifiant_bits)
    print("unstuffed_bits décodés :", "".join(unstuffed_bits[:256]), len(unstuffed_bits))



    byte_values = bits_to_bytes(unstuffed_bits)
    hex_array = [f"{byte:02X}" for byte in byte_values]
    decoded.append(hex_array)
    ##decode_descriptor(hex_array)
    
    #print("[byte_values] Début du flux :\n", byte_values[:128])
    # ASCII brut pour inspection manuelle
    #ascii_text = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in byte_values)
    #print("[ASCII] Début du flux :\n", ascii_text[:128])

    # Recherche Device Descriptor : [0x12, 0x01] suivi de 16 octets
    #found = False
    #for i in range(len(byte_values) - 18):
    #    if byte_values[i] == 0x12 and byte_values[i + 1] == 0x01:
    #        desc = byte_values[i:i+18]
    #        print(f"\n[+] Device Descriptor trouvé à l'offset {i}")
    #        print(f"  bDeviceClass : 0x{desc[4]:02x}")
    #        print(f"  idVendor     : 0x{desc[8] + (desc[9] << 8):04x}")
    #        print(f"  idProduct    : 0x{desc[10] + (desc[11] << 8):04x}")
    #        print("  Dump :", [f"{x:02x}" for x in desc])
    #        break
    #else:
    #    print("\n[!] Aucun descripteur de périphérique détecté.")
print("Resultat :")
print(decoded)
i = 0
for frame in decoded:
    if not frame:
        continue
    pid_str = frame[0]
    pid_type = get_pid_type(pid_str)
    print(f"[{i:02}] PID = {pid_str} → {pid_type} | Data: {frame[1:]}")
    i = i+1
    if pid_str in ['C3', '4B']:  # DATA0 or DATA1
        print(decode_descriptor(frame[1:]))
    #print_data(frame[1:])