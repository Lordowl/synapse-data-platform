# my_fastapi_backend/db/schemas.py
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional,List

# --- Schemi per l'Utente ---

# Proprietà di base condivise da tutti gli schemi utente
class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None

# Schema per la creazione di un nuovo utente (dall'API)
# Eredita da UserBase e aggiunge la password
class UserCreate(UserBase):
    password: Optional[str] = None 
    role: str = "user"
    permissions: Optional[List[str]] = []
# Schema per la lettura dei dati di un utente dall'API
# Non deve mai includere la password!
class UserInDB(UserBase):
    id: int
    role: str
    is_active: bool
    permissions: List[str] # Aggiungiamo il campo alla risposta

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

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None

class AuditLogBase(BaseModel):
    action: str
    details: Optional[dict] = None

class AuditLogCreate(AuditLogBase):
    user_id: Optional[int] = None

class AuditLogInDB(AuditLogBase):
    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None # Campo extra che aggiungeremo per comodità

    class Config:
        from_attributes = True