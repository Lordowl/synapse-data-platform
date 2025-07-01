import argparse
import time

def main(flow_id, package, week):
    print(f"--- Esecuzione dello script generico ---")
    print(f"  - ID Flusso ricevuto: {flow_id}")
    print(f"  - Package ricevuto: {package}")
    print(f"  - Settimana ricevuta: {week}")
    
    # Qui metti la tua logica reale...
    # Esempio:
    print("  - Sto processando i dati...")
    time.sleep(2) # Simula lavoro
    
    # Puoi anche simulare un fallimento per testare
    # import sys
    # if 'fail' in package.lower():
    #     print("ERRORE: Questo è un errore simulato.", file=sys.stderr)
    #     sys.exit(1)

    print(f"--- Esecuzione per il flusso {flow_id} completata. ---")

if __name__ == "__main__":
    # 1. Crea un parser per gli argomenti
    parser = argparse.ArgumentParser(description="Script di esecuzione generico per flussi.")
    
    # 2. Definisci gli argomenti che ti aspetti di ricevere
    parser.add_argument("--flow-id", required=True, help="L'ID univoco del flusso.")
    parser.add_argument("--package", required=True, help="Il package del flusso.")
    parser.add_argument("--week", help="La settimana di riferimento per l'esecuzione.")
    
    # 3. Parsa gli argomenti passati dalla riga di comando
    args = parser.parse_args()
    
    # 4. Chiama la tua funzione principale con gli argomenti parsati
    main(flow_id=args.flow_id, package=args.package, week=args.week)