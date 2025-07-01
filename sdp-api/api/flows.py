# sdp-api/api/flows.py
import json
from pathlib import Path
from fastapi import APIRouter, Depends, Security, HTTPException
from typing import List
from sqlalchemy.orm import Session 
from sqlalchemy import func, desc
from db.database import get_db 
from db import models
from core.security import get_current_active_admin

router = APIRouter()

# Definiamo il percorso del nostro file JSON
DATA_FILE = Path(__file__).parent.parent / "data" / "flows.json"

@router.get("/", response_model=List[dict])
def get_all_flows(
    # Proteggiamo l'endpoint, solo gli admin possono vedere i flussi
    # admin_user: models.User = Security(get_current_active_admin)
):
    """Legge e restituisce la lista di flussi dal file flows.json."""
    if not DATA_FILE.is_file():
        raise HTTPException(status_code=404, detail="File dei flussi non trovato.")
    
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    
    # Il tuo JSON ha una chiave "flows" che contiene la lista
    return data.get("flows", []) 
@router.get("/history")
def get_flows_history(db: Session = Depends(get_db)):
    """
    Restituisce l'ultima esecuzione per ogni flow_id usando una query più robusta.
    """
    try:
        # Ordiniamo tutte le esecuzioni per ID (o timestamp) in modo decrescente
        all_executions = db.query(models.FlowExecutionHistory).order_by(models.FlowExecutionHistory.id.desc()).all()
        
        history_map = {}
        # Cicliamo sui risultati e prendiamo solo il primo che troviamo per ogni flow_id
        for exec in all_executions:
            if exec.flow_id_str not in history_map:
                history_map[exec.flow_id_str] = {
                    "lastRun": exec.timestamp.isoformat(),
                    "result": exec.status,
                    "duration": f"{exec.duration_seconds // 60}m {exec.duration_seconds % 60}s" if exec.duration_seconds is not None else None
                }
        
        return history_map
    except Exception as e:
        print(f"Errore nel recuperare lo storico dei flussi: {e}")
        return {} # Restituisce un dizionario vuoto in caso di errore