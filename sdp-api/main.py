# my_fastapi_backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importiamo i nostri moduli
from db import models
from db.database import engine
from api import auth, users, tasks

# 1. Creazione delle tabelle del database
# Questa riga dice a SQLAlchemy di creare tutte le tabelle definite
# nei tuoi modelli (come la classe User in db/models.py) nel database
# specificato dal 'engine'. Lo fa solo se le tabelle non esistono già.
try:
    models.Base.metadata.create_all(bind=engine)
    print("Database tables created successfully (if they didn't exist).")
except Exception as e:
    print(f"Error creating database tables: {e}")


# 2. Creazione dell'istanza dell'app FastAPI
app = FastAPI(
    title="My Tauri/React App Backend",
    description="API per la gestione di utenti, permessi e task.",
    version="1.0.0",
)

# 3. Configurazione del CORS (Cross-Origin Resource Sharing)
# Questo è FONDAMENTALE per permettere al frontend di comunicare con il backend.
# Durante lo sviluppo, il frontend (es. http://localhost:3000 o tauri://localhost)
# ha un'"origine" diversa dal backend (http://127.0.0.1:8000).
# Il browser bloccherebbe le richieste per motivi di sicurezza se non lo abilitassimo.

# Per lo sviluppo, possiamo essere permissivi. In produzione, dovresti restringere le origini.
origins = [
    "http://localhost",
    "http://localhost:3000",  # Origine comune per React in sviluppo
    "http://localhost:1420",  # Origine comune per Tauri in sviluppo
    "tauri://localhost",
    "https://tauri.localhost"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Permette a queste origini di fare richieste
    allow_credentials=True, # Permette l'invio di cookie/header di autorizzazione
    allow_methods=["*"],    # Permette tutti i metodi (GET, POST, etc.)
    allow_headers=["*"],    # Permette tutti gli header
)


# 4. Inclusione dei Router
# Qui colleghiamo i file di endpoint che abbiamo creato all'app principale.
# Ogni gruppo di endpoint avrà un prefisso, rendendo l'API più organizzata.
# Esempio: gli endpoint in `auth.router` saranno accessibili sotto /api/v1/auth/...
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")


# 5. Endpoint di Root (opzionale, ma utile per un health check)
@app.get("/api/v1/healthcheck", tags=["Health Check"])
def read_root():
    """Endpoint di base per verificare che l'API sia attiva."""
    return {"status": "ok", "message": "Welcome to the FastAPI Backend!"}