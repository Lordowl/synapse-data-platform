from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import core config e modulo DB
from core.config import config_manager, settings
from db import database, models, crud, schemas

router = APIRouter(tags=["Settings"])

# Modello per ricevere il folder_path
class FolderUpdate(BaseModel):
    folder_path: str

# Dipendenza per autenticazione (usando OAuth2 Bearer token già presente)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Dummy auth
def get_current_user(token: str = Depends(oauth2_scheme)):
    return {"username": "admin"}

# Endpoint per aggiornare il folder path
@router.post("/folder/update")
async def update_folder_path(data: FolderUpdate, user: dict = Depends(get_current_user)):
    try:
        # Costruisci la nuova URL SQLite
        new_db_url = f"sqlite:///{data.folder_path}/sdp.db"

        # Aggiorna il file di configurazione .env
        updated = config_manager.update_setting("DATABASE_URL", new_db_url)
        if not updated:
            raise HTTPException(status_code=500, detail="Impossibile aggiornare il file di configurazione")

        logging.info(f"[Settings] Impostazione DATABASE_URL aggiornata: {new_db_url}")

        # Ricrea engine e sessionmaker per puntare al nuovo DB
        database.engine = create_engine(new_db_url, connect_args={"check_same_thread": False})
        database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)

        # Ricrea le tabelle se non esistono
        models.Base.metadata.create_all(bind=database.engine)

        # Crea admin di default se non presente
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

        logging.info(f"[Settings] Utente {user['username']} ha aggiornato DATABASE_URL a: {new_db_url}")

        return {
            "status": "success",
            "database_url": new_db_url,
            "note": "Il database è stato aggiornato e l'admin di default è pronto (se mancava)."
        }

    except Exception as e:
        logging.error(f"Errore nell'aggiornamento folder_path: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Errore interno")
