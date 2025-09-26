from db import models
from db.database import get_db

def init_banks_from_file(banks_data):
    """
    Inizializza le banche nel DB.
    banks_data: lista di dict già letta dal JSON.
    """
    if not banks_data:
        print("[WARN] Nessun dato banche fornito, niente da inizializzare.")
        return

    db = next(get_db())
    try:
        for bank in banks_data:
            exists = db.query(models.Bank).filter_by(value=bank["value"]).first()
            if not exists:
                db.add(models.Bank(**bank))
        db.commit()
    finally:
        db.close()
    print(f"[DB] Banche inizializzate correttamente ({len(banks_data)} entries)")
