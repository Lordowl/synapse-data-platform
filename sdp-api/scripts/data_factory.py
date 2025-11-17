from os.path import *
import sys
import time
import logging
from fluentx.flow_executor import run_flow
from fluentx.utility import get_general_config
from openpyxl import load_workbook
from scripts.utility import extract_information, extract_html_table, check_and_move, get_download_path, get_destination_path, extract_error, get_resource_path, get_users_list, get_config_from_sharepoint, get_users_from_sharepoint, get_flow_from_sharepoint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
import pandas as pd

logger = logging.getLogger(__name__)


def wait_until_element_disappears_robust(driver: webdriver.Chrome, element_xpath: str, timeout: int = 300) -> bool:
    """
    Waits until an element identified by XPath disappears from the DOM with robust error handling.
    :param driver: Selenium driver instance
    :type driver: webdriver.Chrome
    :param element_xpath: XPath of the element to wait for disappearance
    :type element_xpath: str
    :param timeout: Maximum waiting time in seconds
    :type timeout: int
    :return: True if the element disappeared, False if timeout occurred
    :rtype: bool
    """
    try:
        wait = WebDriverWait(driver, timeout, poll_frequency=0.5, 
                             ignored_exceptions=[StaleElementReferenceException])
        wait.until_not(EC.presence_of_element_located((By.XPATH, element_xpath)))
        return True
    except TimeoutException:
        # Element is still present after timeout
        return False



from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time 

def estrai_dettagli_errore_azure(driver):
    """
    Estrae i dettagli dal pannello di errore Azure (versione mat-dialog).
    Nessun iframe necessario.
    """
    
    # --- XPaths basati sul tuo HTML ---
    
    # XPath robusto per il contenitore del pannello
    xpath_pannello_errore = "//div[contains(@role, 'dialog') and contains(@aria-label, 'Error details')]"
    
    
    # XPath per le righe di errore (relativo al pannello)
    xpath_errore_lines = ".//div[contains(@class, 'error-line')]"
    
    # XPath per la "chiave" dell'errore (relativo alla riga)
    xpath_errore_key = ".//span[contains(@class, 'error-type')]"
    
    # XPath per il bottone di chiusura (relativo al pannello)
    xpath_bottone_chiudi = ".//div[@role='button' and @aria-label='Close']"
    
    # --- Fine XPaths ---

    try:
        wait = WebDriverWait(driver, 10)
        dettagli_errore = {}

        # 1. Attendi che il pannello dell'errore sia visibile
        print("Attendo la comparsa del pannello di errore (mat-dialog)...")
        pannello = wait.until(EC.visibility_of_element_located((By.XPATH, xpath_pannello_errore)))
        print("Pannello di errore apparso.")
        
        # 2. Trova tutte le righe di dettaglio
        error_lines = pannello.find_elements(By.XPATH, xpath_errore_lines)
        print(f"Trovate {len(error_lines)} linee di dettaglio da estrarre.")

        # 3. Itera su ogni riga ed estrai chiave e valore
        for line in error_lines:
            try:
                key_element = line.find_element(By.XPATH, xpath_errore_key)
                key = key_element.text.strip()
                
                full_text = line.text
                value = full_text.replace(key_element.text, "").strip()
                
                if key and value:
                    print(f"  - Estratto: {key} = {value[:70]}...") # Tronca log lunghi
                    dettagli_errore[key] = value
                    
            except NoSuchElementException:
                continue

        # 4. Chiudi il pannello
        print("Estrazione completata. Chiudo il pannello di errore.")
        pannello.find_element(By.XPATH, xpath_bottone_chiudi).click()
        
        # Attendi che il pannello sparisca
        wait.until(EC.invisibility_of_element_located((By.XPATH, xpath_pannello_errore)))
        
        return dettagli_errore

    except (TimeoutException, NoSuchElementException) as e:
        print(f"Errore: Impossibile trovare o estrarre i dettagli dal pannello di errore. {e}")
        return None
    

