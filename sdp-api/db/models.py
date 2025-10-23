from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, func, Index
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    permissions = Column(JSON, nullable=False, server_default='[]')
    bank = Column(String, index=True, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, index=True, nullable=False)
    details = Column(JSON, nullable=True)
    bank = Column(String, index=True, nullable=True)  # nuova colonna




class FlowExecutionHistory(Base):
    __tablename__ = "flow_execution_history"

    id = Column(Integer, primary_key=True, index=True)
    flow_id_str = Column(String, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String)  # "Success" / "Failed"
    duration_seconds = Column(Integer)
    log_key = Column(String, unique=True, index=True)
    details = Column(JSON, nullable=True)  # Dettagli extra
    bank = Column(String, index=True, nullable=True)  # nuova colonna
    anno = Column(Integer, nullable=True)  # anno di esecuzione
    settimana = Column(Integer, nullable=True)  # settimana di esecuzione


class Reportistica(Base):
    __tablename__ = "reportistica"
    __table_args__ = (
        # Unique constraint sulla coppia (nome_file, banca)
        # Permette stesso nome_file per banche diverse
        Index('idx_reportistica_banca', 'banca'),
        Index('idx_reportistica_anno_settimana', 'anno', 'settimana'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    banca = Column(String, nullable=False)  # ✅ Obbligatorio (NOT NULL nel DB)
    anno = Column(Integer, nullable=True)
    settimana = Column(Integer, nullable=True)
    nome_file = Column(String, nullable=False)  # ✅ Rimosso unique=True, gestito da __table_args__
    package = Column(String, nullable=True)
    finalita = Column(String, nullable=True)
    disponibilita_server = Column(Boolean, default=False)
    ultima_modifica = Column(DateTime(timezone=True), nullable=True)
    dettagli = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReportMapping(Base):
    __tablename__ = "report_mapping"

    Type_reportisica = Column(String, primary_key=True)
    bank = Column(String, primary_key=True)
    ws_precheck = Column(String, nullable=True)
    ws_production = Column(String, nullable=True)
    package = Column(String, primary_key=True)
    finality = Column(String, nullable=True)  # Finalità del report


class RepoUpdateInfo(Base):
    __tablename__ = "repo_update_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    settimana = Column(Integer, nullable=True)
    anno = Column(Integer, nullable=True)
    semaforo = Column(Integer, nullable=True)
    log_key = Column(String, unique=True, index=True)  # serve per collegare i dettagli
    details = Column(JSON, nullable=True)
    bank = Column(String, index=True, nullable=True)  # nuova colonna


class FlowExecutionDetail(Base):
    __tablename__ = "flow_execution_detail"

    id = Column(Integer, primary_key=True, index=True)
    log_key = Column(String, index=True)
    element_id = Column(String)
    result = Column(String)
    error_lines = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    bank = Column(String, index=True, nullable=True)  # nuova colonna
    anno = Column(Integer, nullable=True)  # anno di esecuzione
    settimana = Column(Integer, nullable=True)  # settimana di esecuzione


class Bank(Base):
    __tablename__ = "banks"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    ini_path = Column(String, nullable=True)
    is_current = Column(Boolean, default=False)


class PublicationLog(Base):
    __tablename__ = "publication_logs"

    id = Column(Integer, primary_key=True, index=True)
    bank = Column(String, index=True, nullable=False)
    workspace = Column(String, nullable=False)
    packages = Column(JSON, nullable=False)  # Lista di package pubblicati
    publication_type = Column(String, nullable=False)  # 'precheck' o 'production'
    status = Column(String, nullable=False)  # 'success' o 'error'
    output = Column(Text, nullable=True)  # Log completo dell'esecuzione
    error = Column(Text, nullable=True)  # Errore se presente
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
