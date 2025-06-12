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
    db: Session = Depends(get_db),
    # --- AGGIUNGIAMO LA SICUREZZA QUI ---
    admin_user: models.User = Security(get_current_active_admin)
):
    """
    Crea un nuovo utente.
    Endpoint accessibile solo agli admin.
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
@router.get("/all", response_model=List[schemas.UserInDB])
def read_all_users(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user: models.User = Security(get_current_active_admin)
):
    """
    Restituisce una lista di tutti gli utenti nel database.
    Accessibile solo agli admin.
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users
@router.put("/{user_id}", response_model=schemas.UserInDB)
def update_user_data(
    user_id: int,
    user_in: schemas.UserUpdate,
    db: Session = Depends(get_db),
    admin_user: models.User = Security(get_current_active_admin)
):
    """
    Aggiorna i dati di un utente (ruolo, permessi, etc.).
    Accessibile solo agli admin.
    """
    user = crud.update_user(db, user_id=user_id, user_data=user_in)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# --- NUOVO ENDPOINT PER CANCELLARE UN UTENTE ---
@router.delete("/{user_id}", response_model=schemas.UserInDB)
def remove_user_data(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Security(get_current_active_admin)
):
    """
    Cancella un utente dal database.
    Accessibile solo agli admin.
    """
    # Non permettere a un admin di cancellare se stesso
    if admin_user.id == user_id:
        raise HTTPException(status_code=400, detail="Admins cannot delete themselves.")

    user = crud.delete_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user