from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import logging
import os
import json
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

# ----------------------- FOLDER UPDATE -----------------------
@router.post("/folder/update")
async def update_folder_path(data: FolderUpdate, user: dict = Depends(get_current_user)):
    folder = data.folder_path
    try:
        # --- 1. Path obbligatori da controllare ---
        ingestion_ps1 = os.path.join(folder, "App", "Ingestion", "ingestion.ps1")
        banks_file = os.path.join(folder, "App", "Ingestion", "banks_default.json")
        logging.info(f"[Settings] Folder ricevuto: {folder}")
        logging.info(f"[Settings] Controllo files obbligatori: {ingestion_ps1}, {banks_file}")
        required_paths = [ingestion_ps1, banks_file]
        missing = [p for p in required_paths if not os.path.exists(p)]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Percorsi obbligatori mancanti: {missing}"
            )

        logging.info(f"[Settings] Tutti i path obbligatori trovati in {folder}")

        # --- 2. Verifica tutti i .ini dal JSON ---
        with open(banks_file, "r", encoding="utf-8") as f:
            banks_data = json.load(f)

        ini_paths = [os.path.join(folder, "App", "Ingestion", bank["ini_path"]) for bank in banks_data]
        missing_ini = [p for p in ini_paths if not os.path.exists(p)]
        if missing_ini:
            raise HTTPException(
                status_code=400,
                detail=f"Mancano i seguenti file .ini: {missing_ini}"
            )

        logging.info(f"[Settings] Tutti i file .ini delle banche presenti: {ini_paths}")

        # --- 3. Path del DB ---
        db_path = os.path.join(folder, "App", "Dashboard", "sdp.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        new_db_url = f"sqlite:///{db_path}"

        if not config_manager.update_setting("DATABASE_URL", new_db_url):
            raise HTTPException(status_code=500, detail="Impossibile aggiornare DATABASE_URL")
        logging.info(f"[Settings] DATABASE_URL aggiornata: {new_db_url}")

        if not config_manager.update_setting("SETTINGS_PATH", folder):
            raise HTTPException(status_code=500, detail="Impossibile aggiornare SETTINGS_PATH")
        logging.info(f"[Settings] SETTINGS_PATH aggiornata: {folder}")

        # --- 4. Ricrea engine SQLAlchemy e tabelle ---
        database.engine = create_engine(new_db_url, connect_args={"check_same_thread": False})
        database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
        models.Base.metadata.create_all(bind=database.engine)

        # --- 5. Crea admin se non presente ---
        db = database.SessionLocal()
        try:
            admin_user = crud.get_user_by_username(db, username="admin")
            if not admin_user:
                logging.info(f"--- Creazione utente admin di default (admin/admin) ---")
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
            "ini_files": ini_paths,
            "note": "Database creato e configurazioni aggiornate."
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Errore nell'aggiornamento folder_path: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Errore interno")

# ----------------------- FOLDER CURRENT -----------------------
@router.get("/folder/current")
async def get_current_folder(user: dict = Depends(get_current_user)):
    try:
        db_url = config_manager.get_setting("DATABASE_URL")
        if not db_url:
            raise HTTPException(status_code=404, detail="Nessun folder salvato")

        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            folder_path = os.path.dirname(os.path.dirname(db_path))
        else:
            folder_path = None

        return {"folder_path": folder_path}
    except Exception as e:
        logging.error(f"Errore recupero folder corrente: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Errore interno")

# ----------------------- FOLDER INI -----------------------
@router.get("/folder/ini")
async def read_ini(user: dict = Depends(get_current_user)):
    try:
        db_url = config_manager.get_setting("DATABASE_URL")
        if not db_url:
            raise HTTPException(status_code=404, detail="DATABASE_URL non configurato")

        db_path = db_url.replace("sqlite:///", "")
        folder_path = os.path.dirname(os.path.dirname(db_path))

        # --- Leggi JSON banche ---
        banks_json_path = os.path.join(folder_path, "Ingestion", "banks_default.json")
        if not os.path.exists(banks_json_path):
            raise HTTPException(status_code=404, detail=f"File banks_default.json non trovato: {banks_json_path}")

        import json
        with open(banks_json_path, "r", encoding="utf-8") as f:
            banks_data = json.load(f)

        # --- Leggi tutti gli INI ---
        import configparser
        ini_contents = {}
        for bank in banks_data:
            ini_path = os.path.join(folder_path, "Ingestion", bank["ini_path"])
            if os.path.exists(ini_path):
                config = configparser.ConfigParser(allow_no_value=True)
                config.read(ini_path, encoding="utf-8")

                def expand_env_vars(d):
                    return {k: os.path.expandvars(v) if v is not None else None for k, v in d.items()}

                bank_ini = {"DEFAULT": expand_env_vars(config.defaults())}
                for section in config.sections():
                    bank_ini[section] = expand_env_vars(dict(config[section]))
                ini_contents[bank["value"]] = {"ini_path": ini_path, "data": bank_ini}
            else:
                ini_contents[bank["value"]] = {"ini_path": ini_path, "data": None}

        return {"inis": ini_contents}

    except Exception as e:
        logging.error(f"Errore lettura INI: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Errore lettura INI: {e}")