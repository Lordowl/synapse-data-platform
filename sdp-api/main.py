# sdp-api/main.py

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

# Importa i moduli del nostro progetto
from db import models
from db.database import engine
from api import auth, users, tasks, audit, flows

# Questo comando crea le tabelle nel database (se non esistono già)
# quando l'applicazione si avvia. Includerà la nuova tabella 'audit_logs'.
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Synapse Data Platform API",
    description="API per la Synapse Data Platform.",
    version="1.0.0",
)

# Configurazione CORS per permettere al frontend di comunicare
origins = [
    "http://localhost:1420",
    "tauri://localhost",
    "https://tauri.localhost" 
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

