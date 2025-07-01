# sdp-api/api/tasks.py

import subprocess
import sys
import json
from pathlib import Path # <-- IMPORT MANCANTE

from fastapi import APIRouter, Depends, HTTPException, status, Security # <-- AGGIUNTO Security

# Importiamo la dependency di sicurezza e i modelli
from core.security import get_current_active_admin
from db import models # <-- IMPORT MANCANTE

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
@router.post("/update-flows-from-excel", response_model=dict)
def trigger_update_flows_from_excel(
    # La dependency di sicurezza va qui come parametro della funzione
    admin_user: models.User = Security(get_current_active_admin)
):
    """
    Esegue lo script Python per leggere il file Excel e generare il file flows.json aggiornato.
    Questo endpoint è protetto e accessibile solo agli admin.
    """
    # Usiamo pathlib per un percorso più robusto
    script_path = Path(__file__).parent.parent / "scripts" / "generate_flows_from_excel.py"
    
    if not script_path.is_file():
        raise HTTPException(status_code=500, detail=f"Script non trovato: {script_path}")

    print(f"--- Richiesto aggiornamento flussi da {admin_user.username}. Avvio script... ---")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            timeout=120
        )
        
        print("--- Script completato con successo ---")
        print("Output dello script:\n", result.stdout)
        if result.stderr:
            print("Avvisi/Errori minori dallo script:\n", result.stderr)

        return {"message": "Lista flussi aggiornata con successo dal file Excel.", "output": result.stdout}

    except subprocess.CalledProcessError as e:
        print(f"!!! ERRORE: Lo script ha fallito con codice {e.returncode} !!!\n{e.stderr}")
        raise HTTPException(
            status_code=500, 
            detail=f"L'aggiornamento dei flussi è fallito. Dettagli: {e.stderr}"
        )
    except subprocess.TimeoutExpired:
        print("!!! ERRORE: Lo script ha superato il tempo limite !!!")
        raise HTTPException(status_code=504, detail="Timeout durante l'aggiornamento dei flussi.")
    except Exception as e:
        print(f"!!! ERRORE SCONOSCIUTO: {e} !!!")
        raise HTTPException(status_code=500, detail=str(e))