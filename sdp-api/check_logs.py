import sqlite3

conn = sqlite3.connect('C:/Users/EmanueleDeFeo/Documents/Projects/Synapse-Data-Platform/Nuova cartella/App/Dashboard/sdp.db')
cursor = conn.cursor()
cursor.execute('''SELECT id, bank, publication_type, status, anno, settimana, mese,
                  substr(output, 1, 80), substr(error, 1, 80)
                  FROM publication_logs ORDER BY id DESC LIMIT 5''')
rows = cursor.fetchall()

print('ID | Bank | Type | Status | Anno | Sett | Mese | Output | Error')
print('-' * 200)
for r in rows:
    print(f'{r[0]:2} | {r[1]:12} | {r[2]:12} | {r[3]:8} | {r[4]} | {str(r[5]):4} | {str(r[6]):4} | {str(r[7])[:40]} | {str(r[8])[:60]}')

conn.close()
