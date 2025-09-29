# sdp-api/api/tasks.py

import subprocess
import sys
import time
import uuid
import logging
from pathlib import Path
from typing import List, Dict
import os
import re

from fastapi import APIRouter, Depends, Security, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import crud, models
from db.database import get_db
from core.security import require_settings_permission, require_ingest_permission
from core.config import config_manager

# --- Schemi Pydantic ---
class FlowExecutionResult(BaseModel):
    ids: str
    status: str
    log_key: str

class ExecuteFlowsResponse(BaseModel):
    status: str
    message: str
    results: List[FlowExecutionResult]

class FilePathRequest(BaseModel):
    file_path: str

class FlowPayload(BaseModel):
    id: str
    name: str

class ExecutionRequest(BaseModel):
    flows: List[FlowPayload]
    params: Dict

# --- Router FastAPI ---
router = APIRouter(tags=["Tasks"])
logger = logging.getLogger("uvicorn")

# ----------------------------
# Helper per pulizia log
# ----------------------------
def clean_log_line(line):
    match = re.search(r"\b(ERROR|WARNING|WARN|INFO)\b", line, re.IGNORECASE)
    if match:
        return line[match.end():].strip()
    else:
        return line.strip()

# ----------------------------
# Endpoint aggiornamento flussi da Excel
# ----------------------------
@router.post("/update-flows-from-excel", response_model=Dict)
def trigger_update_flows_from_excel(
    request_data: FilePathRequest,
    current_user: models.User = Security(require_settings_permission),
):
    input_excel_path = Path(request_data.file_path)
    if not input_excel_path.is_file():
        raise HTTPException(400, f"File Excel non trovato: {input_excel_path}")

    script_path = Path(__file__).parent.parent / "scripts" / "generate_flows_from_excel.py"
    if not script_path.is_file():
        raise HTTPException(500, f"Script mancante: {script_path}")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), str(input_excel_path)],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            timeout=120,
        )

        return {
            "status": "success",
            "message": "Lista flussi aggiornata con successo dal file Excel.",
            "output": result.stdout,
            "stderr": result.stderr,
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            500, {"message": "Errore durante l'esecuzione dello script.", "stderr": e.stderr}
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Timeout: l'elaborazione del file Excel ha richiesto troppo tempo.")
    except Exception as e:
        raise HTTPException(500, f"Errore imprevisto del server: {e}")

# ----------------------------
# Endpoint esecuzione flussi
# ----------------------------
@router.post("/execute-flows", response_model=Dict)
def execute_selected_flows(
    request: ExecutionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Security(require_ingest_permission),
):
    logger.info("=== INIZIO ESECUZIONE FLOWS ===")
    logger.info(f"User: {current_user.username}")

    # Selezione banca
    selected_bank = request.params.get("selectedBank") if isinstance(request.params, dict) else None
    if not selected_bank:
        selected_bank = getattr(current_user, "current_bank", None)
        if not selected_bank:
            raise HTTPException(400, "Nessuna banca selezionata e l'utente non ha banca predefinita.")

    logger.info(f"Banca selezionata per l'esecuzione: {selected_bank}")

    folder_path = config_manager.get_setting("SETTINGS_PATH")
    script_path = Path(folder_path) / "App" / "Ingestion" / "ingestion.ps1"
    if not script_path.is_file():
        raise HTTPException(500, "File di esecuzione .ps1 non trovato.")

    # Costruzione flow_ids e log_key
    flow_ids_str = " ".join(str(flow.id).replace("/", "-") for flow in request.flows)
    log_key = uuid.uuid4().hex[:8]
    start_time = time.time()

    # Funzione interna per salvare dettagli elemento con banca
    def save_element_detail(element_id, buffer, result="Success"):
        try:
            crud.create_execution_detail(
                db=db,
                log_key=log_key,
                element_id=element_id,
                error_lines=[line for line in buffer if line.strip()],
                result=result,
                bank=selected_bank
            )
        except Exception as e:
            logger.error(f"Errore nel salvataggio dettagli: {e}")

    # --- Recupero cartelle log e filelog template ---
    ini_contents = config_manager.get_ini_contents()
    filelog_template = None
    if selected_bank and ini_contents.get(selected_bank):
        filelog_template = ini_contents[selected_bank].get("data", {}).get("DEFAULT", {}).get("filelog")

    folder_name = None
    if filelog_template:
        folder_name = filelog_template.split("\\")[0].split("/")[0]

    log_folder = Path(folder_path) / "App" / "Ingestion" / (folder_name or "log")
    if not log_folder.exists():
        log_folder.mkdir(parents=True, exist_ok=True)

    # Comando powershell
    command_args = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script_path),
        "-id", flow_ids_str,
        "-anno", str(request.params.get("selectedYear", "")),
        "-settimana", str(request.params.get("selectedWeek", "")),
        "-log_key", log_key,
    ]
    logger.info(f"Comando da eseguire: {' '.join(command_args)}")

    lines = []
    status = "Failed"

    try:
        result = subprocess.run(
            command_args,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
            encoding="cp1252",
            shell=False,
        )
        logger.info(f"Script completato - Return code: {result.returncode}")

        # Ricerca file di log
        log_files = list(log_folder.glob(f"*_{log_key}.log"))
        if log_files:
            log_file_path = log_files[0]
        else:
            all_logs = list(log_folder.glob("*.log"))
            if not all_logs:
                raise HTTPException(500, f"Nessun file .log trovato in {log_folder}")
            log_file_path = max(all_logs, key=os.path.getctime)

        # Lettura log
        for enc in ["cp1252", "utf-8", "latin-1"]:
            try:
                with open(log_file_path, "r", encoding=enc) as f:
                    lines = f.readlines()
                break
            except Exception:
                continue
        if not lines:
            raise HTTPException(500, f"Impossibile leggere il log: {log_file_path}")

        # Analisi log e salvataggio dettagli
        current_id = None
        buffer = []
        start_patterns = ["Inizio processo elemento con ID"]
        id_regex = re.compile(r"ID\s+(\d+)")
        for line in lines:
            line_clean = line.strip()
            for pattern in start_patterns:
                if pattern.lower() in line_clean.lower():
                    match = id_regex.search(line_clean)
                    if match:
                        potential_id = match.group(1).strip()
                        if current_id is not None:
                            save_element_detail(current_id, buffer)
                        buffer = []
                        current_id = potential_id
                    break
            else:
                if current_id is not None:
                    buffer.append(line)
        if current_id is not None:
            save_element_detail(current_id, buffer)

        status = "Failed" if any("ERROR" in l.upper() for l in lines) else "Success"

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Errore durante l'esecuzione", exc_info=True)
        status = "Failed"
        for flow in request.flows:
            element_id = str(flow.id).replace("/", "-")
            save_element_detail(element_id, [f"Errore imprevisto: {str(e)}"], result="Failed")

    # Salvataggio log aggregato
    duration = int(time.time() - start_time)
    try:
        crud.create_execution_log(
            db=db,
            flow_id_str=flow_ids_str,
            status=status,
            duration_seconds=duration,
            details={"executed_by": current_user.username, "params": request.params},
            log_key=log_key,
            bank=selected_bank
        )
    except Exception as e:
        logger.error(f"Errore nel salvare log di esecuzione: {e}", exc_info=True)

    logger.info("=== FINE ESECUZIONE FLOWS ===")
    return {
        "status": "success",
        "message": "Esecuzione dei flussi richiesta.",
        "results": [{"ids": flow_ids_str, "status": status, "log_key": log_key}],
    }
