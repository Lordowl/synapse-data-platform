import os
import sys
import subprocess
import logging
import json
from importlib.metadata import version, PackageNotFoundError

import uvicorn
import requests
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Importa moduli del progetto
from db import models, crud
import db.schemas as schemas
# Import database functions from db package (not db.database)
from db import engine, SessionLocal, init_db, get_db
from db.init_banks import init_banks_from_file

# Import init_repo_update with fallback for older compiled versions
try:
    from db.init_repo_update import init_repo_update_from_file
    HAS_REPO_UPDATE_INIT = True
except ImportError:
    HAS_REPO_UPDATE_INIT = False
    init_repo_update_from_file = None
# Import api modules directly for PyInstaller compatibility
import api.auth as auth
import api.users as users
import api.tasks as tasks
import api.audit as audit
import api.flows as flows
import api.reportistica as reportistica
import api.repo_update as repo_update
import api.settings_path as settings_path
import api.banks as banks
from core.config import settings, config_manager

# Logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ----------------- Funzioni aggiornamento ----------------- #
GITHUB_REPO_API = f"https://api.github.com/repos/{settings.github_repo}/releases/latest"


def get_latest_version():
    try:
        r = requests.get(GITHUB_REPO_API)
        r.raise_for_status()
        return r.json()["tag_name"]
    except Exception as e:
        logging.error(f"[Updater] Errore nel recupero versione: {e}", exc_info=True)
        return None


def get_current_version():
    try:
        return version("sdp-api")
    except PackageNotFoundError:
        return "0.0.0-dev"
    except Exception as e:
        logging.error(
            f"[Updater] Errore nel recupero versione locale: {e}", exc_info=True
        )
        return "0.0.0"


