# sdp-api/api/flows.py
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Security, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from db import models, crud
from core.security import get_current_user, get_current_active_admin

router = APIRouter()

DATA_FILE = Path(__file__).parent.parent / "data" / "flows.json"


@router.get("/", response_model=List[dict])
def get_all_flows():
    """Restituisce la lista di flussi dal file JSON."""
    if not DATA_FILE.is_file():
        raise HTTPException(status_code=404, detail="File dei flussi non trovato. Eseguire l'aggiornamento.")
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("flows", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nella lettura del file dei flussi: {e}")


@router.get("/historylatest")
def get_flows_history_latest(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Restituisce l'ultima esecuzione per ogni element_id filtrata per bank."""
    try:
        all_executions = (
            db.query(models.FlowExecutionDetail)
            .filter(models.FlowExecutionDetail.bank == current_user.bank)
            .order_by(models.FlowExecutionDetail.timestamp.desc())
            .all()
        )
        history_map = {}
        for exec in all_executions:
            if exec.element_id not in history_map:
                # Aggiungi 'Z' per indicare UTC, altrimenti JS interpreta come local time
                timestamp_str = exec.timestamp.isoformat() + 'Z' if exec.timestamp else None
                history_map[exec.element_id] = {
                    "timestamp": timestamp_str,
                    "result": exec.result,
                    "error_lines": exec.error_lines or "",
                    "log_key": exec.log_key,
                    "anno": exec.anno,
                    "settimana": exec.settimana,
                }
        return history_map
    except Exception as e:
        print(f"Errore nel recuperare lo storico dei flussi: {e}")
        return {}


@router.get("/history")
def get_execution_details(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Restituisce tutti i dettagli delle esecuzioni filtrati per bank."""
    try:
        all_executions = (
            db.query(models.FlowExecutionDetail)
            .filter(models.FlowExecutionDetail.bank == current_user.bank)
            .order_by(models.FlowExecutionDetail.timestamp.desc())
            .all()
        )
        details_list = []
        for exec in all_executions:
            # Aggiungi 'Z' per indicare UTC, altrimenti JS interpreta come local time
            timestamp_str = exec.timestamp.isoformat() + 'Z' if exec.timestamp else None
            details_list.append({
                "timestamp": timestamp_str,
                "result": exec.result,
                "error_lines": exec.error_lines or "",
                "log_key": exec.log_key,
                "element_id": exec.element_id,
                "anno": exec.anno,
                "settimana": exec.settimana,
            })
        return details_list
    except Exception as e:
        print(f"Errore nel recuperare i dettagli delle esecuzioni: {e}")
        return []


# --- Schemi Pydantic ---
class FlowExecutionLog(BaseModel):
    id: int
    timestamp: str  # Stringa ISO con 'Z' invece di datetime
    element_id: str
    status: str
    duration_seconds: Optional[int]
    details: Optional[Dict]

    class Config:
        arbitrary_types_allowed = True
        from_attributes = True


class LogFilterRequest(BaseModel):
    flow_id: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: Optional[int] = 200


# --- Helper ---
def format_log(log: models.FlowExecutionHistory) -> FlowExecutionLog:
    """Converte un log FlowExecutionHistory in FlowExecutionLog con timestamp formattato."""
    message = f"Esecuzione flusso"
    if log.status:
        message += f": {log.status}"
    if log.details and isinstance(log.details, dict):
        if 'processed_records' in log.details:
            message += f" - Record elaborati: {log.details['processed_records']}"
        if 'error_count' in log.details and log.details['error_count'] > 0:
            message += f" - Errori: {log.details['error_count']}"
        if 'error_message' in log.details:
            message += f" - {log.details['error_message']}"

    # Converti timestamp in stringa ISO con 'Z' per indicare UTC
    timestamp_str = log.timestamp.isoformat() + 'Z' if log.timestamp else None

    return FlowExecutionLog(
        id=log.id,
        timestamp=timestamp_str,
        element_id=log.flow_id_str,
        status=log.status or "unknown",
        duration_seconds=log.duration_seconds,
        details={
            "flow_id_str": log.flow_id_str,
            "status": log.status,
            "log_key": log.log_key,
            "message": message,
            "anno": log.anno,
            "settimana": log.settimana,
            "original_details": log.details or {}
        }
    )


@router.get("/logs", response_model=List[FlowExecutionLog])
def get_execution_logs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 200
):
    """Restituisce gli ultimi N log filtrati per bank."""
    try:
        logs = (
            db.query(models.FlowExecutionHistory)
            .filter(models.FlowExecutionHistory.bank == current_user.bank)
            .order_by(models.FlowExecutionHistory.id.desc())
            .limit(limit)
            .all()
        )
        return [format_log(log) for log in logs]
    except Exception as e:
        print(f"Errore nel recuperare i log di esecuzione: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/logs")
def clear_execution_logs(
    db: Session = Depends(get_db), 
    admin_user: models.User = Security(get_current_active_admin)
):
    """Cancella tutti i log di esecuzione (admin)."""
    try:
        count_before = db.query(models.FlowExecutionHistory).count()
        db.query(models.FlowExecutionHistory).delete()
        db.commit()
        return {
            "message": f"Log di esecuzione cancellati con successo. Rimossi {count_before} record.",
            "deleted_count": count_before
        }
    except Exception as e:
        db.rollback()
        print(f"Errore nella cancellazione dei log: {e}")
        raise HTTPException(status_code=500, detail="Errore nella cancellazione dei log di esecuzione")


@router.post("/logs/search", response_model=List[FlowExecutionLog])
def search_execution_logs(
    filter_request: LogFilterRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cerca nei log di esecuzione con filtri opzionali, solo per la bank dell'utente."""
    try:
        query = db.query(models.FlowExecutionHistory).filter(models.FlowExecutionHistory.bank == current_user.bank)

        if filter_request.flow_id:
            query = query.filter(models.FlowExecutionHistory.flow_id_str.contains(filter_request.flow_id))
        if filter_request.status:
            query = query.filter(models.FlowExecutionHistory.status == filter_request.status)
        if filter_request.start_date:
            query = query.filter(models.FlowExecutionHistory.timestamp >= filter_request.start_date)
        if filter_request.end_date:
            query = query.filter(models.FlowExecutionHistory.timestamp <= filter_request.end_date)

        logs = query.order_by(models.FlowExecutionHistory.id.desc()).limit(filter_request.limit or 200).all()
        return [format_log(log) for log in logs]
    except Exception as e:
        print(f"Errore nella ricerca dei log: {e}")
        raise HTTPException(status_code=500, detail="Errore nella ricerca dei log")


@router.get("/debug/counts")
def get_debug_counts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Endpoint di debug per verificare i conteggi delle tabelle."""
    try:
        history_count = db.query(models.FlowExecutionHistory).filter(
            models.FlowExecutionHistory.bank == current_user.bank
        ).count()

        detail_count = db.query(models.FlowExecutionDetail).filter(
            models.FlowExecutionDetail.bank == current_user.bank
        ).count()

        # Esempi di dati
        sample_history = db.query(models.FlowExecutionHistory).filter(
            models.FlowExecutionHistory.bank == current_user.bank
        ).order_by(models.FlowExecutionHistory.id.desc()).limit(3).all()

        sample_details = db.query(models.FlowExecutionDetail).filter(
            models.FlowExecutionDetail.bank == current_user.bank
        ).order_by(models.FlowExecutionDetail.id.desc()).limit(3).all()

        return {
            "bank": current_user.bank,
            "history_count": history_count,
            "detail_count": detail_count,
            "sample_history": [
                {
                    "id": h.id,
                    "flow_id_str": h.flow_id_str,
                    "log_key": h.log_key,
                    "status": h.status,
                    "timestamp": h.timestamp.isoformat() + 'Z' if h.timestamp else None,
                    "anno": h.anno,
                    "settimana": h.settimana
                } for h in sample_history
            ],
            "sample_details": [
                {
                    "id": d.id,
                    "log_key": d.log_key,
                    "element_id": d.element_id,
                    "result": d.result,
                    "timestamp": d.timestamp.isoformat() + 'Z' if d.timestamp else None,
                    "anno": d.anno,
                    "settimana": d.settimana
                } for d in sample_details
            ]
        }
    except Exception as e:
        print(f"Errore nel debug counts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
