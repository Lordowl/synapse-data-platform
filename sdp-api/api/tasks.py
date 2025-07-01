# sdp-api/api/tasks.py

import subprocess
import sys
import json
from pydantic import BaseModel
from pathlib import Path 
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Security # <-- AGGIUNTO Security

# Importiamo la dependency di sicurezza e i modelli
from core.security import get_current_active_admin
from db import models # <-- IMPORT MANCANTE
class UpdateRequest(BaseModel):
    file_path: str
class FilePathRequest(BaseModel):
    file_path: str
# Definiamo il router con il prefisso, così non dobbiamo ripeterlo
router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.post("/run-script")
def run_python_script(
    argument: str,
    # Proteggiamo l'endpoint passando la dependency come parametro
    admin_user: models.User = Security(get_current_active_admin)
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
    admin_user: models.User = Security(get_current_active_admin)
):
    """
    Esegue lo script Python per generare il file flows.json dall'Excel specificato,
    gestendo i percorsi dei file in modo robusto.
    """
    # 1. Estrae e normalizza il percorso del file di input dall'Excel
    raw_path_from_frontend = request_data.file_path
    try:
        # Usiamo pathlib per creare un oggetto percorso pulito e standard
        input_excel_path = Path(raw_path_from_frontend)
    except TypeError:
        raise HTTPException(status_code=400, detail="Il percorso del file fornito non è valido.")

    # 2. Costruisce il percorso dello script Python da eseguire
    script_path = Path(__file__).parent.parent / "scripts" / "generate_flows_from_excel.py"

    # 3. Controlli di esistenza dei file prima di procedere
    if not script_path.is_file():
        print(f"!!! ERRORE INTERNO: Script non trovato al percorso: {script_path}")
        raise HTTPException(status_code=500, detail="Errore di configurazione del server: script di aggiornamento mancante.")
    
    if not input_excel_path.is_file():
        print(f"!!! ERRORE UTENTE: File Excel non trovato al percorso: {input_excel_path}")
        raise HTTPException(status_code=400, detail=f"File Excel non trovato al percorso specificato: '{input_excel_path}'")

    print(f"--- Richiesto aggiornamento da {admin_user.username} ---")
    print(f"File di input: {input_excel_path}")
    print(f"Script da eseguire: {script_path}")

    # 4. Esegue lo script in un sottoprocesso sicuro
    try:
        # Convertiamo gli oggetti Path in stringhe per il comando
        command = [sys.executable, str(script_path), str(input_excel_path)]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,  # Lancia un'eccezione se lo script fallisce
            encoding="utf-8",
            timeout=120  # Timeout di 2 minuti
        )
        
        print("--- Script completato con successo ---")
        print("Output dello script:\n", result.stdout)
        if result.stderr:
            print("Avvisi/Errori minori dallo script (stderr):\n", result.stderr)

        return {"message": "Lista flussi aggiornata con successo dal file Excel.", "output": result.stdout}

    except subprocess.CalledProcessError as e:
        # Questo blocco viene attivato se lo script esce con un codice di errore
        error_details = e.stderr
        print(f"!!! ERRORE: Lo script Python ha fallito (exit code {e.returncode}) !!!")
        print(f"Dettaglio errore dallo script:\n{error_details}")
        raise HTTPException(
            status_code=500, 
            detail=f"L'esecuzione dello script di aggiornamento è fallita: {error_details}"
        )
    except subprocess.TimeoutExpired:
        print("!!! ERRORE: Lo script ha superato il tempo limite !!!")
        raise HTTPException(status_code=504, detail="Timeout: l'elaborazione del file Excel ha richiesto troppo tempo.")
    except Exception as e:
        # Per qualsiasi altro errore imprevisto durante l'esecuzione
        print(f"!!! ERRORE SCONOSCIUTO durante l'esecuzione del sottoprocesso: {e} !!!")
        raise HTTPException(status_code=500, detail=f"Errore imprevisto del server: {e}")