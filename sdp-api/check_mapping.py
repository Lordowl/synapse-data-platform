import sqlite3

conn = sqlite3.connect('C:/Users/EmanueleDeFeo/Documents/Projects/Synapse-Data-Platform/Nuova cartella/App/Dashboard/sdp.db')
cursor = conn.cursor()

# 1. Vedi i package mensili in report_mapping
print("=== REPORT MAPPING (Mensile) ===")
cursor.execute('''
    SELECT package, ws_precheck, ws_production, bank, Type_reportisica
    FROM report_mapping
    WHERE Type_reportisica = "Mensile" AND bank = "Sparkasse"
''')
packages = cursor.fetchall()
for p in packages:
    print(f"Package: {p[0]}, WS_Precheck: {p[1]}, WS_Prod: {p[2]}, Bank: {p[3]}, Type: {p[4]}")

print("\n=== PUBLICATION LOGS (Precheck) ===")
# 2. Vedi i log di precheck per questi package
cursor.execute('''
    SELECT id, packages, publication_type, status, anno, settimana, mese,
           substr(output, 1, 40), substr(error, 1, 40), timestamp
    FROM publication_logs
    WHERE bank = "Sparkasse" AND publication_type = "precheck"
    ORDER BY timestamp DESC
    LIMIT 5
''')
logs = cursor.fetchall()
for log in logs:
    print(f"ID: {log[0]}, Packages: {log[1]}, Type: {log[2]}, Status: {log[3]}")
    print(f"  Anno: {log[4]}, Sett: {log[5]}, Mese: {log[6]}")
    print(f"  Output: {log[7]}, Error: {log[8]}")
    print(f"  Timestamp: {log[9]}\n")

conn.close()
