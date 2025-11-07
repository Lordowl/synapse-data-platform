import sqlite3
import pandas as pd

# Leggi il file Excel
excel_path = 'C:/Users/EmanueleDeFeo/Documents/Projects/Synapse-Data-Platform/Nuova cartella/App/Dashboard/SPK_CVB mappatura_DEV.xlsx'
df = pd.read_excel(excel_path, sheet_name='Sparkasse power BI')

print("Dati letti dal file Excel:")
print(df.head(20))
print(f"\nColonne: {df.columns.tolist()}")

# Connetti al database
conn = sqlite3.connect('C:/Users/EmanueleDeFeo/Documents/Projects/Synapse-Data-Platform/Nuova cartella/App/Dashboard/sdp.db')
cursor = conn.cursor()

# Verifica i dati attuali in report_mapping
cursor.execute("SELECT Type_reportisica, bank, package, datafactory FROM report_mapping")
rows = cursor.fetchall()
print(f"\n\nDati attuali in report_mapping ({len(rows)} righe):")
for row in rows[:10]:
    print(f"  {row[0]:15} | {row[1]:10} | {row[2]:25} | {row[3]}")

# Aggiorna i valori di datafactory basandoti sui dati Excel
# Cerca la colonna giusta nell'Excel che contiene il datafactory workspace
updates_count = 0

for index, excel_row in df.iterrows():
    # Estrai i valori dall'Excel (adatta i nomi colonne se necessari)
    package = excel_row.get('Package') or excel_row.get('package')
    periodicity = excel_row.get('Periodicità') or excel_row.get('periodicity') or excel_row.get('Periodicita')
    datafactory_ws = excel_row.get('Datafactory') or excel_row.get('datafactory')

    if pd.notna(package) and pd.notna(datafactory_ws) and datafactory_ws != '':
        # Determina Type_reportisica
        type_rep = None
        if pd.notna(periodicity):
            if 'mensile' in str(periodicity).lower():
                type_rep = 'Mensile'
            elif 'settimanale' in str(periodicity).lower():
                type_rep = 'Settimanale'

        # Aggiorna il database
        if type_rep:
            cursor.execute("""
                UPDATE report_mapping
                SET datafactory = ?
                WHERE package = ? AND Type_reportisica = ?
            """, (datafactory_ws, package, type_rep))

            if cursor.rowcount > 0:
                updates_count += cursor.rowcount
                print(f"[UPDATE] {package} ({type_rep}) -> datafactory = {datafactory_ws}")

conn.commit()
print(f"\n\n[OK] Aggiornati {updates_count} record!")

# Verifica finale
cursor.execute("SELECT Type_reportisica, bank, package, datafactory FROM report_mapping WHERE datafactory IS NOT NULL")
rows = cursor.fetchall()
print(f"\n\nRecord con datafactory popolato ({len(rows)} righe):")
for row in rows:
    print(f"  {row[0]:15} | {row[1]:10} | {row[2]:25} | {row[3]}")

conn.close()
