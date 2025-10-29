"""
Migration: Add log_key and details columns to repo_update_info table

This migration adds the missing columns that the SQLAlchemy model expects
but are not present in the database.
"""

import sqlite3
import sys
from pathlib import Path

# Database path
DB_PATH = r"C:\Users\EmanueleDeFeo\Documents\Projects\Synapse-Data-Platform\Nuova cartella\App\Dashboard\sdp.db"

def run_migration():
    """Add missing columns to repo_update_info table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check current schema
        cursor.execute("PRAGMA table_info(repo_update_info)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"Existing columns: {existing_columns}")

        # Add log_key column if not exists
        if 'log_key' not in existing_columns:
            print("Adding log_key column...")
            cursor.execute("""
                ALTER TABLE repo_update_info
                ADD COLUMN log_key TEXT
            """)
            print("[OK] log_key column added")
        else:
            print("[OK] log_key column already exists")

        # Add details column if not exists
        if 'details' not in existing_columns:
            print("Adding details column...")
            cursor.execute("""
                ALTER TABLE repo_update_info
                ADD COLUMN details TEXT
            """)
            print("[OK] details column added")
        else:
            print("[OK] details column already exists")

        # Commit changes
        conn.commit()

        # Verify final schema
        cursor.execute("PRAGMA table_info(repo_update_info)")
        final_columns = [row[1] for row in cursor.fetchall()]
        print(f"\nFinal schema: {final_columns}")

        conn.close()
        print("\n[SUCCESS] Migration completed successfully!")
        return True

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