def estrai_dettagli_errore(driver):
    """
    Attende il popup dell'errore, espande i dettagli, estrae tutte le
    informazioni in un dizionario, chiude il popup e restituisce i dati.
    """
    # Definisci gli XPath basati sull'HTML fornito
    dialog_xpath = "//mat-dialog-container[@role='dialog']"
    details_button_xpath = "//button[@data-testid='see-detail-expand-button']"
    close_button_xpath = "//button[@data-testid='close-button']"
    
    try:
        wait = WebDriverWait(driver, 10)

        # 1. Attendi che il pannello dell'errore sia visibile
        print("Attendo la comparsa del pannello di errore...")
        dialog = wait.until(EC.visibility_of_element_located((By.XPATH, dialog_xpath)))
        print("Pannello di errore apparso.")

        # 2. Clicca su "Visualizza dettagli" se non sono già mostrati
        try:
            details_button = dialog.find_element(By.XPATH, details_button_xpath)
            # Espando se trovo "Visualizza dettagli"
            if "Visualizza" in details_button.text:
                print("Espando i dettagli dell'errore...")
                details_button.click()
                # Aggiungo una piccola attesa
                time.sleep(0.5)
        except NoSuchElementException:
            print("Bottone 'Visualizza dettagli' non trovato, si presume siano già visibili.")

        # Estraggo tutte le informazioni
        dettagli_errore = {}
        # Trova tutti gli elementi <li> nella lista degli errori
        error_items = dialog.find_elements(By.XPATH, ".//ul/li")
        
        print("Estraggo le informazioni dall'elenco:")
        for item in error_items:
            try:
                # Per ogni <li>, trova il label e il suo valore
                label = item.find_element(By.XPATH, ".//span[contains(@class, 'error-info-label')]").text
                value = item.find_element(By.XPATH, ".//span[contains(@class, 'errornfo')]").text
                dettagli_errore[label] = value
                print(f"  - {label}: {value}")
            except NoSuchElementException:
                print()
                continue # Salta eventuali <li> malformati

        # Chiudo il pannello di errore
        print("Chiudo il pannello di errore.")
        dialog.find_element(By.XPATH, close_button_xpath).click()
        # Attendi che il pannello sparisca per essere sicuro
        wait.until(EC.invisibility_of_element_located((By.XPATH, dialog_xpath)))

        return dettagli_errore

    except TimeoutException:
        print("Il pannello di errore non è apparso in tempo.")
        return None