def upgrade_package(asset_url):
    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                asset_url,
                "--force-reinstall",
                "--no-deps",
            ]
        )
        logging.info("[Updater] Aggiornamento completato.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"[Updater] Errore durante l'aggiornamento: {e}", exc_info=True)
        return False


def check_and_update():
    if not settings.auto_update_check:
        logging.info("[Updater] Controllo aggiornamenti disabilitato")
        return
    latest = get_latest_version()
    current = get_current_version()
    if latest and current and latest != current:
        try:
            release_data = requests.get(GITHUB_REPO_API).json()
            asset_url = None
            for asset in release_data.get("assets", []):
                if asset["name"].endswith((".whl", ".tar.gz")):
                    asset_url = asset["browser_download_url"]
                    break
            if asset_url:
                upgrade_package(asset_url)
        except Exception as e:
            logging.error(
                f"[Updater] Errore durante richiesta GitHub: {e}", exc_info=True
            )


# ----------------- Funzioni database ----------------- #
def create_default_admin_if_not_exists():
    db = get_db().__next__()
    try:
        for bank in crud.get_banks(db):
            username = f"admin_{bank.label.lower()}"
            email = f"admin@{bank.label.lower()}.example.com"
            
            # Controllo sia username che email
            admin_user = crud.get_user_by_username(db, username=username)
            if not admin_user:
                admin_user = crud.get_user_by_email(db, email=email)
            
            if not admin_user:
                default_admin_data = schemas.UserCreate(
                    username=username,
                    password="admin",
                    email=email,
                    role="admin",
                    permissions=[],
                )
                crud.create_user(db, user=default_admin_data, bank=bank.label)
                logger.info(f"[STARTUP] Admin creato per la banca '{bank.label}'")
            else:
                logger.info(f"[STARTUP] Admin già presente per la banca '{bank.label}'")
    finally:
        db.close()
# ----------------- FastAPI app ----------------- #
app = FastAPI(
    title="Cruscotto Operativo API",
    description="API per il Cruscotto Operativo.",
    version="0.2.29",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:3000",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router)
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(flows.router, prefix="/flows", tags=["Flows"])
api_router.include_router(reportistica.router, prefix="/reportistica", tags=["Reportistica"])
api_router.include_router(repo_update.router, prefix="/repo-update", tags=["RepoUpdate"])
api_router.include_router(settings_path.router)
api_router.include_router(banks.router)

app.include_router(api_router, prefix="/api/v1")


# ----------------- Eventi di startup ----------------- #
@app.on_event("startup")
def startup_event():
    # Setup file di configurazione (copia da install_dir a ~/.sdp-api/ se necessario)
    try:
        from core.config_setup import setup_config_files
        setup_config_files()
    except Exception as e:
        logging.warning(f"[STARTUP] Errore setup config files: {e}")

    # Leggi il file banks_default.json per configurare automaticamente il settings_path
    # Prima cerca in ~/.sdp-api/, altrimenti usa quello nel pacchetto installato
    config_banks_file = os.path.join(os.path.expanduser("~"), ".sdp-api", "banks_default.json")
    if not os.path.exists(config_banks_file):
        config_banks_file = os.path.join(os.path.dirname(__file__), "config", "banks_default.json")

    if os.path.exists(config_banks_file):
        try:
            with open(config_banks_file, "r", encoding="utf-8") as f:
                banks_config = json.load(f)

            # Supporta sia la vecchia struttura (array) che la nuova (oggetto con settings_path)
            if isinstance(banks_config, dict):
                settings_path_from_file = banks_config.get("settings_path")
            else:
                # Vecchia struttura: solo array, nessun settings_path
                settings_path_from_file = None

            if settings_path_from_file and os.path.exists(settings_path_from_file):
                logging.info(f"[STARTUP] Trovato banks_default.json con settings_path: {settings_path_from_file}")

                # Normalizza il percorso
                folder = settings_path_from_file
                if folder.endswith(os.path.join("App", "Ingestion")):
                    folder = folder[:-len(os.path.join("App", "Ingestion"))].rstrip(os.sep)
                elif folder.endswith("App/Ingestion"):
                    folder = folder[:-len("App/Ingestion")].rstrip("/")

                # Verifica i file obbligatori
                ingestion_ps1 = os.path.join(folder, "App", "Ingestion", "ingestion.ps1")
                banks_file = os.path.join(folder, "App", "Ingestion", "banks_default.json")

                if os.path.exists(ingestion_ps1) and os.path.exists(banks_file):
                    # Configura il database e settings path
                    db_path = os.path.join(folder, "App", "Dashboard", "sdp.db")
                    os.makedirs(os.path.dirname(db_path), exist_ok=True)
                    new_db_url = f"sqlite:///{db_path}"

                    config_manager.update_setting("DATABASE_URL", new_db_url)
                    config_manager.update_setting("SETTINGS_PATH", folder)

                    logging.info(f"[STARTUP] Configurazione automatica completata: {folder}")

                    # Ricrea engine SQLAlchemy
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    import db.database as database

                    database.engine = create_engine(new_db_url, connect_args={"check_same_thread": False})
                    database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
                    models.Base.metadata.create_all(bind=database.engine)

                    logging.info(f"[STARTUP] Database configurato: {new_db_url}")
                else:
                    logging.warning(f"[STARTUP] File obbligatori mancanti in {folder}")
            else:
                if settings_path_from_file:
                    logging.warning(f"[STARTUP] settings_path in banks_default.json non valido o inesistente: {settings_path_from_file}")
        except Exception as e:
            logging.warning(f"[STARTUP] Errore durante la lettura di banks_default.json: {e}")

    db_url = settings.DATABASE_URL
    if not db_url:
        logging.warning(
            "[STARTUP] Nessun DATABASE_URL configurato. Modifica app_config.json con il percorso corretto."
        )
        return

    # Inizializza sempre il database engine, anche senza folder structure
    try:
        init_db(db_url)
        logging.info(f"[STARTUP] Database engine inizializzato: {db_url}")
    except Exception as e:
        logging.error(
            f"[STARTUP] Errore nell'inizializzazione del DB: {e}", exc_info=True
        )
        return

    # Controlla la folder structure solo per inizializzare banche e admin
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        base_folder = os.path.dirname(os.path.dirname(db_path))  # fino a .../App

        # Percorsi richiesti
        ingestion_ps1 = os.path.join(base_folder, "Ingestion", "ingestion.ps1")

        # Cerca banks_default.json in ordine di priorità:
        # 1. ~/.sdp-api/banks_default.json (modificabile dall'utente)
        # 2. App/Ingestion/banks_default.json (default installazione)
        config_banks_file = os.path.join(os.path.expanduser("~"), ".sdp-api", "banks_default.json")
        original_banks_file = os.path.join(base_folder, "Ingestion", "banks_default.json")

        if os.path.exists(config_banks_file):
            banks_file = config_banks_file
            logger.info(f"[STARTUP] Usando banks_default.json da config directory: {config_banks_file}")
        elif os.path.exists(original_banks_file):
            banks_file = original_banks_file
            logger.info(f"[STARTUP] Usando banks_default.json da installazione: {original_banks_file}")
        else:
            banks_file = None

        if not os.path.exists(ingestion_ps1) or not banks_file:
            logging.warning(
                "[STARTUP] Alberatura incompleta (script o JSON mancante). Attendo /folder/update."
            )
            logging.warning(
                f"[STARTUP] Mancano i seguenti file: {ingestion_ps1} o banks_default.json. Attendo /folder/update."
            )
            return

        # Leggi tutti i file .ini dal JSON
        with open(banks_file, "r", encoding="utf-8") as f:
            banks_config = json.load(f)

        from core.config import get_banks_from_config
        banks_data = get_banks_from_config(banks_config)

        ini_paths = [
            os.path.join(base_folder, "Ingestion", bank["ini_path"])
            for bank in banks_data
        ]

        # Controlla che tutti i .ini esistano
        if not all(os.path.exists(p) for p in ini_paths):
            missing = [p for p in ini_paths if not os.path.exists(p)]
            logging.warning(
                f"[STARTUP] Mancano i seguenti file .ini: {missing}. Attendo /folder/update."
            )
            return

        # Se manca il DB → ricrealo
        if not os.path.exists(db_path):
            logging.info(f"[STARTUP] DB non trovato, ricreo in {db_path}")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            open(db_path, "a").close()

        try:
            # PRIMA crea le banche (necessario per creare gli admin)
            logger.info(f"[STARTUP] Inizializzazione banche da banks_default.json...")
            init_banks_from_file(banks_data)
            logger.info(f"[STARTUP] Banche inizializzate: {len(banks_data)} entries")

            # POI crea gli admin per ogni banca
            logger.info(f"[STARTUP] Creazione admin per ogni banca...")
            create_default_admin_if_not_exists()
            logger.info(f"[STARTUP] Banche e admin inizializzati correttamente")

            # Inizializza repo_update_info per ogni banca (se disponibile)
            if HAS_REPO_UPDATE_INIT:
                init_repo_update_from_file()
                print(f"[STARTUP] Repo update info inizializzate correttamente")
            else:
                logging.warning("[STARTUP] Modulo init_repo_update non disponibile, skip inizializzazione repo_update_info")
        except Exception as e:
            logging.error(
                f"[STARTUP] Errore nell'inizializzazione banche/admin: {e}", exc_info=True
            )


# ----------------- Endpoints generali ----------------- #
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome! Navigate to /docs for the API documentation."}


@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    return {"status": "ok"}

@app.get("/test-packages", tags=["Test"])
def test_packages():
    """Test endpoint per verificare report_mapping"""
    from db import SessionLocal
    from db import models
    db = SessionLocal()
    try:
        query = db.query(
            models.ReportMapping.package,
            models.ReportMapping.bank
        ).filter(
            models.ReportMapping.Type_reportisica == "Settimanale"
        )
        results = query.all()
        return {
            "count": len(results),
            "packages": [{"package": r[0], "bank": r[1]} for r in results if r[0]]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()

@app.get("/debug-reportistica-table", tags=["Debug"])
def debug_reportistica_table():
    """Endpoint di debug PUBBLICO per verificare se la tabella reportistica esiste"""
    from db import SessionLocal
    from db import models
    import sqlalchemy
    db = SessionLocal()
    try:
        inspector = sqlalchemy.inspect(engine)
        tables = inspector.get_table_names()

        # Verifica se la tabella esiste
        table_exists = "reportistica" in tables

        # Conta elementi se esiste
        count = 0
        sample_data = []
        if table_exists:
            try:
                count = db.query(models.Reportistica).count()
                sample_data = db.query(models.Reportistica).limit(5).all()
                sample_data = [
                    {
                        "id": item.id,
                        "banca": item.banca,
                        "package": item.package,
                        "nome_file": item.nome_file,
                        "anno": item.anno,
                        "settimana": item.settimana,
                        "disponibilita_server": item.disponibilita_server
                    }
                    for item in sample_data
                ]
            except Exception as e:
                return {
                    "table_exists": table_exists,
                    "error_reading_data": str(e),
                    "all_tables": tables
                }

        return {
            "table_exists": table_exists,
            "count": count,
            "sample_data": sample_data,
            "all_tables": tables
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


@app.get("/config", tags=["Config"])
def get_config_info():
    return {
        "config_file": str(config_manager.get_config_path()),
        "version": get_current_version(),
        "auto_update_enabled": settings.auto_update_check,
    }


# ----------------- Main CLI ----------------- #
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Cruscotto Operativo API Server")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--no-update-check", action="store_true")
    parser.add_argument("--config", action="store_true")
    parser.add_argument("--regenerate-secret", action="store_true")
    args = parser.parse_args()

    # Comandi speciali
    if args.config:
        print(f"[CONFIG] File di configurazione: {config_manager.get_config_path()}")
        print(f"[VERSION] Versione: {get_current_version()}")
        return
    if args.regenerate_secret:
        new_secret = config_manager.regenerate_secret_key()
        if new_secret:
            print(f"[SECRET] Nuova SECRET_KEY generata: {new_secret}")
        return

    # Avvio Uvicorn
    if args.reload:
        uvicorn.run("main:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
