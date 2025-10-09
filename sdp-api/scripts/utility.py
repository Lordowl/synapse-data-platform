from typing import *
import os
import time
import shutil
import platform
import sys
# from pypdf import PdfWriter
# from pypdf.errors import PdfReadError # Importa l'errore
import logging # o semplicemente print
import pandas as pd


def extract_error(data: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    """
    Estrae le informazioni dai dati JSON analizzati.
    
    Args:
        data: Dati JSON analizzati
        
    Returns:
        - Errore utente non abilitato
    """
    
    def process_object(obj):
        if not isinstance(obj, dict):
            return
        
        error = None
        if "Scelta utente" in obj:
            user_choice = obj["Scelta utente"]
            for item_key, item_value in user_choice.items():
                if isinstance(item_value, dict) and ("premere su inserisci indirizzi posta elettronica" in item_value or "premere su visualizzatore" in item_value):
                    for error_key, error_value in item_value.items():
                        if error_key == "estrarre errore utente":
                            if item_value[error_key]["status"] == "success":
                                error = item_value[error_key]["extracted_texts"][0]
                        if error_key == "estrarre banner errore utente":
                            if item_value[error_key]["status"] == "success":
                                error = item_value[error_key]["extracted_texts"][0]
        elif "Download dati" in obj:
            download_data = obj["Download dati"]
            print(download_data)
            for item_key, item_value in download_data.items():
                print(item_key, item_value)
                if isinstance(item_value, dict) and "Controllo tabella" in item_value:
                    if item_value["Controllo tabella"]["status"] == "success":
                        error = item_value["Controllo tabella"]["extracted_texts"][0]
        
        for value in obj.values():
            if isinstance(value, dict):
                process_object(value)
        
        return error
    
    error = process_object(data)
    
    return error


def extract_information(data: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    """
    Estrae le informazioni dai dati JSON analizzati.
    
    Args:
        data: Dati JSON analizzati
        
    Returns:
        Tupla contenente:
        - Lista di testi estratti da Super header
        - Lista di testi estratti da Titoli
        - Lista di testi estratti da Sottotitoli
    """
    super_header_texts = []
    titoli_texts = []
    sottotitoli_texts = []
    
    def process_object(obj):
        if not isinstance(obj, dict):
            return
        
        if "Super header" in obj:
            super_header = obj["Super header"]
            for item_key, item_value in super_header.items():
                if isinstance(item_value, dict) and "extracted_texts" in item_value:
                    super_header_texts.extend(item_value["extracted_texts"])
        elif "Singolo super header" in obj:
            super_header = obj["Singolo super header"]
            for item_key, item_value in super_header.items():
                if isinstance(item_value, dict) and "extracted_texts" in item_value:
                    super_header_texts.extend(item_value["extracted_texts"])
        
        if "Titoli" in obj:
            titoli = obj["Titoli"]
            for item_key, item_value in titoli.items():
                if isinstance(item_value, dict) and "extracted_texts" in item_value:
                    if "titolo" in item_key.lower() and "sotto" not in item_key.lower():
                        titoli_texts.extend(item_value["extracted_texts"])
                    elif "sottotitolo" in item_key.lower():
                        sottotitoli_texts.extend(item_value["extracted_texts"])
        
        for value in obj.values():
            if isinstance(value, dict):
                process_object(value)
    
    process_object(data)
    
    return super_header_texts, titoli_texts, sottotitoli_texts


def get_download_path():
    """Restituisce il percorso della cartella download in base al sistema operativo"""
    if platform.system() == "Windows":
        import winreg
        # Prova a ottenere la cartella Downloads dal registro di sistema
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders') as key:
                download_path = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')[0]
                return download_path
        except Exception:
            # Fallback alla posizione predefinita
            return os.path.join(os.path.expanduser("~"), "Downloads")
    else:  # Linux/Unix/MacOS
        return os.path.join(os.path.expanduser("~"), "Downloads")

def get_destination_path():
    """Restituisce il percorso di destinazione nella cartella home dell'utente"""
    return os.path.join(os.path.expanduser("~"), "spks_dispatching tmp")

def is_file_downloading(file_path):
    """
    Controlla se il file è ancora in download
    Restituisce True se la dimensione del file sta cambiando (ancora in download)
    """
    try:
        if not os.path.exists(file_path):
            return False
           
        initial_size = os.path.getsize(file_path)
        time.sleep(1)  # Attendi 1 secondo
        current_size = os.path.getsize(file_path)
       
        # Se la dimensione sta cambiando, il file è ancora in download
        return initial_size != current_size
    except Exception as e:
        print(f"Errore durante il controllo del download: {e}")
        return False

def is_file_recent(file_path, max_age_seconds=20):
    """Controlla se il file non è più vecchio dei secondi specificati"""
    try:
        file_time = os.path.getctime(file_path)
        current_time = time.time()
        return (current_time - file_time) <= max_age_seconds
    except Exception as e:
        print(f"Errore durante il controllo dell'età del file: {e}")
        return False

def wait_for_download_completion(file_path, timeout_seconds=300):
    """Attendi il completamento del download con un timeout"""
    start_time = time.time()
   
    while is_file_downloading(file_path):
        if time.time() - start_time > timeout_seconds:
            print(f"Timeout dopo aver atteso {timeout_seconds} secondi per il completamento del download")
            return False
       
        print("Il file è ancora in download. Attendo...")
        time.sleep(2)
   
    print("Il download sembra essere completato o ha smesso di trasferire dati")
    return True

def wait_for_file_to_appear(file_path, timeout_seconds=300):
    """Attendi che il file appaia nella cartella download con un timeout"""
    start_time = time.time()
   
    while not os.path.exists(file_path):
        if time.time() - start_time > timeout_seconds:
            print(f"Timeout dopo aver atteso {timeout_seconds} secondi per l'apparizione del file")
            return False
       
        print(f"In attesa che {os.path.basename(file_path)} appaia nella cartella download...")
        time.sleep(2)
   
    print(f"Il file {os.path.basename(file_path)} è apparso nella cartella download")
    return True

def check_and_move(download_folder: Optional[str] = None):
    try:
        # Ottieni i percorsi
        if not download_folder:
            download_folder = get_download_path()
        destination_folder = get_destination_path()
        file_path = os.path.join(download_folder, "data.xlsx")
       
        print(f"Cercando data.xlsx in: {download_folder}")
       
        # Crea la cartella di destinazione se non esiste
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
            print(f"Cartella creata: {destination_folder}")
       
        # Controlla se il file esiste nella cartella download
        if not os.path.exists(file_path):
            print(f"File {file_path} non trovato. Attendo che appaia...")
            if not wait_for_file_to_appear(file_path):
                print("Il file non è apparso entro il periodo di timeout. Uscita.")
                return
       
        print(f"File trovato: {file_path}")
       
        # Controlla se il file è ancora in download
        if is_file_downloading(file_path):
            print("Il file sembra essere ancora in download.")
            if not wait_for_download_completion(file_path):
                print("Non è stato possibile completare l'operazione poiché il file è ancora in download.")
                return
       
        # Controlla se il file è abbastanza recente
        if is_file_recent(file_path):
            print("Il file è recente (creato negli ultimi 20 secondi).")
            # Sposta il file a destinazione
            destination_file = os.path.join(destination_folder, "data.xlsx")
            shutil.move(file_path, destination_file)
            print(f"File spostato con successo in: {destination_file}")
        else:
            print("Il file è più vecchio di 20 secondi. Operazione saltata.")
           
    except Exception as e:
        print(f"Si è verificato un errore: {e}")
        sys.exit(1)


# def merge_pdf(pdf_list: list, output_name: str):
#     print("Merging pdf...")
#     merging_pdf_error = []
#     writer = PdfWriter()
#     for pdf_file in pdf_list:
#         try:
#             # print(f"Tentativo di aggiungere il file: {pdf_file}") # <-- AGGIUNGI QUESTO
#             writer.append(pdf_file)
#         except PdfReadError:    # Gestisci l'errore se vuoi che il programma continui
#             print(f"Errore di lettura PDF: il file '{pdf_file}' è corrotto o malformato. Verrà saltato.")
#             merging_pdf_error.append(f"Errore di lettura PDF: il file '{pdf_file}' è corrotto o malformato. Saltato.")  # Aggiungi il file problematico alla lista degli errori
#             continue # Continua con il prossimo file
#         except Exception as e:  # Gestisci altri errori se necessario   
#             print(f"Errore {e} nella gestione del PDF '{pdf_file}. Verrà saltato.")
#             merging_pdf_error.append(f"Errore {e} nella gestione del PDF '{pdf_file}. Saltato.")  # Aggiungi il file problematico alla lista degli errori
#             continue    # raise    Rilancia l'errore per fermare l'esecuzione (comportamento attuale)
#     with open(output_name, "wb") as output_file:
#         writer.write(output_file)
#     return merging_pdf_error  # Restituisci la lista degli errori di merging PDF

# def ex_merge_pdf(pdf_list: list, output_name: str):
#     print("Merging pdf...")
#     writer = PdfWriter()
#     for pdf_file in pdf_list:
#         writer.append(pdf_file)
#     with open(output_name, "wb") as output_file:
#         writer.write(output_file)


# def merge_html(html_list: list, output_name: str):
#     print("Merging html...")
#     merged_html = ""
#     for html_file in html_list:
#         # Leggi i contenuti dei file HTML
#         with open(html_file, 'r') as file:
#             new_html = file.read()
#         # Concatenarli
#         merged_html += new_html
#     # Salva il risultato in un nuovo file
#     with open(output_name, 'w') as output_file:
#         output_file.write(merged_html)


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev, library, and PyInstaller"""
 
    if hasattr(sys, "_MEIPASS"):
        base_path = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "spks_dispatching")
    else:
        if "site-packages" in os.path.abspath(__file__):
            base_path = os.path.dirname(os.path.abspath(__file__))
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
   
    return os.path.join(base_path, relative_path)


def get_script_path(relative_path):
    """Restituisce il path assoluto del file nella build (sia in dev che in exe)."""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def get_users_list(users_db_path: str) -> list:
    users_db = pd.read_excel(users_db_path, sheet_name=None)
    users_list = []
    for sheet in users_db:
        users = list(users_db[sheet]["Email"])
        users_list += users
    return users_list


def get_users_from_sharepoint():
    "Restituisce la lista degli utenti dal file disponibile su sharepoint."
    pass


def get_config_from_sharepoint():
    "Restituisce il dizionario dei modelli semantici dal file disponibile su sharepoint."
    pass


def get_flow_from_sharepoint():
    "Restituisce il workbook e il _FLOW_NAME di FluentX dal file disponibile su sharepoint."
    pass
    