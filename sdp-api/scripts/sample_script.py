# my_fastapi_backend/scripts/sample_script.py

import sys
import time
import json

def run_task(argument: str):
    """
    Simula un'operazione che richiede tempo e produce un risultato.
    """
    print(f"INFO: Script avviato alle {time.ctime()} con l'argomento: '{argument}'.")
    
    # Simula del lavoro
    for i in range(5):
        print(f"INFO: Lavoro in corso... step {i+1}/5")
        time.sleep(1)
        
    # Prepara un output in formato JSON
    result = {
        "status": "success",
        "input_argument": argument,
        "completion_time": time.ctime(),
        "message": "Il task è stato completato con successo!"
    }
    
    # Scrive il risultato su stdout in formato JSON, così può essere catturato facilmente.
    print(json.dumps(result))

    print("INFO: Script terminato.")

if __name__ == "__main__":
    # Lo script viene eseguito solo se chiamato direttamente
    # e si aspetta esattamente un argomento.
    if len(sys.argv) != 2:
        error_message = {
            "status": "error",
            "message": "Errore: lo script richiede esattamente un argomento."
        }
        print(json.dumps(error_message), file=sys.stderr) # Scrivi l'errore su stderr
        sys.exit(1) # Esce con un codice di errore
    
    # Prende l'argomento dalla riga di comando
    arg = sys.argv[1]
    run_task(arg)