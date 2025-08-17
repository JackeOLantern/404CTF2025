def simulate_comparators(VIN, VCC=5.0):
    result = []
    for i in range(15):  # 15 comparateurs avec seuils > 0
        threshold = (15 - i) * VCC / 16
        bit = 1 if VIN > threshold else 0
        result.append(bit)
    
    # Comparateur 16 → compare à GND
    result.append(1 if VIN > 0 else 0)
    return result

def simulate_output_bits(comparator_bits):
    """Simule le code Arduino qui transforme la sortie comparateurs en 4 bits (A3–A0)."""
    value = -1
    for bit in comparator_bits:
        if bit == 1:
            value += 1

    # Extraction des bits A3 à A0
    A_bits = []
    for _ in range(4):
        A_bits.append(value & 1)
        value >>= 1

    #A_bits.reverse()  # Pour afficher dans l'ordre A3 A2 A1 A0
    return A_bits



# Exemple d'utilisation
flag = "404CTF{"
for vin in [2.34, 3.9, 0.47, 0.78, 4.52, 2.96]:
    comparator_out = simulate_comparators(vin)
    #print(f"VIN = {vin:.2f} V → {''.join(map(str, comparator_out))}")

    A_bits = simulate_output_bits(comparator_out)
    print(f"VIN = {vin:.2f} V → comparateurs = {''.join(map(str, comparator_out))} → A3..A0 - D1..D4  = {''.join(map(str, A_bits))}")
    flag += ''.join(map(str, A_bits))
flag += "}"
print ("flag:", flag)