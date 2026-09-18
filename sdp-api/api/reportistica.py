from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone
from pydantic import BaseModel
import asyncio
import subprocess
import sys
import os
import traceback
import logging
import json
import re

from db import get_db, crud, schemas
import db.models as models
from db.models import User
from core.security import get_current_user


# Configura logger per questo modulo
logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# WebSocket Manager per aggiornamenti real-time
# ============================================================

class ConnectionManager:
    """Gestisce le connessioni WebSocket attive"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Invia un messaggio a tutti i client connessi"""
        if not self.active_connections:
            return

        disconnected = set()
        async with self._lock:
            connections = self.active_connections.copy()

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error sending to WebSocket client: {e}")
                disconnected.add(connection)

        # Rimuovi connessioni morte
        if disconnected:
            async with self._lock:
                self.active_connections -= disconnected

# Istanza globale del manager
ws_manager = ConnectionManager()


# Schema per i package pronti
class PackageReady(BaseModel):
    package: str
    ws_precheck: Optional[str] = None
    ws_produzione: Optional[str] = None
    user: str = "N/D"
    data_esecuzione: Optional[datetime] = None
    pre_check: bool = False
    prod: bool = False
    log: str = "In attesa di elaborazione"


class TriggerSyncRequest(BaseModel):
    bank: Optional[str] = None


def normalize_bank_label(bank: Optional[str]) -> str:
    """Normalize known bank labels to canonical casing used by reposync."""
    if not bank:
        return ""

    cleaned = bank.strip()
    if not cleaned:
        return ""

    canonical_map = {
        "sparkasse": "Sparkasse",
        "civibank": "CiviBank",
    }
    return canonical_map.get(cleaned.lower(), cleaned)


def _bank_to_token(bank: Optional[str]) -> str:
    normalized = normalize_bank_label(bank)
    token = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return token or "default"


