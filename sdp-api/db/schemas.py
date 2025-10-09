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
    bank: Optional[str] = None

# Schema per la lettura dei dati di un utente dall'API
# Non deve mai includere la password!
class UserInDB(UserBase):
    id: int
    role: str
    is_active: bool
    permissions: List[str]
    bank: Optional[str] = None

    class Config:
        from_attributes = True

# --- Schemi per l'Autenticazione ---

# Schema per la risposta del token
class Token(BaseModel):
    access_token: str
    token_type: str

# Schema per i dati contenuti nel payload del token JWT
class TokenData(BaseModel):
    username: str | None = None
    bank: str | None = None   # <-- aggiunto

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None
    bank: Optional[str] = None

class PasswordChange(BaseModel):
    new_password: str

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

# --- Schemi per Reportistica ---

class ReportisticaBase(BaseModel):
    banca: Optional[str] = None
    anno: Optional[int] = None
    settimana: Optional[int] = None
    nome_file: str
    package: Optional[str] = None
    finalita: Optional[str] = None
    disponibilita_server: Optional[bool] = False
    ultima_modifica: Optional[datetime] = None
    dettagli: Optional[str] = None

class ReportisticaCreate(ReportisticaBase):
    pass

class ReportisticaUpdate(BaseModel):
    banca: Optional[str] = None
    anno: Optional[int] = None
    settimana: Optional[int] = None
    nome_file: Optional[str] = None
    package: Optional[str] = None
    finalita: Optional[str] = None
    disponibilita_server: Optional[bool] = None
    ultima_modifica: Optional[datetime] = None
    dettagli: Optional[str] = None

class ReportisticaInDB(ReportisticaBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Schemi per RepoUpdateInfo ---

class RepoUpdateInfoBase(BaseModel):
    settimana: Optional[int] = None
    anno: Optional[int] = None
    semaforo: Optional[int] = None
    bank: Optional[str] = None

class RepoUpdateInfoCreate(RepoUpdateInfoBase):
    pass

class RepoUpdateInfoUpdate(BaseModel):
    settimana: Optional[int] = None
    anno: Optional[int] = None
    semaforo: Optional[int] = None
    bank: Optional[str] = None

class RepoUpdateInfoInDB(RepoUpdateInfoBase):
    id: int

    class Config:
        from_attributes = True
        
class BankBase(BaseModel):
    label: str
    ini_path: Optional[str] = None


class BankCreate(BankBase):
    pass  


class BankUpdate(BaseModel):
    label: str


class BankResponse(BankBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True  # ✅ compatibile con Pydantic v2


class BanksListResponse(BaseModel):
    banks: list[BankResponse]
    current_bank: str | None