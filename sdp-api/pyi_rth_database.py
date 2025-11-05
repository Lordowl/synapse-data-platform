# PyInstaller runtime hook to ensure db module is properly initialized

import sys
import os
import importlib.util

# FIRST: Load core.config to ensure SECRET_KEY is loaded from .env BEFORE anything else
if hasattr(sys, '_MEIPASS'):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# Create core package first
import types
if 'core' not in sys.modules:
    core_module = types.ModuleType('core')
    core_module.__package__ = 'core'
    core_module.__path__ = [os.path.join(base_path, 'core')]
    sys.modules['core'] = core_module

# Load core.config from .env
core_config_file = os.path.join(base_path, 'core', 'config.py')
if os.path.exists(core_config_file):
    print("[RUNTIME HOOK] Pre-loading core.config from .env")
    spec = importlib.util.spec_from_file_location('core.config', core_config_file)
    config_module = importlib.util.module_from_spec(spec)
    sys.modules['core.config'] = config_module
    sys.modules['core'].config = config_module
    spec.loader.exec_module(config_module)
    if hasattr(config_module, 'settings') and hasattr(config_module.settings, 'SECRET_KEY'):
        secret_preview = config_module.settings.SECRET_KEY[:10] + "..." if len(config_module.settings.SECRET_KEY) > 10 else "***"
        print(f"[RUNTIME HOOK] core.config loaded with SECRET_KEY: {secret_preview}")

# core.security will be loaded normally by imports (after db is ready)
# to avoid circular import issues

print("[RUNTIME HOOK] Forcibly loading db package...")

# Create db package first
if 'db' not in sys.modules:
    db_module = types.ModuleType('db')
    db_module.__package__ = 'db'
    db_module.__path__ = [os.path.join(base_path, 'db')]
    sys.modules['db'] = db_module

# Now we can reference db
import db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Add these to the db module
db.engine = None
db.SessionLocal = None
db.Base = declarative_base()

# Create db.database module
db_database_module = types.ModuleType('db.database')
db_database_module.__package__ = 'db'
sys.modules['db.database'] = db_database_module
db.database = db_database_module

# Set Base instance
db.database.Base = db.Base

def init_db(db_url=None):
    import logging
    logger = logging.getLogger(__name__)

    if db_url is None:
        from core.config import settings
        db_url = settings.DATABASE_URL
        if not db_url:
            raise RuntimeError("Nessun database configurato. Imposta DATABASE_URL nel file .env")

    db.engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {}
    )
    db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db.engine)

    # Also sync to db.database module
    db.database.engine = db.engine
    db.database.SessionLocal = db.SessionLocal

    # Force model registration - models are defined later in this runtime hook
    # but by the time init_db is called, they should already be defined
    # We need to ensure they're in Base.metadata
    logger.info(f"[INIT_DB] About to create tables, Base has {len(db.Base.metadata.tables)} tables registered")
    logger.info(f"[INIT_DB] db_url = {db_url}")

    # If no tables are registered, something went wrong - try to get models from db.models
    if len(db.Base.metadata.tables) == 0:
        logger.warning("[INIT_DB] WARNING: No tables registered in Base.metadata!")
        # Try to trigger model registration by accessing db.models attributes
        try:
            if hasattr(db.models, 'User'):
                logger.info(f"[INIT_DB] Found models in db.models: User, Bank, etc.")
        except Exception as e:
            logger.error(f"[INIT_DB] Error accessing db.models: {e}")

    db.Base.metadata.create_all(bind=db.engine)
    logger.info(f"[INIT_DB] Tables created successfully, tables: {list(db.Base.metadata.tables.keys())}")

def get_db():
    if db.SessionLocal is None:
        raise RuntimeError("Database non inizializzato. Chiama prima init_db(path).")
    db_session = db.SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

def get_db_optional():
    if db.SessionLocal is None:
        yield None
    else:
        db_session = db.SessionLocal()
        try:
            yield db_session
        finally:
            db_session.close()

# Inject these into the db module
db.init_db = init_db
db.get_db = get_db
db.get_db_optional = get_db_optional

# Also inject into db.database (required by core.security)
db.database.init_db = init_db
db.database.get_db = get_db
db.database.get_db_optional = get_db_optional

