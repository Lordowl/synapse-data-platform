# sdp-api/api/audit.py

from fastapi import APIRouter, Depends, Security
from sqlalchemy.orm import Session
from typing import List
from db import models, schemas
from db.database import get_db
from core.security import get_current_active_admin

router = APIRouter()

@router.get("/logs", response_model=List[schemas.AuditLogInDB])
def read_audit_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user: models.User = Security(get_current_active_admin)
):
    """Recupera il registro delle attività. Accessibile solo agli admin."""
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    results = []
    for log in logs:
        log_data = schemas.AuditLogInDB.from_orm(log)
        # Arricchiamo il log con lo username per comodità
        if log.user_id:
            user = db.query(models.User).filter(models.User.id == log.user_id).first()
            if user:
                log_data.username = user.username
        results.append(log_data)
    
    return results