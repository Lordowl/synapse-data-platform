
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
def create_execution_log(db: Session, flow_id_str: str, status: str, duration_seconds: int = 0, details: dict = None):
    db_log = models.FlowExecutionHistory(
        flow_id_str=flow_id_str,
        status=status,
        duration_seconds=duration_seconds,
        details=details
    )
    db.add(db_log)
    db.commit()      # <- commit necessario
    db.refresh(db_log)
    return db_log
