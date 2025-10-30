"""
Script per trovare il database usato dall'app e applicare la migration
"""
import os
import sqlite3

# Possibili percorsi del database
possible_paths = [
    r"C:\Users\EmanueleDeFeo\Documents\Projects\Synapse-Data-Platform\Nuova cartella\App\Dashboard\sdp.db",
    r"C:\Users\ate0405\Documents\Projects\Synapse-Data-Platform\Nuova cartella\App\Dashboard\sdp.db",
    r"C:\Users\ate0405\AppData\Local\sdp\sdp.db",
    r"C:\Users\EmanueleDeFeo\AppData\Local\sdp\sdp.db",
]

def migrate_database(db_path):
    """Aggiunge le colonne mancanti a repo_update_info"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check schema corrente
        cursor.execute("PRAGMA table_info(repo_update_info)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"\n[DB: {db_path}]")
        print(f"Colonne esistenti: {existing_columns}")

        # Aggiungi log_key se manca
        if 'log_key' not in existing_columns:
            print("  Aggiungendo log_key...")
            cursor.execute("ALTER TABLE repo_update_info ADD COLUMN log_key TEXT")
            print("  [OK] log_key aggiunta")
        else:
            print("  [OK] log_key già presente")

        # Aggiungi details se manca
        if 'details' not in existing_columns:
            print("  Aggiungendo details...")
            cursor.execute("ALTER TABLE repo_update_info ADD COLUMN details TEXT")
            print("  [OK] details aggiunta")
        else:
            print("  [OK] details già presente")

        conn.commit()
        conn.close()
        print(f"  [SUCCESS] Migration completata!\n")
        return True

    except Exception as e:
        print(f"  [ERROR] {e}\n")
        return False

# Trova tutti i database esistenti e applica la migration
print("Cerco database sdp.db...")
found_count = 0

for path in possible_paths:
    if os.path.exists(path):
        found_count += 1
        print(f"\n[FOUND] {path}")
        migrate_database(path)

# Cerca anche in altre posizioni
import glob
print("\nCerco altri database...")
for pattern in [r"C:\Users\*\**\sdp.db"]:
    for db_path in glob.glob(pattern, recursive=True):
        if db_path not in possible_paths:
            found_count += 1
            print(f"\n[FOUND] {db_path}")
            migrate_database(db_path)

print(f"\n=== Totale database trovati e migrati: {found_count} ===")
