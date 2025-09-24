# main.py
import os
import sys
import subprocess
import logging
from importlib.metadata import version, PackageNotFoundError
import uvicorn
import requests
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import PlainTextResponse
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from db import models, crud, schemas
from db.database import init_db, get_db
from api import auth, users, tasks, audit, flows, settings_path
from core.config import settings, config_manager
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
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
        logging.error(f"[Updater] Errore nel recupero versione locale: {e}", exc_info=True)
        return "0.0.0"

def upgrade_package(asset_url):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", asset_url, "--force-reinstall", "--no-deps"])
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
            logging.error(f"[Updater] Errore durante richiesta GitHub: {e}", exc_info=True)

# ----------------- Funzioni database ----------------- #
def create_default_admin_if_not_exists():
    db = get_db().__next__()
    try:
        admin_user = crud.get_user_by_username(db, username="admin")
        if not admin_user:
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

# ----------------- FastAPI app ----------------- #
app = FastAPI(
    title="Synapse Data Platform API",
    description="API per la Synapse Data Platform.",
    version="1.0.0",
)
class IgnoreHMRMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.headers.get("x-vite-dev-server"):
            return PlainTextResponse("Ignored HMR request", status_code=204)
        if request.method == "OPTIONS":
            return PlainTextResponse("OK", status_code=204)
        return await call_next(request)
app.add_middleware(IgnoreHMRMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:3000",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router)
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(flows.router, prefix="/flows", tags=["Flows"])
api_router.include_router(settings_path.router)
app.include_router(api_router, prefix="/api/v1")

# ----------------- Eventi di startup ----------------- #
@app.on_event("startup")
def startup_event():
    db_url = settings.DATABASE_URL
    if not db_url:
        logging.warning("[STARTUP] Nessun DATABASE_URL configurato. Attendo /folder/update.")
        return

    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        base_folder = os.path.dirname(os.path.dirname(db_path))  # fino a .../App

        # Percorsi richiesti
        ingestion_ps1 = os.path.join(base_folder, "Ingestion", "ingestion.ps1")
        log_folder = os.path.join(base_folder, "Ingestion", "log_SPK")
        ini_file = os.path.join(base_folder, "Ingestion", "main_ingestion_SPK.ini")

        required_paths = [ingestion_ps1, log_folder, ini_file]

        # Se mancano file/cartelle → fermati
        if not all(os.path.exists(p) for p in required_paths):
            logging.warning("[STARTUP] Alberatura incompleta. Attendo /folder/update.")
            return

        # Se manca il DB → ricrealo
        if not os.path.exists(db_path):
            logging.info(f"[STARTUP] DB non trovato, ricreo in {db_path}")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            open(db_path, "a").close()

    try:
        init_db(db_url)
        create_default_admin_if_not_exists()
        print(f"[STARTUP] Database inizializzato: {db_url}")
    except Exception as e:
        logging.error(f"[STARTUP] Errore nell'inizializzazione del DB: {e}", exc_info=True)


# ----------------- Endpoints generali ----------------- #
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome! Navigate to /docs for the API documentation."}

@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    return {"status": "ok"}

@app.get("/config", tags=["Config"])
def get_config_info():
    return {
        "config_file": str(config_manager.get_config_path()),
        "version": get_current_version(),
        "auto_update_enabled": settings.auto_update_check
    }

# ----------------- Main CLI ----------------- #
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Synapse Data Platform API Server')
    parser.add_argument('--host', default=settings.host)
    parser.add_argument('--port', type=int, default=settings.port)
    parser.add_argument('--reload', action='store_true')
    parser.add_argument('--no-update-check', action='store_true')
    parser.add_argument('--config', action='store_true')
    parser.add_argument('--regenerate-secret', action='store_true')
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
