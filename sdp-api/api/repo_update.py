from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from db import crud, schemas
from core.security import get_current_user
from db.models import User

router = APIRouter()

@router.get("/", response_model=schemas.RepoUpdateInfoInDB)
def get_repo_update_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera le informazioni di update del repository per la banca dell'utente.
    """
    # Filtra per banca dell'utente corrente
    repo_info = crud.get_repo_update_info_by_bank(db=db, bank=current_user.bank)

    if not repo_info:
        # Se non esiste, crea una riga di default per questa banca
        default_data = schemas.RepoUpdateInfoCreate(
            anno=2025,
            settimana=1,
            semaforo=0,
            bank=current_user.bank
        )
        repo_info = crud.create_repo_update_info(db=db, repo_info=default_data)

    return repo_info

@router.put("/", response_model=schemas.RepoUpdateInfoInDB)
def update_repo_update_info(
    repo_info_data: schemas.RepoUpdateInfoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna le informazioni di update del repository per la banca dell'utente.
    """
    return crud.update_repo_update_info_by_bank(
        db=db,
        bank=current_user.bank,
        repo_info_data=repo_info_data
    )