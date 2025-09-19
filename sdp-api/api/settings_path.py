from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import logging
import os
import configparser

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import config_manager
from db import database, models, crud, schemas

router = APIRouter(tags=["Settings"])

# Modello per ricevere il folder_path
class FolderUpdate(BaseModel):
    folder_path: str

# OAuth2 dummy auth
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    return {"username": "admin"}





@router.post("/folder/update")
async def update_folder_path(data: FolderUpdate, user: dict = Depends(get_current_user)):
    folder = data.folder_path
    try:
        # --- 1. Path obbligatori da controllare ---
        required_paths = [
            os.path.join(folder, "App", "Ingestion", "ingestion.ps1"),
            os.path.join(folder, "App", "Ingestion", "log_SPK"),
            os.path.join(folder, "App", "Ingestion", "main_ingestion_SPK.ini")
        ]

        # --- 2. Verifica esistenza ---
        missing = [p for p in required_paths if not os.path.exists(p)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Percorsi mancanti: {missing}. "
                       f"Devi predisporre correttamente la cartella prima di procedere."
            )

        logging.info(f"[Settings] Tutti i path obbligatori trovati in {folder}")

        # --- 3. Path del DB ---
        db_path = os.path.join(folder, "App", "Dashboard", "sdp.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        new_db_url = f"sqlite:///{db_path}"
        if not config_manager.update_setting("DATABASE_URL", new_db_url):
            raise HTTPException(status_code=500, detail="Impossibile aggiornare DATABASE_URL")

        logging.info(f"[Settings] DATABASE_URL aggiornata: {new_db_url}")

# --- 4. Verifica esistenza INI main_ingestion_SPK.ini ---
        ini_path = os.path.join(folder, "App", "Ingestion", "main_ingestion_SPK.ini")
        if os.path.exists(ini_path):
            logging.info(f"[Settings] INI trovato: {ini_path}")
        else:
            logging.warning(f"[Settings] INI non trovato: {ini_path}")

        # --- 5. Ricrea engine SQLAlchemy ---
        database.engine = create_engine(new_db_url, connect_args={"check_same_thread": False})
        database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
        models.Base.metadata.create_all(bind=database.engine)

        # --- 6. Crea admin se non presente ---
        db = database.SessionLocal()
        try:
            admin_user = crud.get_user_by_username(db, username="admin")
            if not admin_user:
                logging.info("--- Creazione utente admin di default (admin/admin) ---")
                default_admin_data = schemas.UserCreate(
                    username="admin",
                    password="admin",
                    email="admin@example.com",
                    role="admin",
                    permissions=[]
                )
                crud.create_user(db, user=default_admin_data)
        finally:
            db.close()

        logging.info(f"[Settings] Utente {user['username']} ha aggiornato folder, DB e file Ingestion")

        return {
            "status": "success",
            "database_url": new_db_url,
            "ini_file": ini_path,
            "note": "Database creato e configurazioni aggiornate."
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Errore nell'aggiornamento folder_path: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Errore interno")