def _parse_datetime_value(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None

        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            parsed = None
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                return None
            dt = parsed

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

    return dt


def _build_last_sync_info(last_sync_time: Any, now: Optional[datetime] = None) -> Optional[dict]:
    parsed = _parse_datetime_value(last_sync_time)
    if not parsed:
        return None

    now_utc = now or datetime.utcnow()
    time_diff = max(0.0, (now_utc - parsed).total_seconds())

    if time_diff < 60:
        last_sync_human = f"{int(time_diff)} secondi fa"
    elif time_diff < 3600:
        minutes = int(time_diff / 60)
        last_sync_human = f"{minutes} minuto fa" if minutes == 1 else f"{minutes} minuti fa"
    elif time_diff < 86400:
        hours = int(time_diff / 3600)
        last_sync_human = f"{hours} ora fa" if hours == 1 else f"{hours} ore fa"
    else:
        days = int(time_diff / 86400)
        last_sync_human = f"{days} giorno fa" if days == 1 else f"{days} giorni fa"

    return {
        "last_sync_time": parsed.isoformat(),
        "last_sync_ago_seconds": int(time_diff),
        "last_sync_ago_human": last_sync_human
    }


def _get_sync_run_row(
    db: Session,
    bank: Optional[str],
    columns: str = "end_time, update_interval",
):
    """
    Fetch sync_runs row for a specific bank when available.
    Falls back to legacy row ID=1 if bank filtering is unsupported.
    """
    normalized_bank = normalize_bank_label(bank)
    if normalized_bank:
        try:
            return db.execute(
                text(
                    f"""
                    SELECT {columns}
                    FROM sync_runs
                    WHERE operation_type = 'sync'
                      AND LOWER(TRIM(bank)) = LOWER(TRIM(:bank))
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"bank": normalized_bank},
            ).fetchone()
        except Exception as e:
            logger.debug(f"Bank-specific sync_runs lookup failed, using legacy fallback: {e}")

    return db.execute(
        text(f"SELECT {columns} FROM sync_runs WHERE id = 1")
    ).fetchone()


def _read_sync_metadata(path: Optional[str]) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}

    data: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if ":" in line:
                    key, value = line.split(":", 1)
                    data[key.strip().lower()] = value.strip()
    except Exception:
        return {}
    return data


def _metadata_matches_bank(metadata: Dict[str, str], bank: Optional[str]) -> bool:
    expected = normalize_bank_label(bank)
    if not expected:
        return True

    file_bank = normalize_bank_label(metadata.get("bank"))
    if not file_bank:
        # File legacy senza banca esplicita: non usarlo per stato per-banca
        return False

    return file_bank.lower() == expected.lower()


def _resolve_sync_files(base_folder: str, bank: Optional[str]) -> Dict[str, Optional[str]]:
    sdp_folder = os.path.join(base_folder, ".sdp")
    log_dir = os.path.join(base_folder, "App", "Dashboard", "sync_logs")
    bank_token = _bank_to_token(bank)

    marker_candidates = [
        os.path.join(sdp_folder, f"sync_requested_{bank_token}.marker"),
        os.path.join(sdp_folder, "sync_requested.marker"),
    ]
    pid_candidates = [
        os.path.join(log_dir, f"current_sync_{bank_token}.pid"),
        os.path.join(log_dir, "current_sync.pid"),
    ]

    marker_file = None
    for candidate in marker_candidates:
        metadata = _read_sync_metadata(candidate)
        if metadata and _metadata_matches_bank(metadata, bank):
            marker_file = candidate
            break

    pid_file = None
    for candidate in pid_candidates:
        metadata = _read_sync_metadata(candidate)
        if metadata and _metadata_matches_bank(metadata, bank):
            pid_file = candidate
            break

    return {
        "sdp_folder": sdp_folder,
        "log_dir": log_dir,
        "bank_token": bank_token,
        "marker_file": marker_file,
        "pid_file": pid_file,
        "marker_candidates": marker_candidates,
        "pid_candidates": pid_candidates,
    }


def _read_pid_from_file(pid_file: Optional[str]) -> Optional[int]:
    metadata = _read_sync_metadata(pid_file)
    pid_raw = metadata.get("pid")
    if not pid_raw:
        return None
    try:
        return int(pid_raw)
    except (ValueError, TypeError):
        return None


def _compute_sync_status(db: Session, bank: Optional[str]) -> dict:
    from core.config import config_manager
    import psutil

    effective_bank = normalize_bank_label(bank)
    now = datetime.utcnow()

    base_folder = config_manager.get_setting("SETTINGS_PATH")
    if not base_folder:
        return {"is_running": False, "status": "idle", "bank": effective_bank}

    paths = _resolve_sync_files(base_folder, effective_bank)
    marker_file = paths["marker_file"]
    pid_file = paths["pid_file"]
    log_dir = paths["log_dir"]
    bank_token = paths["bank_token"]
    same_bank_activity = False

    # 1) Marker + PID/log recenti -> starting
    if marker_file and os.path.exists(marker_file):
        same_bank_activity = True
        marker_data = _read_sync_metadata(marker_file)
        marker_time = _parse_datetime_value(marker_data.get("timestamp"))

        if marker_time:
            marker_age = (now - marker_time).total_seconds()
            if marker_age < 300:
                pid = _read_pid_from_file(pid_file)
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        if proc.is_running():
                            response = {"is_running": True, "status": "starting", "bank": effective_bank}
                            last_sync_info = _build_last_sync_info(marker_data.get("timestamp"), now=now)
                            if last_sync_info:
                                response.update(last_sync_info)
                            return response
                    except psutil.NoSuchProcess:
                        pass

                if os.path.exists(log_dir):
                    bank_logs = [f for f in os.listdir(log_dir) if f.startswith(f"sync_stdout_{bank_token}_")]
                    if bank_logs:
                        latest_log = max([os.path.join(log_dir, f) for f in bank_logs], key=os.path.getmtime)
                        log_age = now.timestamp() - os.path.getmtime(latest_log)
                        if log_age < 120:
                            response = {"is_running": True, "status": "starting", "bank": effective_bank}
                            last_sync_info = _build_last_sync_info(marker_data.get("timestamp"), now=now)
                            if last_sync_info:
                                response.update(last_sync_info)
                            return response
            elif marker_age >= 300:
                try:
                    os.remove(marker_file)
                except Exception:
                    pass

    # 2) Processo attivo per banca -> starting
    pid = _read_pid_from_file(pid_file)
    if pid:
        same_bank_activity = True
        try:
            proc = psutil.Process(pid)
            if proc.is_running():
                return {"is_running": True, "status": "starting", "bank": effective_bank}
        except psutil.NoSuchProcess:
            pass

    # 3) Heartbeat DB globale + evidenza locale della banca -> running
    heartbeat_active = False
    update_interval = None
    sync_end_time = None
    sync_row = _get_sync_run_row(db, effective_bank, "end_time, update_interval")
    if sync_row:
        sync_end_time, update_interval = sync_row
        parsed_end = _parse_datetime_value(sync_end_time)
        if parsed_end and update_interval is not None:
            interval_seconds = max(int(update_interval), 0) * 60
            time_diff = (now - parsed_end).total_seconds()
            if interval_seconds > 0 and time_diff < interval_seconds and same_bank_activity:
                heartbeat_active = True

    # Last sync per banca:
    # 1) usa sync_runs.end_time (ora specifico per banca)
    # 2) fallback legacy a repo_update_info.updated_at se sync_runs non è disponibile
    sync_last_sync = _parse_datetime_value(sync_end_time)
    repo_update_last_sync = None
    if effective_bank:
        bank_row = db.execute(
            text(
                "SELECT updated_at FROM repo_update_info "
                "WHERE LOWER(TRIM(bank)) = LOWER(TRIM(:bank)) "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"bank": effective_bank}
        ).fetchone()
        if bank_row:
            repo_update_last_sync = _parse_datetime_value(bank_row[0])

    last_sync_reference = sync_last_sync or repo_update_last_sync
    last_sync_info = _build_last_sync_info(last_sync_reference, now=now)

    if heartbeat_active:
        response = {"is_running": True, "status": "running", "bank": effective_bank}
        if update_interval is not None:
            response["update_interval"] = update_interval
        if last_sync_info:
            response.update(last_sync_info)
        return response

    response = {"is_running": False, "status": "idle", "bank": effective_bank}
    if last_sync_info:
        response.update(last_sync_info)
    return response


@router.get("/")
def get_reportistica_items(
    skip: int = Query(0, ge=0, description="Numero di record da saltare"),
    limit: int = Query(100, ge=0, description="Numero massimo di record da restituire"),
    anno: Optional[int] = Query(None, description="Filtra per anno"),
    settimana: Optional[int] = Query(None, description="Filtra per settimana"),
    package: Optional[str] = Query(None, description="Filtra per package"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera tutti gli elementi di reportistica della banca dell'utente loggato
    includendo il tipo_reportistica mappato da ReportMapping.

    Filtri opzionali: anno, settimana, package
    """
    from sqlalchemy import func
    from sqlalchemy.orm import aliased

    try:
        from sqlalchemy import text
        import logging
        logger = logging.getLogger(__name__)

        # Usa query SQL diretta per bypassare problemi PyInstaller con modelli SQLAlchemy
        # FORCE REBUILD 2025-10-28 16:11 - Fixed disponibilita_server boolean
        logger.info("USANDO QUERY SQL DIRETTA - VERSION 16:00")

        sql = text("""
            SELECT id, banca, tipo_reportistica, anno, settimana, mese, nome_file, package,
                   finalita, disponibilita_server, ultima_modifica, dettagli,
                   created_at, updated_at
            FROM reportistica
            WHERE LOWER(banca) = LOWER(:banca)
            {anno_filter}
            {settimana_filter}
            {package_filter}
            LIMIT :limit OFFSET :skip
        """.format(
            anno_filter="AND anno = :anno" if anno else "",
            settimana_filter="AND settimana = :settimana" if settimana else "",
            package_filter="AND package = :package" if (package and package.lower() != "tutti") else ""
        ))

        params = {"banca": current_user.bank, "limit": limit, "skip": skip}
        if anno:
            params["anno"] = anno
        if settimana:
            params["settimana"] = settimana
        if package and package.lower() != "tutti":
            params["package"] = package

        logger.info(f"Executing SQL with params: {params}")
        result = db.execute(sql, params)
        rows = result.fetchall()
        logger.info(f"Got {len(rows)} rows, first row: {rows[0] if rows else 'none'}")

        # Costruisci dict da righe SQL
        return [
            {
                "id": row[0],
                "banca": row[1],
                "tipo_reportistica": row[2],
                "anno": row[3],
                "settimana": row[4],
                "mese": row[5],
                "nome_file": row[6],
                "package": row[7],
                "finalita": row[8],
                "disponibilita_server": bool(row[9]) if row[9] is not None else None,
                "ultima_modifica": row[10],
                "dettagli": row[11],
                "created_at": row[12],
                "updated_at": row[13]
            }
            for row in rows
        ]

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Errore nel recupero reportistica: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Errore nel recupero dati reportistica: {str(e)}")

@router.get("/is-sync-running")
def is_sync_running(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verifica lo stato del sync per la banca dell'utente loggato.
    """
    try:
        return _compute_sync_status(db, current_user.bank)
    except Exception as e:
        logger.error(f"Errore nel verificare sync status: {e}", exc_info=True)
        return {"is_running": False, "status": "idle", "bank": normalize_bank_label(current_user.bank)}


@router.get("/last-sync-info")
def get_last_sync_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Restituisce informazioni sull'ultimo sync completato.

    Restituisce:
    - last_sync_time: Timestamp dell'ultimo sync (ISO format)
    - last_sync_ago_seconds: Secondi trascorsi dall'ultimo sync
    - last_sync_ago_human: Stringa human-readable (es. "2 ore fa", "5 minuti fa")
    - never_synced: True se non c'Ã¨ mai stato un sync
    """
    try:
        from datetime import datetime

        # Prendi il record sync della banca utente (fallback legacy a ID=1)
        result = _get_sync_run_row(db, current_user.bank, "end_time")

        if not result or not result[0]:
            return {
                "never_synced": True,
                "last_sync_time": None,
                "last_sync_ago_seconds": None,
                "last_sync_ago_human": "Mai sincronizzato"
            }

        end_time = _parse_datetime_value(result[0])
        if not end_time:
            return {
                "never_synced": True,
                "last_sync_time": None,
                "last_sync_ago_seconds": None,
                "last_sync_ago_human": "Mai sincronizzato"
            }

        end_time_str = end_time.isoformat()
        now = datetime.utcnow()

        # Calcola differenza in secondi
        seconds_ago = (now - end_time).total_seconds()

        # Formatta in modo human-readable
        if seconds_ago < 60:
            human_readable = f"{int(seconds_ago)} secondi fa"
        elif seconds_ago < 3600:
            minutes = int(seconds_ago / 60)
            human_readable = f"{minutes} minuto fa" if minutes == 1 else f"{minutes} minuti fa"
        elif seconds_ago < 86400:
            hours = int(seconds_ago / 3600)
            human_readable = f"{hours} ora fa" if hours == 1 else f"{hours} ore fa"
        else:
            days = int(seconds_ago / 86400)
            human_readable = f"{days} giorno fa" if days == 1 else f"{days} giorni fa"

        return {
            "never_synced": False,
            "last_sync_time": end_time_str,
            "last_sync_ago_seconds": int(seconds_ago),
            "last_sync_ago_human": human_readable
        }

    except Exception as e:
        logger.error(f"Errore in get_last_sync_info: {e}", exc_info=True)
        return {
            "never_synced": True,
            "last_sync_time": None,
            "last_sync_ago_seconds": None,
            "last_sync_ago_human": "Errore nel recuperare informazioni",
            "error": str(e)
        }


@router.get("/sync-status")
def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint dettagliato per monitorare lo stato del sync con informazioni estese.

    Stati possibili:
    - idle: Nessun sync in corso
    - starting: Sync appena lanciato, in fase iniziale (marker file presente)
    - running: Sync attivo con heartbeat nel database
    - failed: Sync fallito o crashato
    - completed: Sync completato di recente

    Restituisce anche informazioni su PID, log files, timestamp, ecc.
    """
    try:
        from datetime import datetime
        import psutil
        from core.config import config_manager

        base_folder = config_manager.get_setting("SETTINGS_PATH")
        if not base_folder:
            return {
                "status": "idle",
                "is_running": False,
                "message": "SETTINGS_PATH non configurato"
            }

        # Path ai file di controllo (specifici per banca)
        effective_bank = normalize_bank_label(current_user.bank)
        paths = _resolve_sync_files(base_folder, effective_bank)
        marker_file = paths.get("marker_file")
        log_dir = paths.get("log_dir")
        pid_file = paths.get("pid_file")
        bank_token = paths.get("bank_token")

        now = datetime.utcnow()

        # Informazioni da raccogliere
        result = {
            "status": "idle",
            "is_running": False,
            "bank": effective_bank,
            "marker_exists": os.path.exists(marker_file) if marker_file else False,
            "pid_file_exists": os.path.exists(pid_file) if pid_file else False,
            "process_alive": False,
            "db_heartbeat_active": False,
            "details": {}
        }

        # Controlla marker file
        if marker_file and os.path.exists(marker_file):
            try:
                with open(marker_file, "r") as f:
                    content = f.read()
                    marker_data = {}
                    for line in content.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            marker_data[key] = value

                    if "timestamp" in marker_data:
                        marker_time = datetime.fromisoformat(marker_data["timestamp"])
                        age_seconds = (now - marker_time).total_seconds()
                        result["details"]["marker_age_seconds"] = age_seconds
                        result["details"]["marker_data"] = marker_data
            except Exception as e:
                logger.warning(f"Error reading marker file: {e}")

        # Controlla PID file e processo
        if pid_file and os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    pid_data = {}
                    for line in f:
                        if ":" in line:
                            key, value = line.split(":", 1)
                            pid_data[key] = value.strip()

                    if "PID" in pid_data:
                        pid = int(pid_data["PID"])
                        result["details"]["pid"] = pid

                        try:
                            proc = psutil.Process(pid)
                            if proc.is_running():
                                result["process_alive"] = True
                                result["details"]["process_status"] = proc.status()
                                result["details"]["process_cpu_percent"] = proc.cpu_percent(interval=0.1)
                                result["details"]["process_memory_mb"] = round(proc.memory_info().rss / 1024 / 1024, 2)
                        except psutil.NoSuchProcess:
                            result["process_alive"] = False
            except Exception as e:
                logger.warning(f"Error reading PID file: {e}")

        # Controlla log files
        if log_dir and os.path.exists(log_dir):
            log_prefix = f"sync_stdout_{bank_token}_" if bank_token else "sync_stdout_"
            log_files = [f for f in os.listdir(log_dir) if f.startswith(log_prefix)]
            if log_files:
                latest_log = max([os.path.join(log_dir, f) for f in log_files], key=os.path.getmtime)
                log_age = (now.timestamp() - os.path.getmtime(latest_log))
                result["details"]["latest_log_file"] = os.path.basename(latest_log)
                result["details"]["latest_log_age_seconds"] = round(log_age, 2)

        # Controlla database sync_runs
        db_result = _get_sync_run_row(db, current_user.bank, "end_time, update_interval")

        if db_result:
            end_time_str, update_interval = db_result

            if end_time_str and update_interval:
                end_time = _parse_datetime_value(end_time_str)
                if not end_time:
                    end_time = now
                time_diff = (now - end_time).total_seconds()
                interval_seconds = update_interval * 60

                result["details"]["db_end_time"] = end_time.isoformat()
                result["details"]["db_update_interval_minutes"] = update_interval
                result["details"]["db_last_update_seconds_ago"] = round(time_diff, 2)

                if time_diff < interval_seconds:
                    result["db_heartbeat_active"] = True

        # Determina lo stato finale
        if result["db_heartbeat_active"]:
            result["status"] = "running"
            result["is_running"] = True
            result["message"] = "Sync attivo con heartbeat nel database"
        elif result["marker_exists"] and result["process_alive"]:
            result["status"] = "starting"
            result["is_running"] = True
            result["message"] = "Sync in fase di avvio"
        elif result["marker_exists"] and not result["process_alive"]:
            result["status"] = "failed"
            result["is_running"] = False
            result["message"] = "Sync fallito o crashato (marker presente ma processo non attivo)"
        elif result["process_alive"]:
            result["status"] = "starting"
            result["is_running"] = True
            result["message"] = "Processo sync attivo, in attesa di heartbeat"
        else:
            # Controlla se c'Ã¨ stato un sync recente completato
            if "latest_log_age_seconds" in result["details"] and result["details"]["latest_log_age_seconds"] < 600:
                result["status"] = "completed"
                result["message"] = "Sync completato di recente"
            else:
                result["status"] = "idle"
                result["message"] = "Nessun sync in corso"

        return result

    except Exception as e:
        logger.error(f"Errore in get_sync_status: {e}", exc_info=True)
        return {
            "status": "error",
            "is_running": False,
            "message": f"Errore nel verificare lo stato: {str(e)}"
        }


@router.get("/publish-status")
def get_publish_status(
    db: Session = Depends(get_db)
):
    """
    Recupera lo stato dell'operazione di publish dalla tabella sync_runs (ID=2).
    Restituisce informazioni su publish in corso, contatori e tempi.
    Endpoint pubblico per permettere il monitoraggio in tempo reale.
    """
    try:
        from datetime import datetime

        # Prendi il record ID=2 (quello per le operazioni di publish)
        sql = text("""
            SELECT start_time, end_time, update_interval,
                   files_processed, files_copied, files_skipped, files_failed,
                   error_details
            FROM sync_runs
            WHERE id = 2 AND operation_type = 'publish'
        """)
        result = db.execute(sql).fetchone()

        if not result:
            return {
                "is_running": False,
                "data": None
            }

        start_time_str, end_time_str, update_interval, files_processed, files_copied, files_skipped, files_failed, error_details = result

        # Determina se il publish Ã¨ in corso
        is_running = end_time_str is None

        # Se il publish Ã¨ in corso, error_details contiene la fase (precheck/production)
        # Altrimenti contiene eventuali errori
        phase = None
        actual_error = None
        if is_running and error_details in ["precheck", "production"]:
            phase = error_details
        else:
            actual_error = error_details

        # Se end_time esiste, calcola durata
        duration_seconds = None
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            if end_time_str:
                end_time = datetime.fromisoformat(end_time_str)
                duration_seconds = (end_time - start_time).total_seconds()
            else:
                # Ancora in corso, calcola tempo trascorso
                now = datetime.utcnow()
                duration_seconds = (now - start_time).total_seconds()

        return {
            "is_running": is_running,
            "data": {
                "start_time": start_time_str,
                "end_time": end_time_str,
                "duration_seconds": duration_seconds,
                "update_interval": update_interval,
                "files_processed": files_processed or 0,
                "files_copied": files_copied or 0,
                "files_skipped": files_skipped or 0,
                "files_failed": files_failed or 0,
                "phase": phase,
                "error_details": actual_error,
                "has_errors": (files_failed or 0) > 0 or actual_error is not None
            }
        }
    except Exception as e:
        logger.error(f"Errore nel recupero publish status: {e}")
        return {
            "is_running": False,
            "data": None
        }


@router.get("/sync-debug-paths")
def sync_debug_paths(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Endpoint di debug per vedere i path usati dall'API"""
    try:
        from core.config import config_manager

        base_folder = config_manager.get_setting("SETTINGS_PATH")
        effective_bank = normalize_bank_label(current_user.bank)
        paths = _resolve_sync_files(base_folder, effective_bank) if base_folder else {}
        sdp_folder = paths.get("sdp_folder")
        log_dir = paths.get("log_dir")
        marker_file = paths.get("marker_file")
        pid_file = paths.get("pid_file")

        return {
            "bank": effective_bank,
            "SETTINGS_PATH": base_folder,
            "sdp_folder": sdp_folder,
            "marker_file": marker_file,
            "marker_exists": os.path.exists(marker_file) if marker_file else False,
            "log_dir": log_dir,
            "pid_file": pid_file,
            "pid_exists": os.path.exists(pid_file) if pid_file else False
        }
    except Exception as e:
        logger.error(f"Errore in sync-debug-paths: {e}", exc_info=True)
        return {"error": str(e)}


@router.get("/sync-debug")
def sync_debug(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Endpoint di debug per verificare lo stato del sync"""
    import psutil
    from sqlalchemy import text

    try:
        # Leggi info dal database (gestito da reposync), banca-specifico con fallback legacy
        result = _get_sync_run_row(
            db,
            current_user.bank,
            "operation_type, start_time, end_time, update_interval"
        )

        if not result:
            return {"error": "Nessun record sync_runs trovato"}

        operation_type, start_time, end_time, update_interval = result

        # Leggi PID dal file
        from core.config import config_manager
        base_folder = config_manager.get_setting("SETTINGS_PATH")
        paths = _resolve_sync_files(base_folder, current_user.bank) if base_folder else {}
        pid_file = paths.get("pid_file")

        pid = None
        stdout_log = None
        stderr_log = None
        user = None
        sync_start_time = None

        if pid_file and os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PID:"):
                        pid = int(line.split(":")[1])
                    elif line.startswith("User:"):
                        user = line.split(":")[1]
                    elif line.startswith("Stdout:"):
                        stdout_log = line.split(":", 1)[1]
                    elif line.startswith("Stderr:"):
                        stderr_log = line.split(":", 1)[1]
                    elif line.startswith("StartTime:"):
                        sync_start_time = line.split(":", 1)[1]

        # Verifica se il processo Ã¨ ancora attivo
        process_alive = False
        process_info = None

        if pid:
            try:
                proc = psutil.Process(pid)
                process_alive = proc.is_running()
                process_info = {
                    "pid": pid,
                    "name": proc.name(),
                    "status": proc.status(),
                    "cpu_percent": proc.cpu_percent(interval=0.1),
                    "memory_mb": proc.memory_info().rss / 1024 / 1024,
                    "create_time": datetime.fromtimestamp(proc.create_time()).isoformat()
                }
            except psutil.NoSuchProcess:
                process_alive = False
                process_info = {"error": f"Processo PID {pid} non trovato (terminato)"}

        # Leggi ultimi 50 righe dei log se esistono
        stdout_tail = None
        stderr_tail = None

        if stdout_log and os.path.exists(stdout_log):
            with open(stdout_log, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                stdout_tail = "".join(lines[-50:])

        if stderr_log and os.path.exists(stderr_log):
            with open(stderr_log, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                stderr_tail = "".join(lines[-50:])

        return {
            "database": {
                "operation_type": operation_type,
                "start_time": start_time,
                "end_time": end_time,
                "update_interval": update_interval
            },
            "sync_process": {
                "launched_by": user,
                "started_at": sync_start_time,
                "pid": pid,
                "is_alive": process_alive,
                "details": process_info
            },
            "logs": {
                "stdout_path": stdout_log,
                "stderr_path": stderr_log,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail
            }
        }

    except Exception as e:
        logger.error(f"Errore in sync-debug: {e}", exc_info=True)
        return {"error": str(e)}


@router.post("/trigger-sync")
def trigger_sync(
      request: Optional[TriggerSyncRequest] = None,
      db: Session = Depends(get_db),
      current_user: User = Depends(get_current_user)
  ):
      try:
          from datetime import datetime

          requested_bank = normalize_bank_label(request.bank) if request else ""
          user_bank = normalize_bank_label(current_user.bank)

          if requested_bank and user_bank and requested_bank.lower() != user_bank.lower():
              logger.warning(
                  "Mismatched bank in trigger-sync request: requested='%s', user_bank='%s', user='%s'. Using user bank.",
                  requested_bank,
                  user_bank,
                  current_user.username,
              )

          effective_bank = user_bank or requested_bank
          if not effective_bank:
              raise HTTPException(status_code=400, detail="Nessuna banca disponibile per avviare il sync")

          # Path base per marker e configurazione
          from core.config import config_manager
          base_folder = config_manager.get_setting("SETTINGS_PATH")
          if not base_folder:
              raise HTTPException(status_code=500, detail="SETTINGS_PATH non configurato")

          # Controlla il record sync della banca utente (fallback legacy a ID=1)
          result = _get_sync_run_row(db, effective_bank, "end_time, update_interval")

          if result:
              end_time_str, update_interval = result

              if end_time_str and update_interval:
                  end_time = _parse_datetime_value(end_time_str)
                  if not end_time:
                      end_time = datetime.utcnow()
                  # Usa UTC per confrontare con timestamp salvati in UTC
                  now = datetime.utcnow()
                  time_diff = (now - end_time).total_seconds()

                  # update_interval Ã¨ in MINUTI, convertiamo in secondi
                  interval_seconds = update_interval * 60

                  # Se la differenza Ã¨ minore di update_interval (in secondi), il sync Ã¨ giÃ  attivo
                  if time_diff < interval_seconds:
                      return {
                          "success": False,
                          "message": "Un sync Ã¨ giÃ  in corso",
                          "is_running": True
                      }

          # âœ… CREA IL MARKER FILE IMMEDIATAMENTE per feedback istantaneo
          bank_token = _bank_to_token(effective_bank)
          sdp_folder = os.path.join(base_folder, ".sdp")
          os.makedirs(sdp_folder, exist_ok=True)
          marker_file = os.path.join(sdp_folder, f"sync_requested_{bank_token}.marker")

          with open(marker_file, "w") as f:
              f.write(f"timestamp:{datetime.utcnow().isoformat()}\n")
              f.write(f"user:{current_user.username}\n")
              f.write(f"bank:{effective_bank}\n")

          logger.info(f"âœ“ Marker file created: {marker_file}")

          # Cerca reposync.exe in path centralizzato o standard
          logger.info(f"sys.frozen = {getattr(sys, 'frozen', False)}")
          logger.info(f"sys.executable = {sys.executable}")

          # 1. Prova a leggere il path da configurazione (opzionale)
          reposync_exe = config_manager.get_setting("REPOSYNC_PATH")

          if reposync_exe and os.path.exists(reposync_exe):
              logger.info(f"âœ“ Usando reposync.exe da configurazione: {reposync_exe}")
          else:
              # 2. Cerca in posizioni standard
              possible_locations = []

              if getattr(sys, 'frozen', False):
                  # Produzione (exe compilato)
                  exe_dir = os.path.dirname(sys.executable)
                  possible_locations = [
                      os.path.join(base_folder, "App", "Demons", "reposync.exe"),  # Path preferito
                      os.path.join(exe_dir, "reposync.exe"),  # Accanto all'exe
                      os.path.join(base_folder, "reposync.exe"),  # Nella cartella SETTINGS_PATH
                      os.path.join(base_folder, "App", "Dashboard", "reposync.exe"),
                  ]
              else:
                  # Sviluppo
                  venv_scripts = os.path.dirname(sys.executable)
                  possible_locations = [
                      os.path.join(base_folder, "App", "Demons", "reposync.exe"),  # Path preferito
                      os.path.join(venv_scripts, "reposync.exe"),  # Nel venv
                      os.path.join(base_folder, "reposync.exe"),  # Nella cartella SETTINGS_PATH
                      os.path.join(base_folder, "App", "Dashboard", "reposync.exe"),
                  ]

              # Cerca in tutte le posizioni
              reposync_exe = None
              for location in possible_locations:
                  logger.info(f"Cercando reposync.exe in: {location}")
                  if os.path.exists(location):
                      reposync_exe = location
                      logger.info(f"âœ“ Trovato reposync.exe: {reposync_exe}")
                      break

              if not reposync_exe:
                  logger.error(f"âœ— reposync.exe non trovato in nessuna posizione")
                  logger.error(f"Posizioni cercate: {possible_locations}")
                  # Rimuovi il marker se reposync non viene trovato
                  if os.path.exists(marker_file):
                      os.remove(marker_file)
                      logger.info(f"Marker file rimosso dopo errore: {marker_file}")
                  raise HTTPException(
                      status_code=500,
                      detail=f"reposync.exe non trovato. Installalo in C:\\reposync\\ o configura REPOSYNC_PATH"
                  )

          # Prepara il comando con logging abilitato
          sync_command = [
              reposync_exe,
              "-c",
              "--bank", effective_bank,
              "--enable-file-logging",
              "--log-level", "DEBUG"
          ]

          logger.info(f"Comando reposync: {' '.join(sync_command)}")

          # âŒ RIMUOVI QUESTA PARTE - NON creare il record!
          # sql_insert = text("""
          #     INSERT INTO sync_runs ...
          # """)
          # db.execute(sql_insert, {"bank": current_user.bank})
          # db.commit()

          # Lancia il comando (reposync aggiornerÃ  automaticamente sync_runs)
          work_dir = os.path.join(base_folder, "App", "Dashboard")

          # Crea file di log per stdout/stderr
          log_dir = os.path.join(work_dir, "sync_logs")
          os.makedirs(log_dir, exist_ok=True)
          timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
          stdout_log = os.path.join(log_dir, f"sync_stdout_{bank_token}_{timestamp}.log")
          stderr_log = os.path.join(log_dir, f"sync_stderr_{bank_token}_{timestamp}.log")

          # Lancia reposync.exe come subprocess (sia in sviluppo che in produzione)
          with open(stdout_log, "w") as out_file, open(stderr_log, "w") as err_file:
              process = subprocess.Popen(
                  sync_command,
                  cwd=work_dir,
                  stdout=out_file,
                  stderr=err_file,
                  creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
              )

          # Salva PID in un file per il monitoring
          pid_file = os.path.join(log_dir, f"current_sync_{bank_token}.pid")
          with open(pid_file, "w") as f:
              f.write(f"PID:{process.pid}\n")
              f.write(f"User:{current_user.username}\n")
              f.write(f"bank:{effective_bank}\n")
              f.write(f"Stdout:{stdout_log}\n")
              f.write(f"Stderr:{stderr_log}\n")
              f.write(f"StartTime:{datetime.utcnow().isoformat()}\n")

          logger.info(f"Sync avviato da {current_user.username}, PID: {process.pid}")
          process_pid = process.pid

          logger.info(f"Logs: stdout={stdout_log}, stderr={stderr_log}")
          logger.info(f"PID file: {pid_file}")

          return {
              "success": True,
              "message": "Sync avviato con successo",
              "is_running": True,
              "pid": process_pid,
              "stdout_log": stdout_log,
              "stderr_log": stderr_log,
              "bank": effective_bank
          }

      except HTTPException:
          raise
      except Exception as e:
          logger.error(f"Errore sync: {e}", exc_info=True)
          # Rimuovi il marker file se c'Ã¨ stato un errore
          try:
              from core.config import config_manager
              base_folder = config_manager.get_setting("SETTINGS_PATH")
              if base_folder:
                  sdp_folder = os.path.join(base_folder, ".sdp")
                  bank_token = _bank_to_token(normalize_bank_label(current_user.bank))
                  marker_file = os.path.join(sdp_folder, f"sync_requested_{bank_token}.marker")
                  if os.path.exists(marker_file):
                      os.remove(marker_file)
                      logger.info(f"Marker file rimosso dopo errore generico: {marker_file}")
          except Exception as cleanup_error:
              logger.warning(f"Errore nella rimozione del marker: {cleanup_error}")
          raise HTTPException(status_code=500, detail=str(e))


@router.post("/publish-data-factory")
async def publish_data_factory(
    year_month_values: Optional[List[str]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Trigger Azure Data Factory pipeline execution for monthly reports.

    Args:
        year_month_values: Optional list of YYMM values (e.g., ["2511", "2510"]).
                          If not provided, uses current mese from repo_update_info.
        db: Database session
        current_user: Authenticated user

    Returns:
        Dict with status, workspace, year_months processed, and results
    """
    try:
        logger.info(f"Starting Data Factory publish for user: {current_user.username}, bank: {current_user.bank}")

        # 1. Get anno and mese from repo_update_info
        repo_info = db.query(RepoUpdateInfo).filter(
            func.lower(RepoUpdateInfo.bank) == func.lower(current_user.bank)
        ).first()

        anno = repo_info.anno if repo_info else 2025
        mese = repo_info.mese if repo_info else None

        # If year_month_values not provided, use current mese
        if not year_month_values:
            if not mese:
                raise HTTPException(
                    status_code=400,
                    detail="Nessun mese disponibile in repo_update_info e nessun valore fornito"
                )
            year_month_values = [f"{str(anno)[-2:]}{mese:02d}"]

        logger.info(f"Processing year_month values: {year_month_values}")

        # 2. Start publish tracking
        if not publish_tracker.start_publish_run(db, update_interval=5, phase="data_factory"):
            raise HTTPException(
                status_code=409,
                detail="Un'operazione di pubblicazione Ã¨ giÃ  in corso. Attendere il completamento."
            )

        # 3. Query workspace from report_mapping
        result = db.query(ReportMapping.ws_precheck).filter(
            ReportMapping.Type_reportisica == "Mensile",
            func.lower(ReportMapping.bank) == func.lower(current_user.bank)
        ).first()

        workspace = result[0] if result else "MAIN_BNF_DEV"
        logger.info(f"Using Azure Data Factory workspace: {workspace}")

        # 4. Execute script
        def run_script():
            import io
            import contextlib

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            try:
                with contextlib.redirect_stdout(stdout_capture), \
                     contextlib.redirect_stderr(stderr_capture):

                    from scripts import data_factory
                    status = data_factory.main(year_month_values, workspace)

                    # Controlla se c'Ã¨ un errore nel risultato di data_factory
                    if isinstance(status, dict) and "error" in status:
                        stderr_capture.write(f"Data factory error: {status['error']}\n")
                        print("\n[RESULT]")
                        print(json.dumps(status, indent=2))
                        return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

                    # Print result as JSON for parsing
                    print("\n[RESULT]")
                    print(json.dumps(status, indent=2))

                return 0, stdout_capture.getvalue(), stderr_capture.getvalue()

            except Exception as e:
                stderr_capture.write(f"Exception in data_factory script: {str(e)}\n")
                stderr_capture.write(traceback.format_exc())
                return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        returncode, stdout, stderr = await loop.run_in_executor(None, run_script)

        logger.info(f"Script execution completed with return code: {returncode}")

        # 5. Parse results from stdout
        result_match = re.search(r'\[RESULT\]\s*(\{.*\})', stdout, re.DOTALL)
        result_dict = json.loads(result_match.group(1)) if result_match else {}

        logger.info(f"Parsed results: {result_dict}")

        # 6. Save logs to database for each year_month
        success_count = 0
        failed_count = 0

        for year_month in year_month_values:
            status_value = result_dict.get(year_month, "Unknown")

            # Determine if succeeded or failed
            is_success = status_value == "Succeeded"

            if is_success:
                success_count += 1
            else:
                failed_count += 1

            # Parse mese from year_month (last 2 digits)
            try:
                mese_value = int(year_month[-2:])
            except (ValueError, IndexError):
                mese_value = mese

            log_entry = PublicationLog(
                bank=current_user.bank,
                workspace=workspace,
                packages=[year_month],  # Store year_month as package
                publication_type="data_factory",
                status="success" if is_success else "error",
                output=json.dumps(status_value, indent=2) if is_success else None,
                error=json.dumps(status_value, indent=2) if not is_success else None,
                user_id=current_user.id,
                anno=anno,
                settimana=None,  # Not applicable for monthly
                mese=mese_value
            )
            db.add(log_entry)

        db.commit()
        logger.info(f"Saved {len(year_month_values)} publication logs to database")

        # 7. Update publish tracking with counters
        publish_tracker.update_publish_run(
            db=db,
            files_processed=len(year_month_values),
            files_copied=success_count,
            files_failed=failed_count
        )

        # 8. End publish tracking
        if returncode != 0:
            error_msg = stderr[:500] if stderr else "Script execution failed"
            publish_tracker.end_publish_run(db=db, error_details=error_msg)
            raise HTTPException(
                status_code=500,
                detail=f"Errore durante l'esecuzione dello script Data Factory: {error_msg}"
            )

        publish_tracker.end_publish_run(db=db, error_details=None)

        return {
            "status": "success",
            "workspace": workspace,
            "year_months": year_month_values,
            "results": result_dict,
            "summary": {
                "total": len(year_month_values),
                "succeeded": success_count,
                "failed": failed_count
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in publish_data_factory: {e}", exc_info=True)

        # Try to end publish tracking
        try:
            publish_tracker.end_publish_run(db=db, error_details=str(e)[:500])
        except Exception as tracker_error:
            logger.error(f"Failed to end publish tracking: {tracker_error}")

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/publication-logs/latest")
def get_latest_publication_logs(
    publication_type: Optional[str] = Query(None, description="Filtra per tipo: precheck o production"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera l'ultimo log di pubblicazione per ogni package della banca dell'utente.
    Restituisce i dati pronti per popolare la tabella di pubblicazione.
    """
    from sqlalchemy import func

    try:
        # Se il modello non esiste nel runtime, fai fallback a SQL diretto
        if not hasattr(models, "PublicationLog"):
            logger.error("PublicationLog model missing; falling back to raw SQL")
            # Verifica che la tabella esista
            tbl = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='publication_logs'")).fetchone()
            if not tbl:
                logger.error("Table publication_logs not found")
                return []

            # Costruisci query semplice; filtra per bank e, se richiesto, per publication_type
            base_sql = """
                SELECT workspace, bank, publication_type, status, output, error, packages, timestamp, anno, settimana, mese
                FROM publication_logs
                WHERE LOWER(bank) = LOWER(:bank)
            """
            params = {"bank": current_user.bank}
            if publication_type:
                base_sql += " AND publication_type = :ptype"
                params["ptype"] = publication_type
            base_sql += " ORDER BY timestamp DESC LIMIT 200"

            rows = db.execute(text(base_sql), params).fetchall()
            if not rows:
                return []

            # Raggruppa per package (piÃ¹ recente per package)
            latest_by_package = {}
            for r in rows:
                workspace, _, ptype, status, output, error, packages, ts, anno, settimana, mese = r
                # packages puÃ² essere JSON string â†’ normalizza
                pkg_list = []
                try:
                    if isinstance(packages, str):
                        pkg_list = json.loads(packages)
                    elif isinstance(packages, (list, tuple)):
                        pkg_list = list(packages)
                except Exception:
                    pkg_list = []

                for package in pkg_list or []:
                    # Se non presente, memorizza la riga piÃ¹ recente
                    if package not in latest_by_package:
                        latest_by_package[package] = {
                            "workspace": workspace,
                            "publication_type": ptype,
                            "status": status,
                            "output": output,
                            "error": error,
                            "timestamp": ts,
                            "anno": anno,
                            "settimana": settimana,
                            "mese": mese
                        }

            result = []
            for package, info in latest_by_package.items():
                log_text = info["output"] if info["status"] == "success" else info["error"]
                package_message = log_text

                # Prova a estrarre il messaggio specifico per package se log Ã¨ JSON
                if log_text:
                    try:
                        log_dict = json.loads(log_text) if isinstance(log_text, str) else log_text
                        if isinstance(log_dict, dict) and package in log_dict:
                            package_message = log_dict[package]
                    except Exception:
                        package_message = log_text

                # Determina lo stato in base al messaggio e allo status
                pre_check_status = False
                prod_status = False

                if info["publication_type"] == "precheck":
                    if info["status"] == "success" and package_message and "successo" in package_message.lower():
                        pre_check_status = True
                    elif package_message and "timeout" in package_message.lower():
                        pre_check_status = "timeout"
                    elif info["status"] == "error" or (package_message and ("errore" in package_message.lower() or "error" in package_message.lower())):
                        pre_check_status = "error"
                elif info["publication_type"] == "production":
                    if info["status"] == "success" and package_message and "successo" in package_message.lower():
                        prod_status = True
                    elif package_message and "timeout" in package_message.lower():
                        prod_status = "timeout"
                    elif info["status"] == "error" or (package_message and ("errore" in package_message.lower() or "error" in package_message.lower())):
                        prod_status = "error"

                result.append({
                    "package": package,
                    "workspace": info["workspace"],
                    "user": "N/D",
                    "data_esecuzione": info["timestamp"],
                    "pre_check": pre_check_status,
                    "prod": prod_status,
                    "log": package_message,
                    "status": info["status"],
                    "anno": info["anno"],
                    "settimana": info["settimana"],
                    "mese": info["mese"]
                })

            return result

        # Percorso normale con ORM se il modello esiste
        query = db.query(models.PublicationLog).filter(
            func.lower(models.PublicationLog.bank) == func.lower(current_user.bank)
        )
        if publication_type:
            query = query.filter(models.PublicationLog.publication_type == publication_type)

        logs = query.order_by(desc(models.PublicationLog.timestamp)).all()
        if not logs:
            return []

        latest_by_package = {}
        for log in logs:
            for package in log.packages:
                if package not in latest_by_package:
                    latest_by_package[package] = log

        result = []
        for package, log in latest_by_package.items():
            log_text = log.output if log.status == "success" else log.error
            package_message = log_text
            if log_text:
                try:
                    log_dict = json.loads(log_text) if isinstance(log_text, str) else log_text
                    if isinstance(log_dict, dict) and package in log_dict:
                        package_message = log_dict[package]
                except (json.JSONDecodeError, TypeError, KeyError):
                    package_message = log_text

            # Determina lo stato in base al messaggio e allo status
            pre_check_status = False
            prod_status = False

            if log.publication_type == "precheck":
                if log.status == "success" and package_message and "successo" in package_message.lower():
                    pre_check_status = True
                elif package_message and "timeout" in package_message.lower():
                    pre_check_status = "timeout"
                elif log.status == "error" or (package_message and ("errore" in package_message.lower() or "error" in package_message.lower())):
                    pre_check_status = "error"
            elif log.publication_type == "production":
                if log.status == "success" and package_message and "successo" in package_message.lower():
                    prod_status = True
                elif package_message and "timeout" in package_message.lower():
                    prod_status = "timeout"
                elif log.status == "error" or (package_message and ("errore" in package_message.lower() or "error" in package_message.lower())):
                    prod_status = "error"

            result.append({
                "package": package,
                "workspace": log.workspace,
                "user": "N/D",
                "data_esecuzione": log.timestamp,
                "pre_check": pre_check_status,
                "prod": prod_status,
                "log": package_message,
                "status": log.status
            })
        return result
    except Exception as e:
        logger.error("get_latest_publication_logs failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/packages-ready-test")
def get_packages_ready_test():
    """Test endpoint completamente pubblico"""
    from db import SessionLocal
    db = SessionLocal()
    try:
        query = db.query(
            models.ReportMapping.package,
            models.ReportMapping.ws_precheck,
            models.ReportMapping.ws_production,
            models.ReportMapping.bank
        ).filter(
            models.ReportMapping.Type_reportisica == "Settimanale"
        )
        results = query.all()
        return {"count": len(results), "data": [{"package": r[0], "ws": r[1], "bank": r[3]} for r in results if r[0]]}
    except Exception as e:
        logger.error(f"packages_ready_test failed: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()

@router.get("/test-packages-v2")
def get_packages_ready(
    type_reportistica: Optional[str] = Query(None, description="Filtra per tipo: Settimanale o Mensile"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Recupera i package pronti dalla tabella report_mapping filtrati per banca utente con stato da publication_logs"""
    from sqlalchemy import func, and_
    import json

    logger.info(f"test-packages-v2 endpoint called for user: {current_user.username}, bank: {current_user.bank}, type: {type_reportistica}")

    try:
        # Recupera il periodo corrente da repo_update_info per confrontarlo con le pubblicazioni
        repo_info_query = db.query(models.RepoUpdateInfo).filter(
            func.lower(models.RepoUpdateInfo.bank) == func.lower(current_user.bank)
        ).first()

        current_anno = repo_info_query.anno if repo_info_query else None
        current_settimana = repo_info_query.settimana if repo_info_query else None
        current_mese = repo_info_query.mese if repo_info_query else None

        logger.info(f"Current period from repo_update_info: anno={current_anno}, settimana={current_settimana}, mese={current_mese}")

        # Filtra per banca dell'utente corrente (case-insensitive)
        # NOTA: Usa query SQL diretta per poter usare rowid per l'ordinamento
        sql = text("""
            SELECT package, ws_precheck, ws_production, bank, Type_reportisica
            FROM report_mapping
            WHERE LOWER(bank) = LOWER(:bank)
            AND (:type_reportistica IS NULL OR Type_reportisica = :type_reportistica)
            ORDER BY rowid
        """)

        params = {
            "bank": current_user.bank,
            "type_reportistica": type_reportistica
        }

        results = db.execute(sql, params).fetchall()
        logger.debug(f"Found {len(results)} packages for bank {current_user.bank}")

        # Per ogni package, cerca l'ultimo log in publication_logs
        packages_with_status = []
        for r in results:
            if not r[0]:  # Skip se package Ã¨ None
                continue

            package_name = r[0]

            # Cerca tutti i log recenti per questa banca - PRECHECK
            precheck_logs = db.query(models.PublicationLog).filter(
                and_(
                    func.lower(models.PublicationLog.bank) == func.lower(current_user.bank),
                    models.PublicationLog.publication_type == 'precheck'
                )
            ).order_by(models.PublicationLog.timestamp.desc()).limit(50).all()

            # Cerca tutti i log recenti per questa banca - PRODUCTION
            production_logs = db.query(models.PublicationLog).filter(
                and_(
                    func.lower(models.PublicationLog.bank) == func.lower(current_user.bank),
                    models.PublicationLog.publication_type == 'production'
                )
            ).order_by(models.PublicationLog.timestamp.desc()).limit(50).all()

            # Variabili per precheck
            pre_check_status = False
            dettagli_precheck = "In attesa di elaborazione"
            error_precheck = None
            data_esecuzione_precheck = None
            user_precheck = "N/D"
            anno_precheck = None
            settimana_precheck = None
            mese_precheck = None

            # Variabili per production
            prod_status = False
            dettagli_prod = "In attesa di elaborazione"
            error_prod = None
            data_esecuzione_prod = None
            user_prod = "N/D"
            anno_prod = None
            settimana_prod = None
            mese_prod = None

            # Cerca il log di PRECHECK che contiene questo package specifico
            for log in precheck_logs:
                try:
                    packages_list = log.packages if isinstance(log.packages, list) else json.loads(log.packages)

                    # Se questo log contiene il package che stiamo cercando
                    if package_name in packages_list:
                        logger.info(f"Found precheck log for package {package_name}: log_id={log.id}, status={log.status}")
                        data_esecuzione_precheck = log.timestamp
                        user_precheck = "Sistema" if not log.user_id else f"User #{log.user_id}"
                        anno_precheck = log.anno
                        settimana_precheck = log.settimana
                        mese_precheck = log.mese

                        # Prendi il messaggio dall'output o dall'error
                        message = log.output if log.output else (log.error if log.error else "")
                        logger.debug(f"Message for {package_name}: {message[:200] if message else 'EMPTY'}")

                        # Salva il campo error separatamente se presente
                        error_precheck = log.error if log.error else None

                        # Determina lo stato in base al CONTENUTO del messaggio
                        if "successo" in message.lower():
                            pre_check_status = True  # Verde
                            dettagli_precheck = message
                            logger.info(f"Package {package_name}: status=TRUE (found 'successo' in message)")
                        elif "timeout" in message.lower():
                            pre_check_status = "timeout"  # Giallo/Arancione
                            dettagli_precheck = message
                            logger.info(f"Package {package_name}: status=TIMEOUT")
                        elif "errore" in message.lower() or "error" in message.lower():
                            pre_check_status = "error"  # Rosso
                            dettagli_precheck = message
                            logger.info(f"Package {package_name}: status=ERROR")
                        else:
                            # Fallback sul campo status del log
                            if log.status == 'success':
                                pre_check_status = True
                                dettagli_precheck = message if message else "Aggiornamento completato con successo"
                                logger.info(f"Package {package_name}: status=TRUE (from log.status)")
                            else:
                                pre_check_status = False
                                dettagli_precheck = message if message else "Errore durante l'aggiornamento"
                                logger.warning(f"Package {package_name}: status=FALSE (log.status={log.status})")

                        # Abbiamo trovato il log per questo package, usiamo il piÃ¹ recente
                        break
                except Exception as e:
                    logger.warning(f"Error parsing precheck log for {package_name}: {e}")
                    continue

            # Cerca il log di PRODUCTION che contiene questo package specifico
            for log in production_logs:
                try:
                    packages_list = log.packages if isinstance(log.packages, list) else json.loads(log.packages)

                    # Se questo log contiene il package che stiamo cercando
                    if package_name in packages_list:
                        data_esecuzione_prod = log.timestamp
                        user_prod = "Sistema" if not log.user_id else f"User #{log.user_id}"
                        anno_prod = log.anno
                        settimana_prod = log.settimana
                        mese_prod = log.mese

                        # Prendi il messaggio dall'output o dall'error
                        message = log.output if log.output else (log.error if log.error else "")

                        # Salva il campo error separatamente se presente
                        error_prod = log.error if log.error else None

                        # Determina lo stato in base al CONTENUTO del messaggio
                        if "successo" in message.lower():
                            prod_status = True  # Verde
                            dettagli_prod = message
                        elif "timeout" in message.lower():
                            prod_status = "timeout"  # Giallo/Arancione
                            dettagli_prod = message
                        elif "errore" in message.lower() or "error" in message.lower():
                            prod_status = "error"  # Rosso
                            dettagli_prod = message
                        else:
                            # Fallback sul campo status del log
                            if log.status == 'success':
                                prod_status = True
                                dettagli_prod = message if message else "Pubblicazione in produzione completata con successo"
                            else:
                                prod_status = False
                                dettagli_prod = message if message else "Errore durante la pubblicazione in produzione"

                        # Abbiamo trovato il log per questo package, usiamo il piÃ¹ recente
                        break
                except Exception as e:
                    logger.warning(f"Error parsing production log for {package_name}: {e}")
                    continue

            # RESET LOGIC: Confronta il periodo della pubblicazione con quello corrente
            # Se non corrispondono, resetta i semafori ma mantieni i dati storici
            is_settimanale = type_reportistica == "Settimanale"
            is_mensile = type_reportistica == "Mensile"

            # Controlla se la pubblicazione PRE-CHECK Ã¨ del periodo corrente
            if pre_check_status and pre_check_status != False:
                if is_settimanale:
                    # Per settimanale: confronta anno + settimana
                    if (anno_precheck != current_anno or settimana_precheck != current_settimana):
                        logger.info(f"Resetting precheck status for {package_name}: published in {anno_precheck}-W{settimana_precheck}, current is {current_anno}-W{current_settimana}")
                        pre_check_status = False
                        dettagli_precheck = "Pubblicazione di un periodo precedente"
                elif is_mensile:
                    # Per mensile: confronta anno + mese
                    if (anno_precheck != current_anno or mese_precheck != current_mese):
                        logger.info(f"Resetting precheck status for {package_name}: published in {anno_precheck}-M{mese_precheck}, current is {current_anno}-M{current_mese}")
                        pre_check_status = False
                        dettagli_precheck = "Pubblicazione di un periodo precedente"

            # Controlla se la pubblicazione PRODUCTION Ã¨ del periodo corrente
            if prod_status and prod_status != False:
                if is_settimanale:
                    # Per settimanale: confronta anno + settimana
                    if (anno_prod != current_anno or settimana_prod != current_settimana):
                        logger.info(f"Resetting production status for {package_name}: published in {anno_prod}-W{settimana_prod}, current is {current_anno}-W{current_settimana}")
                        prod_status = False
                        dettagli_prod = "Pubblicazione di un periodo precedente"
                elif is_mensile:
                    # Per mensile: confronta anno + mese
                    if (anno_prod != current_anno or mese_prod != current_mese):
                        logger.info(f"Resetting production status for {package_name}: published in {anno_prod}-M{mese_prod}, current is {current_anno}-M{current_mese}")
                        prod_status = False
                        dettagli_prod = "Pubblicazione di un periodo precedente"

            packages_with_status.append({
                "package": package_name,
                "ws_precheck": r[1],
                "ws_produzione": r[2],
                "bank": r[3],
                "type_reportistica": r[4],
                "user": user_precheck,
                "data_esecuzione": data_esecuzione_precheck,
                "pre_check": pre_check_status,
                "prod": prod_status,
                "dettagli": dettagli_precheck,
                "error_precheck": error_precheck,
                "user_prod": user_prod,
                "data_esecuzione_prod": data_esecuzione_prod,
                "dettagli_prod": dettagli_prod,
                "error_prod": error_prod,
                "anno_precheck": anno_precheck,
                "settimana_precheck": settimana_precheck,
                "mese_precheck": mese_precheck,
                "anno_prod": anno_prod,
                "settimana_prod": settimana_prod,
                "mese_prod": mese_prod
            })

        return packages_with_status

    except Exception as e:
        logger.error(f"test-packages-v2 failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{reportistica_id}", response_model=schemas.ReportisticaInDB)
def get_reportistica_item(
    reportistica_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera un elemento di reportistica specifico per ID della propria banca.

    Note:
        - PuÃ² visualizzare solo elementi della propria banca
    """
    item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # âœ… Verifica che l'elemento appartenga alla banca dell'utente
    if item.banca != current_user.bank:
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per visualizzare questo elemento (appartiene a un'altra banca)"
        )

    return item

@router.post("/", response_model=schemas.ReportisticaInDB)
def create_reportistica_item(
    reportistica: schemas.ReportisticaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un nuovo elemento di reportistica per la banca dell'utente loggato.

    Note:
        - banca viene automaticamente settata a current_user.bank
        - La coppia (nome_file, banca) deve essere unica
    """
    logger.info(f"Creating reportistica item for bank: {current_user.bank}, file: {reportistica.nome_file}")

    # âœ… Verifica che la coppia (nome_file, banca utente) non esista giÃ 
    existing_item = crud.get_reportistica_by_nome_file(
        db=db,
        nome_file=reportistica.nome_file,
        banca=current_user.bank  # âœ… Usa la banca dell'utente loggato
    )
    if existing_item:
        raise HTTPException(
            status_code=400,
            detail=f"Un elemento con nome file '{reportistica.nome_file}' esiste giÃ  per la tua banca"
        )

    # âœ… Passa la banca dell'utente loggato
    return crud.create_reportistica(
        db=db,
        reportistica=reportistica,
        banca=current_user.bank  # âœ… Automatico
    )

@router.put("/{reportistica_id}", response_model=schemas.ReportisticaInDB)
def update_reportistica_item(
    reportistica_id: int,
    reportistica_data: schemas.ReportisticaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna un elemento di reportistica della banca dell'utente loggato.

    Note:
        - PuÃ² modificare solo elementi della propria banca
        - Se viene modificato nome_file, verifica che non esista giÃ  nella banca
    """
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # âœ… Verifica che l'elemento appartenga alla banca dell'utente (case-insensitive)
    if existing_item.banca.lower() != current_user.bank.lower():
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per modificare questo elemento (appartiene a un'altra banca)"
        )

    # âœ… Se il nome file viene cambiato, verifica che non esista giÃ  nella stessa banca
    if reportistica_data.nome_file and reportistica_data.nome_file != existing_item.nome_file:
        existing_with_name = crud.get_reportistica_by_nome_file(
            db=db,
            nome_file=reportistica_data.nome_file,
            banca=current_user.bank  # âœ… Verifica solo nella banca dell'utente
        )
        if existing_with_name and existing_with_name.id != reportistica_id:
            raise HTTPException(
                status_code=400,
                detail=f"Un elemento con nome file '{reportistica_data.nome_file}' esiste giÃ  per la tua banca"
            )

    return crud.update_reportistica(db=db, reportistica_id=reportistica_id, reportistica_data=reportistica_data)

@router.delete("/{reportistica_id}")
def delete_reportistica_item(
    reportistica_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Elimina un elemento di reportistica della banca dell'utente loggato.

    Note:
        - PuÃ² eliminare solo elementi della propria banca
    """
    # âœ… Prima verifica che l'elemento esista e appartenga alla banca dell'utente
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # âœ… Verifica che l'elemento appartenga alla banca dell'utente
    if existing_item.banca != current_user.bank:
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per eliminare questo elemento (appartiene a un'altra banca)"
        )

    item = crud.delete_reportistica(db=db, reportistica_id=reportistica_id)
    return {"message": "Elemento reportistica eliminato con successo"}

@router.patch("/{reportistica_id}/disponibilita", response_model=schemas.ReportisticaInDB)
def toggle_disponibilita_server(
    reportistica_id: int,
    disponibilita: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna solo lo stato di disponibilitÃ  server per un elemento della propria banca.

    Note:
        - PuÃ² modificare solo elementi della propria banca
    """
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # âœ… Verifica che l'elemento appartenga alla banca dell'utente (case-insensitive)
    if existing_item.banca.lower() != current_user.bank.lower():
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per modificare questo elemento (appartiene a un'altra banca)"
        )

    update_data = schemas.ReportisticaUpdate(disponibilita_server=disponibilita)
    return crud.update_reportistica(db=db, reportistica_id=reportistica_id, reportistica_data=update_data)

def _resolve_log_status(log_status, log_output, log_error):
    """
    Traduce un record di publication_logs in True (verde) / "error" (rosso).
    Stessa regola usata da get_packages_ready_data(), cosi' il blocco della Homepage
    coincide con i pallini rossi mostrati in tabella.
    """
    full_message = ""
    if log_output:
        full_message += str(log_output) + " "
    if log_error:
        full_message += str(log_error)
    full_message_lower = full_message.lower()

    if "errore" in full_message_lower or "error" in full_message_lower or "timeout" in full_message_lower:
        return "error"
    if "successo" in full_message_lower or log_status == "success":
        return True
    return "error"


def _compute_blocked_packages(
    db: Session,
    bank: str,
    publication_type: str,
    anno: Optional[int],
    settimana: Optional[int],
    mese: Optional[int],
    is_weekly: bool,
    candidates: List[str],
    packages_in_run: List[str],
) -> List[str]:
    """
    Package che risultano in ERRORE a DB per il periodo corrente e che NON fanno parte
    di questa esecuzione. Bloccano l'aggiornamento dei package finali (Homepage).

    Due regole importanti:
    - un package senza alcun log non blocca: non e' "in errore", semplicemente non e'
      ancora stato eseguito (caso normale quando si pubblica solo una selezione);
    - conta solo l'ultimo log a package singolo del periodo corrente, esattamente come
      fa la tabella in UI.
    """
    in_run = set(packages_in_run)
    to_check = [pkg for pkg in candidates if pkg not in in_run]
    if not to_check:
        return []

    rows = db.execute(
        text(
            """
            SELECT packages, status, output, error, anno, settimana, mese
            FROM publication_logs
            WHERE LOWER(bank) = LOWER(:bank)
              AND publication_type = :pub_type
              AND anno = :anno
            ORDER BY timestamp DESC, id DESC
            """
        ),
        {"bank": bank, "pub_type": publication_type, "anno": anno},
    ).fetchall()

    latest: Dict[str, Any] = {}
    for row in rows:
        raw_packages, log_status, log_output, log_error, log_anno, log_settimana, log_mese = row
        try:
            pkg_list = json.loads(raw_packages) if isinstance(raw_packages, str) else raw_packages
        except Exception:
            continue
        # I log multi-package non sono attribuibili a un singolo package: ignorati.
        if not pkg_list or len(pkg_list) != 1:
            continue
        pkg_name = pkg_list[0]
        if pkg_name not in to_check or pkg_name in latest:
            continue
        # Il semaforo vale solo per il periodo corrente.
        if is_weekly and log_settimana != settimana:
            continue
        if not is_weekly and log_mese != mese:
            continue
        latest[pkg_name] = _resolve_log_status(log_status, log_output, log_error)

    blocked = [pkg for pkg in to_check if latest.get(pkg) == "error"]
    if blocked:
        logger.info(
            f"Package gia' in errore a DB per il periodo corrente (bloccano i package finali): {blocked}"
        )
    return blocked


@router.post("/publish-precheck")
async def publish_precheck(
    periodicity: str = Query(..., description="PeriodicitÃ : 'settimanale' o 'mensile'"),
    selected_packages: Optional[List[str]] = Query(None, description="Lista dei package selezionati (opzionale)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    import traceback
    from sqlalchemy import func
    from db import publish_tracker

    logger.info(f"publish_precheck called for user: {current_user.username}, bank: {current_user.bank}, periodicity: {periodicity}, selected_packages: {selected_packages}")

    try:
        # Normalizza periodicitÃ 
        is_mensile = periodicity.lower() == "mensile"
        periodicity_db = "Mensile" if is_mensile else "Settimanale"

        # Recupera anno, settimana e mese da repo_update_info per questo utente
        repo_info_query = db.query(models.RepoUpdateInfo).filter(
            func.lower(models.RepoUpdateInfo.bank) == func.lower(current_user.bank)
        ).first()

        anno = repo_info_query.anno if repo_info_query else 2025
        settimana = repo_info_query.settimana if repo_info_query and not is_mensile else None
        mese = repo_info_query.mese if repo_info_query and is_mensile else None

        logger.info(f"Publishing for period: anno={anno}, settimana={settimana}, mese={mese}, periodicity_db={periodicity_db}")

        # Avvia il tracking della publish run
        if not publish_tracker.start_publish_run(db, update_interval=5, phase="precheck"):
            raise HTTPException(
                status_code=409,
                detail="Un'operazione di pubblicazione Ã¨ giÃ  in corso. Attendere il completamento."
            )

        # Prendi i dati dalla tabella report_mapping filtrati per banca e periodicitÃ 
        # Usa raw SQL con ORDER BY rowid per mantenere l'ordine del database
        from sqlalchemy import text
        sql = text("""
            SELECT ws_precheck, package, datafactory, obbligatorio
            FROM report_mapping
            WHERE Type_reportisica = :periodicity
            AND LOWER(bank) = LOWER(:bank)
            ORDER BY rowid
        """)

        results = db.execute(sql, {
            "periodicity": periodicity_db,
            "bank": current_user.bank
        }).fetchall()
        logger.debug(f"Found {len(results)} records from report_mapping")

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Nessun package trovato per la banca {current_user.bank}"
            )

        # Estrai workspace Power BI (per settimanale o fase 2 mensile)
        workspace_powerbi = results[0][0]

        # Estrai workspace Data Factory (solo per mensile)
        workspace_datafactory = results[0][2] if len(results[0]) > 2 else None

        # Estrai lista dei package
        all_packages = [row[1] for row in results if row[1]]

        # Se selected_packages Ã¨ fornito, filtra solo quelli selezionati
        if selected_packages:
            pbi_packages = [pkg for pkg in all_packages if pkg in selected_packages]
            logger.info(f"Filtered packages based on selection: {pbi_packages} (from {len(all_packages)} total)")
        else:
            pbi_packages = all_packages

        # Package "finali": Obbligatorio = Y nella mappatura (oggi solo 'Homepage').
        # Aggregano i dati degli altri, quindi vanno aggiornati per ultimi e solo se
        # tutto il resto e' andato a buon fine.
        mandatory_packages = {
            row[1] for row in results
            if row[1] and len(row) > 3 and str(row[3] or "").strip().upper() == "Y"
        }
        final_packages = [pkg for pkg in pbi_packages if pkg in mandatory_packages]
        normal_packages = [pkg for pkg in pbi_packages if pkg not in mandatory_packages]

        # Package gia' rossi a DB per questo periodo e non rilanciati ora: bloccano
        # comunque i package finali.
        try:
            blocked_by = _compute_blocked_packages(
                db=db,
                bank=current_user.bank,
                publication_type="precheck",
                anno=anno,
                settimana=settimana,
                mese=mese,
                is_weekly=not is_mensile,
                candidates=[pkg for pkg in all_packages if pkg not in mandatory_packages],
                packages_in_run=normal_packages,
            )
        except Exception as e:
            logger.warning(f"Impossibile calcolare i package bloccanti da DB: {e}")
            blocked_by = []

        logger.info(f"Package normali: {normal_packages}")
        logger.info(f"Package finali: {final_packages}")
        logger.info(f"Package bloccanti (errori pregressi a DB): {blocked_by}")

        logger.info(f"Workspace Power BI: {workspace_powerbi}")
        logger.info(f"Workspace Data Factory: {workspace_datafactory}")
        logger.info(f"Packages to publish: {pbi_packages}")

        # Importa e chiama direttamente lo script invece di usare subprocess
        # Questo permette di usare le dipendenze incluse nel bundle PyInstaller
        def run_script():
            import io
            import contextlib

            # Cattura stdout/stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            try:
                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                    import json

                    if is_mensile:
                        # ==========================================
                        # MENSILE: FLUSSO A 2 FASI
                        # ==========================================

                        # FASE 1: Azure Data Factory
                        if workspace_datafactory:
                            logger.info("="*80)
                            logger.info("FASE 1: Esecuzione Azure Data Factory")
                            logger.info("="*80)

                            from scripts import data_factory

                            # Prepara year_month_values (es. ["2511"])
                            year_month_values = [f"{str(anno)[-2:]}{mese:02d}"]
                            logger.info(f"Calling data_factory.main with year_month={year_month_values}, workspace_datafactory={workspace_datafactory}")

                            try:
                                df_status = data_factory.main(year_month_values, workspace_datafactory)
                                logger.info(f"Data Factory result: {df_status}")

                                # Controlla se c'Ã¨ un errore nel risultato di data_factory
                                if isinstance(df_status, dict) and "error" in df_status:
                                    error_msg = f"FASE 1 FALLITA - Data Factory error: {df_status['error']}"
                                    logger.error(error_msg)
                                    stderr_capture.write(error_msg + "\n")
                                    print("\n[RESULT]")
                                    print(json.dumps(df_status, indent=2))
                                    return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

                                # Verifica se Data Factory ha avuto successo
                                year_month = year_month_values[0]
                                if isinstance(df_status, dict):
                                    df_result = df_status.get(year_month, "Unknown")
                                    if df_result != "Succeeded":
                                        error_msg = f"FASE 1 FALLITA - Data Factory non ha completato con successo: {df_result}"
                                        logger.error(error_msg)
                                        stderr_capture.write(error_msg + "\n")
                                        print("\n[RESULT]")
                                        print(json.dumps(df_status, indent=2))
                                        return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

                                logger.info("FASE 1 COMPLETATA CON SUCCESSO!")

                            except Exception as e:
                                error_msg = f"FASE 1 FALLITA - Eccezione in data_factory.main: {str(e)}"
                                logger.error(error_msg)
                                import traceback
                                stderr_capture.write(error_msg + "\n" + traceback.format_exc())
                                return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

                        # FASE 2: Power BI (solo se FASE 1 ha avuto successo)
                        logger.info("="*80)
                        logger.info("FASE 2: Pubblicazione Power BI")
                        logger.info("="*80)

                        from scripts import main as script_main
                        logger.info(f"Calling scripts.main.main with workspace_powerbi={workspace_powerbi}, packages={normal_packages}, final={final_packages}, blocked_by={blocked_by}")

                        try:
                            pbi_status = script_main.main(
                                workspace_powerbi, normal_packages,
                                final_packages=final_packages, blocked_by=blocked_by,
                                bank=current_user.bank
                            )
                            logger.info(f"Power BI result: {pbi_status}")

                            # Combina i risultati di entrambe le fasi
                            combined_status = {
                                "phase_1_datafactory": df_status if workspace_datafactory else "Skipped",
                                "phase_2_powerbi": pbi_status
                            }

                            print("\n[RESULT]")
                            print(json.dumps(combined_status, indent=2))
                            logger.info("FASE 2 COMPLETATA!")

                        except SystemExit as e:
                            error_msg = f"FASE 2 FALLITA - Script terminato: {str(e)}"
                            logger.error(error_msg)
                            stderr_capture.write(error_msg + "\n")
                            # Ritorna un risultato vuoto invece di crashare
                            combined_status = {
                                "phase_1_datafactory": df_status if workspace_datafactory else "Skipped",
                                "phase_2_powerbi": {},
                                "error": str(e)
                            }
                            print("\n[RESULT]")
                            print(json.dumps(combined_status, indent=2))
                            return 1, stdout_capture.getvalue(), stderr_capture.getvalue()
                        except Exception as e:
                            error_msg = f"FASE 2 FALLITA - Eccezione in scripts.main: {str(e)}"
                            logger.error(error_msg)
                            import traceback
                            stderr_capture.write(error_msg + "\n" + traceback.format_exc())
                            return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

                    else:
                        # ==========================================
                        # SETTIMANALE: SOLO POWER BI
                        # ==========================================
                        from scripts import main as script_main

                        logger.info(f"Calling scripts.main.main with workspace_powerbi={workspace_powerbi}, packages={normal_packages}, final={final_packages}, blocked_by={blocked_by}")
                        try:
                            status = script_main.main(
                                workspace_powerbi, normal_packages,
                                final_packages=final_packages, blocked_by=blocked_by,
                                bank=current_user.bank
                            )
                        except SystemExit as e:
                            error_msg = f"Script Power BI terminato con errore: {str(e)}"
                            logger.error(error_msg)
                            stderr_capture.write(error_msg + "\n")
                            status = {"error": str(e)}
                            print("\n[RESULT]")
                            print(json.dumps(status, indent=2))
                            return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

                        print("\n[RESULT]")
                        print(json.dumps(status, indent=2))

                return 0, stdout_capture.getvalue(), stderr_capture.getvalue()
            except Exception as e:
                import traceback
                error_msg = f"ERRORE GENERALE: {str(e)}"
                logger.error(error_msg)
                stderr_capture.write(traceback.format_exc())
                return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        returncode, stdout, stderr = await loop.run_in_executor(None, run_script)

        logger.info(f"Script completed with return code: {returncode}")
        logger.debug(f"Script stdout: {stdout}")
        if stderr:
            logger.warning(f"Script stderr: {stderr}")

        # Parse dello stdout per estrarre il JSON dei risultati
        import json
        import re

        packages_details = {}
        try:
            # Cerca il JSON nel formato [RESULT]\n{...}
            match = re.search(r'\[RESULT\]\s*(\{.*\})', stdout, re.DOTALL)
            if match:
                json_str = match.group(1)
                packages_details = json.loads(json_str)
                logger.debug(f"Parsed packages details: {packages_details}")
            else:
                logger.debug("No [RESULT] JSON found in output")
        except Exception as e:
            logger.warning(f"Error parsing packages details: {e}")

        # Salva log in base alla periodicitÃ 
        if is_mensile:
            # MENSILE: Salva log per entrambe le fasi
            logger.info("Salvando log per pubblicazione mensile (2 fasi)")

            # Estrai risultati delle 2 fasi
            phase_1_result = packages_details.get("phase_1_datafactory", {})
            phase_2_result = packages_details.get("phase_2_powerbi", {})

            year_month = f"{str(anno)[-2:]}{mese:02d}"

            # Determina lo status generale: successo solo se entrambe le fasi hanno successo
            phase_1_success = True  # Default True se skippata
            phase_2_success = False

            # Controlla se Data Factory Ã¨ stata eseguita o skippata
            if phase_1_result == "Skipped" or (isinstance(phase_1_result, dict) and len(phase_1_result) == 0):
                phase_1_success = True  # Se skippata, considerala come successo
                logger.info("FASE 1 Data Factory: Skipped")
            elif isinstance(phase_1_result, dict):
                df_status_value = phase_1_result.get(year_month, "Unknown")
                phase_1_success = df_status_value == "Succeeded"
                logger.info(f"FASE 1 Data Factory status: {df_status_value}")

            if isinstance(phase_2_result, dict):
                # Power BI ritorna un dizionario con i package come chiavi
                phase_2_success = all("successo" in str(v).lower() for v in phase_2_result.values())
                logger.info(f"FASE 2 Power BI success: {phase_2_success}")

            overall_success = phase_1_success and phase_2_success
            logger.info(f"Overall success: {overall_success}")

            # MENSILE: Salva un log per OGNI package (come settimanale)
            # Questo permette alla UI di mostrare lo stato di ogni package separatamente
            for package_name in pbi_packages:
                # Estrai il risultato specifico per questo package dalla fase 2
                package_detail = phase_2_result.get(package_name, "Nessun dettaglio disponibile")
                package_success = "successo" in str(package_detail).lower()

                # Combina i risultati di entrambe le fasi per questo package
                combined_result = {
                    "phase_1_datafactory": phase_1_result,
                    "phase_2_powerbi": {package_name: package_detail}
                }

                log_entry = models.PublicationLog(
                    bank=current_user.bank,
                    workspace=workspace_powerbi,  # Usa sempre workspace Power BI perchÃ© i package sono lÃ¬
                    packages=[package_name],  # Un package per volta (come settimanale)
                    publication_type="precheck",
                    status="success" if (phase_1_success and package_success) else "error",
                    output=json.dumps(combined_result, indent=2) if (phase_1_success and package_success) else None,
                    error=json.dumps(combined_result, indent=2) if not (phase_1_success and package_success) else None,
                    user_id=current_user.id,
                    anno=anno,
                    settimana=None,
                    mese=mese
                )
                db.add(log_entry)
                logger.info(f"Log salvato per package mensile {package_name}: status={'success' if (phase_1_success and package_success) else 'error'}")

        else:
            # SETTIMANALE: Salva per ogni package (scripts.main)
            logger.info("Salvando log per pubblicazione settimanale")

            for package_name in pbi_packages:
                package_detail = packages_details.get(package_name, stdout if returncode == 0 else stderr)

                log_entry = models.PublicationLog(
                    bank=current_user.bank,
                    workspace=workspace_powerbi,
                    packages=[package_name],  # Un package per volta
                    publication_type="precheck",
                    status="success" if returncode == 0 and "successo" in str(package_detail).lower() else "error",
                    output=package_detail if returncode == 0 or "successo" in str(package_detail).lower() else None,
                    error=package_detail if returncode != 0 or "errore" in str(package_detail).lower() or "timeout" in str(package_detail).lower() else None,
                    user_id=current_user.id,
                    anno=anno,
                    settimana=settimana,
                    mese=None
                )
                db.add(log_entry)

        db.commit()

        # Aggiorna i contatori della publish run
        if is_mensile:
            # Per mensile, conta i package individuali (non solo il year_month)
            total_packages = len(pbi_packages)
            phase_2_result = packages_details.get("phase_2_powerbi", {})
            success_count = sum(1 for pkg in pbi_packages if "successo" in str(phase_2_result.get(pkg, "")).lower())
            failed_count = total_packages - success_count
            logger.info(f"Mensile PRECHECK publish run stats: total={total_packages}, success={success_count}, failed={failed_count}")
        else:
            total_packages = len(pbi_packages)
            success_count = sum(1 for pkg in pbi_packages if "successo" in str(packages_details.get(pkg, "")).lower())
            failed_count = total_packages - success_count

        publish_tracker.update_publish_run(
            db=db,
            files_processed=total_packages,
            files_copied=success_count,
            files_skipped=0,
            files_failed=failed_count
        )

        if returncode != 0:
            # Chiudi la publish run con errore
            publish_tracker.end_publish_run(db=db, error_details=stderr[:500] if stderr else None)
            raise HTTPException(
                status_code=500,
                detail=f"Errore nell'esecuzione dello script: {stderr}"
            )

        # Chiudi la publish run con successo
        publish_tracker.end_publish_run(db=db, error_details=None)

        return {
            "status": "success",
            "message": "Pre-check pubblicato con successo",
            "workspace": workspace_datafactory if workspace_datafactory else workspace_powerbi,
            "packages": pbi_packages,
            "output": stdout,
            "packages_details": packages_details
        }

    except HTTPException as http_exc:
        # Chiudi la publish run con errore se Ã¨ stata avviata
        try:
            publish_tracker.end_publish_run(db=db, error_details=str(http_exc.detail)[:500])
        except:
            pass
        raise
    except Exception as e:
        logger.error(f"Exception in publish_precheck: {e}", exc_info=True)

        # Chiudi la publish run con errore
        try:
            publish_tracker.end_publish_run(db=db, error_details=str(e)[:500])
        except:
            pass

        # Salva anche gli errori nel database
        try:
            log_entry = models.PublicationLog(
                bank=current_user.bank if current_user else "unknown",
                workspace=workspace if 'workspace' in locals() else "unknown",
                packages=pbi_packages if 'pbi_packages' in locals() else [],
                publication_type="precheck",
                status="error",
                output=None,
                error=str(e),
                user_id=current_user.id if current_user else None,
                anno=anno if 'anno' in locals() else None,
                settimana=settimana if 'settimana' in locals() else None,
                mese=mese if 'mese' in locals() else None
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_error:
            logger.error(f"Failed to save error log to database: {db_error}")

        raise HTTPException(status_code=500, detail=str(e))


@router.post("/publish-production")
async def publish_production(
    periodicity: str = Query(..., description="PeriodicitÃ : 'settimanale' o 'mensile'"),
    selected_packages: Optional[List[str]] = Query(None, description="Lista dei package selezionati (opzionale)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    import traceback
    from sqlalchemy import func
    from db import publish_tracker

    logger.info(f"publish_production called for user: {current_user.username}, bank: {current_user.bank}, periodicity: {periodicity}, selected_packages: {selected_packages}")

    try:
        # Normalizza periodicitÃ 
        is_mensile = periodicity.lower() == "mensile"
        periodicity_db = "Mensile" if is_mensile else "Settimanale"

        # Recupera anno, settimana e mese da repo_update_info per questo utente
        repo_info_query = db.query(models.RepoUpdateInfo).filter(
            func.lower(models.RepoUpdateInfo.bank) == func.lower(current_user.bank)
        ).first()

        anno = repo_info_query.anno if repo_info_query else 2025
        settimana = repo_info_query.settimana if repo_info_query and not is_mensile else None
        mese = repo_info_query.mese if repo_info_query and is_mensile else None

        logger.info(f"Publishing to production for period: anno={anno}, settimana={settimana}, mese={mese}, periodicity_db={periodicity_db}")

        # Avvia il tracking della publish run con fase "production"
        if not publish_tracker.start_publish_run(db, update_interval=5, phase="production"):
            raise HTTPException(
                status_code=409,
                detail="Un'operazione di pubblicazione Ã¨ giÃ  in corso. Attendere il completamento."
            )
        # Prendi i dati dalla tabella report_mapping filtrati per banca e periodicitÃ 
        # Usa ws_production invece di ws_precheck
        # Usa raw SQL con ORDER BY rowid per mantenere l'ordine del database
        from sqlalchemy import text
        sql = text("""
            SELECT ws_production, package, datafactory, obbligatorio
            FROM report_mapping
            WHERE Type_reportisica = :periodicity
            AND LOWER(bank) = LOWER(:bank)
            ORDER BY rowid
        """)

        results = db.execute(sql, {
            "periodicity": periodicity_db,
            "bank": current_user.bank
        }).fetchall()
        logger.debug(f"Found {len(results)} records from report_mapping")

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Nessun package trovato per la banca {current_user.bank}"
            )

        # Estrai workspace Power BI (per settimanale o fase 2 mensile)
        workspace_powerbi = results[0][0]

        # Estrai workspace Data Factory (solo per mensile)
        workspace_datafactory = results[0][2] if len(results[0]) > 2 else None

        # Estrai lista dei package
        all_packages = [row[1] for row in results if row[1]]

        # Se selected_packages Ã¨ fornito, filtra solo quelli selezionati
        if selected_packages:
            pbi_packages = [pkg for pkg in all_packages if pkg in selected_packages]
            logger.info(f"Filtered packages based on selection: {pbi_packages} (from {len(all_packages)} total)")
        else:
            pbi_packages = all_packages

        # Package "finali": Obbligatorio = Y nella mappatura (oggi solo 'Homepage').
        # Aggregano i dati degli altri, quindi vanno aggiornati per ultimi e solo se
        # tutto il resto e' andato a buon fine.
        mandatory_packages = {
            row[1] for row in results
            if row[1] and len(row) > 3 and str(row[3] or "").strip().upper() == "Y"
        }
        final_packages = [pkg for pkg in pbi_packages if pkg in mandatory_packages]
        normal_packages = [pkg for pkg in pbi_packages if pkg not in mandatory_packages]

        # Package gia' rossi a DB per questo periodo e non rilanciati ora: bloccano
        # comunque i package finali.
        try:
            blocked_by = _compute_blocked_packages(
                db=db,
                bank=current_user.bank,
                publication_type="production",
                anno=anno,
                settimana=settimana,
                mese=mese,
                is_weekly=not is_mensile,
                candidates=[pkg for pkg in all_packages if pkg not in mandatory_packages],
                packages_in_run=normal_packages,
            )
        except Exception as e:
            logger.warning(f"Impossibile calcolare i package bloccanti da DB: {e}")
            blocked_by = []

        logger.info(f"Package normali: {normal_packages}")
        logger.info(f"Package finali: {final_packages}")
        logger.info(f"Package bloccanti (errori pregressi a DB): {blocked_by}")

        logger.info(f"Production Workspace Power BI: {workspace_powerbi}")
        logger.info(f"Production Workspace Data Factory: {workspace_datafactory}")
        logger.info(f"Packages to publish: {pbi_packages}")

        # Importa e chiama direttamente lo script invece di usare subprocess
        # Questo permette di usare le dipendenze incluse nel bundle PyInstaller
        def run_script():
            import io
            import contextlib

            # Cattura stdout/stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            try:
                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                    import json

                    if is_mensile:
                        # ==========================================
                        # MENSILE PRODUCTION: Solo Power BI (Data Factory giÃ  eseguito in precheck)
                        # ==========================================
                        logger.info("="*80)
                        logger.info("PRODUCTION FASE 2: Pubblicazione Power BI")
                        logger.info("="*80)

                        from scripts import main as script_main
                        logger.info(f"Calling scripts.main.main (PRODUCTION) with workspace_powerbi={workspace_powerbi}, packages={normal_packages}, final={final_packages}, blocked_by={blocked_by}")

                        try:
                            pbi_status = script_main.main(
                                workspace_powerbi, normal_packages,
                                final_packages=final_packages, blocked_by=blocked_by,
                                bank=current_user.bank
                            )
                            logger.info(f"Power BI result (PRODUCTION): {pbi_status}")

                            # Combina i risultati di entrambe le fasi
                            combined_status = {
                                "phase_1_datafactory": "Skipped",  # Data Factory temporaneamente disabilitata
                                "phase_2_powerbi": pbi_status
                            }

                            print("\n[RESULT]")
                            print(json.dumps(combined_status, indent=2))
                            logger.info("PRODUCTION FASE 2 COMPLETATA!")

                        except SystemExit as e:
                            error_msg = f"PRODUCTION FASE 2 FALLITA - Script terminato: {str(e)}"
                            logger.error(error_msg)
                            stderr_capture.write(error_msg + "\n")
                            # Ritorna un risultato vuoto invece di crashare
                            combined_status = {
                                "phase_1_datafactory": "Skipped",
                                "phase_2_powerbi": {},
                                "error": str(e)
                            }
                            print("\n[RESULT]")
                            print(json.dumps(combined_status, indent=2))
                            return 1, stdout_capture.getvalue(), stderr_capture.getvalue()
                        except Exception as e:
                            error_msg = f"PRODUCTION FASE 2 FALLITA - Eccezione in scripts.main: {str(e)}"
                            logger.error(error_msg)
                            import traceback
                            stderr_capture.write(error_msg + "\n" + traceback.format_exc())
                            return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

                    else:
                        # ==========================================
                        # SETTIMANALE PRODUCTION: SOLO POWER BI
                        # ==========================================
                        from scripts import main as script_main

                        logger.info(f"Calling scripts.main.main (PRODUCTION) with workspace_powerbi={workspace_powerbi}, packages={normal_packages}, final={final_packages}, blocked_by={blocked_by}")
                        try:
                            status = script_main.main(
                                workspace_powerbi, normal_packages,
                                final_packages=final_packages, blocked_by=blocked_by,
                                bank=current_user.bank
                            )
                        except SystemExit as e:
                            error_msg = f"PRODUCTION Script Power BI terminato con errore: {str(e)}"
                            logger.error(error_msg)
                            stderr_capture.write(error_msg + "\n")
                            status = {"error": str(e)}
                            print("\n[RESULT]")
                            print(json.dumps(status, indent=2))
                            return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

                        print("\n[RESULT]")
                        print(json.dumps(status, indent=2))

                return 0, stdout_capture.getvalue(), stderr_capture.getvalue()
            except Exception as e:
                import traceback
                error_msg = f"PRODUCTION ERRORE GENERALE: {str(e)}"
                logger.error(error_msg)
                stderr_capture.write(traceback.format_exc())
                return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        returncode, stdout, stderr = await loop.run_in_executor(None, run_script)

        logger.info(f"Script completed with return code: {returncode}")
        logger.debug(f"Script stdout: {stdout}")
        if stderr:
            logger.warning(f"Script stderr: {stderr}")

        # Parse dello stdout per estrarre il JSON dei risultati
        import json
        import re

        packages_details = {}
        try:
            # Cerca il JSON nel formato [RESULT]\n{...}
            match = re.search(r'\[RESULT\]\s*(\{.*\})', stdout, re.DOTALL)
            if match:
                json_str = match.group(1)
                packages_details = json.loads(json_str)
                logger.debug(f"Parsed packages details: {packages_details}")
            else:
                logger.debug("No [RESULT] JSON found in output")
        except Exception as e:
            logger.warning(f"Error parsing packages details: {e}")

        # Salva log in base alla periodicitÃ 
        # IMPORTANTE: publication_type = "production"
        if is_mensile:
            # MENSILE PRODUCTION: Salva log per entrambe le fasi
            logger.info("Salvando log per pubblicazione mensile PRODUCTION (2 fasi)")

            # Estrai risultati delle 2 fasi
            phase_1_result = packages_details.get("phase_1_datafactory", {})
            phase_2_result = packages_details.get("phase_2_powerbi", {})

            year_month = f"{str(anno)[-2:]}{mese:02d}"

            # Determina lo status generale: successo solo se entrambe le fasi hanno successo
            phase_1_success = False
            phase_2_success = False

            if isinstance(phase_1_result, dict) and phase_1_result != "Skipped":
                df_status_value = phase_1_result.get(year_month, "Unknown")
                phase_1_success = df_status_value == "Succeeded"
                logger.info(f"PRODUCTION FASE 1 Data Factory status: {df_status_value}")

            if isinstance(phase_2_result, dict):
                # Power BI ritorna un dizionario con i package come chiavi
                phase_2_success = all("successo" in str(v).lower() for v in phase_2_result.values())
                logger.info(f"PRODUCTION FASE 2 Power BI success: {phase_2_success}")

            overall_success = phase_1_success and phase_2_success
            logger.info(f"PRODUCTION Overall success: {overall_success}")

            # MENSILE PRODUCTION: Salva un log per OGNI package (come settimanale)
            # Questo permette alla UI di mostrare lo stato di ogni package separatamente
            for package_name in pbi_packages:
                # Estrai il risultato specifico per questo package dalla fase 2
                package_detail = phase_2_result.get(package_name, "Nessun dettaglio disponibile")
                package_success = "successo" in str(package_detail).lower()

                # Combina i risultati di entrambe le fasi per questo package
                combined_result = {
                    "phase_1_datafactory": phase_1_result,
                    "phase_2_powerbi": {package_name: package_detail}
                }

                log_entry = models.PublicationLog(
                    bank=current_user.bank,
                    workspace=workspace_powerbi,  # Usa sempre workspace Power BI perchÃ© i package sono lÃ¬
                    packages=[package_name],  # Un package per volta (come settimanale)
                    publication_type="production",
                    status="success" if (phase_1_success and package_success) else "error",
                    output=json.dumps(combined_result, indent=2) if (phase_1_success and package_success) else None,
                    error=json.dumps(combined_result, indent=2) if not (phase_1_success and package_success) else None,
                    user_id=current_user.id,
                    anno=anno,
                    settimana=None,
                    mese=mese
                )
                db.add(log_entry)
                logger.info(f"Log salvato per package mensile PRODUCTION {package_name}: status={'success' if (phase_1_success and package_success) else 'error'}")

        else:
            # SETTIMANALE PRODUCTION: Salva per ogni package (scripts.main)
            logger.info("Salvando log per pubblicazione settimanale PRODUCTION")

            for package_name in pbi_packages:
                package_detail = packages_details.get(package_name, stdout if returncode == 0 else stderr)

                log_entry = models.PublicationLog(
                    bank=current_user.bank,
                    workspace=workspace_powerbi,
                    packages=[package_name],  # Un package per volta
                    publication_type="production",
                    status="success" if returncode == 0 and "successo" in str(package_detail).lower() else "error",
                    output=package_detail if returncode == 0 or "successo" in str(package_detail).lower() else None,
                    error=package_detail if returncode != 0 or "errore" in str(package_detail).lower() or "timeout" in str(package_detail).lower() else None,
                    user_id=current_user.id,
                    anno=anno,
                    settimana=settimana,
                    mese=None
                )
                db.add(log_entry)

        db.commit()

        # Aggiorna i contatori della publish run
        if is_mensile:
            # Per mensile, conta i package individuali (non solo il year_month)
            total_packages = len(pbi_packages)
            phase_2_result = packages_details.get("phase_2_powerbi", {})
            success_count = sum(1 for pkg in pbi_packages if "successo" in str(phase_2_result.get(pkg, "")).lower())
            failed_count = total_packages - success_count
            logger.info(f"Mensile PRODUCTION publish run stats: total={total_packages}, success={success_count}, failed={failed_count}")
        else:
            total_packages = len(pbi_packages)
            success_count = sum(1 for pkg in pbi_packages if "successo" in str(packages_details.get(pkg, "")).lower())
            failed_count = total_packages - success_count

        publish_tracker.update_publish_run(
            db=db,
            files_processed=total_packages,
            files_copied=success_count,
            files_skipped=0,
            files_failed=failed_count
        )

        if returncode != 0:
            # Chiudi la publish run con errore
            publish_tracker.end_publish_run(db=db, error_details=stderr[:500] if stderr else None)
            raise HTTPException(
                status_code=500,
                detail=f"Errore nell'esecuzione dello script: {stderr}"
            )

        # Chiudi la publish run con successo
        publish_tracker.end_publish_run(db=db, error_details=None)

        return {
            "status": "success",
            "message": "Pubblicazione in produzione completata con successo",
            "workspace": workspace_datafactory if workspace_datafactory else workspace_powerbi,
            "packages": pbi_packages,
            "output": stdout,
            "packages_details": packages_details
        }

    except HTTPException as http_exc:
        # Chiudi la publish run con errore se Ã¨ stata avviata
        try:
            publish_tracker.end_publish_run(db=db, error_details=str(http_exc.detail)[:500])
        except:
            pass
        raise
    except Exception as e:
        logger.error(f"Exception in publish_production: {e}", exc_info=True)

        # Chiudi la publish run con errore
        try:
            publish_tracker.end_publish_run(db=db, error_details=str(e)[:500])
        except:
            pass

        # Salva anche gli errori nel database
        try:
            log_entry = models.PublicationLog(
                bank=current_user.bank if current_user else "unknown",
                workspace=workspace if 'workspace' in locals() else "unknown",
                packages=pbi_packages if 'pbi_packages' in locals() else [],
                publication_type="production",
                status="error",
                output=None,
                error=str(e),
                user_id=current_user.id if current_user else None,
                anno=anno if 'anno' in locals() else None,
                settimana=settimana if 'settimana' in locals() else None,
                mese=mese if 'mese' in locals() else None
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_error:
            logger.error(f"Failed to save error log to database: {db_error}")

        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# WebSocket Endpoint per aggiornamenti real-time
# ============================================================

@router.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    WebSocket endpoint per ricevere aggiornamenti real-time su:
    - Stato sync
    - Package disponibili
    - Stato pubblicazione
    - Info repo update

    Autenticazione: passare il token JWT come query parameter ?token=xxx
    """
    # Verifica autenticazione
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    try:
        # Verifica il token JWT
        from jose import jwt, JWTError
        from core.config import settings

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        bank = payload.get("bank")

        if not username or not bank:
            await websocket.close(code=1008, reason="Invalid token payload")
            return

        logger.info(f"WebSocket authenticated for user: {username} (bank: {bank})")

    except JWTError as e:
        logger.warning(f"WebSocket JWT decode error: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")
        return

    await ws_manager.connect(websocket)

    try:
        # Import necessari per le query
        from core.config import config_manager
        import psutil

        # Loop per inviare aggiornamenti periodici
        while True:
            try:
                # Prepara i dati aggregati
                update_data = {
                    "type": "status_update",
                    "timestamp": datetime.utcnow().isoformat()
                }

                # 1. Sync Status
                try:
                    sync_status_data = await get_sync_status_data(bank=bank)
                    update_data["sync_status"] = sync_status_data
                except Exception as e:
                    logger.error(f"Error getting sync status: {e}")
                    update_data["sync_status"] = {"is_running": False, "status": "idle"}

                # 2. Publish Status
                try:
                    publish_status_data = await get_publish_status_data()
                    update_data["publish_status"] = publish_status_data
                except Exception as e:
                    logger.error(f"Error getting publish status: {e}")
                    update_data["publish_status"] = None

                # 3. Reportistica Data
                try:
                    reportistica_data = await get_reportistica_data(bank=bank)
                    update_data["reportistica_data"] = reportistica_data
                except Exception as e:
                    logger.error(f"Error getting reportistica data: {e}")
                    update_data["reportistica_data"] = []

                # 4. Packages Ready (per tabella pubblicazione)
                try:
                    packages_ready_data = await get_packages_ready_data(bank=bank, type_reportistica=None)
                    update_data["packages_ready"] = packages_ready_data
                    logger.info(f"Loaded {len(packages_ready_data)} packages ready")

                    # Debug: mostra lo stato dei primi package
                    if packages_ready_data:
                        for pkg in packages_ready_data[:3]:  # Primi 3 package
                            logger.info(f"  Package {pkg['package']}: precheck={pkg['pre_check']}, prod={pkg['prod']}")
                except Exception as e:
                    logger.error(f"Error getting packages ready data: {e}", exc_info=True)
                    update_data["packages_ready"] = []

                # Invia aggiornamento al client
                try:
                    # Serializza manualmente per evitare problemi con PyInstaller
                    import json
                    json_data = json.dumps(update_data, ensure_ascii=False, default=str)
                    json_size = len(json_data)
                    logger.debug(f"Sending WebSocket update: {json_size} bytes, keys: {list(update_data.keys())}")

                    await websocket.send_text(json_data)
                    logger.debug("WebSocket update sent successfully")
                except WebSocketDisconnect:
                    logger.info("Client disconnected during send")
                    break
                except Exception as send_error:
                    logger.error(f"Error sending WebSocket data: {send_error}", exc_info=True)
                    logger.error(f"Data keys: {update_data.keys()}")
                    if 'reportistica_data' in update_data:
                        logger.error(f"Reportistica data count: {len(update_data['reportistica_data'])}")
                    if 'packages_ready' in update_data:
                        logger.error(f"Packages ready count: {len(update_data['packages_ready'])}")
                    # Non fare raise, continua il loop
                    break

                # Aspetta 2 secondi prima del prossimo update
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error in WebSocket update loop: {e}", exc_info=True)
                # Se c'Ã¨ un errore, esci dal loop per evitare di inviare a una connessione chiusa
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(websocket)


async def get_sync_status_data(bank: Optional[str] = None) -> dict:
    """Helper per ottenere lo stato del sync"""
    try:
        db_gen = get_db()
        db = next(db_gen)

        try:
            return _compute_sync_status(db, bank)
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in get_sync_status_data: {e}")
        return {"is_running": False, "status": "idle", "bank": normalize_bank_label(bank)}

async def get_publish_status_data() -> Optional[dict]:
    """Helper per ottenere lo stato della pubblicazione dalla tabella sync_runs"""
    try:
        db_gen = get_db()
        db = next(db_gen)

        try:
            from datetime import datetime

            # Leggi dalla tabella sync_runs (ID=2 per publish)
            query = text("""
                SELECT
                    start_time,
                    end_time,
                    update_interval,
                    files_processed,
                    files_copied,
                    files_skipped,
                    files_failed,
                    error_details
                FROM sync_runs
                WHERE id = 2 AND operation_type = 'publish'
            """)

            result = db.execute(query).fetchone()

            if not result:
                return {"is_running": False, "status": "idle"}

            start_time, end_time, update_interval, files_processed, files_copied, files_skipped, files_failed, error_details = result

            # Se end_time Ã¨ NULL, publish Ã¨ in corso
            is_running = end_time is None

            if is_running:
                return {
                    "is_running": True,
                    "status": "running",
                    "phase": error_details or "unknown",  # phase salvata in error_details
                    "start_time": start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time) if start_time else None,
                    "files_processed": files_processed or 0,
                    "files_copied": files_copied or 0,
                    "files_skipped": files_skipped or 0,
                    "files_failed": files_failed or 0
                }
            else:
                return {
                    "is_running": False,
                    "status": "completed",
                    "start_time": start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time) if start_time else None,
                    "end_time": end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time) if end_time else None,
                    "files_processed": files_processed or 0,
                    "files_copied": files_copied or 0,
                    "files_skipped": files_skipped or 0,
                    "files_failed": files_failed or 0
                }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in get_publish_status_data: {e}")
        return {"is_running": False, "status": "error"}


async def get_reportistica_data(bank: Optional[str] = None) -> List[dict]:
    """Helper per ottenere i dati reportistica"""
    try:
        db_gen = get_db()
        db = next(db_gen)

        try:
            # Query per ottenere i dati reportistica (usa direttamente la tabella reportistica)
            query = """
                SELECT
                    id,
                    banca,
                    package,
                    nome_file,
                    finalita,
                    anno,
                    settimana,
                    mese,
                    ultima_modifica,
                    updated_at,
                    tipo_reportistica,
                    dettagli,
                    disponibilita_server
                FROM reportistica
                ORDER BY updated_at DESC
            """

            result = db.execute(text(query))
            rows = result.fetchall()

            # Mappa i risultati
            data = []
            for row in rows:
                # Converti datetime in string per JSON serialization
                ultima_modifica = row[8]
                if ultima_modifica and not isinstance(ultima_modifica, str):
                    ultima_modifica = ultima_modifica.isoformat() if hasattr(ultima_modifica, 'isoformat') else str(ultima_modifica)

                updated_at = row[9]
                if updated_at and not isinstance(updated_at, str):
                    updated_at = updated_at.isoformat() if hasattr(updated_at, 'isoformat') else str(updated_at)

                # Gestisci dettagli che potrebbe essere JSON
                dettagli = row[11]
                if dettagli and isinstance(dettagli, str):
                    try:
                        import json
                        dettagli = json.loads(dettagli)
                    except:
                        pass  # Mantieni come stringa se non Ã¨ JSON valido

                data.append({
                    "id": row[0],
                    "banca": row[1],
                    "package": row[2] or row[3],  # package o nome_file
                    "nome_file": row[3],
                    "finalita": row[4],
                    "anno": row[5],
                    "settimana": row[6],
                    "mese": row[7],
                    "ultima_modifica": ultima_modifica,
                    "updated_at": updated_at,
                    "tipo_reportistica": row[10],
                    "dettagli": dettagli,
                    "disponibilita_server": bool(row[12]) if row[12] is not None else None
                })

            return data

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in get_reportistica_data: {e}")
        return []


async def get_packages_ready_data(bank: str, type_reportistica: Optional[str] = None) -> List[dict]:
    """Helper per ottenere i dati packages ready (test-packages-v2)"""
    try:
        db_gen = get_db()
        db = next(db_gen)

        try:
            # Query packages da report_mapping (ORDER BY rowid per mantenere ordine DB)
            sql = text("""
                SELECT package, ws_precheck, ws_production, bank, Type_reportisica, obbligatorio
                FROM report_mapping
                WHERE LOWER(bank) = LOWER(:bank)
                AND (:type_reportistica IS NULL OR Type_reportisica = :type_reportistica)
                ORDER BY rowid
            """)

            params = {
                "bank": bank,
                "type_reportistica": type_reportistica
            }

            results = db.execute(sql, params).fetchall()

            # Ottieni periodo corrente da repo_update_info filtrato per banca
            repo_info_query = """
                SELECT anno, settimana, mese
                FROM repo_update_info
                WHERE LOWER(bank) = LOWER(:bank)
                ORDER BY updated_at DESC
                LIMIT 1
            """
            repo_info_result = db.execute(text(repo_info_query), {"bank": bank}).fetchone()

            current_anno = None
            current_settimana = None
            current_mese = None

            if repo_info_result:
                current_anno = repo_info_result[0]
                current_settimana = repo_info_result[1]
                current_mese = repo_info_result[2]

            packages = []

            # Carica tutti i publication logs per il periodo corrente
            pub_logs_query = """
                SELECT id, packages, publication_type, status, anno, settimana, mese, output, error, timestamp
                FROM publication_logs
                WHERE LOWER(bank) = LOWER(:bank)
                AND anno = :anno
                ORDER BY timestamp DESC, id DESC
            """
            pub_logs_result = db.execute(text(pub_logs_query), {
                "bank": bank,
                "anno": current_anno
            }).fetchall()

            # Crea un dizionario per tracciare lo stato di ogni package
            # Usa SOLO log con singolo package, ignora completamente log multi-package
            package_status = {}  # {package_name: {"precheck": status, "prod": status, "anno": int, "settimana": int, "mese": int}}
            seen_combinations = {}  # {(pkg_name, pub_type): True} per tracciare cosa abbiamo giÃ  processato

            logger.debug(f"Processing {len(pub_logs_result)} publication logs")

            # Parse JSON packages
            import json

            # Processa SOLO i log con singolo package
            for log_row in pub_logs_result:
                log_id = log_row[0]
                logger.debug(f"  Processing log ID {log_id}")
                log_packages = log_row[1]  # JSON array
                pub_type = log_row[2]  # "precheck" o "production"
                log_status = log_row[3]  # "success" o "error"
                log_anno = log_row[4]
                log_settimana = log_row[5]
                log_mese = log_row[6]
                log_output = log_row[7]  # output
                log_error = log_row[8]  # error
                log_timestamp = log_row[9]  # timestamp

                try:
                    if isinstance(log_packages, str):
                        pkg_list = json.loads(log_packages)
                    else:
                        pkg_list = log_packages
                except:
                    continue

                # IGNORA completamente log con package multipli
                if len(pkg_list) != 1:
                    logger.debug(f"    Skipping multi-package log (contains {len(pkg_list)} packages)")
                    continue

                # Per ogni package nel log (in questo caso sarÃ  sempre 1)
                for pkg_name in pkg_list:
                    # Chiave per identificare univocamente package + tipo
                    combo_key = (pkg_name, pub_type)

                    # Salta se giÃ  processato (prendiamo solo il primo = piÃ¹ recente)
                    if combo_key in seen_combinations:
                        continue

                    seen_combinations[combo_key] = True

                    # Inizializza lo stato del package se non esiste
                    if pkg_name not in package_status:
                        package_status[pkg_name] = {
                            "precheck": False,
                            "prod": False,
                            "anno_precheck": None,
                            "settimana_precheck": None,
                            "mese_precheck": None,
                            "anno_prod": None,
                            "settimana_prod": None,
                            "mese_prod": None,
                            "dettagli_precheck": None,
                            "dettagli_prod": None,
                            "error_precheck": None,
                            "error_prod": None,
                            "data_esecuzione_precheck": None,
                            "data_esecuzione_prod": None
                        }

                    # Determina lo stato: analizza il contenuto dei messaggi
                    # Solo ROSSO o VERDE (niente arancione)
                    status_value = False

                    # Concatena output ed error per analizzare tutto il contenuto
                    full_message = ""
                    if log_output:
                        full_message += str(log_output) + " "
                    if log_error:
                        full_message += str(log_error)

                    full_message_lower = full_message.lower()

                    # Determina lo stato basandosi sul contenuto del messaggio
                    # Timeout viene trattato come errore (ROSSO)
                    if "errore" in full_message_lower or "error" in full_message_lower or "timeout" in full_message_lower:
                        status_value = "error"  # Rosso
                    elif "successo" in full_message_lower or log_status == "success":
                        status_value = True  # Verde
                    elif log_status == "success":
                        status_value = True  # Verde (fallback su status se nessuna parola chiave trovata)
                    else:
                        status_value = "error"  # Rosso (default per status != success)

                    # Prepara dettagli e error
                    # Se c'Ã¨ output, usa quello per dettagli
                    # Se c'Ã¨ solo error, NON metterlo in dettagli (andrÃ  in error_precheck/error_prod)
                    dettagli_message = log_output if log_output else None
                    error_message = log_error if log_error else None

                    # Aggiorna lo stato del package (solo per il primo log = piÃ¹ recente)
                    if pub_type == "precheck":
                        package_status[pkg_name]["precheck"] = status_value
                        package_status[pkg_name]["anno_precheck"] = log_anno
                        package_status[pkg_name]["settimana_precheck"] = log_settimana
                        package_status[pkg_name]["mese_precheck"] = log_mese
                        package_status[pkg_name]["dettagli_precheck"] = dettagli_message
                        package_status[pkg_name]["error_precheck"] = error_message
                        package_status[pkg_name]["data_esecuzione_precheck"] = log_timestamp
                    elif pub_type == "production":
                        package_status[pkg_name]["prod"] = status_value
                        package_status[pkg_name]["anno_prod"] = log_anno
                        package_status[pkg_name]["settimana_prod"] = log_settimana
                        package_status[pkg_name]["mese_prod"] = log_mese
                        package_status[pkg_name]["dettagli_prod"] = dettagli_message
                        package_status[pkg_name]["error_prod"] = error_message
                        package_status[pkg_name]["data_esecuzione_prod"] = log_timestamp

            # Ora processa ogni package da report_mapping
            for row in results:
                package_name = row[0]
                ws_precheck = row[1]
                ws_production = row[2]
                pkg_type = row[4]
                obbligatorio = row[5] if len(row) > 5 else None

                # Determina se Ã¨ settimanale o mensile
                is_weekly = 'settimanale' in (pkg_type or '').lower()

                # Default values - NON impostare anno/settimana/mese se non ci sono log
                pre_check = False
                prod = False
                anno_precheck = None
                settimana_precheck = None
                mese_precheck = None
                anno_prod = None
                settimana_prod = None
                mese_prod = None
                dettagli_precheck = None
                dettagli_prod = None
                error_precheck = None
                error_prod = None
                data_esecuzione_precheck = None
                data_esecuzione_prod = None

                # Controlla se abbiamo uno stato per questo package
                # I dati vengono sempre mostrati, ma i semafori solo se il periodo corrisponde
                if package_name in package_status:
                    pkg_state = package_status[package_name]

                    # Carica precheck se esiste
                    if pkg_state["anno_precheck"] is not None:
                        # Verifica se il periodo corrisponde per il semaforo
                        period_matches = True
                        if pkg_state["anno_precheck"] != current_anno:
                            period_matches = False
                        elif is_weekly and pkg_state["settimana_precheck"] != current_settimana:
                            period_matches = False
                        elif not is_weekly and pkg_state["mese_precheck"] != current_mese:
                            period_matches = False

                        # Semaforo solo se periodo corrisponde, dati sempre
                        pre_check = pkg_state["precheck"] if period_matches else False
                        anno_precheck = pkg_state["anno_precheck"]
                        settimana_precheck = pkg_state["settimana_precheck"]
                        mese_precheck = pkg_state["mese_precheck"]
                        dettagli_precheck = pkg_state["dettagli_precheck"]
                        error_precheck = pkg_state["error_precheck"]
                        data_esecuzione_precheck = pkg_state["data_esecuzione_precheck"]

                    # Carica production se esiste
                    if pkg_state["anno_prod"] is not None:
                        # Verifica se il periodo corrisponde per il semaforo
                        period_matches = True
                        if pkg_state["anno_prod"] != current_anno:
                            period_matches = False
                        elif is_weekly and pkg_state["settimana_prod"] != current_settimana:
                            period_matches = False
                        elif not is_weekly and pkg_state["mese_prod"] != current_mese:
                            period_matches = False

                        # Semaforo solo se periodo corrisponde, dati sempre
                        prod = pkg_state["prod"] if period_matches else False
                        anno_prod = pkg_state["anno_prod"]
                        settimana_prod = pkg_state["settimana_prod"]
                        mese_prod = pkg_state["mese_prod"]
                        dettagli_prod = pkg_state["dettagli_prod"]
                        error_prod = pkg_state["error_prod"]
                        data_esecuzione_prod = pkg_state["data_esecuzione_prod"]

                # Converti timestamp da UTC a ora locale (come in ingest)
                def format_timestamp(ts):
                    if ts is None:
                        return None

                    from datetime import datetime, timezone
                    try:
                        from zoneinfo import ZoneInfo
                    except ImportError:
                        from backports.zoneinfo import ZoneInfo

                    if isinstance(ts, str):
                        ts_clean = ts.replace('Z', '').replace('+00:00', '').split('.')[0]
                        try:
                            ts = datetime.fromisoformat(ts_clean)
                        except:
                            return ts_clean

                    if hasattr(ts, 'isoformat'):
                        # Converti da UTC a ora italiana (gestisce automaticamente ora legale)
                        ts_utc = ts.replace(tzinfo=timezone.utc)
                        ts_local = ts_utc.astimezone(ZoneInfo('Europe/Rome'))
                        return ts_local.replace(tzinfo=None).isoformat()

                    return str(ts)

                packages.append({
                    "package": package_name,
                    "user": "N/D",
                    "data_esecuzione": format_timestamp(data_esecuzione_precheck),
                    "pre_check": pre_check,
                    "prod": prod,
                    "dettagli": dettagli_precheck,
                    "error_precheck": error_precheck,
                    "user_prod": "N/D",
                    "data_esecuzione_prod": format_timestamp(data_esecuzione_prod),
                    "dettagli_prod": dettagli_prod,
                    "error_prod": error_prod,
                    "anno_precheck": anno_precheck,
                    "settimana_precheck": settimana_precheck,
                    "mese_precheck": mese_precheck,
                    "anno_prod": anno_prod,
                    "settimana_prod": settimana_prod,
                    "mese_prod": mese_prod,
                    "type_reportistica": pkg_type,
                    "ws_precheck": ws_precheck,
                    "ws_production": ws_production,
                    "obbligatorio": obbligatorio == "Y"  # True se Y, False altrimenti
                })

            return packages

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in get_packages_ready_data: {e}")
        return []


