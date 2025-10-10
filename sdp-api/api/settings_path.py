from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import logging
import os
import json
import configparser
import subprocess
import platform
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import config_manager
from core.security import get_current_user
from db import database, models, crud, schemas
from db.models import User

router = APIRouter(tags=["Settings"])

# Modello per ricevere il folder_path
class FolderUpdate(BaseModel):
    folder_path: str

# Modello per ricevere il percorso del file da aprire
class OpenFileRequest(BaseModel):
    file_path: str

# Modello per aprire il log di un flow
class OpenLogRequest(BaseModel):
    log_key: str
    bank: str

# ----------------------- FOLDER UPDATE -----------------------
@router.post("/folder/update")
async def update_folder_path(data: FolderUpdate):
    """Endpoint pubblico per configurare il folder iniziale (non richiede autenticazione)"""
    folder = data.folder_path
    try:
        # --- 1. Normalizza il percorso ---
        # Se il path finisce con App\Ingestion, rimuovilo per ottenere la base
        if folder.endswith(os.path.join("App", "Ingestion")):
            folder = folder[:-len(os.path.join("App", "Ingestion"))].rstrip(os.sep)
        elif folder.endswith("App/Ingestion"):
            folder = folder[:-len("App/Ingestion")].rstrip("/")

        logging.info(f"[Settings] Folder base normalizzato: {folder}")

        # --- 2. Path obbligatori da controllare ---
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

        # --- 3. Verifica tutti i .ini dal JSON ---
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

        # --- 4. Path del DB ---
        db_path = os.path.join(folder, "App", "Dashboard", "sdp.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        new_db_url = f"sqlite:///{db_path}"

        if not config_manager.update_setting("DATABASE_URL", new_db_url):
            raise HTTPException(status_code=500, detail="Impossibile aggiornare DATABASE_URL")
        logging.info(f"[Settings] DATABASE_URL aggiornata: {new_db_url}")

        if not config_manager.update_setting("SETTINGS_PATH", folder):
            raise HTTPException(status_code=500, detail="Impossibile aggiornare SETTINGS_PATH")
        logging.info(f"[Settings] SETTINGS_PATH aggiornata: {folder}")

        # --- 5. Ricrea engine SQLAlchemy e tabelle ---
        database.engine = create_engine(new_db_url, connect_args={"check_same_thread": False})
        database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
        models.Base.metadata.create_all(bind=database.engine)

        # --- 6. Inizializza banche e admin in un'unica sessione ---
        db = database.SessionLocal()
        try:
            # Inserisci banche nel database
            for bank_info in banks_data:
                exists = db.query(models.Bank).filter_by(label=bank_info["label"]).first()
                if not exists:
                    new_bank = models.Bank(
                        label=bank_info["label"],
                        ini_path=bank_info.get("ini_path"),
                        is_active=True,
                        is_current=False
                    )
                    db.add(new_bank)
                    logging.info(f"[Settings] Banca '{bank_info['label']}' aggiunta al database")

            # Commit delle banche prima di creare gli admin
            db.commit()
            logging.info(f"[Settings] {len(banks_data)} banca/e inizializzata/e nel database")

            # Crea admin per ogni banca
            for bank_info in banks_data:
                bank_label = bank_info["label"]
                username = f"admin_{bank_label.lower()}"
                email = f"admin@{bank_label.lower()}.example.com"

                # Controllo sia username che email
                admin_user = crud.get_user_by_username(db, username=username)
                if not admin_user:
                    admin_user = crud.get_user_by_email(db, email=email)

                if not admin_user:
                    logging.info(f"[Settings] Creazione utente admin per banca '{bank_label}' (username: {username}, password: admin)")
                    default_admin_data = schemas.UserCreate(
                        username=username,
                        password="admin",
                        email=email,
                        role="admin",
                        permissions=[],
                    )
                    crud.create_user(db, user=default_admin_data, bank=bank_label)
                    logging.info(f"[Settings] Admin creato per la banca '{bank_label}'")
                else:
                    logging.info(f"[Settings] Admin già presente per la banca '{bank_label}'")

            # Commit finale
            db.commit()
        except Exception as e:
            db.rollback()
            logging.error(f"[Settings] Errore durante inizializzazione banche/admin: {e}")
            raise
        finally:
            db.close()

        logging.info(f"[Settings] Folder, DB e file Ingestion aggiornati")

        # Prepara la lista degli admin creati per la risposta
        admin_accounts = [
            {
                "bank": bank_info["label"],
                "username": f"admin_{bank_info['label'].lower()}",
                "password": "admin"
            }
            for bank_info in banks_data
        ]

        return {
            "status": "success",
            "database_url": new_db_url,
            "ini_files": ini_paths,
            "banks": [bank_info["label"] for bank_info in banks_data],
            "admin_accounts": admin_accounts,
            "note": f"Database creato con {len(banks_data)} banca/e configurata/e. Account admin creati per ogni banca (password: admin)."
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Errore nell'aggiornamento folder_path: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Errore interno")

# ----------------------- FOLDER CURRENT -----------------------
@router.get("/folder/current")
async def get_current_folder():
    """Endpoint pubblico per ottenere il folder corrente senza autenticazione"""
    try:
        db_url = config_manager.get_setting("DATABASE_URL")
        if not db_url:
            return {"folder_path": None}

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
async def read_ini(current_user: User = Depends(get_current_user)):
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
                ini_contents[bank["label"]] = {"ini_path": ini_path, "data": bank_ini}
            else:
                ini_contents[bank["label"]] = {"ini_path": ini_path, "data": None}

        return {"inis": ini_contents}

    except Exception as e:
        logging.error(f"Errore lettura INI: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Errore lettura INI: {e}")

# ----------------------- FOLDER INI PATH -----------------------
@router.get("/folder/ini-path")
async def get_ini_path(bank: str, current_user: User = Depends(get_current_user)):
    """
    Restituisce il percorso del file INI e del file metadati per la banca specificata.
    """
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

        with open(banks_json_path, "r", encoding="utf-8") as f:
            banks_data = json.load(f)

        # Trova la banca richiesta
        bank_info = next((b for b in banks_data if b["label"] == bank), None)
        if not bank_info:
            raise HTTPException(status_code=404, detail=f"Banca '{bank}' non trovata")

        ini_path = os.path.join(folder_path, "Ingestion", bank_info["ini_path"])
        if not os.path.exists(ini_path):
            raise HTTPException(status_code=404, detail=f"File INI non trovato: {ini_path}")

        # Leggi il file INI per ottenere il percorso del file metadati
        config = configparser.ConfigParser(allow_no_value=True)
        config.read(ini_path, encoding="utf-8")

        metadata_path = config.get("DEFAULT", "filemetadati", fallback=None)
        if metadata_path:
            metadata_path = os.path.expandvars(metadata_path)

        return {
            "ini_path": ini_path,
            "metadata_path": metadata_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Errore recupero percorso INI: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Errore recupero percorso INI: {e}")

# ----------------------- OPEN FILE -----------------------
@router.post("/folder/open-file")
async def open_file(data: OpenFileRequest, current_user: User = Depends(get_current_user)):
    """
    Apre un file con l'applicazione predefinita del sistema operativo.
    """
    try:
        file_path = data.file_path

        # Verifica che il file esista
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File non trovato: {file_path}")

        # Determina il sistema operativo e usa il comando appropriato
        system = platform.system()

        if system == "Windows":
            os.startfile(file_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", file_path], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", file_path], check=True)
        else:
            raise HTTPException(status_code=500, detail=f"Sistema operativo non supportato: {system}")

        logging.info(f"File aperto con successo: {file_path}")
        return {"status": "success", "message": f"File aperto: {file_path}"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Errore nell'apertura del file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Errore nell'apertura del file: {e}")

# ----------------------- OPEN LOG FILE -----------------------
@router.post("/folder/open-log")
async def open_log_file(data: OpenLogRequest, current_user: User = Depends(get_current_user)):
    """
    Apre il file di log di un flow dato il log_key e la banca.
    """
    try:
        log_key = data.log_key
        bank = data.bank

        db_url = config_manager.get_setting("DATABASE_URL")
        if not db_url:
            raise HTTPException(status_code=404, detail="DATABASE_URL non configurato")

        db_path = db_url.replace("sqlite:///", "")
        folder_path = os.path.dirname(os.path.dirname(db_path))

        # Leggi il file INI per ottenere il template del filelog
        banks_json_path = os.path.join(folder_path, "Ingestion", "banks_default.json")
        if not os.path.exists(banks_json_path):
            raise HTTPException(status_code=404, detail=f"File banks_default.json non trovato")

        with open(banks_json_path, "r", encoding="utf-8") as f:
            banks_data = json.load(f)

        bank_info = next((b for b in banks_data if b["label"] == bank), None)
        if not bank_info:
            raise HTTPException(status_code=404, detail=f"Banca '{bank}' non trovata")

        ini_path = os.path.join(folder_path, "Ingestion", bank_info["ini_path"])
        if not os.path.exists(ini_path):
            raise HTTPException(status_code=404, detail=f"File INI non trovato: {ini_path}")

        # Leggi il template del filelog dal file INI
        config = configparser.ConfigParser(allow_no_value=True)
        config.read(ini_path, encoding="utf-8")
        filelog_template = config.get("DEFAULT", "filelog", fallback=None)

        if not filelog_template:
            raise HTTPException(status_code=404, detail="Template filelog non trovato nel file INI")

        # Estrai la cartella dal template (es. "log_SPK" da "log_SPK\${now}_...")
        log_folder_name = filelog_template.split("\\")[0].split("/")[0] if "\\" in filelog_template or "/" in filelog_template else "log"
        log_folder = os.path.join(folder_path, "Ingestion", log_folder_name)

        if not os.path.exists(log_folder):
            raise HTTPException(status_code=404, detail=f"Cartella log non trovata: {log_folder}")

        # Cerca il file di log con pattern *_{log_key}.log
        import glob
        log_pattern = os.path.join(log_folder, f"*_{log_key}.log")
        log_files = glob.glob(log_pattern)

        if not log_files:
            raise HTTPException(status_code=404, detail=f"File di log non trovato per log_key: {log_key}")

        log_file_path = log_files[0]  # Prende il primo match

        # Apre il file
        system = platform.system()
        if system == "Windows":
            os.startfile(log_file_path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", log_file_path], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", log_file_path], check=True)
        else:
            raise HTTPException(status_code=500, detail=f"Sistema operativo non supportato: {system}")

        logging.info(f"File di log aperto con successo: {log_file_path}")
        return {"status": "success", "message": f"File di log aperto: {log_file_path}"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Errore nell'apertura del file di log: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Errore nell'apertura del file di log: {e}")