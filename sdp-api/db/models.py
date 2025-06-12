from sqlalchemy import Boolean, Column, Integer, String
from .database import Base

class User(Base):
    # Nome della tabella nel database
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    # Aggiungiamo un campo "role" per la gestione dei permessi
    role = Column(String, default="user")  # Esempi: 'user', 'admin'
    is_active = Column(Boolean, default=True)