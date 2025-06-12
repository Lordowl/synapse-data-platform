# my_fastapi_backend/core/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from .config import settings  # Importiamo le nostre impostazioni (chiave segreta, etc.)
from db import schemas, models, crud
from db.database import get_db
from sqlalchemy.orm import Session

# 1. Hashing delle Password
# Specifichiamo l'algoritmo di hashing da usare (bcrypt è lo standard)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica che la password in chiaro corrisponda a quella hashata."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Genera l'hash di una password."""
    return pwd_context.hash(password)


# 2. Logica JWT
# Questo oggetto dice a FastAPI "cerca un token nell'header Authorization: Bearer <token>"
# e l'URL a cui il frontend deve fare la richiesta di login è `/auth/token`
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un nuovo token di accesso JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Se non viene specificata una durata, usa un default di 15 minuti
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


# 3. Dependency per ottenere l'utente corrente
# Questa funzione verrà usata come dipendenza negli endpoint protetti.
# Prende il token dalla richiesta, lo valida, e restituisce l'utente dal database.
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decodifica il token usando la nostra chiave segreta
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")  # "sub" è il nome standard per il soggetto del token
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        # Se il token è scaduto o non valido, lancia l'eccezione
        raise credentials_exception
    
    # Ora che abbiamo lo username, cerchiamo l'utente nel database
    user = crud.get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    
    # Se l'utente non è attivo, rifiuta l'accesso
    if not user.is_active:
         raise HTTPException(status_code=400, detail="Inactive user")

    return user

# 4. Dependency per ottenere un utente con privilegi di admin
def get_current_active_admin(current_user: models.User = Depends(get_current_user)):
    """Verifica che l'utente corrente sia un admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user