# Also define init_banks function
def init_banks_from_file(banks_data):
    """
    Inizializza le banche nel DB.
    banks_data: lista di dict già letta dal JSON.
    """
    from db import models

    if not banks_data:
        print("[WARN] Nessun dato banche fornito, niente da inizializzare.")
        return

    db_session = next(get_db())
    try:
        for bank in banks_data:
            exists = db_session.query(models.Bank).filter_by(label=bank["label"]).first()
            if not exists:
                db_session.add(models.Bank(**bank))
        db_session.commit()
    finally:
        db_session.close()
    print(f"[DB] Banche inizializzate correttamente ({len(banks_data)} entries)")

# Create init_banks module
init_banks_module = types.ModuleType('db.init_banks')
init_banks_module.init_banks_from_file = init_banks_from_file
sys.modules['db.init_banks'] = init_banks_module

# Define init_repo_update function with JSON file support
def init_repo_update_from_file(repo_update_data=None):
    """
    Inizializza la tabella repo_update_info con dati di default.
    Se repo_update_data è None, cerca di leggere da repo_update_default.json
    in queste posizioni (in ordine):
    1. ~/.sdp-api/repo_update_default.json (priorità massima - modificabile dall'utente)
    2. sys._MEIPASS/config/repo_update_default.json (dentro il bundle PyInstaller)
    3. Directory corrente/config/repo_update_default.json
    Se non trova il file, usa dati di default hardcoded.
    """
    from db import models
    import logging
    import json
    from pathlib import Path
    logger = logging.getLogger(__name__)

    if db.SessionLocal is None:
        logger.warning("[INIT_REPO_UPDATE] Database non inizializzato, skip.")
        return

    # Se non sono stati passati dati, cerca di leggerli dal file JSON
    if repo_update_data is None:
        json_found = False

        # Posizioni dove cercare il file JSON
        search_paths = []

        # 1. Directory ~/.sdp-api/ (priorità massima - file modificabile dall'utente)
        search_paths.append(Path.home() / ".sdp-api" / "repo_update_default.json")

        # 2. Directory dell'eseguibile (sys._MEIPASS per PyInstaller)
        if hasattr(sys, '_MEIPASS'):
            search_paths.append(Path(sys._MEIPASS) / "config" / "repo_update_default.json")
            search_paths.append(Path(sys._MEIPASS) / "db" / "repo_update_default.json")
            search_paths.append(Path(sys._MEIPASS) / "repo_update_default.json")

        # 3. Directory del file corrente (se non bundled)
        if hasattr(sys, 'argv') and sys.argv:
            exe_dir = Path(sys.argv[0]).parent if sys.argv[0] else Path.cwd()
            search_paths.append(exe_dir / "config" / "repo_update_default.json")
            search_paths.append(exe_dir / "repo_update_default.json")

        # 4. Directory corrente
        search_paths.append(Path.cwd() / "config" / "repo_update_default.json")
        search_paths.append(Path.cwd() / "repo_update_default.json")

        # Cerca il file
        for json_path in search_paths:
            if json_path.exists():
                try:
                    logger.info(f"[INIT_REPO_UPDATE] Trovato file JSON: {json_path}")
                    with open(json_path, "r", encoding="utf-8") as f:
                        repo_update_data = json.load(f)
                    json_found = True
                    logger.info(f"[INIT_REPO_UPDATE] Caricati {len(repo_update_data)} record dal JSON")
                    break
                except Exception as e:
                    logger.error(f"[INIT_REPO_UPDATE] Errore lettura JSON da {json_path}: {e}")
                    continue

        # Se non trova il file, usa dati di default hardcoded
        if not json_found:
            logger.warning("[INIT_REPO_UPDATE] File JSON non trovato, uso dati di default hardcoded")
            repo_update_data = [
                {"settimana": 1, "anno": 2025, "semaforo": 0, "bank": "Sparkasse"},
                {"settimana": 1, "anno": 2025, "semaforo": 0, "bank": "CiviBank"}
            ]

    db_session = next(get_db())
    try:
        for entry in repo_update_data:
            bank_name = entry.get("bank")
            settimana = entry.get("settimana")
            anno = entry.get("anno")
            semaforo = entry.get("semaforo", 0)

            if not bank_name:
                logger.warning(f"[INIT_REPO_UPDATE] Entry senza bank, skip: {entry}")
                continue

            # Verifica se esiste già un record per questa banca
            existing = db_session.query(models.RepoUpdateInfo).filter(
                models.RepoUpdateInfo.bank == bank_name
            ).first()

            if existing:
                logger.info(f"[INIT_REPO_UPDATE] Record gia presente per banca '{bank_name}', skip.")
                continue

            # Crea nuovo record
            new_record = models.RepoUpdateInfo(
                settimana=settimana,
                anno=anno,
                semaforo=semaforo,
                bank=bank_name
            )
            db_session.add(new_record)
            logger.info(f"[INIT_REPO_UPDATE] Creato record per banca '{bank_name}': anno={anno}, settimana={settimana}")

        db_session.commit()
        logger.info("[INIT_REPO_UPDATE] Inizializzazione completata con successo.")
        print(f"[DB] Repo update info inizializzate correttamente ({len(repo_update_data)} entries)")

    except Exception as e:
        logger.error(f"[INIT_REPO_UPDATE] Errore durante l'inizializzazione: {e}", exc_info=True)
        db_session.rollback()
    finally:
        db_session.close()