def estrai_e_analizza_errori(actions):
    """
    Estrae la tabella di stato di Azure, la analizza,
    e per ogni riga con "Failed", clicca l'icona di errore
    e ne estrae i dettagli. Tutto in un'unica azione.
    """
    print("Avvio estrazione e analisi errori tabella Azure...")
    driver = actions.driver
    wait = WebDriverWait(driver, 10)
    
    # --- 1. ESTRAZIONE TABELLA (Metodo robusto) ---
    try:
        xpath_tabella = "//table[contains(@id, 'pn_id_189-table')]"
        print(f"Ricerca tabella con XPath: {xpath_tabella}")
        table_element = driver.find_element(By.XPATH, xpath_tabella)
        table_html = table_element.get_attribute('outerHTML')
        tabella_dati = pd.read_html(table_html)[0]
        print(f"Tabella estratta con {len(tabella_dati)} righe.")
        
    except Exception as e:
        print(f"Errore critico: Impossibile estrarre la tabella. {e}")
        return False # Interrompe l'azione
        
    # --- 2. ANALISI DATI E AZIONE ---

    logger.info(f"Colonne disponibili nella tabella: {tabella_dati.columns.tolist()}")

    # Trova i nomi delle colonne (potrebbero avere spazi extra o case diverso)
    colonna_nome_attivita = None
    colonna_stato = None

    for col in tabella_dati.columns:
        col_lower = col.lower().strip()
        if 'activity' in col_lower and 'name' in col_lower:
            colonna_nome_attivita = col
        if 'activity' in col_lower and 'status' in col_lower:
            colonna_stato = col

    if not colonna_nome_attivita or not colonna_stato:
        error_msg = f"Colonne non trovate nella tabella! Disponibili: {tabella_dati.columns.tolist()}"
        logger.error(error_msg)
        return False

    logger.info(f"Usando colonne: name='{colonna_nome_attivita}', status='{colonna_stato}'")

    valore_errore = "Failed" # Il testo che cerchiamo

    # Filtra il DataFrame per trovare solo le righe con errore
    righe_con_errore = tabella_dati[tabella_dati[colonna_stato] == valore_errore]

    if righe_con_errore.empty:
        logger.info("Analisi completata: Nessun errore ('Failed') trovato nella tabella.")
        return True # Successo

    logger.info(f"Trovate {len(righe_con_errore)} attività con stato '{valore_errore}'.")
    errori_raccolti = []

    # --- 3. CICLO SULLE RIGHE FALLITE ---
    for nome_attivita in righe_con_errore[colonna_nome_attivita]:
        print(f"--- Processo per l'attività fallita: {nome_attivita} ---")
        try:
            # --- Ecco l'XPath dinamico che ti serve ---
            xpath_icona_errore = f"//span[@title='{nome_attivita}']/ancestor::tr//div[@role='button' and @title='Error']"
            
            print(f"Cerco icona errore con XPath: {xpath_icona_errore}")
            
            # 4. Trova e clicca l'icona
            icona_element = wait.until(
                EC.element_to_be_clickable((By.XPATH, xpath_icona_errore))
            )
            icona_element.click()


            
            # 5. Estrai i dettagli
            print("Icona cliccata. Estraggo dettagli...")
            dettagli_errore = estrai_dettagli_errore(driver) 
            
            if dettagli_errore:
                dettagli_errore['attivita_fallita'] = nome_attivita
                errori_raccolti.append(dettagli_errore)
            
        except (NoSuchElementException, TimeoutException) as e:
            print(f"Impossibile trovare/cliccare icona errore per {nome_attivita}: {e}")
    
    # (Opzionale) Stampa un riepilogo finale
    print("\n--- RIEPILOGO ERRORI ESTRATTI ---")
    for errore in errori_raccolti:
        print(errore)
    print("---------------------------------")
    
    # Se vuoi che fluentx fallisca se ci sono stati errori,
    # puoi restituire False qui. Altrimenti True.
    # return not bool(errori_raccolti) # Fallisce se la lista non è vuota
    return True # Completa con successo, anche se ha trovato errori


