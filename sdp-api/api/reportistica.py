from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from db import get_db
from db import crud, schemas
from core.security import get_current_user
from db.models import User

router = APIRouter()

@router.get("/", response_model=List[schemas.ReportisticaInDB])
def get_reportistica_items(
    skip: int = 0,
    limit: int = 100,
    banca: Optional[str] = Query(None, description="Filtra per banca"),
    anno: Optional[int] = Query(None, description="Filtra per anno"),
    settimana: Optional[int] = Query(None, description="Filtra per settimana"),
    package: Optional[str] = Query(None, description="Filtra per package"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera tutti gli elementi di reportistica con filtri opzionali.
    """
    if banca or anno or settimana or package:
        # Usa filtri se specificati
        items = crud.get_reportistica_by_filters(
            db=db,
            banca=banca,
            anno=anno,
            settimana=settimana,
            package=package
        )
    else:
        # Recupera tutti gli elementi
        items = crud.get_reportistica_items(db=db, skip=skip, limit=limit)

    return items

@router.get("/{reportistica_id}", response_model=schemas.ReportisticaInDB)
def get_reportistica_item(
    reportistica_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera un elemento di reportistica specifico per ID.
    """
    item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")
    return item

@router.post("/", response_model=schemas.ReportisticaInDB)
def create_reportistica_item(
    reportistica: schemas.ReportisticaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un nuovo elemento di reportistica.
    """
    # Verifica che il nome file non esista già
    existing_item = crud.get_reportistica_by_nome_file(db=db, nome_file=reportistica.nome_file)
    if existing_item:
        raise HTTPException(status_code=400, detail="Un elemento con questo nome file esiste già")

    return crud.create_reportistica(db=db, reportistica=reportistica)

@router.put("/{reportistica_id}", response_model=schemas.ReportisticaInDB)
def update_reportistica_item(
    reportistica_id: int,
    reportistica_data: schemas.ReportisticaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna un elemento di reportistica esistente.
    """
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # Se il nome file viene cambiato, verifica che non esista già
    if reportistica_data.nome_file and reportistica_data.nome_file != existing_item.nome_file:
        existing_with_name = crud.get_reportistica_by_nome_file(db=db, nome_file=reportistica_data.nome_file)
        if existing_with_name:
            raise HTTPException(status_code=400, detail="Un elemento con questo nome file esiste già")

    return crud.update_reportistica(db=db, reportistica_id=reportistica_id, reportistica_data=reportistica_data)

@router.delete("/{reportistica_id}")
def delete_reportistica_item(
    reportistica_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Elimina un elemento di reportistica.
    """
    item = crud.delete_reportistica(db=db, reportistica_id=reportistica_id)
    if not item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    return {"message": "Elemento reportistica eliminato con successo"}

@router.patch("/{reportistica_id}/disponibilita", response_model=schemas.ReportisticaInDB)
def toggle_disponibilita_server(
    reportistica_id: int,
    disponibilita: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna solo lo stato di disponibilità server per un elemento.
    """
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    update_data = schemas.ReportisticaUpdate(disponibilita_server=disponibilita)
    return crud.update_reportistica(db=db, reportistica_id=reportistica_id, reportistica_data=update_data)