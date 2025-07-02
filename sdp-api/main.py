# main.py
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from db import models, crud, schemas
from db.database import engine, SessionLocal
from api import auth, users, tasks, audit, flows
from core.config import settings, config_manager  # Importa le impostazioni

import sys
import subprocess
import os
import requests
import logging
from importlib.metadata import version, PackageNotFoundError
import uvicorn

# Il logging è già configurato in config.py
GITHUB_REPO_API = f"https://api.github.com/repos/{settings.github_repo}/releases/latest"

def get_latest_version():
    try:
        r = requests.get(GITHUB_REPO_API)
        r.raise_for_status()
        data = r.json()
        return data["tag_name"]
    except Exception as e:
        logging.error(f"[Updater] Errore nel recupero versione: {e}", exc_info=True)
        return None

def get_current_version():
    try:
        pkg_version = version("sdp-api")
        logging.debug(f"Versione corrente del pacchetto: {pkg_version}")
        return pkg_version
    except PackageNotFoundError:
        logging.warning("Pacchetto sdp-api non trovato. Probabilmente in fase di sviluppo.")
        return "0.0.0-dev"
    except Exception as e:
        logging.error(f"[Updater] Errore nel recupero versione locale: {e}", exc_info=True)
        return "0.0.0"

def upgrade_package(asset_url):
    try:
        logging.info(f"[Updater] Aggiornamento pacchetto da: {asset_url}")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", asset_url, "--force-reinstall", "--no-deps"
        ])
        logging.info("[Updater] Aggiornamento completato. Riavvio necessario...")
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
    logging.info(f"[Updater] Versione attuale: {current}, ultima versione: {latest}")

    if latest is not None and current is not None and latest != current:
        logging.info("[Updater] Trovata nuova versione.")
        try:
            response = requests.get(GITHUB_REPO_API)
            response.raise_for_status()
            release_data = response.json()
            asset_url = None
            for asset in release_data.get("assets", []):
                if asset["name"].endswith((".whl", ".tar.gz")):
                    asset_url = asset["browser_download_url"]
                    break
            if asset_url:
                if upgrade_package(asset_url):
                    print("Uscita per riavvio...")
                    os._exit(1)
                else:
                    logging.error("Aggiornamento fallito.")
            else:
                logging.warning("Nessun asset wheel o tar.gz trovato nella release.")
        except Exception as e:
            logging.error(f"Errore durante la richiesta all'API GitHub: {e}", exc_info=True)
    else:
        logging.info("[Updater] Nessun aggiornamento disponibile.")

models.Base.metadata.create_all(bind=engine)

def create_default_admin_if_not_exists():
    db = SessionLocal()
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
            logging.info("--- Utente admin di default creato con successo. ---")
        else:
            logging.info("--- Utente admin già presente. Nessuna azione richiesta. ---")
    finally:
        db.close()

# Definisci l'app FastAPI
app = FastAPI(
    title="Synapse Data Platform API",
    description="API per la Synapse Data Platform.",
    version="1.0.0",
)

# Usa le impostazioni CORS dal file di configurazione
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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
api_router.include_router(tasks.router)

app.include_router(api_router, prefix="/api/v1")

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome! Navigate to /docs for the API documentation."}

@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    return {"status": "ok"}

@app.get("/config", tags=["Config"])
def get_config_info():
    """Endpoint per ottenere informazioni sulla configurazione"""
    return {
        "config_file": str(config_manager.get_config_path()),
        "version": get_current_version(),
        "auto_update_enabled": settings.auto_update_check
    }

def main():
    """Entry point per il comando sdp-api"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Synapse Data Platform API Server')
    parser.add_argument('--host', default=settings.host, help='Host to bind to')
    parser.add_argument('--port', type=int, default=settings.port, help='Port to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    parser.add_argument('--no-update-check', action='store_true', help='Skip update check')
    parser.add_argument('--config', action='store_true', help='Show config file location')
    parser.add_argument('--regenerate-secret', action='store_true', help='Regenerate SECRET_KEY')
    
    args = parser.parse_args()
    
    # Gestisci comandi speciali
    if args.config:
        print(f"[CONFIG] File di configurazione: {config_manager.get_config_path()}")
        print(f"[VERSION] Versione: {get_current_version()}")
        return
        
    if args.regenerate_secret:
        new_secret = config_manager.regenerate_secret_key()
        if new_secret:
            print(f"[SECRET] Nuova SECRET_KEY generata: {new_secret}")
            print("[WARNING] Riavviare l'applicazione per applicare le modifiche")
        return
    
    # Mostra informazioni di avvio
    print(f"[STARTUP] Synapse Data Platform API v{get_current_version()}")
    print(f"[CONFIG] Configurazione: {config_manager.get_config_path()}")
    
    # Esegui il controllo aggiornamenti se abilitato
    if not args.no_update_check and settings.auto_update_check:
        check_and_update()
    
    models.Base.metadata.create_all(bind=engine)
    create_default_admin_if_not_exists()
    
    if args.reload:
        uvicorn.run("main:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()