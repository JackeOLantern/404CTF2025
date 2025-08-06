
import pandas as pd

CSV_FILE = "filtered_security_logs.csv"

def analyse_security_events(csv_path):
    df = pd.read_csv(csv_path)

    print("\n=== Résumé des types d'événements ===")
    print(df['Type'].value_counts())

    print("\n=== Connexions suspectes (ID 4624, type RDP ou nom d'utilisateur 'Administrator') ===")
    if 'Details' in df.columns:
        suspicious_logons = df[df['Details'].str.contains('LogonType">10|TargetUserName">Administrator', na=False)]
        print(suspicious_logons)
    else:
        print("⚠️ Colonne 'Details' manquante : impossible d’analyser finement les types de logon.")

    print("\n=== Événements critiques ===")
    critical_ids = ['1102', '4672', '4720', '4726']
    print(df[df['EventID'].astype(str).isin(critical_ids)])

if __name__ == "__main__":
    analyse_security_events(CSV_FILE)
