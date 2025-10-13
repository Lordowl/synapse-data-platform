"""
Script per gestire il file di configurazione repo_update_default.json

Permette di:
- Visualizzare il contenuto corrente
- Aggiungere una nuova banca
- Modificare i valori esistenti
- Ripristinare i valori di default
"""
import json
import sys
from pathlib import Path

CONFIG_FILE = Path.home() / ".sdp-api" / "repo_update_default.json"
DEFAULT_DATA = [
    {"settimana": 1, "anno": 2025, "semaforo": 0, "bank": "Sparkasse"},
    {"settimana": 1, "anno": 2025, "semaforo": 0, "bank": "CiviBank"}
]

def load_config():
    """Carica la configurazione dal file"""
    if not CONFIG_FILE.exists():
        print(f"[INFO] File non trovato, creo nuovo file in: {CONFIG_FILE}")
        save_config(DEFAULT_DATA)
        return DEFAULT_DATA

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Errore nella lettura del file: {e}")
        return None

def save_config(data):
    """Salva la configurazione nel file"""
    try:
        CONFIG_FILE.parent.mkdir(exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[OK] Configurazione salvata in: {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"[ERROR] Errore nel salvataggio: {e}")
        return False

def show_config():
    """Mostra la configurazione corrente"""
    data = load_config()
    if not data:
        return

    print("\n" + "="*60)
    print("CONFIGURAZIONE REPO_UPDATE_INFO")
    print("="*60)
    print(f"File: {CONFIG_FILE}\n")

    for i, entry in enumerate(data, 1):
        print(f"{i}. Bank: {entry.get('bank', 'N/A'):15s} | "
              f"Anno: {entry.get('anno', 'N/A')} | "
              f"Settimana: {entry.get('settimana', 'N/A')} | "
              f"Semaforo: {entry.get('semaforo', 'N/A')}")
    print("="*60 + "\n")

def add_bank():
    """Aggiunge una nuova banca"""
    data = load_config()
    if data is None:
        return

    print("\n--- Aggiungi nuova banca ---")
    bank = input("Nome banca: ").strip()

    if not bank:
        print("[ERROR] Nome banca obbligatorio")
        return

    # Verifica se esiste già
    if any(e.get('bank') == bank for e in data):
        print(f"[ERROR] La banca '{bank}' esiste già")
        return

    anno = input("Anno (default 2025): ").strip() or "2025"
    settimana = input("Settimana (default 1): ").strip() or "1"
    semaforo = input("Semaforo (default 0): ").strip() or "0"

    try:
        new_entry = {
            "settimana": int(settimana),
            "anno": int(anno),
            "semaforo": int(semaforo),
            "bank": bank
        }
        data.append(new_entry)
        save_config(data)
        print(f"[OK] Banca '{bank}' aggiunta con successo")
    except ValueError:
        print("[ERROR] Anno, settimana e semaforo devono essere numeri")

def update_bank():
    """Modifica i valori di una banca esistente"""
    data = load_config()
    if data is None or not data:
        print("[ERROR] Nessuna configurazione trovata")
        return

    show_config()
    try:
        idx = int(input("Numero della banca da modificare: ")) - 1
        if idx < 0 or idx >= len(data):
            print("[ERROR] Numero non valido")
            return
    except ValueError:
        print("[ERROR] Inserisci un numero valido")
        return

    entry = data[idx]
    print(f"\nModifica banca: {entry['bank']}")
    print("(Premi INVIO per mantenere il valore corrente)")

    anno = input(f"Anno ({entry.get('anno')}): ").strip()
    settimana = input(f"Settimana ({entry.get('settimana')}): ").strip()
    semaforo = input(f"Semaforo ({entry.get('semaforo')}): ").strip()

    try:
        if anno:
            entry['anno'] = int(anno)
        if settimana:
            entry['settimana'] = int(settimana)
        if semaforo:
            entry['semaforo'] = int(semaforo)

        save_config(data)
        print(f"[OK] Banca '{entry['bank']}' aggiornata")
    except ValueError:
        print("[ERROR] Anno, settimana e semaforo devono essere numeri")

def remove_bank():
    """Rimuove una banca"""
    data = load_config()
    if data is None or not data:
        print("[ERROR] Nessuna configurazione trovata")
        return

    show_config()
    try:
        idx = int(input("Numero della banca da rimuovere: ")) - 1
        if idx < 0 or idx >= len(data):
            print("[ERROR] Numero non valido")
            return
    except ValueError:
        print("[ERROR] Inserisci un numero valido")
        return

    bank_name = data[idx]['bank']
    confirm = input(f"Sicuro di voler rimuovere '{bank_name}'? (s/N): ")

    if confirm.lower() == 's':
        data.pop(idx)
        save_config(data)
        print(f"[OK] Banca '{bank_name}' rimossa")
    else:
        print("[INFO] Operazione annullata")

def reset_to_default():
    """Ripristina la configurazione di default"""
    print("\n[WARNING] Questa operazione sovrascrivera' la configurazione corrente")
    confirm = input("Continuare? (s/N): ")

    if confirm.lower() == 's':
        save_config(DEFAULT_DATA)
        print("[OK] Configurazione ripristinata ai valori di default")
    else:
        print("[INFO] Operazione annullata")

def main():
    while True:
        print("\n" + "="*60)
        print("GESTIONE CONFIGURAZIONE REPO_UPDATE_INFO")
        print("="*60)
        print("1. Visualizza configurazione")
        print("2. Aggiungi banca")
        print("3. Modifica banca")
        print("4. Rimuovi banca")
        print("5. Ripristina valori di default")
        print("0. Esci")
        print("="*60)

        choice = input("\nScelta: ").strip()

        if choice == '1':
            show_config()
        elif choice == '2':
            add_bank()
        elif choice == '3':
            update_bank()
        elif choice == '4':
            remove_bank()
        elif choice == '5':
            reset_to_default()
        elif choice == '0':
            print("\n[INFO] Arrivederci!")
            break
        else:
            print("[ERROR] Scelta non valida")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Operazione interrotta dall'utente")
        sys.exit(0)
