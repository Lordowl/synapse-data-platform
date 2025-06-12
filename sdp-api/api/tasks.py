# my_fastapi_backend/api/tasks.py

import subprocess
import sys
from fastapi import APIRouter, Depends, HTTPException, status
import json

# Importiamo la dependency per assicurarci che solo un admin possa eseguire questo task
from core.security import get_current_active_admin

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.post("/run-script", dependencies=[Depends(get_current_active_admin)])
def run_python_script(argument: str):
    """
    Esegue lo script `sample_script.py` in un sottoprocesso.
    Questo endpoint è protetto e richiede privilegi di amministratore.
    
    - **argument**: L'argomento da passare allo script.
    """
    script_path = "scripts/sample_script.py"
    
    try:
        # sys.executable garantisce che usiamo lo stesso interprete Python
        # dell'ambiente virtuale in cui FastAPI è in esecuzione.
        # Questo è FONDAMENTALE per la coerenza delle dipendenze.
        process = subprocess.run(
            [sys.executable, script_path, argument],
            capture_output=True,  # Cattura stdout e stderr
            text=True,            # Decodifica output e error come testo (UTF-8)
            check=True,           # Lancia un'eccezione se lo script esce con un codice di errore (es. sys.exit(1))
            timeout=30            # Imposta un timeout di 30 secondi
        )
        
        # Tentiamo di parsare l'ultima riga dell'output come JSON
        # perché il nostro script è progettato per stampare il risultato JSON alla fine.
        try:
            # Cerchiamo l'ultima riga che inizia con '{' per trovare il nostro JSON
            json_output = [line for line in process.stdout.strip().split('\n') if line.startswith('{')][-1]
            result_data = json.loads(json_output)
        except (json.JSONDecodeError, IndexError):
            # Se il parsing fallisce, restituisci l'output grezzo
            result_data = {
                "warning": "Impossibile parsare l'output JSON dello script.",
                "raw_output": process.stdout
            }

        return {
            "message": "Script eseguito con successo.",
            "script_result": result_data,
            "full_log": process.stdout # Possiamo anche restituire l'intero log
        }
        
    except subprocess.CalledProcessError as e:
        # Questo errore viene lanciato se `check=True` e lo script ha un errore
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={
                "message": "Errore durante l'esecuzione dello script.",
                "stderr": e.stderr
            }
        )
    except subprocess.TimeoutExpired:
        # Questo errore viene lanciato se lo script impiega più di `timeout` secondi
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="L'esecuzione dello script ha superato il tempo limite di 30 secondi."
        )