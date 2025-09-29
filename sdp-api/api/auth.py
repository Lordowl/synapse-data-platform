from fastapi import APIRouter, Depends, HTTPException, status , Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from db import crud, schemas, models
from db.database import get_db
from core import security
from core.config import settings
from core.auditing import record_audit_log

router = APIRouter(tags=["Auth"])

# Estendiamo il form per includere la banca
class OAuth2PasswordRequestFormWithBank(OAuth2PasswordRequestForm):
    bank: str = None


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    username: str = Form(...),
    password: str = Form(...),
    bank: str = Form(...),
    db: Session = Depends(get_db)
):
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank must be specified"
        )

    # Recupera l'utente filtrando per username e banca
    user = crud.get_user_by_username(db, username=username, bank=bank)
    if not user or not security.verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username, password, or bank",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Registra login nell'audit log
    details = {"bank": bank}
    record_audit_log(db, user_id=user.id, action="USER_LOGIN", details=details)
    db.commit()

    # Crea il token includendo la banca
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.username, "bank": bank},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}