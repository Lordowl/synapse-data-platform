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
    match = re.search(r"\b(ERROR|WARNING|WARN|INFO)\b", line, re.IGNORECASE)
    if match:
        # Prendi tutto ciò che segue la keyword
        return line[match.end() :].strip()
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
    current_user: models.User = Security(require_ingest_permission),
):
    logger.info(f"=== INIZIO ESECUZIONE FLOWS ===")
    logger.info(f"User: {current_user.username if current_user else 'unknown'}")
    logger.info(f"Flows richiesti: {[flow.id for flow in request.flows]}")
    logger.info(f"Parametri: {request.params}")
    
    folder_path = config_manager.get_setting("SETTINGS_PATH")
    if not folder_path:
        logger.error("Folder base non configurato in settings_path")
        raise HTTPException(500, "Folder base non configurato in settings_path")

    script_path = Path(folder_path) / "App" / "Ingestion" / "ingestion.ps1"
    logger.info(f"Script path: {script_path}")
    if not script_path.is_file():
        logger.error(f"File di esecuzione .ps1 non trovato: {script_path}")
        raise HTTPException(500, "File di esecuzione .ps1 non trovato.")

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

    def save_element_detail(element_id, buffer):
        """Determina il risultato basandosi sull'ultima riga significativa e salva nel DB."""
        logger.info(f"--- ANALISI ELEMENTO {element_id} ---")
        logger.info(f"Buffer contiene {len(buffer)} righe:")
        
        # Debug: stampa tutto il buffer
        for i, buf_line in enumerate(buffer):
            logger.info(f"  Buffer[{i}]: {repr(buf_line.strip())}")
        
        last_line = ""
        logger.info("Ricerca ultima riga significativa (dal fondo):")
        
        for i, prev_line in enumerate(reversed(buffer)):
            prev_line_clean = prev_line.strip()
            logger.debug(f"  Controllo riga {len(buffer)-i-1}: {repr(prev_line_clean)}")
            
            if not prev_line_clean:
                logger.debug("    -> Riga vuota, skip")
                continue
                
            upper_line = prev_line_clean.upper()
            
            # Salta righe di debug
            if "DEBUG" in upper_line:
                logger.debug("    -> Riga DEBUG, skip")
                continue
            
            # Salta righe INFO vuote (solo "INFO" o "TIMESTAMP INFO")
            line_parts = prev_line_clean.split()
            if (upper_line.startswith("INFO") and len(line_parts) == 1) or \
               (len(line_parts) == 2 and line_parts[1].upper() == "INFO"):
                logger.debug("    -> Riga INFO vuota, skip")
                continue
                
            # Salta righe che contengono solo timestamp + INFO senza contenuto significativo
            if upper_line.startswith("INFO") and "INIZIO PROCESSO ELEMENTO" in upper_line:
                logger.debug("    -> Riga inizio processo, skip")
                continue
                
            last_line = prev_line_clean
            logger.info(f"    -> TROVATA ultima riga significativa: {repr(last_line)}")
            break

        if not last_line:
            logger.warning(f"Nessuna riga significativa trovata per elemento {element_id}")

        # Determina il risultato in base al contenuto
        upper_last_line = last_line.upper()
        logger.info(f"Analisi contenuto riga (uppercase): {repr(upper_last_line)}")
        
        if "ERROR" in upper_last_line:
            result = "Failed"
            to_add = clean_log_line(last_line)
            logger.info(f"    -> RISULTATO: Failed (trovato ERROR)")
            logger.info(f"    -> Messaggio pulito: {repr(to_add)} (tipo: {type(to_add)})")
        elif "WARNING" in upper_last_line or "WARN" in upper_last_line:
            result = "Warning"  
            to_add = clean_log_line(last_line)
            logger.info(f"    -> RISULTATO: Warning (trovato WARNING/WARN)")
            logger.info(f"    -> Messaggio pulito: {repr(to_add)} (tipo: {type(to_add)})")
        else:
            result = "Success"
            to_add = ""
            logger.info(f"    -> RISULTATO: Success (nessun errore/warning)")

        logger.info(f"Elemento {element_id} - Risultato finale: {result} - Messaggio: {repr(to_add)}")

        try:
            crud.create_execution_detail(
                db=db,
                log_key=log_key,
                element_id=element_id,
                error_lines=[to_add] if to_add else [],  # Passa come lista
                result=result,
            )
            logger.info(f"✓ Dettagli salvati nel DB per elemento {element_id}")
            return 1
        except Exception as e:
            logger.error(f"✗ Errore nel salvare dettagli per elemento {element_id}: {e}")
            return 0

    elements_processed = 0
    try:
        logger.info("=== ESECUZIONE SCRIPT POWERSHELL ===")
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
        if result.stdout:
            logger.info(f"STDOUT: {result.stdout[:500]}...")
        if result.stderr:
            logger.warning(f"STDERR: {result.stderr[:500]}...")

        logger.info("=== RICERCA E LETTURA LOG FILE ===")
        log_folder = Path(folder_path) / "App" / "Ingestion" / "log_SPK"
        logger.info(f"Cartella log: {log_folder}")
        
        log_files = glob.glob(str(log_folder / f"*_{log_key}.log"))
        logger.info(f"File log con log_key {log_key}: {log_files}")
        
        if not log_files:
            logger.warning("Nessun file log con log_key trovato, cerco il più recente...")
            all_logs = glob.glob(str(log_folder / "*.log"))
            logger.info(f"Tutti i file log disponibili: {all_logs}")
            if not all_logs:
                logger.error("Nessun file log trovato nella cartella")
                raise FileNotFoundError("Nessun file log trovato")
            log_file_path = max(all_logs, key=os.path.getctime)
            logger.info(f"File log più recente selezionato: {log_file_path}")
        else:
            log_file_path = log_files[0]
            logger.info(f"File log con log_key selezionato: {log_file_path}")

        # Lettura del file log
        logger.info("=== LETTURA FILE LOG ===")
        lines = []
        encoding_used = None
        for enc in ["cp1252", "utf-8", "latin-1"]:
            try:
                logger.info(f"Tentativo lettura con encoding {enc}...")
                with open(log_file_path, "r", encoding=enc) as f:
                    lines = f.readlines()
                encoding_used = enc
                logger.info(f"✓ Lettura riuscita con encoding {enc}, {len(lines)} righe")
                break
            except Exception as e:
                logger.warning(f"✗ Fallito encoding {enc}: {e}")
                continue
                
        if not lines:
            logger.error("Impossibile leggere il file log con nessun encoding")
            raise Exception("Impossibile leggere il file log con nessun encoding")

        # Debug: stampa prime e ultime righe del log
        logger.info("=== CONTENUTO LOG FILE (primi e ultimi estratti) ===")
        for i in range(min(5, len(lines))):
            logger.info(f"Log[{i}]: {repr(lines[i].strip())}")
        if len(lines) > 10:
            logger.info("... (righe intermedie omesse) ...")
            for i in range(max(5, len(lines)-5), len(lines)):
                logger.info(f"Log[{i}]: {repr(lines[i].strip())}")

        logger.info("=== PARSING LOG PER ELEMENTI ===")
        current_id = None
        buffer = []
        start_patterns = ["Inizio processo elemento con ID"]
        id_regex = re.compile(r"ID\s+(\d+)")  # manteniamo solo numeri per l'ID
        
        logger.info(f"Pattern di ricerca: {start_patterns}")
        logger.info(f"Regex ID: {id_regex.pattern}")

        for line_idx, line in enumerate(lines):
            line_clean = line.strip()
            is_start = False
            
            for pattern in start_patterns:
                if pattern.lower() in line_clean.lower():
                    logger.info(f"Riga {line_idx}: Trovato pattern inizio - {repr(line_clean)}")
                    match = id_regex.search(line_clean)
                    if match:
                        potential_id = match.group(1).strip()
                        logger.info(f"  -> ID estratto: {repr(potential_id)}")
                        
                        # Salva il buffer precedente se esiste
                        if current_id is not None:
                            logger.info(f"Processando buffer precedente per ID {current_id} ({len(buffer)} righe)")
                            elements_processed += save_element_detail(current_id, buffer)
                        
                        # Reset per il nuovo ID
                        buffer = []
                        current_id = potential_id
                        is_start = True
                        logger.info(f"Nuovo elemento attivo: ID {current_id}")
                    else:
                        logger.warning(f"  -> Pattern trovato ma ID non estratto da: {repr(line_clean)}")
                    break
            
            # Aggiungi la riga al buffer solo se non è la riga di inizio
            if not is_start and current_id is not None:
                buffer.append(line)
                logger.debug(f"Aggiunta al buffer ID {current_id}: {repr(line_clean)}")

        # Salva ultimo elemento
        if current_id is not None:
            logger.info(f"Processando ultimo buffer per ID {current_id} ({len(buffer)} righe)")
            elements_processed += save_element_detail(current_id, buffer)
        
        logger.info(f"=== FINE PARSING - Elementi processati: {elements_processed} ===")

        # Stato globale
        logger.info("=== DETERMINAZIONE STATO GLOBALE ===")
        error_lines_global = [l for l in lines if "ERROR" in l.upper()]
        logger.info(f"Righe con ERROR globali trovate: {len(error_lines_global)}")
        for err_line in error_lines_global[:5]:  # mostra prime 5
            logger.info(f"  ERROR: {repr(err_line.strip())}")
            
        status = "Failed" if error_lines_global else "Success"
        logger.info(f"Stato globale determinato: {status}")

    except Exception as e:
        logger.error(f"=== ERRORE DURANTE L'ESECUZIONE ===")
        logger.error(f"Tipo errore: {type(e).__name__}")
        logger.error(f"Dettaglio errore: {str(e)}")
        logger.error(f"Traceback completo:", exc_info=True)
        
        status = "Failed"
        lines = [f"Errore imprevisto nell'API: {str(e)}"]
        
        # Salva errori per tutti i flows
        for flow in request.flows:
            element_id = str(flow.id).replace("/", "-")
            logger.info(f"Creazione dettaglio errore per flow {element_id}")
            try:
                crud.create_execution_detail(
                    db=db,
                    log_key=log_key,
                    element_id=element_id,
                    error_lines=[f"Errore imprevisto nell'API: {str(e)}"],
                    result="Failed",
                )
                logger.info(f"✓ Dettaglio errore salvato per {element_id}")
            except Exception as detail_error:
                logger.error(f"✗ Errore nel creare dettagli di errore per flow {element_id}: {detail_error}")

    duration = int(time.time() - start_time)
    executed_by = current_user.username if current_user else "unknown"
    
    logger.info("=== SALVATAGGIO LOG DI ESECUZIONE ===")
    logger.info(f"Durata: {duration}s")
    logger.info(f"Eseguito da: {executed_by}")
    logger.info(f"Stato finale: {status}")

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
        logger.error(f"✗ Errore nel salvare log di esecuzione: {e}")

    logger.info("=== FINE ESECUZIONE FLOWS ===")
    return {
        "status": "success",
        "message": "Esecuzione dei flussi richiesta.",
        "results": [{"ids": flow_ids_str, "status": status, "log_key": log_key}],
    }