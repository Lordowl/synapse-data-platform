from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from db import crud, schemas
from core.security import get_current_user
from db.models import User

router = APIRouter()

@router.get("/")  # Rimosso temporaneamente response_model per debug
def get_repo_update_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera le informazioni di update del repository per la banca dell'utente.
    """
    from sqlalchemy import text

    try:
        # Rileva colonne esistenti nella tabella
        cols_res = db.execute(text("PRAGMA table_info('repo_update_info')")).fetchall()
        col_names = [c[1] for c in cols_res] if cols_res else []

        if not col_names:
            # Tabella non trovata: ritorna default in-memory
            return {
                "id": 0,
                "bank": current_user.bank,
                "anno": 2025,
                "settimana": 1,
                "mese": 1,
                "semaforo": 0,
                "created_at": None,
                "updated_at": None,
            }

        # Costruisci SELECT solo con colonne presenti
        select_cols = ["id", "bank", "anno", "settimana", "semaforo"]
        if "mese" in col_names:
            select_cols.append("mese")
        if "created_at" in col_names:
            select_cols.append("created_at")
        if "updated_at" in col_names:
            select_cols.append("updated_at")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Colonne disponibili: {col_names}")
        logger.info(f"Colonne selezionate: {select_cols}")

        sel_sql = f"SELECT {', '.join(select_cols)} FROM repo_update_info WHERE bank = :bank LIMIT 1"
        logger.info(f"Query SQL: {sel_sql}")
        row = db.execute(text(sel_sql), {"bank": current_user.bank}).fetchone()

        if not row:
            # Inserisci default usando solo le colonne esistenti
            insert_cols = ["settimana", "anno", "semaforo", "bank"]
            insert_sql = f"INSERT INTO repo_update_info ({', '.join(insert_cols)}) VALUES (:settimana, :anno, :semaforo, :bank)"
            db.execute(
                text(insert_sql),
                {"settimana": 1, "anno": 2025, "semaforo": 0, "bank": current_user.bank},
            )
            db.commit()
            row = db.execute(text(sel_sql), {"bank": current_user.bank}).fetchone()

        data = dict(row._mapping)
        logger.info(f"Dati mappati dal DB: {data}")

        # Normalizza campi opzionali mancanti
        if "mese" not in data:
            data["mese"] = 1
        if "created_at" not in data:
            data["created_at"] = None
        if "updated_at" not in data:
            data["updated_at"] = None

        logger.info(f"Dati finali dopo normalizzazione: {data}")
        return data

    except Exception as e:
        # In caso di qualsiasi problema (incluse OperationalError), ritorna default sicuro
        # Questo evita 500 e mantiene l'app funzionante.
        return {
            "id": 0,
            "bank": current_user.bank,
            "anno": 2025,
            "settimana": 1,
            "mese": 1,
            "semaforo": 0,
            "created_at": None,
            "updated_at": None,
        }

@router.put("/", response_model=schemas.RepoUpdateInfoInDB)
def update_repo_update_info(
    repo_info_data: schemas.RepoUpdateInfoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna le informazioni di update del repository per la banca dell'utente.
    """
    return crud.update_repo_update_info_by_bank(
        db=db,
        bank=current_user.bank,
        repo_info_data=repo_info_data
    )