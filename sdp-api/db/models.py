from sqlalchemy import Column, Integer, String, Boolean, JSON, ForeignKey, DateTime, Text
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean,ForeignKey,func, result_tuple
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    # Nome della tabella nel database
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    # Aggiungiamo un campo "role" per la gestione dei permessi
    role = Column(String, default="user")  # Esempi: 'user', 'admin'
    is_active = Column(Boolean, default=True)
    permissions = Column(JSON, nullable=False, server_default='[]')
    # --- AGGIUNGI QUESTA NUOVA CLASSE ---
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, index=True, nullable=False)
    details = Column(JSON, nullable=True)
class FlowExecutionHistory(Base):
    __tablename__ = "flow_execution_history"

    id = Column(Integer, primary_key=True, index=True)
    flow_id_str = Column(String, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String)  # "Success" / "Failed"
    duration_seconds = Column(Integer)
    details = Column(JSON, nullable=True) # Dettagli extra

class Reportistica(Base):
    __tablename__ = "reportistica"

    id = Column(Integer, primary_key=True, autoincrement=True)
    banca = Column(String, nullable=True)
    anno = Column(Integer, nullable=True)
    settimana = Column(Integer, nullable=True)
    nome_file = Column(String, unique=True, nullable=False)
    package = Column(String, nullable=True)
    disponibilita_server = Column(Boolean, default=False)
    ultima_modifica = Column(DateTime(timezone=True), nullable=True)
    dettagli = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class RepoUpdateInfo(Base):
    __tablename__ = "repo_update_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    settimana = Column(Integer, nullable=True)
    anno = Column(Integer, nullable=True)
    semaforo = Column(Integer, nullable=True)
    log_key = Column(String, unique=True, index=True)  # serve per collegare i dettagli
    details = Column(JSON, nullable=True)


class FlowExecutionDetail(Base):
    __tablename__ = "flow_execution_detail"

    id = Column(Integer, primary_key=True, index=True)
    log_key = Column(String, index=True)
    element_id = Column(String)
    result = Column(String)
    error_lines = Column(Text)  # salva come JSON o testo multilinea
    timestamp = Column(DateTime(timezone=True), server_default=func.now())  # <-- aggiunto


class Bank(Base):
    __tablename__ = "banks"

    id = Column(Integer, primary_key=True, index=True)
    value = Column(String, unique=True, index=True, nullable=False)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    ini_path = Column(String, nullable=True)  
    is_current = Column(Boolean, default=False)
