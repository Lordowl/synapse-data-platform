# sdp-api/core/auditing.py

from sqlalchemy.orm import Session
from db import models, schemas

def record_audit_log(
    db: Session,
    user_id: int,
    action: str,
    details: dict = None
):
    """Crea un nuovo record nell'audit log con la banca dell'utente."""
    # Recupera l'utente per ottenere la banca
    user = db.query(models.User).filter(models.User.id == user_id).first()
    bank = user.bank if user else None

    log_entry = schemas.AuditLogCreate(
        user_id=user_id,
        action=action,
        details=details
    )
    db_log = models.AuditLog(**log_entry.model_dump())
    db_log.bank = bank  # Assegna la banca al log
    db.add(db_log)
    # Nota: il commit non viene fatto qui, ma nella funzione che chiama questa helper.