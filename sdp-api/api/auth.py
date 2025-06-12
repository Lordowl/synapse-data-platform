# my_fastapi_backend/api/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from db import crud
from db.database import get_db
from core import security
from core.config import settings
from db import schemas

# Creiamo un router. Possiamo dargli un prefisso e dei "tag" per la documentazione.
router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Autentica l'utente e restituisce un token di accesso.
    OAuth2PasswordRequestForm è una classe speciale che riceve i dati
    in formato 'form-data' (username e password).
    """
    # 1. Cerca l'utente nel database
    user = crud.get_user_by_username(db, username=form_data.username)
    
    # 2. Se l'utente non esiste o la password è sbagliata, restituisci un errore
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 3. Se le credenziali sono corrette, crea il token JWT
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        # Il "subject" del token sarà lo username dell'utente
        data={"sub": user.username}, 
        expires_delta=access_token_expires
    )
    
    # 4. Restituisci il token al client
    return {"access_token": access_token, "token_type": "bearer"}