import pandas as pd
import json
import os
import sys
from pathlib import Path
import numpy as np

def clean_and_filter_data(file_path: str, sheet_name: str) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str).fillna('')

        required_cols = ['Package', 'Filename out', 'Path out', 'Formato out']
        for col in required_cols:
            if col not in df.columns:
                print(f"Errore Critico: La colonna essenziale '{col}' non è stata trovata.")
                return None

        # Forward fill su Package
        print("   -> Applicazione forward fill sulla colonna 'Package'...")
        package_col = df['Package']
        package_col_cleaned = package_col.replace(r'^\s*$', np.nan, regex=True)
        df['Package'] = package_col_cleaned.ffill()

        # 🔑 Ricostruzione della colonna "Filename out"
        print("   -> Creazione nuova colonna 'Filename out' da Path/Filename/Formato...")
        df['Filename out'] = (
            df['Path out'].str.strip() + "/" +
            df['Filename out'].str.strip() + "." +
            df['Formato out'].str.strip()
        )

        # Rimozione righe completamente vuote (eccetto Package)
        other_cols = [col for col in df.columns if col != 'Package']
        df.dropna(subset=other_cols, how='all', inplace=True)

        # Filtra righe con Filename out non vuoto
        initial_rows = len(df)
        df = df[df['Filename out'].str.strip() != ''].copy()
        print(f"   -> Filtraggio per 'Filename out' non vuoto: {initial_rows} -> {len(df)} righe.")

        # Conversione numerica ID e SEQ (se presenti)
        for col in ['ID', 'SEQ']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64').where(pd.notna(df[col]), None)

        return df

    except FileNotFoundError:
        print(f"Errore: File non trovato al percorso '{file_path}'")
        return None
    except Exception as e:
        print(f"Errore durante la lettura o pulizia del file: {e}")
        return None

# --- NUOVA FUNZIONE PER RIMUOVERE I DUPLICATI ---
def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rimuove le righe duplicate basate sulla coppia di colonne (ID, SEQ),
    mantenendo solo la prima occorrenza.
    """
    if 'ID' not in df.columns or 'SEQ' not in df.columns:
        print("Avviso: Colonne 'ID' o 'SEQ' non trovate, impossibile rimuovere i duplicati.")
        return df

    # Identifica le righe duplicate basate su ID e SEQ
    # `keep='first'` assicura che la prima riga venga mantenuta
    # `~` inverte la selezione, quindi selezioniamo solo le righe NON duplicate
    num_righe_prima = len(df)
    df_deduplicated = df.drop_duplicates(subset=['ID', 'SEQ'], keep='first')
    num_righe_dopo = len(df_deduplicated)
    
    if num_righe_prima > num_righe_dopo:
        print(f"   -> Rimossi {num_righe_prima - num_righe_dopo} duplicati basati su (ID, SEQ).")
    
    return df_deduplicated

def extract_flows_to_flat_list(df_filtered: pd.DataFrame, columns_to_extract: list) -> dict | None:
    # ... (questa funzione rimane invariata)
    if df_filtered is None or df_filtered.empty: return None
    existing_columns = [col for col in columns_to_extract if col in df_filtered.columns]
    flows_list = df_filtered[existing_columns].to_dict('records')
    return {"flows": flows_list}

def save_json(data: dict, output_path: str):
    # ... (questa funzione rimane invariata)
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"✅ JSON salvato con successo in: {output_path}")
    except Exception as e:
        print(f"Errore durante il salvataggio del file JSON: {e}")

# --- Blocco Principale di Esecuzione (MODIFICATO) ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Errore: Percorso del file Excel non fornito come argomento.")
        sys.exit(1)
        
    INPUT_FILE = sys.argv[1]
    # --- CONFIGURAZIONE ---
    BASE_PATH = Path(__file__).parent
    SHEET_NAME = 'File reportistica'
    OUTPUT_JSON_FILE = BASE_PATH.parent / "data" / "flows.json"
    COLUMNS_FOR_JSON = ['ID', 'SEQ', 'Package','Filename out', ]

    print("--- INIZIO ESTRAZIONE FLUSSI ---")

    # 1. Legge, pulisce e filtra i dati
    print(f"1. Lettura e filtraggio del foglio '{SHEET_NAME}'...")
    df_filtered = clean_and_filter_data(INPUT_FILE, SHEET_NAME)

    if df_filtered is not None and not df_filtered.empty:
        print(f"   -> Trovati {len(df_filtered)} flussi validi inizialmente.")
        
        # 2. NUOVO STEP: Rimuovi i duplicati
        print("\n2. Rimozione dei duplicati...")
        df_deduplicated = remove_duplicates(df_filtered)
        print(f"   -> Numero finale di flussi unici: {len(df_deduplicated)}.")
        
        # 3. Trasforma i dati de-duplicati in JSON
        print("\n3. Creazione della lista piatta JSON...")
        flows_json = extract_flows_to_flat_list(df_deduplicated, COLUMNS_FOR_JSON)
        
        if flows_json:
            flow_count = len(flows_json.get("flows", []))
            print(f"   -> Trasformazione completata. Creato un array con {flow_count} flussi.")
            
            # 4. Salva il file JSON
            print("\n4. Salvataggio del file JSON...")
            save_json(flows_json, OUTPUT_JSON_FILE)
            
    elif df_filtered is not None:
         print("\nNessun flusso valido trovato. Il file JSON non verrà creato.")

    print("\n--- ESECUZIONE COMPLETATA ---")