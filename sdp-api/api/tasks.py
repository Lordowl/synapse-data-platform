# sdp-api/api/tasks.py

import subprocess
import sys
import time
import uuid
import glob
import logging
from pathlib import Path
from typing import List, Dict
import logging
import os
import re

from fastapi import APIRouter, Depends, Security, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import crud, models
from db.database import get_db
from core.security import require_settings_permission, require_ingest_permission
from core.config import config_manager


class FlowExecutionResult(BaseModel):
    ids: str
    status: str
    log_key: str


class ExecuteFlowsResponse(BaseModel):
    status: str
    message: str
    results: List[FlowExecutionResult]


# --- Schemi Pydantic ---
class UpdateRequest(BaseModel):
    file_path: str


logger = logging.getLogger("uvicorn")


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

def clean_log_line(line):
    """
    Rimuove timestamp iniziale e livello (ERROR/WARN/INFO) da una riga di log.
    Funziona anche se ci sono spazi multipli o tab.
    """
    # Cerca la prima occorrenza di ERROR/WARNING/WARN/INFO
    match = re.search(r'\b(ERROR|WARNING|WARN|INFO)\b', line, re.IGNORECASE)
    if match:
        # Prendi tutto ciò che segue la keyword
        return line[match.end():].strip()
    else:
        return line.strip()
