# sdp-api/api/users.py

from fastapi import APIRouter, Depends, HTTPException, status, Security
from sqlalchemy.orm import Session
from typing import List, Dict

from db import schemas, models, crud
from db import get_db
from core.security import get_current_user, get_current_active_admin
from core.auditing import record_audit_log # Importa la funzione di audit

# Il router è già configurato con prefisso e tag
router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_new_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Security(get_current_active_admin)
):
    """
    Crea un nuovo utente. Se la password non è fornita, ne genera una casuale.
    Endpoint accessibile solo agli admin.
    """
    db_user_by_username = crud.get_user_by_username(db, username=user.username)
    if db_user_by_username:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_user_by_email = crud.get_user_by_email(db, email=user.email)
    if db_user_by_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    created_user = crud.create_user(db=db, user=user)

    # Registra l'azione di creazione nell'audit log
    record_audit_log(
        db=db,
        user_id=admin_user.id,
        action="USER_CREATE",
        details={
            "created_user_id": created_user.id,
            "created_username": created_user.username
        }
    )
    db.commit()

    # Restituisci i dati dell'utente + la password generata se presente
    response = {
        "id": created_user.id,
        "username": created_user.username,
        "email": created_user.email,
        "role": created_user.role,
        "is_active": created_user.is_active,
        "permissions": created_user.permissions
    }

    if hasattr(created_user, 'generated_password') and created_user.generated_password:
        response["generated_password"] = created_user.generated_password

    return response

@router.get("/me", response_model=schemas.UserInDB)
def read_current_user_me(current_user: models.User = Security(get_current_user)):
    """Endpoint protetto. Restituisce i dati dell'utente attualmente loggato."""
    return current_user

@router.get("/admin/dashboard", response_model=Dict)
def read_admin_dashboard(current_admin: models.User = Security(get_current_active_admin)):
    """Endpoint protetto accessibile solo agli admin."""
    return {"message": f"Welcome Admin {current_admin.username}!", "dashboard_data": "Here is your secret data."}

@router.get("/all", response_model=List[schemas.UserInDB])
def read_all_users(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
    admin_user: models.User = Security(get_current_active_admin)
):
    """Restituisce una lista di tutti gli utenti nel database."""
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@router.put("/{user_id}", response_model=schemas.UserInDB)
def update_user_data(
    user_id: int,
    user_in: schemas.UserUpdate,
    db: Session = Depends(get_db),
    admin_user: models.User = Security(get_current_active_admin)
):
    """Aggiorna i dati di un utente (ruolo, permessi, etc.)."""
    old_user = crud.get_user(db, user_id)
    if not old_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_role = old_user.role
    old_permissions = old_user.permissions

    updated_user = crud.update_user(db, user_id=user_id, user_data=user_in)

    # Registra l'azione di aggiornamento nell'audit log
    record_audit_log(
        db=db,
        user_id=admin_user.id,
        action="USER_PERMISSIONS_UPDATE",
        details={
            "target_user_id": user_id,
            "target_username": updated_user.username,
            "changes": {
                "role": {"from": old_role, "to": updated_user.role},
                "permissions": {"from": old_permissions, "to": updated_user.permissions}
            }
        }
    )
    db.commit()
    return updated_user

@router.delete("/{user_id}", response_model=schemas.UserInDB)
def remove_user_data(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Security(get_current_active_admin)
):
    """Cancella un utente dal database."""
    if admin_user.id == user_id:
        raise HTTPException(status_code=400, detail="Admins cannot delete themselves.")

    user_to_delete = crud.get_user(db, user_id=user_id)
    if not user_to_delete:
        raise HTTPException(status_code=404, detail="User not found")

    deleted_user_username = user_to_delete.username # Salva il nome prima di cancellare
    crud.delete_user(db, user_id=user_id)

    # Registra l'azione di cancellazione nell'audit log
    record_audit_log(
        db=db,
        user_id=admin_user.id,
        action="USER_DELETE",
        details={
            "deleted_user_id": user_id,
            "deleted_username": deleted_user_username
        }
    )
    db.commit()
    return user_to_delete