def main(year_month_values: list, workspace: str) -> dict:
    print(year_month_values)
    print(workspace)
    modules = ["web", "windows app", "file", "sharepoint"]
    # modelli_semantici = ["Breve_Termine", "Flussi Esterni", "Flussi Netti", "Impieghi", "ML_Termine", "Raccolta Indiretta", "Raccolta_Diretta"]   # "Bonifico_istantaneo", "Homepage_Pre_Check", 
    login_chain = ["Login"]
    main_chain = ["Raggiungi Main"]
    debug_chain = ["Debug"]
    trigger_chain = ["Trigger"]
    output_chain = ["Output"]
    status_chain = ["Check Status"]
    refresh_chain = ["Refresh Status"]
    error_chain = ["Extract Error"]
    next_chain = ["Next"]

    # Carica il flusso .xlsx o .xlsm per FluentX
    try:
        _FLOW_PATH = get_resource_path(r"config_data/DataFactory.xlsm")
        _FLOW_NAME = basename(_FLOW_PATH).split(".")[0]
        workbook = load_workbook(_FLOW_PATH, data_only=True)
    except Exception as e:
        print(f'Problema con il caricamento del flusso FluentX: {e}')

    data, data_chains = get_general_config(workbook)
    print(data)
    print(data_chains)

    # Login
    # data_chains["chains"] = {chain: data[chain] for chain in login_chain}
    # actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook)
    # print(log)
    # for l in log["Login"]["Login"].values():
    #     if l["status"] == "error":  # al momento non accade mai, probabilmente perché tutte le task hanno "CONTINUE" in caso di errore - DA VERIFICARE
    #         error_msg = l.get('message', 'Errore sconosciuto')
    #         error_result = {"error": f"ERROR: non sono riuscito a fare il login: {error_msg}"}
    #         print(f"Returning error: {error_result}")
    #         return error_result
    
    # Main
    workbook["Raggiungi Main"]["F7"].value = f'{workspace}'    # da modificare
    workbook["Raggiungi Main"]["B11"].value = f'//div[contains(@data-parent-name, "Pipelines") and contains(@data-sa-idt, "{workspace}") and contains(@aria-label, "{workspace}")]'    # da modificare
    data_chains["chains"] = {chain: data[chain] for chain in main_chain}
    actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook) #actions=actions) 
    for key, value in log["Raggiungi Main"]["Raggiungi Main"].items():
        # print(f"{key}: {value['status']}") 
        if value['status'] == "error":
            print(f"ERROR: non sono riuscito a raggiungere il Main.")

    print(log)

    output_dict = {}

    for year_month in year_month_values:
        output_dict[year_month] = []
        print(year_month)
        print(f'Debug...')
        workbook["Debug"]["F5"].value = year_month    # da modificare
        data_chains["chains"] = {chain: data[chain] for chain in debug_chain}
        actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
        print(log)
        data_chains["chains"] = {chain: data[chain] for chain in output_chain}
        actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
        data_chains["chains"] = {chain: data[chain] for chain in status_chain}
        actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
        process_status = log['Check Status']['Check Status']['Chech Status']['extracted_texts'][0]
        while process_status == 'Queued':
            time.sleep(2)
            data_chains["chains"] = {chain: data[chain] for chain in status_chain}
            actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
            process_status = log['Check Status']['Check Status']['Chech Status']['extracted_texts'][0]
        while process_status == 'In progress':
            print('Aspetto 30 secondi...')
            time.sleep(30)
            data_chains["chains"] = {chain: data[chain] for chain in refresh_chain}
            actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
            data_chains["chains"] = {chain: data[chain] for chain in status_chain}
            actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
            process_status = log['Check Status']['Check Status']['Chech Status']['extracted_texts'][0]
        print(log)
        if process_status != 'Succeeded':
            logger.info('Processo completato con errori, ne estraggo i dettagli...')
            status_table = extract_html_table(actions)
            logger.info(f"Tabella estratta:\n{status_table}")
            logger.info(f"Colonne disponibili: {status_table.columns.tolist()}")

            # Trova i nomi delle colonne (potrebbero avere spazi extra o case diverso)
            col_activity_name = None
            col_activity_status = None

            for col in status_table.columns:
                col_lower = col.lower().strip()
                if 'activity' in col_lower and 'name' in col_lower:
                    col_activity_name = col
                if 'activity' in col_lower and 'status' in col_lower:
                    col_activity_status = col

            if not col_activity_name or not col_activity_status:
                error_msg = f"Colonne non trovate! Disponibili: {status_table.columns.tolist()}"
                logger.error(error_msg)
                output_dict[year_month] = f"Errore: {error_msg}"
                continue

            logger.info(f"Usando colonne: name='{col_activity_name}', status='{col_activity_status}'")

            # Filtra il DataFrame e seleziona solo la colonna 'Activity name'
            failed_activities = list(status_table[status_table[col_activity_status] == 'Failed'][col_activity_name])
            for failed_activity in failed_activities:
                error_path = f"//span[@title='{failed_activity}']/ancestor::tr//div[@role='button' and @title='Error']"
                workbook["Extract Error"]["B3"].value = error_path
                data_chains["chains"] = {chain: data[chain] for chain in error_chain}
                actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
                errori = estrai_dettagli_errore_azure(actions.driver)
                print(f"Dettagli errore per l'attività '{failed_activity}': {errori}")
                output_dict[year_month].append({
                    "activity_name": failed_activity,  
                    "error_details": errori
                })
            # print(status_table)
            # print(log)
        else:
            print('Processo completato con successo.')
            output_dict[year_month] = 'Succeeded'
        data_chains["chains"] = {chain: data[chain] for chain in refresh_chain}
        actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)

    
    return output_dict


if __name__ == "__main__":
    print("Starting DataFactory Flow...")
    year_month_values = ["2511"]  # "2510", "2509", "2508", "2507", "2506"
    workspace = "MAIN_BNF_DEV"
    status = main(year_month_values, workspace)
    from pprint import pprint
    pprint(status)

