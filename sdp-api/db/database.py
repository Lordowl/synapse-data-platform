# my_fastapi_backend/db/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Il percorso del nostro file di database SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./database.db"

# Creiamo il "motore" di SQLAlchemy
engine = create_engine(
    # connect_args è necessario solo per SQLite per permettere l'uso in un'app multi-thread come FastAPI
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Ogni istanza di SessionLocal sarà una sessione di database.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Questa classe Base sarà la base per tutti i nostri modelli ORM
Base = declarative_base()

# Dependency per gli endpoint API: apre una sessione, la fornisce alla richiesta e la chiude alla fine.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()