# Create init_repo_update module
init_repo_update_module = types.ModuleType('db.init_repo_update')
init_repo_update_module.init_repo_update_from_file = init_repo_update_from_file
sys.modules['db.init_repo_update'] = init_repo_update_module

# Create db.crud and db.schemas modules
print("[RUNTIME HOOK] Creating db.crud module...")
db_crud_module = types.ModuleType('db.crud')
db_crud_module.__package__ = 'db'
sys.modules['db.crud'] = db_crud_module
db.crud = db_crud_module

print("[RUNTIME HOOK] Creating db.schemas module...")
db_schemas_module = types.ModuleType('db.schemas')
db_schemas_module.__package__ = 'db'
sys.modules['db.schemas'] = db_schemas_module
db.schemas = db_schemas_module

# Create a mock db.models module that we'll populate with our model classes
db.models = types.ModuleType('db.models')
sys.modules['db.models'] = db.models

# Define model classes directly since imports fail in frozen environment
print("[RUNTIME HOOK] Defining model classes...")
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, func

# Define all model classes manually
class User(db.Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    permissions = Column(JSON, nullable=False, server_default='[]')
    bank = Column(String, nullable=True)

class AuditLog(db.Base):
    __tablename__ = "audit_logs"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    bank = Column(String, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

class FlowExecutionHistory(db.Base):
    __tablename__ = "flow_execution_history"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    flow_id_str = Column(String)
    timestamp = Column(DateTime, server_default=func.now())
    status = Column(String)
    duration_seconds = Column(Integer)
    log_key = Column(String, unique=True)
    details = Column(JSON, nullable=True)
    bank = Column(String, nullable=True)
    anno = Column(Integer, nullable=True)
    settimana = Column(Integer, nullable=True)

class Reportistica(db.Base):
    __tablename__ = "reportistica"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    banca = Column(String, nullable=True)
    anno = Column(Integer, nullable=True)
    settimana = Column(Integer, nullable=True)
    nome_file = Column(String, unique=True, nullable=False)
    package = Column(String, nullable=True)
    finalita = Column(String, nullable=True)
    disponibilita_server = Column(Boolean, default=False)
    ultima_modifica = Column(DateTime, nullable=True)
    dettagli = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class RepoUpdateInfo(db.Base):
    __tablename__ = "repo_update_info"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    bank = Column(String, nullable=True)
    anno = Column(Integer, nullable=True)
    settimana = Column(Integer, nullable=True)
    mese = Column(Integer, nullable=True)
    semaforo = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class FlowExecutionDetail(db.Base):
    __tablename__ = "flow_execution_detail"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    log_key = Column(String)
    element_id = Column(String)
    result = Column(String)
    error_lines = Column(Text)
    timestamp = Column(DateTime, server_default=func.now())
    bank = Column(String, nullable=True)
    anno = Column(Integer, nullable=True)
    settimana = Column(Integer, nullable=True)

class Bank(db.Base):
    __tablename__ = "banks"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    ini_path = Column(String, nullable=True)
    is_current = Column(Boolean, default=False)

class ReportMapping(db.Base):
    __tablename__ = "report_mapping"
    __table_args__ = {'extend_existing': True}
    Type_reportisica = Column(String, primary_key=True)
    bank = Column(String, primary_key=True)
    ws_precheck = Column(String, nullable=True)
    ws_production = Column(String, nullable=True)
    package = Column(String, primary_key=True)
    finality = Column(String, nullable=True)  # Finalità del report

class PublicationLog(db.Base):
    __tablename__ = "publication_logs"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    bank = Column(String, nullable=False)
    workspace = Column(String, nullable=False)
    packages = Column(JSON, nullable=False)
    publication_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

class SyncRun(db.Base):
    __tablename__ = "sync_runs"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True)
    bank = Column(String, nullable=True)
    start_time = Column(DateTime, server_default=func.now())
    end_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)
    files_processed = Column(Integer, default=0)
    files_copied = Column(Integer, default=0)
    files_skipped = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)
    error_details = Column(Text, nullable=True)

