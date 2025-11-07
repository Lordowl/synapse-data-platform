import sqlite3

conn = sqlite3.connect('C:/Users/EmanueleDeFeo/Documents/Projects/Synapse-Data-Platform/Nuova cartella/App/Dashboard/sdp.db')
cursor = conn.cursor()
cursor.execute('''SELECT id, error FROM publication_logs WHERE id = 9''')
row = cursor.fetchone()

if row:
    print(f'ID: {row[0]}')
    print(f'Error: {row[1]}')

conn.close()
