
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from . import models, schemas
from core.security import get_password_hash # Importiamo la nostra funzione di hashing

def get_user_by_username(db: Session, username: str):
    """Recupera un utente dal database tramite il suo username."""
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_email(db: Session, email: str):
    """Recupera un utente dal database tramite la sua email."""
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username, 
        email=user.email, 
        hashed_password=hashed_password,
        role=user.role,
        permissions=user.permissions # Aggiungiamo questa riga
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def update_user(db: Session, user_id: int, user_data: schemas.UserUpdate):
    """
    Aggiorna i dati di un utente usando un approccio di UPDATE esplicito.
    """
    # Rimuoviamo 'None' dai dati per non sovrascrivere campi non inviati
    update_data = user_data.model_dump(exclude_unset=True)

    if not update_data:
        # Se non ci sono dati da aggiornare, restituiamo l'utente così com'è
        return get_user(db, user_id)
    
    # --- AGGIUNGIAMO DEI PRINT PER UN DEBUG CHIARO ---
    print(f"--- ESEGUENDO UPDATE ESPLICITO SUL DB PER L'UTENTE ID: {user_id} ---")
    print(f"Dati da salvare: {update_data}")
    # ---------------------------------------------
    
    # Eseguiamo l'UPDATE direttamente sulla tabella
    db.query(models.User).filter(models.User.id == user_id).update(
        values=update_data, 
        synchronize_session=False # Importante per non creare conflitti
    )
    
    db.commit()

    # Dopo il commit, dobbiamo ricaricare l'utente per ottenere i dati aggiornati
    updated_user = get_user(db, user_id)

    # --- ALTRO PRINT PER VERIFICARE ---
    print(f"Dati letti dal DB dopo il commit: {updated_user.permissions if updated_user else 'UTENTE NON TROVATO'}")
    print("----------------------------------------------------------\n")

    return updated_user

def delete_user(db: Session, user_id: int):
    """Cancella un utente."""
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    db.delete(db_user)
    db.commit()
    return db_user

# --- CRUD operations for Reportistica ---

def get_reportistica_items(db: Session, skip: int = 0, limit: int = 100):
    """Recupera tutti gli elementi di reportistica."""
    return db.query(models.Reportistica).offset(skip).limit(limit).all()

def get_reportistica_by_id(db: Session, reportistica_id: int):
    """Recupera un elemento di reportistica per ID."""
    return db.query(models.Reportistica).filter(models.Reportistica.id == reportistica_id).first()

def get_reportistica_by_nome_file(db: Session, nome_file: str):
    """Recupera un elemento di reportistica per nome file."""
    return db.query(models.Reportistica).filter(models.Reportistica.nome_file == nome_file).first()

def create_reportistica(db: Session, reportistica: schemas.ReportisticaCreate):
    """Crea un nuovo elemento di reportistica."""
    db_reportistica = models.Reportistica(**reportistica.model_dump())
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
    """Recupera elementi di reportistica con filtri."""
    query = db.query(models.Reportistica)

    if banca:
        query = query.filter(models.Reportistica.banca == banca)
    if anno:
        query = query.filter(models.Reportistica.anno == anno)
    if settimana:
        query = query.filter(models.Reportistica.settimana == settimana)
    if package:
        query = query.filter(models.Reportistica.package == package)

    return query.all()

# --- CRUD operations for RepoUpdateInfo ---

def get_repo_update_info(db: Session):
    """Recupera l'unica riga di repo_update_info."""
    return db.query(models.RepoUpdateInfo).first()

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