# Inject model classes into db.models
db.models.Base = db.Base  # Important: db.models.Base must point to the same Base
db.models.User = User
db.models.AuditLog = AuditLog
db.models.FlowExecutionHistory = FlowExecutionHistory
db.models.Reportistica = Reportistica
db.models.RepoUpdateInfo = RepoUpdateInfo
db.models.FlowExecutionDetail = FlowExecutionDetail
db.models.Bank = Bank
db.models.ReportMapping = ReportMapping
db.models.PublicationLog = PublicationLog
db.models.SyncRun = SyncRun

print(f"[RUNTIME HOOK] db.models has Bank: {hasattr(db.models, 'Bank')}")
print(f"[RUNTIME HOOK] Models defined and injected")

# Define CRUD functions directly
print("[RUNTIME HOOK] Defining CRUD functions...")
from sqlalchemy.orm import Session

# Import security function for password hashing
from core.security import get_password_hash

# User CRUD functions
def get_user_by_username(db: Session, username: str, bank: str = None):
    query = db.query(User).filter(User.username == username)
    if bank:
        query = query.filter(User.bank == bank)
    return query.first()

def get_user_by_email(db: Session, email: str, bank: str = None):
    query = db.query(User).filter(User.email == email)
    if bank:
        query = query.filter(User.bank == bank)
    return query.first()

