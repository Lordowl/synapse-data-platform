# my_fastapi_backend/db/schemas.py

from pydantic import BaseModel, EmailStr
from typing import Optional

# --- Schemi per l'Utente ---

# Proprietà di base condivise da tutti gli schemi utente
class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None

# Schema per la creazione di un nuovo utente (dall'API)
# Eredita da UserBase e aggiunge la password
class UserCreate(UserBase):
    password: str
    role: str = "user"

# Schema per la lettura dei dati di un utente dall'API
# Non deve mai includere la password!
class UserInDB(UserBase):
    id: int
    role: str
    is_active: bool

    # Configurazione per dire a Pydantic di leggere i dati
    # anche se non sono un dizionario (es. un oggetto ORM)
    class Config:
        from_attributes = True

# --- Schemi per l'Autenticazione ---

# Schema per la risposta del token
class Token(BaseModel):
    access_token: str
    token_type: str

# Schema per i dati contenuti nel payload del token JWT
class TokenData(BaseModel):
    username: Optional[str] = None