# Define database functions directly in __init__.py for PyInstaller compatibility
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

engine = None
SessionLocal = None
Base = declarative_base()

def init_db(db_url: str = None):
    global engine, SessionLocal
    if db_url is None:
        from core.config import settings
        db_url = settings.DATABASE_URL
        if not db_url:
            raise RuntimeError("Nessun database configurato. Imposta DATABASE_URL nel file .env")

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # CREA TUTTE LE TABELLE DEFINITE NEI MODELS
    Base.metadata.create_all(bind=engine)

def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database non inizializzato. Chiama prima init_db(path).")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_optional():
    """Versione opzionale di get_db che restituisce None se il DB non è inizializzato"""
    if SessionLocal is None:
        yield None
    else:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

__all__ = ['engine', 'SessionLocal', 'Base', 'init_db', 'get_db', 'get_db_optional']
