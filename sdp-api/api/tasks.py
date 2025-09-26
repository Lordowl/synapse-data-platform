# sdp-api/api/tasks.py

import subprocess
import sys
import time
import uuid
import glob
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

class UpdateRequest(BaseModel):
    file_path: str

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
        raise HTTPException(
            status_code=400,
            detail=f"File Excel non trovato: {input_excel_path}"
        )

    script_path = Path(__file__).parent.parent / "scripts" / "generate_flows_from_excel.py"
    if not script_path.is_file():
        raise HTTPException(status_code=500, detail=f"Script mancante: {script_path}")

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
            status_code=500,
            detail={"message": "Errore durante l'esecuzione dello script.", "stderr": e.stderr},
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Timeout: l'elaborazione del file Excel ha richiesto troppo tempo.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Errore imprevisto del server: {e}"
        )

@router.post("/execute-flows", response_model=Dict)
def execute_selected_flows(
    request: ExecutionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Security(require_ingest_permission),
):
    logger.info("=== INIZIO ESECUZIONE FLOWS ===")
    logger.info(f"User: {current_user.username if current_user else 'unknown'}")
    logger.info(f"Flows richiesti: {[flow.id for flow in request.flows]}")
    logger.info(f"Parametri: {request.params}")

    folder_path = config_manager.get_setting("SETTINGS_PATH")
    if not folder_path:
        logger.error("Folder base non configurato in settings_path")
        raise HTTPException(500, "Folder base non configurato in settings_path")

    script_path = Path(folder_path) / "App" / "Ingestion" / "ingestion.ps1"
    if not script_path.is_file():
        logger.error(f"File .ps1 non trovato: {script_path}")
        raise HTTPException(500, "File di esecuzione .ps1 non trovato.")

    # --- Recupero INI e filelog template ---
    ini_contents = config_manager.get_ini_contents()

    # Prendi la banca selezionata dai parametri della richiesta, altrimenti fallback sulla prima disponibile
    selected_bank = request.params.get("selectedBank") if isinstance(request.params, dict) else None
    if not selected_bank:
        selected_bank = next(iter(ini_contents), None)

    logger.info(f"Banca usata per estrarre filelog: {selected_bank}")

    filelog_template = None
    if selected_bank and ini_contents.get(selected_bank):
        filelog_template = ini_contents[selected_bank].get("data", {}).get("DEFAULT", {}).get("filelog")

    # Helper robusto per estrarre la cartella dal template filelog
    def extract_folder_from_template(template: str) -> str | None:
        if not template:
            return None
        # supporta sia backslash che slash
        part = template.split("\\", 1)[0]
        part = part.split("/", 1)[0]
        return part or None

    folder_name = extract_folder_from_template(filelog_template)
    if folder_name:
        log_folder = Path(folder_path) / "App" / "Ingestion" / folder_name
    else:
        log_folder = Path(folder_path) / "App" / "Ingestion" / "log"  # fallback generico

    logger.info(f"Cartella log selezionata: {log_folder} (template: {filelog_template})")

    # Assicuriamoci che la cartella esista (non la creiamo se vuota? qui la creiamo per sicurezza)
    if not log_folder.exists():
        logger.warning(f"La cartella log {log_folder} non esiste; la creo.")
        try:
            log_folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Impossibile creare la cartella log {log_folder}: {e}", exc_info=True)

    flow_ids_str = " ".join(str(flow.id).replace("/", "-") for flow in request.flows)
    log_key = uuid.uuid4().hex[:8]
    start_time = time.time()

    logger.info(f"Flow IDs string: {flow_ids_str}")
    logger.info(f"Log key generato: {log_key}")

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

    # --- Funzione interna per salvare dettagli elemento (definita DOPO log_key) ---
    def save_element_detail(element_id, buffer, script_failed=False):
        logger.info(f"--- ANALISI ELEMENTO {element_id} ---")
        result = "Success"
        to_add = ""

        for prev_line in reversed(buffer):
            prev_line_clean = prev_line.strip()
            if not prev_line_clean:
                logger.debug(f"[{element_id}] Riga vuota ignorata")
                continue

            upper_line = prev_line_clean.upper()
            logger.debug(f"[{element_id}] Analizzo riga: {prev_line_clean}")

            if "DEBUG" in upper_line:
                logger.debug(f"[{element_id}] Riga DEBUG ignorata")
                continue

            if "INFO" in upper_line:
                logger.debug(f"[{element_id}] Riga INFO ignorata")
                continue

            if "ERROR" in upper_line:
                result = "Failed"
                to_add = prev_line_clean
                logger.info(f"[{element_id}] Trovato ERRORE → Failed")
                break
            elif "WARNING" in upper_line or "WARN" in upper_line:
                result = "Warning"
                to_add = prev_line_clean
                logger.info(f"[{element_id}] Trovato WARNING → Warning")
                break
            elif any(word in upper_line for word in ["FAIL", "KO", "TERMINATE"]):
                result = "Failed"
                to_add = prev_line_clean
                logger.info(f"[{element_id}] Trovato FAIL/KO/TERMINATE → Failed")
                break

        if result == "Success" and script_failed:
            result = "Failed"
            to_add = "Script principale fallito (return code diverso da 0)"
            logger.warning(f"[{element_id}] Nessun errore trovato ma script fallito → Forced Failed")

        try:
            crud.create_execution_detail(
                db=db,
                log_key=log_key,
                element_id=element_id,
                error_lines=[to_add] if to_add else [],
                result=result,
            )
            logger.info(f"[{element_id}] ✓ Dettagli salvati nel DB (risultato: {result})")
            return 1
        except Exception as e:
            logger.error(f"[{element_id}] ✗ Errore nel salvataggio dettagli: {e}")
            return 0

    elements_processed = 0
    lines = []
    status = "Failed"

    try:
        # Esegui lo script
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
        logger.debug(f"STDOUT: {result.stdout}")
        logger.debug(f"STDERR: {result.stderr}")

        # --- Ricerca file di log (prima prova con log_key, altrimenti fallback) ---
        log_files = list(log_folder.glob(f"*_{log_key}.log"))
        if log_files:
            log_file_path = log_files[0]
            logger.info(f"File log trovato con log_key: {log_file_path}")
        else:
            all_logs = list(log_folder.glob("*.log"))
            if not all_logs:
                logger.error(f"Nessun file .log trovato in {log_folder}")
                raise HTTPException(status_code=500, detail=f"Nessun file .log trovato in {log_folder}")
            log_file_path = max(all_logs, key=os.path.getctime)
            logger.warning(f"File log con log_key non trovato, uso fallback: {log_file_path}")

        # --- Lettura log (diverse codifiche) ---
        for enc in ["cp1252", "utf-8", "latin-1"]:
            try:
                with open(log_file_path, "r", encoding=enc) as f:
                    lines = f.readlines()
                logger.info(f"Lettura file log avvenuta con encoding {enc}")
                break
            except Exception as e:
                logger.debug(f"Impossibile leggere {log_file_path} con {enc}: {e}")

        if not lines:
            logger.warning(f"File log {log_file_path} letto ma vuoto o non decodificabile")
            raise HTTPException(status_code=500, detail=f"Impossibile leggere il log: {log_file_path}")

        # --- Analisi log e salvataggio dettagli ---
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
                            elements_processed += save_element_detail(current_id, buffer)
                        buffer = []
                        current_id = potential_id
                    break
            else:
                if current_id is not None:
                    buffer.append(line)

        if current_id is not None:
            elements_processed += save_element_detail(current_id, buffer)

        status = "Failed" if any("ERROR" in l.upper() for l in lines) else "Success"

    except HTTPException:
        # rilancia HTTPException così il client vede il dettaglio già formattato
        raise
    except Exception as e:
        logger.error("=== ERRORE DURANTE L'ESECUZIONE ===", exc_info=True)
        status = "Failed"
        lines = [f"Errore imprevisto nell'API: {str(e)}"]
        for flow in request.flows:
            element_id = str(flow.id).replace("/", "-")
            try:
                crud.create_execution_detail(
                    db=db,
                    log_key=log_key,
                    element_id=element_id,
                    error_lines=[f"Errore imprevisto nell'API: {str(e)}"],
                    result="Failed",
                )
            except Exception:
                continue

    # Salvataggio log di esecuzione aggregato
    duration = int(time.time() - start_time)
    executed_by = current_user.username if current_user else "unknown"
    try:
        crud.create_execution_log(
            db=db,
            flow_id_str=flow_ids_str,
            status=status,
            duration_seconds=duration,
            details={"executed_by": executed_by, "params": request.params},
            log_key=log_key,
        )
        logger.info("✓ Log di esecuzione salvato nel DB")
    except Exception as e:
        logger.error(f"✗ Errore nel salvare log di esecuzione: {e}", exc_info=True)

    logger.info("=== FINE ESECUZIONE FLOWS ===")
    return {
        "status": "success",
        "message": "Esecuzione dei flussi richiesta.",
        "results": [{"ids": flow_ids_str, "status": status, "log_key": log_key}],
    }
