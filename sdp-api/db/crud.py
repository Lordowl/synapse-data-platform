from sqlalchemy import label
from sqlalchemy.orm import Session
from . import models, schemas
from core.security import get_password_hash
from sqlalchemy.orm.attributes import flag_modified
import secrets
import string

# ------------------ USERS ------------------
def get_user_by_username(db: Session, username: str, bank: str | None = None):
    query = db.query(models.User).filter(models.User.username == username)
    if bank:
        query = query.filter(models.User.bank == bank)
    return query.first()

def get_user_by_email(db: Session, email: str, bank: str | None = None):
    query = db.query(models.User).filter(models.User.email == email)
    if bank:
        query = query.filter(models.User.bank == bank)
    return query.first()

def create_user(db: Session, user: schemas.UserCreate, bank: str | None = None):
    # Genera password casuale se non fornita
    if user.password is None or user.password == "":
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        generated_password = ''.join(secrets.choice(alphabet) for i in range(12))
    else:
        generated_password = user.password

    hashed_password = get_password_hash(generated_password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role,
        permissions=user.permissions,
        bank=bank
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Aggiungi la password generata all'oggetto per poterla restituire
    db_user.generated_password = generated_password if user.password is None or user.password == "" else None

    return db_user

def get_users(db: Session, bank: str | None = None, skip: int = 0, limit: int = 100):
    query = db.query(models.User)
    if bank:
        query = query.filter(models.User.bank == bank)
    return query.offset(skip).limit(limit).all()

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def update_user(db: Session, user_id: int, user_data: schemas.UserUpdate, bank: str | None = None):
    update_data = user_data.model_dump(exclude_unset=True)
    if bank:
        update_data["bank"] = bank

    db.query(models.User).filter(models.User.id == user_id).update(
        values=update_data, synchronize_session=False
    )
    db.commit()
    return get_user(db, user_id)

def delete_user(db: Session, user_id: int):
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    db.delete(db_user)
    db.commit()
    return db_user

# ------------------ FLOW EXECUTION ------------------
def create_execution_log(db: Session, flow_id_str: str, status: str,
                         duration_seconds: int, details: dict, log_key: str,
                         bank: str, anno: int = None, settimana: int = None):
    record = models.FlowExecutionHistory(
        flow_id_str=flow_id_str,
        status=status,
        duration_seconds=duration_seconds,
        details=details,
        log_key=log_key,
        bank=bank,
        anno=anno,
        settimana=settimana
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def create_execution_detail(db: Session, log_key: str, element_id: str,
                            error_lines: list, result: str = "Success",
                            bank: str | None = None, anno: int = None, settimana: int = None):
    detail = models.FlowExecutionDetail(
        log_key=log_key,
        element_id=element_id,
        result=result,
        error_lines="\n".join(error_lines),
        bank=bank,
        anno=anno,
        settimana=settimana
    )
    db.add(detail)
    db.commit()
    db.refresh(detail)
    return detail

def update_execution_log_status(db: Session, log_key: str, status: str):
    record = db.query(models.FlowExecutionHistory).filter(
        models.FlowExecutionHistory.log_key == log_key
    ).first()
    if record:
        record.status = status
        db.commit()
        db.refresh(record)
    return record

def get_flows_by_bank(db: Session, bank: str):
    return db.query(models.FlowExecutionHistory).filter(
        models.FlowExecutionHistory.bank == bank
    ).all()

# ------------------ BANKS ------------------
def get_banks(db: Session):
    return db.query(models.Bank).filter(models.Bank.is_active == True).all()


def create_bank(db: Session, bank: schemas.BankCreate):
    db_bank = models.Bank(label=bank.label)
    db.add(db_bank)
    db.commit()
    db.refresh(db_bank)
    return db_bank

def get_current_bank(db: Session):
    return db.query(models.Bank).filter_by(is_current=True).first()

def set_current_bank(db: Session, bank_label: str):
    db.query(models.Bank).update({models.Bank.is_current: False})
    bank = db.query(models.Bank).filter_by(label=bank_label).first()
    if not bank:
        return None
    bank.is_current = True
    db.commit()
    db.refresh(bank)
    return bank

# --- CRUD operations for Reportistica ---

def get_reportistica_items(db: Session, skip: int = 0, limit: int = 100):
    """Recupera tutti gli elementi di reportistica."""
    return db.query(models.Reportistica).offset(skip).limit(limit).all()

def get_reportistica_by_id(db: Session, reportistica_id: int):
    """Recupera un elemento di reportistica per ID."""
    return db.query(models.Reportistica).filter(models.Reportistica.id == reportistica_id).first()

def get_reportistica_by_nome_file(db: Session, nome_file: str, banca: str):
    """Recupera un elemento di reportistica per nome file e banca.

    Note:
        - La coppia (nome_file, banca) è unica nel database
        - Banca è obbligatoria
        - Confronto case-insensitive per banca
    """
    from sqlalchemy import func

    return db.query(models.Reportistica).filter(
        models.Reportistica.nome_file == nome_file,
        func.lower(models.Reportistica.banca) == func.lower(banca)
    ).first()

def create_reportistica(db: Session, reportistica: schemas.ReportisticaCreate, banca: str):
    """Crea un nuovo elemento di reportistica.

    Args:
        db: Database session
        reportistica: Dati del report (senza banca)
        banca: Banca dell'utente loggato (automatico da current_user.bank)
    """
    # Aggiungi la banca ai dati
    db_reportistica = models.Reportistica(
        **reportistica.model_dump(),
        banca=banca  # ✅ Banca presa dall'utente loggato
    )
    db.add(db_reportistica)
    db.commit()
    db.refresh(db_reportistica)
    return db_reportistica

def update_reportistica(db: Session, reportistica_id: int, reportistica_data: schemas.ReportisticaUpdate):
    """Aggiorna un elemento di reportistica."""
    update_data = reportistica_data.model_dump(exclude_unset=True)

    if not update_data:
        return get_reportistica_by_id(db, reportistica_id)

    db.query(models.Reportistica).filter(models.Reportistica.id == reportistica_id).update(
        values=update_data,
        synchronize_session=False
    )

    db.commit()
    return get_reportistica_by_id(db, reportistica_id)

def delete_reportistica(db: Session, reportistica_id: int):
    """Cancella un elemento di reportistica."""
    db_reportistica = get_reportistica_by_id(db, reportistica_id)
    if not db_reportistica:
        return None
    db.delete(db_reportistica)
    db.commit()
    return db_reportistica
def get_reportistica_by_filters(db: Session, banca: str = None, anno: int = None, settimana: int = None, package: str = None):
    """Recupera elementi di reportistica con filtri, includendo tipo_reportistica dal mapping."""
    from sqlalchemy import func
    from sqlalchemy.orm import aliased

    # Alias per il mapping
    mapping = aliased(models.ReportMapping)

    # Join tra Reportistica e ReportMapping
    query = db.query(
        models.Reportistica,
        mapping.Type_reportisica.label("tipo_reportistica")
    ).outerjoin(
        mapping,
        models.Reportistica.package == mapping.package  # join corretto
    )

    # Applica filtri
    if banca:
        query = query.filter(func.lower(models.Reportistica.banca) == func.lower(banca))
    if anno:
        query = query.filter(models.Reportistica.anno == anno)
    if settimana:
        query = query.filter(models.Reportistica.settimana == settimana)
    if package and package.lower() != "tutti":
        query = query.filter(models.Reportistica.package == package)

    results = query.all()

    # Trasforma in lista di dict già pronta per JSON
    return [
        {**item[0].__dict__, "tipo_reportistica": item[1]}
        for item in results
    ]
# --- CRUD operations for RepoUpdateInfo ---

def get_repo_update_info(db: Session):
    """Recupera l'unica riga di repo_update_info."""
    return db.query(models.RepoUpdateInfo).first()

def get_repo_update_info_by_bank(db: Session, bank: str):
    """Recupera le informazioni di repo_update per una specifica banca."""
    return db.query(models.RepoUpdateInfo).filter(models.RepoUpdateInfo.bank == bank).first()

def create_repo_update_info(db: Session, repo_info: schemas.RepoUpdateInfoCreate):
    """Crea un nuovo record repo_update_info."""
    db_repo_info = models.RepoUpdateInfo(**repo_info.model_dump())
    db.add(db_repo_info)
    db.commit()
    db.refresh(db_repo_info)
    return db_repo_info

def update_repo_update_info(db: Session, repo_info_data: schemas.RepoUpdateInfoUpdate):
    """Aggiorna l'unica riga di repo_update_info."""
    # Trova la prima (e unica) riga
    existing_repo_info = get_repo_update_info(db)

    if not existing_repo_info:
        # Se non esiste, crea una nuova riga
        create_data = schemas.RepoUpdateInfoCreate(**repo_info_data.model_dump(exclude_unset=True))
        return create_repo_update_info(db, create_data)

    # Aggiorna i dati esistenti
    update_data = repo_info_data.model_dump(exclude_unset=True)
    if update_data:
        db.query(models.RepoUpdateInfo).filter(models.RepoUpdateInfo.id == existing_repo_info.id).update(
            values=update_data,
            synchronize_session=False
        )
        db.commit()

    return get_repo_update_info(db)

def update_repo_update_info_by_bank(db: Session, bank: str, repo_info_data: schemas.RepoUpdateInfoUpdate):
    """Aggiorna le informazioni di repo_update per una specifica banca."""
    existing_repo_info = get_repo_update_info_by_bank(db, bank)

    if not existing_repo_info:
        # Se non esiste, crea una nuova riga per questa banca
        create_data = schemas.RepoUpdateInfoCreate(
            **repo_info_data.model_dump(exclude_unset=True),
            bank=bank
        )
        return create_repo_update_info(db, create_data)

    # Aggiorna i dati esistenti
    update_data = repo_info_data.model_dump(exclude_unset=True)
    if update_data:
        db.query(models.RepoUpdateInfo).filter(models.RepoUpdateInfo.bank == bank).update(
            values=update_data,
            synchronize_session=False
        )
        db.commit()

    return get_repo_update_info_by_bank(db, bank)

# ------------------ AUDIT LOG ------------------
def create_audit_log(db: Session, user_id: int | None, action: str, details: dict | None = None, bank: str | None = None):
    record = models.AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        bank=bank
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
