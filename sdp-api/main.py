# sdp-api/main.py

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

# Importa i moduli del nostro progetto
from db import models,crud
from db.database import engine , SessionLocal
from api import auth, users, tasks, audit, flows

import sys
import subprocess
import os
import requests
from fastapi import FastAPI

GITHUB_REPO_API = "https://api.github.com/repos/Lordowl//synapse-data-platform/releases/latest"

def get_latest_version():
    try:
        r = requests.get(GITHUB_REPO_API)
        r.raise_for_status()
        data = r.json()
        return data["tag_name"]
    except Exception as e:
        print(f"[Updater] Errore nel recupero versione: {e}")
        return None

def get_current_version():
    try:
        import tuo_modulo
        return tuo_modulo.__version__
    except Exception as e:
        print(f"[Updater] Errore nel recupero versione locale: {e}")
        return None

def upgrade_package():
    print("[Updater] Aggiornamento pacchetto...")
    subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--upgrade",
    f"git+https://github.com/tuo_user/tuo_repo.git@{latest_version}#subdirectory=sdp-api"
])
    print("[Updater] Aggiornamento completato, riavvio server...")
    # Riavvia il processo python corrente con gli stessi argomenti
    os.execv(sys.executable, [sys.executable] + sys.argv)

def check_and_update():
    latest = get_latest_version()
    current = get_current_version()
    print(f"[Updater] Versione attuale: {current}, ultima versione: {latest}")
    if latest is not None and current is not None and latest != current:
        upgrade_package()

# Controlla e aggiorna prima di avviare FastAPI
check_and_update()
# Questo comando crea le tabelle nel database (se non esistono già)
# quando l'applicazione si avvia. Includerà la nuova tabella 'audit_logs'.
models.Base.metadata.create_all(bind=engine)
def create_default_admin_if_not_exists():
    db = SessionLocal() # Crea una sessione di DB
    try:
        # Controlla se esiste già un utente con username 'admin'
        admin_user = crud.get_user_by_username(db, username="admin")
        if not admin_user:
            print("--- Creazione utente admin di default (admin/admin) ---")
            default_admin_data = schemas.UserCreate(
                username="admin",
                password="admin", # Usa una password semplice per il default
                email="admin@example.com",
                role="admin",
                permissions=[]
            )
            crud.create_user(db, user=default_admin_data)
            print("--- Utente admin di default creato con successo. ---")
        else:
            print("--- Utente admin già presente. Nessuna azione richiesta. ---")
    finally:
        db.close()
create_default_admin_if_not_exists() # Chiudi sempre la sessione
app = FastAPI(
    title="Synapse Data Platform API",
    description="API per la Synapse Data Platform.",
    version="1.0.0",
)

# Configurazione CORS per permettere al frontend di comunicare
origins = [
    "*",
    "http://localhost:1420",
    "tauri://localhost",
    "https://tauri.localhost" ,
    "http://tauri.localhost",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Creiamo un router principale per il versioning con /api/v1
api_router = APIRouter()

# Includiamo i router specifici nel nostro router principale
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router) # users.router ha già il suo prefisso "/users"
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"]) # Includi il nuovo router
api_router.include_router(flows.router, prefix="/flows", tags=["Flows"]) 
api_router.include_router(tasks.router)

# Infine, includiamo il nostro router principale nell'app, con il prefisso globale.
app.include_router(api_router, prefix="/api/v1")

# Endpoint di Root e Health Check
@app.get("/", tags=["Root"])
def read_root():
    """Endpoint di base per un saluto e un link alla documentazione."""
    return {"message": "Welcome! Navigate to /docs for the API documentation."}

@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    """Endpoint semplice per verificare che l'API sia attiva."""
    return {"status": "ok"}

