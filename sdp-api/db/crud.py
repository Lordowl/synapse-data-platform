
from sqlalchemy.orm import Session
from . import models, schemas
from core.security import get_password_hash # Importiamo la nostra funzione di hashing

def get_user_by_username(db: Session, username: str):
    """Recupera un utente dal database tramite il suo username."""
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_email(db: Session, email: str):
    """Recupera un utente dal database tramite la sua email."""
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    """Crea un nuovo utente nel database."""
    # Prima di salvare, hashare la password
    hashed_password = get_password_hash(user.password)
    
    # Creiamo un oggetto modello SQLAlchemy usando i dati validati
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password, # Salviamo la password hashata, non quella in chiaro!
        role=user.role
    )
    
    db.add(db_user) # Aggiunge l'oggetto alla sessione
    db.commit()      # Salva le modifiche nel database
    db.refresh(db_user) # Aggiorna l'oggetto db_user con i dati dal DB (es. l'ID generato)
    return db_user
def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()