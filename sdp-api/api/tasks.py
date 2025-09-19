# sdp-api/api/tasks.py

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict

from fastapi import APIRouter, Depends, Security, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import crud, models
from db.database import get_db
from core.security import  require_settings_permission,require_ingest_permission
from fastapi import APIRouter, Depends, HTTPException, status, Security # <-- AGGIUNTO Security

# Importiamo la dependency di sicurezza e i modelli

from db import models # <-- IMPORT MANCANTE
class UpdateRequest(BaseModel):
    file_path: str
class FilePathRequest(BaseModel):
    file_path: str
# Schema per i dati di un singolo flusso che ci aspettiamo dal frontend
class FlowPayload(BaseModel):
    id: str
    name: str
    # Aggiungi altri campi se li invii dal frontend e ti servono nel backend

# Schema per l'intera richiesta di esecuzione
class ExecutionRequest(BaseModel):
    flows: List[FlowPayload]
    params: Dict
# Definiamo il router con il prefisso, così non dobbiamo ripeterlo
router = APIRouter(tags=["Tasks"])

@router.post("/run-script")
def run_python_script(
    argument: str,
    # Proteggiamo l'endpoint passando la dependency come parametro
    admin_user: models.User = Security(require_ingest_permission)
):
    """
    Esegue uno script di esempio con un argomento.
    Protetto e accessibile solo agli admin.
    """
    script_path = "scripts/sample_script.py" # Assumendo che esista
    
    try:
        process = subprocess.run(
            [sys.executable, script_path, argument],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            encoding="utf-8"
        )
        
        return {
            "message": "Script di esempio eseguito con successo.",
            "output": process.stdout
        }
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"message": "Errore durante l'esecuzione dello script.", "stderr": e.stderr}
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="L'esecuzione dello script ha superato il tempo limite."
        )

# --- ENDPOINT CORRETTO PER AGGIORNARE I FLUSSI ---
@router.post("/update-flows-from-excel", response_model=Dict)
def trigger_update_flows_from_excel(
    request_data: FilePathRequest,
    current_user: models.User = Security(require_settings_permission)  # Admin o permesso settings
):
    """
    Esegue lo script Python per generare il file flows.json dall'Excel specificato.
    Gestendo i percorsi dei file in modo robusto.
    """
    raw_path_from_frontend = request_data.file_path
    try:
        input_excel_path = Path(raw_path_from_frontend)
    except TypeError:
        raise HTTPException(status_code=400, detail="Il percorso del file fornito non è valido.")

    script_path = Path(__file__).parent.parent / "scripts" / "generate_flows_from_excel.py"

    if not script_path.is_file():
        raise HTTPException(status_code=500, detail="Errore di configurazione del server: script di aggiornamento mancante.")
    
    if not input_excel_path.is_file():
        raise HTTPException(status_code=400, detail=f"File Excel non trovato al percorso specificato: '{input_excel_path}'")

    print(f"--- Richiesto aggiornamento da {current_user.username} ---")
    print(f"File di input: {input_excel_path}")
    print(f"Script da eseguire: {script_path}")

    try:
        command = [sys.executable, str(script_path), str(input_excel_path)]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            timeout=120
        )
        print("--- Script completato con successo ---")
        print("Output dello script:\n", result.stdout)
        if result.stderr:
            print("Avvisi/Errori minori dallo script (stderr):\n", result.stderr)

        return {"message": "Lista flussi aggiornata con successo dal file Excel.", "output": result.stdout}

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"L'esecuzione dello script di aggiornamento è fallita: {e.stderr}"
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout: l'elaborazione del file Excel ha richiesto troppo tempo.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore imprevisto del server: {e}")



@router.post("/execute-flows", response_model=Dict)
def execute_selected_flows(
    request: ExecutionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Security(require_ingest_permission)
):
    """
    Esegue tutti i flussi selezionati insieme, loggando un unico record
    nel DB con tutti gli ID separati da spazio.
    """
    print(f"Richiesta di esecuzione da {current_user.username} per {len(request.flows)} flussi.")
    print(request)

    script_path = Path(__file__).parent.parent / "scripts" / "ingestion.ps1"
    if not script_path.is_file():
        raise HTTPException(status_code=500, detail="File di esecuzione .ps1 non trovato.")

    # Costruzione stringa con tutti gli ID separati da spazio
    flow_ids_str = " ".join(str(flow.id) for flow in request.flows)
    print(f"Flow IDs da eseguire: {flow_ids_str}")

    start_time = time.time()
    status = "Failed"
    script_output = ""
    script_error = ""

    try:
        # --- COSTRUZIONE COMANDO POWERHELL ---
        command_args = [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-File", str(script_path),
            "-id", flow_ids_str,
            "-anno", str(request.params.get("selectedYear", "")),
            "-settimana", str(request.params.get("selectedWeek", "")),
            "-log_key","abc"
        ]

        print(f"Esecuzione comando: {' '.join(command_args)}")

        # --- ESECUZIONE FILE .ps1 TRAMITE POWERSHELL ---
        result = subprocess.run(
            command_args,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
            encoding="utf-8",
            shell=False
        )

        status = "Success"
        script_output = result.stdout
        if result.stderr:
            script_output += f"\n--- stderr ---\n{result.stderr}"

    except subprocess.CalledProcessError as e:
        status = "Failed"
        script_error = e.stderr
        print(f"!!! ERRORE nello script .ps1: {script_error}")

    except Exception as e:
        status = "Failed"
        script_error = f"Errore imprevisto nell'API: {str(e)}"
        print(f"!!! ERRORE API: {script_error}")

    # --- LOG UNICO ---
    end_time = time.time()
    duration = int(end_time - start_time)

    crud.create_execution_log(
        db=db,
        flow_id_str=flow_ids_str,  # tutti gli ID in un unico record, separati da spazio
        status=status,
        duration_seconds=duration,
        details={
            "executed_by": current_user.username,
            "params": request.params,
            "output": script_output,
            "error": script_error,
            "log_key": f"exec_{int(time.time())}"
        }
    )

    return {
        "status": "success",
        "message": "Esecuzione dei flussi richiesta.",
        "results": [{"ids": flow_ids_str, "status": status}]
    }