# ----------------------------
# Endpoint esecuzione flussi selezionati
# -----------------------------
@router.post("/update-flows-from-excel", response_model=Dict)
def trigger_update_flows_from_excel(
    request_data: FilePathRequest,
    current_user: models.User = Security(require_settings_permission),
):
    """
    Aggiorna i flussi da un file Excel.
    Usa direttamente il percorso passato dal frontend.
    """
    input_excel_path = Path(request_data.file_path)
    if not input_excel_path.is_file():
        raise HTTPException(
            status_code=400, detail=f"File Excel non trovato: {input_excel_path}"
        )

    # Script relativo nella cartella dei scripts
    script_path = (
        Path(__file__).parent.parent / "scripts" / "generate_flows_from_excel.py"
    )
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
            detail={
                "message": "Errore durante l'esecuzione dello script.",
                "stderr": e.stderr,
            },
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
    current_user: models.User = Security(require_ingest_permission)
):
    # Verifica percorso folder base
    folder_path = config_manager.get_setting("SETTINGS_PATH")
    if not folder_path:
        raise HTTPException(status_code=500, detail="Folder base non configurato in settings_path")

    script_path = Path(folder_path) / "App" / "Ingestion" / "ingestion.ps1"
    if not script_path.is_file():
        raise HTTPException(status_code=500, detail="File di esecuzione .ps1 non trovato.")

    # Prepara ID flussi (sostituisci / con -)
    flow_ids_str = " ".join(str(flow.id).replace("/", "-") for flow in request.flows)
    log_key = f"exec_{int(time.time())}_{uuid.uuid4().hex}"
    start_time = time.time()

    command_args = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script_path),
        "-id", flow_ids_str,
        "-anno", str(request.params.get("selectedYear", "")),
        "-settimana", str(request.params.get("selectedWeek", "")),
        "-log_key", log_key
    ]

    try:
        subprocess.run(
            command_args,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
            encoding="cp1252",
            shell=False
        )

        # Leggi file log generati
        log_folder = Path(folder_path) / "App" / "Ingestion" / "log_SPK"
        log_files = glob.glob(str(log_folder / f"*_{log_key}.log"))
        
        logger.info(f"Cercando file log in: {log_folder}")
        logger.info(f"Pattern: *_{log_key}.log")
        logger.info(f"File trovati: {log_files}")
        
        if not log_files:
            # Se non trova file con log_key, prova a cercare i più recenti
            all_log_files = glob.glob(str(log_folder / "*.log"))
            if all_log_files:
                # Prendi il file più recente
                log_file_path = max(all_log_files, key=os.path.getctime)
                logger.info(f"Usando file log più recente: {log_file_path}")
            else:
                raise FileNotFoundError("Nessun file log trovato")
        else:
            log_file_path = log_files[0]

        # Leggi il contenuto del file log
        try:
            with open(log_file_path, "r", encoding="cp1252") as f:
                lines = f.readlines()
            logger.info(f"Lette {len(lines)} righe dal file log")
        except Exception as e:
            logger.error(f"Errore nella lettura del file log: {e}")
            # Prova con encoding diversi
            for encoding in ["utf-8", "latin-1", "cp1252"]:
                try:
                    with open(log_file_path, "r", encoding=encoding) as f:
                        lines = f.readlines()
                    logger.info(f"File log letto con encoding {encoding}")
                    break
                except:
                    continue
            else:
                raise Exception("Impossibile leggere il file log con nessun encoding")

        # Debug: stampa alcune righe del log per capire il formato
        logger.info("Prime 10 righe del log:")
        for i, line in enumerate(lines[:10]):
            logger.info(f"Riga {i}: {repr(line)}")

        # Parsing migliorato per elemento
        current_id = None
        buffer = []
        elements_processed = 0
        
        # Pattern più flessibili per identificare l'inizio di un elemento
        start_patterns = [
            "Inizio processo elemento con ID",
            "Processing element with ID",
            "Elemento ID:",
            "Flow ID:",
            "Starting flow"
        ]
        
        for line_num, line in enumerate(lines):
            line_clean = line.strip()
            
            # Cerca pattern di inizio elemento
            found_start = False
            for pattern in start_patterns:
                if pattern.lower() in line_clean.lower():
                    found_start = True
                    # Estrai ID dalla riga
                    parts = line_clean.split()
                    if parts:
                        # Prendi l'ultima parte che potrebbe essere l'ID
                        potential_id = parts[-1].replace("/", "-")
                        
                        # Salva elemento precedente se esiste
                        if current_id is not None:
                            error_lines = [l for l in buffer if "ERROR" in l.upper()]
                            warning_lines = [l for l in buffer if "WARNING" in l.upper() or "WARN" in l.upper()]
                            cleaned_error_lines = [clean_log_line(l) for l in error_lines]
                            cleaned_warning_lines = [clean_log_line(l) for l in warning_lines]
                            # Determina il risultato basandosi sui log
                            if error_lines:
                                result = "Failed"
                                to_add=cleaned_error_lines
                            elif warning_lines:
                                result = "Warning"
                                to_add=cleaned_warning_lines
                            else:
                                result = "Success"
                                to_add=""
                            
                            logger.info(f"Salvando dettagli per elemento {current_id}, errori: {len(error_lines)}, warnings: {len(warning_lines)}, result: {result}")
                            
                            try:
                                crud.create_execution_detail(
                                    db=db,
                                    log_key=log_key,
                                    element_id=current_id,
                                    error_lines=to_add,
                                    result=result
                                )
                                elements_processed += 1
                                logger.info(f"Dettagli salvati per elemento {current_id}")
                            except Exception as e:
                                logger.error(f"Errore nel salvare dettagli per elemento {current_id}: {e}")
                        
                        # Inizia nuovo elemento
                        buffer = []
                        current_id = potential_id
                        logger.info(f"Trovato nuovo elemento: {current_id}")
                    break
            
            buffer.append(line)

        # Salva ultimo elemento
        if current_id is not None:
            error_lines = [l for l in buffer if "ERROR" in l.upper()]
            warning_lines = [l for l in buffer if "WARNING" in l.upper() or "WARN" in l.upper()]
            cleaned_error_lines = [clean_log_line(l) for l in error_lines]
            cleaned_warning_lines = [clean_log_line(l) for l in warning_lines]
            # Determina il risultato basandosi sui log
            if error_lines:
                result = "Failed"
                to_add=cleaned_error_lines
            elif warning_lines:
                result = "Warning"
                to_add=cleaned_warning_lines
            else:
                result = "Success"
                to_add=""

            logger.info(f"Salvando ultimo elemento {current_id}, errori: {len(error_lines)}, warnings: {len(warning_lines)}, result: {result}")
            
            try:
                crud.create_execution_detail(
                    db=db,
                    log_key=log_key,
                    element_id=current_id,
                    error_lines=to_add,
                    result=result
                )
                elements_processed += 1
                logger.info(f"Dettagli salvati per ultimo elemento {current_id}")
            except Exception as e:
                logger.error(f"Errore nel salvare dettagli per ultimo elemento {current_id}: {e}")

        # Se non ha trovato elementi con i pattern, crea un dettaglio per ogni flow richiesto
        if elements_processed == 0:
            logger.warning("Nessun elemento trovato con i pattern di parsing, creando dettagli per ogni flow richiesto")
            for flow in request.flows:
                element_id = str(flow.id).replace("/", "-")
                error_lines = [l for l in lines if "ERROR" in l.upper()]
                warning_lines = [l for l in lines if "WARNING" in l.upper() or "WARN" in l.upper()]
                
                # Determina il risultato basandosi sui log globali
                if error_lines:
                    result = "Failed"
                    error_lines_to_add=error_lines
                elif warning_lines:
                    result = "Warning"
                    error_lines_to_add=warning_lines
                else:
                    result = "Success"
                
                try:
                    crud.create_execution_detail(
                        db=db,
                        log_key=log_key,
                        element_id=element_id,
                        error_lines=error_lines_to_add,
                        result=result
                    )
                    elements_processed += 1
                    logger.info(f"Dettagli creati per flow {element_id}")
                except Exception as e:
                    logger.error(f"Errore nel creare dettagli per flow {element_id}: {e}")

        error_lines_global = [l for l in lines if "ERROR" in l.upper()]
        status = "Failed" if error_lines_global else "Success"
        
        logger.info(f"Elementi processati: {elements_processed}, Errori globali: {len(error_lines_global)}")

    except Exception as e:
        logger.error(f"Errore durante l'esecuzione: {e}")
        status = "Failed"
        lines = [f"Errore imprevisto nell'API: {str(e)}"]
        
        # Anche in caso di errore, crea dettagli per ogni flow
        for flow in request.flows:
            element_id = str(flow.id).replace("/", "-")
            try:
                crud.create_execution_detail(
                    db=db,
                    log_key=log_key,
                    element_id=element_id,
                    error_lines=[f"Errore imprevisto nell'API: {str(e)}"],
                    result="Failed"  # Errore imprevisto = sempre Failed
                )
                logger.info(f"Dettagli di errore creati per flow {element_id}")
            except Exception as detail_error:
                logger.error(f"Errore nel creare dettagli di errore per flow {element_id}: {detail_error}")

    duration = int(time.time() - start_time)
    executed_by = current_user.username if current_user else "unknown"

    # Salva log di esecuzione principale
    try:
        crud.create_execution_log(
            db=db,
            flow_id_str=flow_ids_str,
            status=status,
            duration_seconds=duration,
            details={"executed_by": executed_by, "params": request.params},
            log_key=log_key,
        )
        logger.info(f"Log di esecuzione salvato con log_key: {log_key}")
    except Exception as e:
        logger.error(f"Errore nel salvare log di esecuzione: {e}")

    return {
        "status": "success",
        "message": "Esecuzione dei flussi richiesta.",
        "results": [{"ids": flow_ids_str, "status": status, "log_key": log_key}]
    }