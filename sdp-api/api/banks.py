from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import crud, schemas
from db.database import get_db, get_db_optional
from db import models
from db.schemas import BankCreate, BankResponse, BanksListResponse

router = APIRouter(prefix="/banks", tags=["Banks"])

@router.get("/available", response_model=schemas.BanksListResponse)
def get_available_banks(db: Session = Depends(get_db_optional)):
    """Endpoint pubblico per ottenere le banche disponibili"""
    if db is None:
        # Database non ancora inizializzato
        return {"banks": [], "current_bank": None}

    banks = crud.get_banks(db)
    current = crud.get_current_bank(db)
    current_bank = current.label if current else None
    return {"banks": banks, "current_bank": current_bank}

@router.post("/update")
def update_bank(bank: schemas.BankUpdate, db: Session = Depends(get_db)):
    updated_bank = crud.set_current_bank(db, bank.label)
    if not updated_bank:
        raise HTTPException(status_code=404, detail="Banca non trovata")
    return {"message": f"Banca aggiornata a {updated_bank.label}"}

@router.post("/add")
def add_bank(bank: BankCreate, db: Session = Depends(get_db)):
    new_bank = models.Bank(
        label=bank.label,
        ini_path=bank.ini_path
    )
    db.add(new_bank)
    db.commit()
    db.refresh(new_bank)
    return new_bank