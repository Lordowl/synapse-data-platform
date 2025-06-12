# my_fastapi_backend/api/users.py

from fastapi import APIRouter, Depends, HTTPException, status, Security
from sqlalchemy.orm import Session
from typing import List, Dict # Assicurati di importare List e Dict

from db import schemas, models, crud
from db.database import get_db
from core.security import get_current_user, get_current_active_admin

# Il prefisso e i tag sono già qui, ottimo!
router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=schemas.UserInDB, status_code=status.HTTP_201_CREATED)
def create_new_user(
    user: schemas.UserCreate, 
    db: Session = Depends(get_db)
):
    """
    Crea un nuovo utente. Questo endpoint è pubblico.
    """
    db_user_by_username = crud.get_user_by_username(db, username=user.username)
    if db_user_by_username:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    db_user_by_email = crud.get_user_by_email(db, email=user.email)
    if db_user_by_email:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    return crud.create_user(db=db, user=user)


@router.get("/me", response_model=schemas.UserInDB)
def read_users_me(
    # Uso Security per la UI di Swagger, come abbiamo discusso
    current_user: models.User = Security(get_current_user)
):
    """
    Endpoint protetto. Restituisce i dati dell'utente attualmente loggato.
    """
    return current_user


@router.get("/admin/dashboard", response_model=Dict)
def read_admin_dashboard(
    # Uso Security per la UI di Swagger
    current_admin: models.User = Security(get_current_active_admin)
):
    """
    Endpoint protetto accessibile solo agli admin.
    """
    return {
        "message": f"Welcome Admin {current_admin.username}!",
        "dashboard_data": "Here is your secret data."
    }

# ===================================================================
# ---         AGGIUNGI QUESTO BLOCCO DI CODICE ALLA FINE          ---
# ===================================================================
@router.get("/", response_model=List[schemas.UserInDB])
def read_all_users(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db),
    # Questa dependency protegge l'endpoint e si assicura che solo un admin possa chiamarlo
    admin_user: models.User = Security(get_current_active_admin)
):
    """
    Restituisce una lista di tutti gli utenti nel database.
    
    Questo endpoint è accessibile solo agli utenti con il ruolo 'admin'.
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users
# ===================================================================