def create_user(db: Session, user, bank: str = None):
    hashed_password = get_password_hash(user.password)
    db_user = User(
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
    return db_user

def get_users(db: Session, bank: str = None, skip: int = 0, limit: int = 100):
    query = db.query(User)
    if bank:
        query = query.filter(User.bank == bank)
    return query.offset(skip).limit(limit).all()

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def update_user(db: Session, user_id: int, user_data, bank: str = None):
    update_data = user_data.model_dump(exclude_unset=True)
    if bank:
        update_data["bank"] = bank
    db.query(User).filter(User.id == user_id).update(values=update_data, synchronize_session=False)
    db.commit()
    return get_user(db, user_id)

def delete_user(db: Session, user_id: int):
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    db.delete(db_user)
    db.commit()
    return db_user

# Bank CRUD functions
def get_banks(db: Session):
    return db.query(Bank).filter(Bank.is_active == True).all()

def create_bank(db: Session, bank):
    db_bank = Bank(label=bank.label)
    db.add(db_bank)
    db.commit()
    db.refresh(db_bank)
    return db_bank

def get_current_bank(db: Session):
    return db.query(Bank).filter_by(is_current=True).first()

def set_current_bank(db: Session, bank_label: str):
    db.query(Bank).update({Bank.is_current: False})
    bank = db.query(Bank).filter_by(label=bank_label).first()
    if not bank:
        return None
    bank.is_current = True
    db.commit()
    db.refresh(bank)
    return bank

# Reportistica CRUD functions
def get_reportistica_items(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Reportistica).offset(skip).limit(limit).all()

def get_reportistica_by_id(db: Session, reportistica_id: int):
    return db.query(Reportistica).filter(Reportistica.id == reportistica_id).first()

def get_reportistica_by_nome_file(db: Session, nome_file: str):
    return db.query(Reportistica).filter(Reportistica.nome_file == nome_file).first()

def create_reportistica(db: Session, reportistica):
    db_reportistica = Reportistica(**reportistica.model_dump())
    db.add(db_reportistica)
    db.commit()
    db.refresh(db_reportistica)
    return db_reportistica

def update_reportistica(db: Session, reportistica_id: int, reportistica_data):
    update_data = reportistica_data.model_dump(exclude_unset=True)
    if not update_data:
        return get_reportistica_by_id(db, reportistica_id)
    db.query(Reportistica).filter(Reportistica.id == reportistica_id).update(values=update_data, synchronize_session=False)
    db.commit()
    return get_reportistica_by_id(db, reportistica_id)

def delete_reportistica(db: Session, reportistica_id: int):
    db_reportistica = get_reportistica_by_id(db, reportistica_id)
    if not db_reportistica:
        return None
    db.delete(db_reportistica)
    db.commit()
    return db_reportistica

def get_reportistica_by_filters(db: Session, banca: str = None, anno: int = None, settimana: int = None, package: str = None):
    query = db.query(Reportistica)
    if banca:
        query = query.filter(Reportistica.banca == banca)
    if anno:
        query = query.filter(Reportistica.anno == anno)
    if settimana:
        query = query.filter(Reportistica.settimana == settimana)
    if package:
        query = query.filter(Reportistica.package == package)
    return query.all()

# RepoUpdateInfo CRUD functions
def get_repo_update_info(db: Session):
    return db.query(RepoUpdateInfo).first()

def create_repo_update_info(db: Session, repo_info):
    db_repo_info = RepoUpdateInfo(**repo_info.model_dump())
    db.add(db_repo_info)
    db.commit()
    db.refresh(db_repo_info)
    return db_repo_info

def update_repo_update_info(db: Session, repo_info_data):
    existing_repo_info = get_repo_update_info(db)
    if not existing_repo_info:
        return create_repo_update_info(db, repo_info_data)
    update_data = repo_info_data.model_dump(exclude_unset=True)
    if update_data:
        db.query(RepoUpdateInfo).filter(RepoUpdateInfo.id == existing_repo_info.id).update(values=update_data, synchronize_session=False)
        db.commit()
    return get_repo_update_info(db)

def delete_repo_update_info(db: Session, repo_info_id: int):
    repo_info = db.query(RepoUpdateInfo).filter(RepoUpdateInfo.id == repo_info_id).first()
    if not repo_info:
        return None
    db.delete(repo_info)
    db.commit()
    return repo_info

def get_repo_update_info_by_bank(db: Session, bank: str):
    """Ottiene il record repo_update_info per una specifica banca"""
    return db.query(RepoUpdateInfo).filter(RepoUpdateInfo.bank == bank).first()

def update_repo_update_info_by_bank(db: Session, bank: str, repo_info_data):
    """Aggiorna il record repo_update_info per una specifica banca"""
    existing_repo_info = get_repo_update_info_by_bank(db, bank)
    if not existing_repo_info:
        # Se non esiste, crea un nuovo record
        new_data = repo_info_data.model_dump(exclude_unset=True)
        new_data['bank'] = bank
        db_repo_info = RepoUpdateInfo(**new_data)
        db.add(db_repo_info)
        db.commit()
        db.refresh(db_repo_info)
        return db_repo_info

    update_data = repo_info_data.model_dump(exclude_unset=True)
    if update_data:
        db.query(RepoUpdateInfo).filter(RepoUpdateInfo.id == existing_repo_info.id).update(values=update_data, synchronize_session=False)
        db.commit()
    return get_repo_update_info_by_bank(db, bank)

# Flow Execution CRUD functions
def create_flow_execution(db: Session, flow_execution):
    db_flow = FlowExecutionHistory(**flow_execution.model_dump())
    db.add(db_flow)
    db.commit()
    db.refresh(db_flow)
    return db_flow

def get_flow_executions(db: Session, skip: int = 0, limit: int = 100):
    return db.query(FlowExecutionHistory).offset(skip).limit(limit).all()

def get_flow_execution_by_id(db: Session, flow_id: int):
    return db.query(FlowExecutionHistory).filter(FlowExecutionHistory.id == flow_id).first()

def update_flow_execution_status(db: Session, flow_id: int, status: str):
    db.query(FlowExecutionHistory).filter(FlowExecutionHistory.id == flow_id).update({"status": status}, synchronize_session=False)
    db.commit()
    return get_flow_execution_by_id(db, flow_id)

def create_flow_execution_detail(db: Session, detail):
    db_detail = FlowExecutionDetail(**detail.model_dump())
    db.add(db_detail)
    db.commit()
    db.refresh(db_detail)
    return db_detail

def get_flow_execution_details(db: Session, flow_id: int):
    return db.query(FlowExecutionDetail).filter(FlowExecutionDetail.flow_execution_id == flow_id).all()

# Functions used by tasks.py
def create_execution_log(db: Session, flow_id_str: str, status: str,
                         duration_seconds: int, details: dict, log_key: str,
                         bank: str, anno: int = None, settimana: int = None):
    record = FlowExecutionHistory(
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
                            bank: str = None, anno: int = None, settimana: int = None):
    detail = FlowExecutionDetail(
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
    record = db.query(FlowExecutionHistory).filter(
        FlowExecutionHistory.log_key == log_key
    ).first()
    if record:
        record.status = status
        db.commit()
        db.refresh(record)
    return record

def get_flows_by_bank(db: Session, bank: str):
    return db.query(FlowExecutionHistory).filter(
        FlowExecutionHistory.bank == bank
    ).all()

# Audit Log CRUD functions
def log_action(db: Session, user_id: int, action: str, details: str = None):
    audit = AuditLog(user_id=user_id, action=action, details=details)
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit

def get_audit_logs(db: Session, skip: int = 0, limit: int = 100):
    return db.query(AuditLog).offset(skip).limit(limit).all()

def create_audit_log(db: Session, user_id: int = None, action: str = None, details: dict = None, bank: str = None):
    record = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        bank=bank
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

# Inject all CRUD functions into db.crud
db.crud.get_user_by_username = get_user_by_username
db.crud.get_user_by_email = get_user_by_email
db.crud.create_user = create_user
db.crud.get_users = get_users
db.crud.get_user = get_user
db.crud.update_user = update_user
db.crud.delete_user = delete_user
db.crud.get_banks = get_banks
db.crud.create_bank = create_bank
db.crud.get_current_bank = get_current_bank
db.crud.set_current_bank = set_current_bank
db.crud.get_reportistica_items = get_reportistica_items
db.crud.get_reportistica_by_id = get_reportistica_by_id
db.crud.get_reportistica_by_nome_file = get_reportistica_by_nome_file
db.crud.create_reportistica = create_reportistica
db.crud.update_reportistica = update_reportistica
db.crud.delete_reportistica = delete_reportistica
db.crud.get_reportistica_by_filters = get_reportistica_by_filters
db.crud.get_repo_update_info = get_repo_update_info
db.crud.create_repo_update_info = create_repo_update_info
db.crud.update_repo_update_info = update_repo_update_info
db.crud.delete_repo_update_info = delete_repo_update_info
db.crud.get_repo_update_info_by_bank = get_repo_update_info_by_bank
db.crud.update_repo_update_info_by_bank = update_repo_update_info_by_bank
db.crud.create_flow_execution = create_flow_execution
db.crud.get_flow_executions = get_flow_executions
db.crud.get_flow_execution_by_id = get_flow_execution_by_id
db.crud.update_flow_execution_status = update_flow_execution_status
db.crud.create_flow_execution_detail = create_flow_execution_detail
db.crud.get_flow_execution_details = get_flow_execution_details
db.crud.create_execution_log = create_execution_log
db.crud.create_execution_detail = create_execution_detail
db.crud.update_execution_log_status = update_execution_log_status
db.crud.get_flows_by_bank = get_flows_by_bank
db.crud.log_action = log_action
db.crud.get_audit_logs = get_audit_logs
db.crud.create_audit_log = create_audit_log

print(f"[RUNTIME HOOK] db.crud has get_banks: {hasattr(db.crud, 'get_banks')}")
print("[RUNTIME HOOK] CRUD functions defined and injected")

# Define ConfigManager class for core.config
print("[RUNTIME HOOK] Defining ConfigManager...")
import logging
from pathlib import Path

class ConfigManager:
    """Gestisce la configurazione dell'applicazione"""

    def __init__(self):
        self.config_dir = Path.home() / ".sdp-api"
        self.env_file = self.config_dir / ".env"

    def get_config_path(self):
        return self.env_file

    def get_setting(self, key: str):
        """Legge il valore di una chiave dal file di configurazione .env"""
        try:
            if not self.env_file.exists():
                logging.error("File di configurazione non trovato")
                return None

            content = self.env_file.read_text().splitlines()
            for line in content:
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()

            return None
        except Exception as e:
            logging.error(f"Errore nel recupero dell'impostazione {key}: {e}")
            return None

    def update_setting(self, key: str, value: str):
        """Aggiorna una singola impostazione nel file di configurazione"""
        try:
            if not self.env_file.exists():
                logging.error("File di configurazione non trovato")
                return False

            content = self.env_file.read_text()
            lines = content.split('\n')
            updated_lines = []
            setting_updated = False

            for line in lines:
                if line.startswith(f'{key}='):
                    updated_lines.append(f'{key}={value}')
                    setting_updated = True
                else:
                    updated_lines.append(line)

            if not setting_updated:
                updated_lines.append(f'{key}={value}')

            self.env_file.write_text('\n'.join(updated_lines))
            logging.info(f"Impostazione {key} aggiornata")
            return True

        except Exception as e:
            logging.error(f"Errore nell'aggiornamento dell'impostazione {key}: {e}")
            return False

    def get_ini_contents(self) -> dict:
        """Legge tutti i file INI delle banche"""
        import configparser
        import json

        folder_path = self.get_setting("SETTINGS_PATH")
        if not folder_path:
            logging.warning("SETTINGS_PATH non configurato, impossibile leggere INI")
            return {}

        banks_file = Path(folder_path) / "App" / "Ingestion" / "banks_default.json"
        if not banks_file.exists():
            logging.warning(f"File banks_default.json non trovato: {banks_file}")
            return {}

        try:
            with open(banks_file, "r", encoding="utf-8") as f:
                banks_data = json.load(f)
        except Exception as e:
            logging.error(f"Errore caricamento JSON banche: {e}")
            return {}

        ini_contents = {}
        for bank in banks_data:
            ini_path = Path(folder_path) / "App" / "Ingestion" / bank["ini_path"]
            if ini_path.exists():
                config = configparser.ConfigParser(allow_no_value=True)
                config.read(ini_path, encoding="utf-8")

                def expand_env_vars(d):
                    return {k: os.path.expandvars(v) if v is not None else None for k, v in d.items()}

                bank_ini = {"DEFAULT": expand_env_vars(config.defaults())}
                for section in config.sections():
                    bank_ini[section] = expand_env_vars(dict(config[section]))
                ini_contents[bank["label"]] = {"ini_path": str(ini_path), "data": bank_ini}
            else:
                ini_contents[bank["label"]] = {"ini_path": str(ini_path), "data": None}

        return ini_contents

# Inject ConfigManager into core.config module
import core.config
config_manager_instance = ConfigManager()
core.config.config_manager = config_manager_instance
core.config.ConfigManager = ConfigManager
sys.modules['core.config'].config_manager = config_manager_instance
sys.modules['core.config'].ConfigManager = ConfigManager

print(f"[RUNTIME HOOK] ConfigManager injected, has get_setting: {hasattr(config_manager_instance, 'get_setting')}")

# Define missing schema classes directly in the runtime hook
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# --- User Schemas ---
class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None

class UserCreate(UserBase):
    password: Optional[str] = None
    role: str = "user"
    permissions: Optional[List[str]] = []
    bank: Optional[str] = None

class UserInDB(UserBase):
    id: int
    role: str
    is_active: bool
    permissions: List[str]
    bank: Optional[str] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None
    bank: Optional[str] = None

class PasswordChange(BaseModel):
    new_password: str

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    bank: Optional[str] = None

# --- Audit Log Schemas ---
class AuditLogBase(BaseModel):
    action: str
    details: Optional[dict] = None

class AuditLogCreate(AuditLogBase):
    user_id: Optional[int] = None

class AuditLogInDB(AuditLogBase):
    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True

# Define the missing Reportistica schemas
class ReportisticaBase(BaseModel):
    banca: Optional[str] = None
    anno: Optional[int] = None
    settimana: Optional[int] = None
    nome_file: str
    package: Optional[str] = None
    finalita: Optional[str] = None
    disponibilita_server: Optional[bool] = False
    ultima_modifica: Optional[datetime] = None
    dettagli: Optional[str] = None

class ReportisticaCreate(ReportisticaBase):
    pass

class ReportisticaUpdate(BaseModel):
    banca: Optional[str] = None
    anno: Optional[int] = None
    settimana: Optional[int] = None
    nome_file: Optional[str] = None
    package: Optional[str] = None
    finalita: Optional[str] = None
    disponibilita_server: Optional[bool] = None
    ultima_modifica: Optional[datetime] = None
    dettagli: Optional[str] = None

class ReportisticaInDB(ReportisticaBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Define the missing RepoUpdateInfo schemas
class RepoUpdateInfoBase(BaseModel):
    bank: Optional[str] = None
    anno: Optional[int] = None
    settimana: Optional[int] = None
    mese: Optional[int] = None
    semaforo: Optional[int] = None

class RepoUpdateInfoCreate(RepoUpdateInfoBase):
    pass

class RepoUpdateInfoUpdate(BaseModel):
    bank: Optional[str] = None
    anno: Optional[int] = None
    settimana: Optional[int] = None
    mese: Optional[int] = None
    semaforo: Optional[int] = None

class RepoUpdateInfoInDB(RepoUpdateInfoBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Define the missing Bank schemas
class BankBase(BaseModel):
    label: str
    status: Optional[str] = None

class BankCreate(BankBase):
    pass

class BankUpdate(BaseModel):
    label: Optional[str] = None
    status: Optional[str] = None

class BankInDB(BankBase):
    id: int

    class Config:
        from_attributes = True

# Define additional Bank response schemas
class BankResponse(BankBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

class BanksListResponse(BaseModel):
    banks: list[BankResponse]
    current_bank: Optional[str] = None

# Inject all missing classes into db.schemas
# User schemas
db.schemas.UserBase = UserBase
db.schemas.UserCreate = UserCreate
db.schemas.UserInDB = UserInDB
db.schemas.UserUpdate = UserUpdate
db.schemas.PasswordChange = PasswordChange

# Auth schemas
db.schemas.Token = Token
db.schemas.TokenData = TokenData

# Audit log schemas
db.schemas.AuditLogBase = AuditLogBase
db.schemas.AuditLogCreate = AuditLogCreate
db.schemas.AuditLogInDB = AuditLogInDB

# Reportistica schemas
db.schemas.ReportisticaBase = ReportisticaBase
db.schemas.ReportisticaCreate = ReportisticaCreate
db.schemas.ReportisticaUpdate = ReportisticaUpdate
db.schemas.ReportisticaInDB = ReportisticaInDB

# RepoUpdateInfo schemas
db.schemas.RepoUpdateInfoBase = RepoUpdateInfoBase
db.schemas.RepoUpdateInfoCreate = RepoUpdateInfoCreate
db.schemas.RepoUpdateInfoUpdate = RepoUpdateInfoUpdate
db.schemas.RepoUpdateInfoInDB = RepoUpdateInfoInDB

# Bank schemas
db.schemas.BankBase = BankBase
db.schemas.BankCreate = BankCreate
db.schemas.BankUpdate = BankUpdate
db.schemas.BankInDB = BankInDB
db.schemas.BankResponse = BankResponse
db.schemas.BanksListResponse = BanksListResponse

print(f"[RUNTIME HOOK] db module initialized. Attributes: {[x for x in dir(db) if not x.startswith('_')]}")
print("[RUNTIME HOOK] db.init_banks module created")
print(f"[RUNTIME HOOK] Missing schema classes injected into db.schemas")
print(f"[RUNTIME HOOK] db.schemas has Token: {hasattr(db.schemas, 'Token')}")
print(f"[RUNTIME HOOK] db.schemas has ReportisticaInDB: {hasattr(db.schemas, 'ReportisticaInDB')}")
print("[RUNTIME HOOK] All modules loaded successfully!")
