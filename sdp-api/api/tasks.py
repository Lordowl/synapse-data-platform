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
from db import get_db
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

    try:
        # Import the script functions directly instead of subprocess
        from scripts import generate_flows_from_excel

        # Execute the script logic
        SHEET_NAME = 'File reportistica'
        BASE_PATH = Path(__file__).parent.parent
        OUTPUT_JSON_FILE = BASE_PATH / "data" / "flows.json"
        COLUMNS_FOR_JSON = ['ID', 'SEQ', 'Package', 'Filename out']

        logger.info(f"Reading Excel file: {input_excel_path}")
        df_filtered = generate_flows_from_excel.clean_and_filter_data(str(input_excel_path), SHEET_NAME)

        if df_filtered is not None and not df_filtered.empty:
            logger.info(f"Found {len(df_filtered)} flows initially")
            df_deduplicated = generate_flows_from_excel.remove_duplicates(df_filtered)
            logger.info(f"After deduplication: {len(df_deduplicated)} flows")

            flows_json = generate_flows_from_excel.extract_flows_to_flat_list(df_deduplicated, COLUMNS_FOR_JSON)

            if flows_json:
                generate_flows_from_excel.save_json(flows_json, str(OUTPUT_JSON_FILE))
                flow_count = len(flows_json.get("flows", []))
                return {
                    "status": "success",
                    "message": f"Lista flussi aggiornata con successo: {flow_count} flussi trovati.",
                    "output": f"Processed {flow_count} flows",
                    "stderr": "",
                }
            else:
                raise HTTPException(500, "Errore nella trasformazione dei dati")
        else:
            return {
                "status": "success",
                "message": "Nessun flusso valido trovato nel file Excel.",
                "output": "No flows found",
                "stderr": "",
            }

    except Exception as e:
        logger.error(f"Error processing Excel file: {e}", exc_info=True)
        raise HTTPException(500, f"Errore durante l'elaborazione del file Excel: {str(e)}")

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
    executed_by = current_user.username if current_user else "unknown"
    logger.info(f"User: {executed_by}")
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

    # Recupero INI e template log
    ini_contents = config_manager.get_ini_contents()
    selected_bank = request.params.get("selectedBank") if isinstance(request.params, dict) else None
    if not selected_bank:
        selected_bank = next(iter(ini_contents), None)
    filelog_template = ini_contents.get(selected_bank, {}).get("data", {}).get("DEFAULT", {}).get("filelog")

    def extract_folder_from_template(template: str) -> str | None:
        if not template:
            return None
        part = template.split("\\", 1)[0].split("/", 1)[0]
        return part or None

    folder_name = extract_folder_from_template(filelog_template)
    log_folder = Path(folder_path) / "App" / "Ingestion" / (folder_name or "log")
    if not log_folder.exists():
        log_folder.mkdir(parents=True, exist_ok=True)
        logger.warning(f"Cartella log creata: {log_folder}")

    flow_ids_str = " ".join(str(flow.id).replace("/", "-") for flow in request.flows)
    log_key = uuid.uuid4().hex[:8]
    start_time = time.time()

    # Estrazione di anno e settimana dai parametri
    anno = request.params.get("selectedYear")
    settimana = request.params.get("selectedWeek")
    anno_int = int(anno) if anno and str(anno).isdigit() else None
    settimana_int = int(settimana) if settimana and str(settimana).isdigit() else None

    # Estrazione del path del file metadati: usa quello dal frontend se disponibile, altrimenti dall'INI
    metadata_file_path = request.params.get("metadataFilePath")

    if not metadata_file_path:
        # Fallback: prendi il path dal file INI
        selected_bank = request.params.get("selectedBank") if isinstance(request.params, dict) else None
        if not selected_bank:
            selected_bank = next(iter(ini_contents), None)
        metadata_file_path = ini_contents.get(selected_bank, {}).get("data", {}).get("DEFAULT", {}).get("filemetadati", "")

    logger.info(f"Flow IDs string: {flow_ids_str}, Log key: {log_key}, Anno: {anno_int}, Settimana: {settimana_int}, Metadata file: {metadata_file_path}")

    command_args = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script_path),
        "-id", flow_ids_str,
        "-anno", str(anno or ""),
        "-settimana", str(settimana or ""),
        "-log_key", log_key,
        "-filemetadati", metadata_file_path,
    ]
    logger.info(f"Comando esecuzione: {' '.join(command_args)}")

    # --- Funzione per salvare dettagli per elemento ---
    def save_element_detail(element_id, buffer, script_failed=False):
        result = "Success"
        to_add = ""
        for prev_line in reversed(buffer):
            line = prev_line.strip()
            if not line or "DEBUG" in line.upper() or "INFO" in line.upper():
                continue
            line_upper = line.upper()
            if "ERROR" in line_upper or any(word in line_upper for word in ["FAIL", "KO", "TERMINATE"]):
                result = "Failed"
                to_add = line
                break
            elif "WARNING" in line_upper or "WARN" in line_upper:
                result = "Warning"
                to_add = line
                break

        if result == "Success" and script_failed:
            result = "Failed"
            to_add = "Script principale fallito (return code diverso da 0)"

        try:
            crud.create_execution_detail(
                db=db,
                log_key=log_key,
                element_id=element_id,
                error_lines=[to_add] if to_add else [],
                result=result,
                bank=current_user.bank,
                anno=anno_int,
                settimana=settimana_int,
            )
        except Exception as e:
            logger.error(f"Errore nel salvare dettagli elemento {element_id}: {e}")

        return result  # restituisce stato dell'elemento

    elements_results = []
    all_lines = []
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
                    raw_lines = f.readlines()
                break
            except Exception:
                continue
        if not raw_lines:
            raise HTTPException(500, f"Impossibile leggere il log: {log_file_path}")

        # Pulizia dei numeri di riga da tutte le righe del log
        import re
        def clean_log_line(line):
            """Rimuove numeri di riga dall'inizio della riga."""
            if not line:
                return line
            # Rimuove pattern come "123:", "123-", "123 " all'inizio della riga
            cleaned = re.sub(r'^\s*\d+[\s\-:]+', '', line)
            return cleaned if cleaned else line

        all_lines = [clean_log_line(line) for line in raw_lines]

        # Analisi log per elementi
        current_id = None
        buffer = []
        start_patterns = ["Inizio processo elemento con ID"]
        id_regex = re.compile(r"ID\s+(\d+)")
        for line in all_lines:
            line_clean = line.strip()
            for pattern in start_patterns:
                if pattern.lower() in line_clean.lower():
                    match = id_regex.search(line_clean)
                    if match:
                        if current_id is not None:
                            elem_status = save_element_detail(current_id, buffer, script_failed=(result.returncode != 0))
                            elements_results.append(elem_status)
                        buffer = []
                        current_id = match.group(1).strip()
                    break
            else:
                if current_id is not None:
                    buffer.append(line)
        if current_id:
            elem_status = save_element_detail(current_id, buffer, script_failed=(result.returncode != 0))
            elements_results.append(elem_status)

        # --- Determinazione stato globale ---
        if "Failed" in elements_results or result.returncode != 0:
            status = "Failed"
        elif "Warning" in elements_results:
            status = "Warning"
        else:
            status = "Success"

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore imprevisto durante esecuzione: {e}", exc_info=True)
        status = "Failed"
        all_lines = [f"Errore imprevisto nell'API: {str(e)}"]
        for flow in request.flows:
            element_id = str(flow.id).replace("/", "-")
            try:
                crud.create_execution_detail(
                    db=db,
                    log_key=log_key,
                    element_id=element_id,
                    error_lines=[f"Errore imprevisto nell'API: {str(e)}"],
                    result="Failed",
                    bank=current_user.bank,
                    anno=anno_int,
                    settimana=settimana_int,
                )
            except Exception:
                continue

    # Salvataggio log aggregato
    duration = int(time.time() - start_time)
    try:
        crud.create_execution_log(
            db=db,
            flow_id_str=flow_ids_str,
            status=status,
            duration_seconds=duration,
            details={"executed_by": executed_by, "params": request.params},
            log_key=log_key,
            bank=current_user.bank,
            anno=anno_int,
            settimana=settimana_int,
        )
    except Exception as e:
        logger.error(f"Errore nel salvare log di esecuzione: {e}", exc_info=True)

    logger.info("=== FINE ESECUZIONE FLOWS ===")
    return {
        "status": "success",
        "message": "Esecuzione dei flussi richiesta.",
        "results": [{"ids": flow_ids_str, "status": status, "log_key": log_key}],
    }
