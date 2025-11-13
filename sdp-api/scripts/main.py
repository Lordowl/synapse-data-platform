from os.path import *
import sys
import time
from fluentx.flow_executor import run_flow
from fluentx.utility import get_general_config
from openpyxl import load_workbook
from utility import extract_information, check_and_move, get_download_path, get_destination_path, extract_error, get_resource_path, get_users_list, get_config_from_sharepoint, get_users_from_sharepoint, get_flow_from_sharepoint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException


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


def main(workspace: str, PBI_packages: list):
    print(workspace)
    print(PBI_packages)
    modules = ["web", "windows app", "file", "sharepoint"]
    # modelli_semantici = ["Breve_Termine", "Flussi Esterni", "Flussi Netti", "Impieghi", "ML_Termine", "Raccolta Indiretta", "Raccolta_Diretta"]   # "Bonifico_istantaneo", "Homepage_Pre_Check", 
    login_chain = ["Login"]
    ms_chain = ["Filtro MS"]
    update_chain = ["Aggiorna MS"]
    app_chain = ["Aggiorna app"]
    workspace_chain = ["Cambia workspace"]

    # Carica il flusso .xlsx o .xlsm per FluentX
    try:
        _FLOW_PATH = get_resource_path(r"config_data/newNewSparkasse.xlsm")
        _FLOW_NAME = basename(_FLOW_PATH).split(".")[0]
        workbook = load_workbook(_FLOW_PATH, data_only=True)
    except Exception as e:
        print(f'Problema con il caricamento del flusso FluentX: {e}')

    data, data_chains = get_general_config(workbook)
    print(data)
    print(data_chains)

    # Login
    data_chains["chains"] = {chain: data[chain] for chain in login_chain}
    actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook)
    print(log)
    for l in log["Login"]["Login"].values():
        if l["status"] == "error":  # al momento non accade mai, probabilmente perché tutte le task hanno "CONTINUE" in caso di errore - DA VERIFICARE
            sys.exit(f"ERROR: non sono riuscito a fare il login: {l['message']}")

    # Workspace
    if workspace != "Engage-PRE CHECK":
        print(f"Cambio workspace in {workspace}...")
        workbook["Cambia workspace"]["B5"].value = f'//button[contains(@data-testid, "workspace-item-btn") and contains(@title, "{workspace}")]'    # da modificare
        data_chains["chains"] = {chain: data[chain] for chain in workspace_chain}
        actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
        if log["Cambia workspace"]["Cambia workspace"]["Selezionare workspace"]["status"] == "error":
            sys.exit(f"ERROR: non sono riuscito a trovare il workspace '{workspace}'. Controlla che il nome sia corretto.")
    
    # Filtro MS
    data_chains["chains"] = {chain: data[chain] for chain in ms_chain}
    actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions) 
    for key, value in log["Filtro MS"]["Filtro MS"].items():
        # print(f"{key}: {value['status']}") 
        if value['status'] == "error":
            sys.exit(f"ERROR: non sono riuscito a filtrare i Modelli Semantici.")

    packages_status = {}

    for package in PBI_packages:
        print(f'Aggiorno {package}...')
        x_path_ms = f'//span[@data-value="{package}"]'
        x_path_updt = f'//span[@data-value="{package}"]//button[@aria-label="Aggiorna adesso"]//mat-icon[@data-mat-icon-name="pbi-glyph-refresh"]'
        workbook["Aggiorna MS"]["B3"].value = x_path_ms    # da modificare
        workbook["Aggiorna MS"]["B4"].value = x_path_updt    # da modificare
        data_chains["chains"] = {chain: data[chain] for chain in update_chain}
        actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
        # print(log["Aggiorna MS"]["Aggiorna MS"])
        if log["Aggiorna MS"]["Aggiorna MS"]["Cerco riga MS"]["status"] == "error":
            print(f"Non sono riuscito a trovare la riga per '{package}'. Controlla che il nome sia corretto.")
            packages_status[package] = "Modello Semantico non trovato."
            continue
        if log["Aggiorna MS"]["Aggiorna MS"]["Aggiorno MS"]["status"] == "error":
            print(f"Non sono riuscito ad aggiornare '{package}'.")
            packages_status[package] = "Modello Semantico non aggiornato."
            continue
        
        driver = actions.driver
        row_xpath = f"//a[@aria-label='{package}']/ancestor::div[@data-testid='workspace-list-content-view-row']"
        spinner_xpath = "//div[@class='powerbi-spinner xsmall shown']" # //div[@class='spinner']//div[@class='circle']"
        update_error = './/i[@class="warning glyphicon pbi-glyph-warning glyph-small"]'

        try:
            # Identifico la riga del modello semantico
            print(f"Ricerca della riga per {package}...")
            wait = WebDriverWait(driver, 10)
            
            # Salvo la riga in una variabile
            ms_row = wait.until(EC.presence_of_element_located((By.XPATH, row_xpath)))
            print("Riga trovata.")

            # Attendo la comparsa dello spinner
            print(f"Attendo lo spinner per {package}...")
            # Combino l'XPath della riga con quello relativo dello spinner
            xpath_spinner_ms = row_xpath + spinner_xpath.replace('.', '')
            try:
                wait.until(EC.presence_of_element_located((By.XPATH, xpath_spinner_ms)))
                print("Spinner apparso sulla riga corretta.")
                # Attendo la scomparsa dello spinner
                print("Attendo la scomparsa dello spinner...")
                no_more_spinner = wait_until_element_disappears_robust(driver, xpath_spinner_ms, timeout=86400)
                if no_more_spinner:
                    print("Lo spinner è scomparso.")
                    no_spinner = False
            except TimeoutException:
                packages_status[package] = f"Timeout! Lo spinner non è apparso in tempo."
                print(f"Timeout! Lo spinner non è apparso in tempo.")
                no_more_spinner = False
                no_spinner = True

            if no_more_spinner or no_spinner:
                print("Controllo la riga per eventuali errori...")
                
                # Ritrovo la riga (per evitare StaleElementReferenceException) e controllo se ha generato errori
                updt_row = driver.find_element(By.XPATH, row_xpath)
                
                try:
                    error_msg = updt_row.find_element(By.XPATH, update_error)
                    print(f"ERRORE RILEVATO per {package}")
                    # print(update_error)
                    # print(error_msg)
                    try:
                        # Trovo il bottone dell'errore
                        error_btn = updt_row.find_element(By.XPATH, update_error)
                        print(f"Clicco per dettagli...")
                        
                        # Clicco il bottone per aprire i dettagli
                        error_btn.click()
                        
                        # Chiama la funzione per estrarre il testo dal popup
                        details = estrai_dettagli_errore(driver)

                        if details:
                            # Ora puoi accedere a qualsiasi informazione per nome
                            main_error = details.get("Errore dell'origine dati")
                            activity_id = details.get("ID attività")
                            
                            print("\n--- Riepilogo Errore ---")
                            print(f"Messaggio Principale: {main_error}")
                            print(f"ID Attività: {activity_id}")
                            print("----------------------")
                            if no_spinner:
                                print(f"Lo spinner non è mai apparso, aggiornamento non effettuato; errore rilevato: {main_error} (ID Attività: {activity_id})")
                                packages_status[package] = f"Lo spinner non è mai apparso, aggiornamento non effettuato; errore rilevato: {main_error} (ID Attività: {activity_id})"
                            else:
                                print(f"Aggiornamento non completato, errore rilevato: {main_error} (ID Attività: {activity_id})")
                                packages_status[package] = f"Aggiornamento non completato, errore rilevato: {main_error} (ID Attività: {activity_id})"
                        else:
                            if no_spinner:
                                print(f"Lo spinner non è mai apparso, aggiornamento non effettuato; errore rilevato ma dettagli non disponibili.")
                                packages_status[package] = f"Lo spinner non è mai apparso, aggiornamento non effettuato; errore rilevato ma dettagli non disponibili."
                            else:
                                packages_status[package] = f"Aggiornamento non completato, errore rilevato ma dettagli non disponibili."
                                print("Aggiornamento non completato, errore rilevato ma dettagli non disponibili.")
                        
                    except NoSuchElementException:
                        if no_spinner:
                            print(f"Lo spinner non è mai apparso, aggiornamento non effettuato; errore rilevato ma popup mancante.")
                            packages_status[package] = f"Lo spinner non è mai apparso, aggiornamento non effettuato; errore rilevato ma popup mancante."
                        else:
                            packages_status[package] = f"Aggiornamento non completato, errore rilevato ma popup mancante."
                            print(f"Aggiornamento non completato, errore rilevato ma popup mancante.")
                    
                except NoSuchElementException:
                    if no_spinner:
                        print(f"Lo spinner non è mai apparso, aggiornamento non effettuato ma nessun errore rilevato.")
                        packages_status[package] = "Lo spinner non è mai apparso, aggiornamento non effettuato ma nessun errore rilevato."
                    else:
                        packages_status[package] = "Aggiornamento completato con successo."
                        print(f"Operazione per '{package}' completata con successo, nessun errore trovato.")
                    
            else:
                packages_status[package] = "Timeout! L'aggiornamento ha richiesto più tempo del previsto: esito non disponibile."
                print(f"Timeout! Lo spinner per '{package}' è ancora visibile.")

        except TimeoutException:
            packages_status[package] = f"Timeout! Non è stato possibile trovare la riga per '{package}'."
            print(f"Timeout! Non è stato possibile trovare la riga per '{package}'.")

        print(log)

    data_chains["chains"] = {chain: data[chain] for chain in app_chain}
    actions, text_list, workbook_report, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
    print(log)
    
    return packages_status


if __name__ == "__main__":
    print("Starting Dispatcher...")
    workspace = "Engage-DEV"    # "Engage-PRE CHECK"
    PBI_packages = ["Bancassurance_v2", "Bonifico_istantaneo_v2", "Breve_Termine_v2", "Copertina", "Flussi Esterni_v2", "Impieghi_v2", "ML_Termine_v2", "Raccolta Indiretta_v2", "Raccolta_Diretta_v2", "Homepage_Pre_Check"]
    PBI_packages = ["Agribusiness", "Bancassurance", "Bonifico_istantaneo", "Breve_Termine", "Flussi Esterni", "Impieghi", "ML_Termine", "Raccolta Indiretta", "Raccolta_Diretta", "Homepage"]
    status = main(workspace, PBI_packages)
    from pprint import pprint
    pprint(status)


# /html/body/div[1]/root/mat-sidenav-container/mat-sidenav-content/tri-shell-panel-outlet/tri-item-renderer-panel/tri-extension-panel-outlet/mat-sidenav-container/mat-sidenav-content/div/div/div[1]/tri-shell/tri-item-renderer/tri-extension-page-outlet/div[2]/workspace-view/tri-workspace-view/mat-sidenav-container/mat-sidenav-content/workspace-list-view/tri-workspace-list-view/section/main/fluent-workspace/mat-sidenav-container/mat-sidenav-content/fluent-workspace-list/fluent-list-table-base/div/cdk-virtual-scroll-viewport/div[1]/div[4]/div[7]/span/dataset-icon-container-modern/span/spinner/div/div/div[5]
# //*[@id="artifactContentView"]/div[1]/div[4]/div[7]/span/dataset-icon-container-modern/span/spinner/div/div/div[5]

# //*[@id="artifactContentView"]/div[1]/div[8]/div[7]/span/dataset-icon-container-modern/span/button/i
# <i _ngcontent-ng-c2335757646="" class="warning glyphicon pbi-glyph-warning glyph-small"></i>
# <div _ngcontent-ng-c1297321065="" class="circle"></div>


# <div _ngcontent-ng-c3322660467="" role="row" cdkmonitorsubtreefocus="" data-testid="workspace-list-content-view-row" tabindex="0" class="row ng-star-inserted"><span _ngcontent-ng-c3322660467="" cdkmonitorelementfocus="" role="cell" class="col col-checkbox ng-star-inserted"><div _ngcontent-ng-c3322660467="" style="display: flex;"><tri-checkbox _ngcontent-ng-c3322660467="" localizetooltip="Toggle_Select_Row" data-testid="checkbox-btn" _nghost-ng-c2114615799="" title="Attiva/Disattiva Seleziona riga" class="checkbox"><div _ngcontent-ng-c2114615799="" class="tri-checkbox"><input _ngcontent-ng-c2114615799="" type="checkbox" data-testid="tri-checkbox-input" class="tri-checkbox-input" id="tri-checkbox-10" aria-label="Seleziona riga" aria-checked="false"><label _ngcontent-ng-c2114615799="" class="tri-checkbox-label tri-items-center" for="tri-checkbox-10"><div _ngcontent-ng-c2114615799="" data-testid="tri-checkbox-checkmark" class="tri-checkbox-checkbox"><tri-svg-icon _ngcontent-ng-c2114615799="" sprite="fluentui-icons" class="tri-checkbox-checkmark" _nghost-ng-c3179469096="" aria-hidden="true"><svg _ngcontent-ng-c3179469096="" class="ng-star-inserted"><use _ngcontent-ng-c3179469096="" xlink:href="#"></use></svg><!----><!----><!----><!----><!----><!----><!----><!----></tri-svg-icon></div><div _ngcontent-ng-c2114615799="" class="tri-checkbox-custom"></div><!----></label></div></tri-checkbox></div></span><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><!----><span _ngcontent-ng-c809159652="" data-testid="fluentListCell.icon" class="col col-icon tri-relative ng-star-inserted"><!----><div _ngcontent-ng-c809159652="" class="tri-artifact-icon-container-24 ng-star-inserted"><tri-artifact-icon _ngcontent-ng-c809159652="" class="tri-icon" _nghost-ng-c1397375839=""><tri-svg-icon _ngcontent-ng-c1397375839="" class="tri-svg-icon ng-star-inserted" _nghost-ng-c3179469096="" tri-svg-icon-24="" aria-label="Modello semantico"><!----><img _ngcontent-ng-c3179469096="" src="https://content.powerapps.com/resource/powerbiwfe/images/artifact-colored-icons.3956afb89ff2d589c246.svg#c_dataset_24" alt="" class="ng-star-inserted"><!----><!----><!----><!----><!----><!----><!----></tri-svg-icon><!----></tri-artifact-icon></div><!----><!----><!----><!----></span><!----></div><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" class="ng-star-inserted"><div _ngcontent-ng-c3322660467="" role="cell" id="popper-reference" item-hover-card-popper="" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c809159652="" ng-non-bindable="" data-testid="fluentListCell.name" class="col col-name ng-star-inserted" data-value="Impieghi" style="width: 400px; min-width: 400px;"><!----><!----><!----><span _ngcontent-ng-c809159652="" class="name-container"><!----><!----><!----><a _ngcontent-ng-c809159652="" data-testid="item-name" cdkmonitorelementfocus="" tabindex="0" rel="noopener noreferrer" queryparamshandling="merge" class="name trimmedTextWithEllipsis ng-star-inserted" href="/groups/deaab94e-0a35-4a0b-b025-3007d78598a0/datasets/28b96a36-0a9b-42d2-8275-c849778934d6/details?ctid=4594981d-9c8d-47af-a282-a9a3507a3415&amp;experience=power-bi" target="_self" aria-label="Impieghi"> Impieghi <!----><!----><!----><!----><!----><!----><!----><!----><!----><!----></a><!----><!----><!----><!----><!----><!----><!----></span><!----><!----><button _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" class="quick-action-button ng-star-inserted" data-testid="quick-action-button-Aggiorna adesso" aria-label="Aggiorna adesso"><mat-icon _ngcontent-ng-c809159652="" role="img" class="mat-icon notranslate glyph-small pbi-glyph-refresh pbi-glyph-font-face mat-icon-no-color ng-star-inserted" aria-hidden="true" data-mat-icon-type="font" data-mat-icon-name="pbi-glyph-refresh" fonticon="pbi-glyph-refresh"></mat-icon><!----><!----><!----></button><button _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" class="quick-action-button ng-star-inserted" data-testid="quick-action-button-Pianifica aggiornamento" aria-label="Pianifica aggiornamento"><mat-icon _ngcontent-ng-c809159652="" role="img" class="mat-icon notranslate glyph-small pbi-glyph-refresh-data pbi-glyph-font-face mat-icon-no-color ng-star-inserted" aria-hidden="true" data-mat-icon-type="font" data-mat-icon-name="pbi-glyph-refresh-data" fonticon="pbi-glyph-refresh-data"></mat-icon><!----><!----><!----></button><!----><!----><!----><!----><!----><!----><dataset-context-menu _ngcontent-ng-c809159652="" trimenuicon="more_horizontal_16_regular" data-testid="dataset-options-menu-btn" class="context-menu ng-star-inserted" _nghost-ng-c3568806463=""><button _ngcontent-ng-c3568806463="" mat-icon-button="" cdkmonitorelementfocus="" aria-haspopup="menu" data-testid="datasetContextMenu" class="mat-mdc-menu-trigger menuTrigger" tabindex="0" aria-label="Altre opzioni" aria-expanded="false"><!----><tri-svg-icon _ngcontent-ng-c3568806463="" _nghost-ng-c3179469096="" class="ng-star-inserted"><svg _ngcontent-ng-c3179469096="" class="ng-star-inserted"><use _ngcontent-ng-c3179469096="" xlink:href="#more_horizontal_16_regular"></use></svg><!----><!----><!----><!----><!----><!----><!----><!----></tri-svg-icon><!----><!----></button><!----><mat-menu _ngcontent-ng-c3568806463="" class="ng-star-inserted"><!----></mat-menu></dataset-context-menu><!----><!----><!----><!----><!----><!----><!----><!----><!----><!----><!----><!----><!----><!----><!----><!----></span><!----></div><!----></div><!----><!----><!----><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><!----><span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.location" class="col col-location ng-star-inserted" title="Engage-DEV" style="width: 180px; min-width: 180px;">Engage-DEV</span><!----><!----><!----></div><!----><!----><!----><!----><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.type" class="col col-type ng-star-inserted" data-value="3" title="Modello semantico" style="width: 140px; min-width: 140px;"><span _ngcontent-ng-c809159652="" class="trimmedTextWithEllipsis">Modello semantico</span></span><!----></div><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c3320181328="" class="col col-task ng-star-inserted" style="width: 156px;"><span _ngcontent-ng-c3320181328="" class="ng-star-inserted">—</span><!----><!----></span><!----></div><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.owner" class="col col-owner ng-star-inserted" title="Engage-DEV" style="width: 140px; min-width: 140px;">Engage-DEV</span><!----></div><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.lastRefresh" class="col col-last-refresh ng-star-inserted" data-value="1759755401633" title="06/10/2025, 14:56:41" style="width: 168px; min-width: 168px;"><span _ngcontent-ng-c809159652="" class="trimmedTextWithEllipsis">06/10/2025, 14:56:41</span><dataset-icon-container-modern _ngcontent-ng-c809159652="" class="col-status-icons ng-star-inserted" _nghost-ng-c2335757646=""><!----><span _ngcontent-ng-c2335757646="" class="datasetRefreshIcons ng-star-inserted"><!----><!----><button _ngcontent-ng-c2335757646="" tabindex="0" aria-label="Si è verificato un errore nel set di dati. Selezionare l'icona di avviso per visualizzare i dettagli dell'errore." class="ng-star-inserted" pbi-focus-tracker-idx="9"><i _ngcontent-ng-c2335757646="" class="warning glyphicon pbi-glyph-warning glyph-small"></i></button><!----><!----><!----><!----><!----></span><!----><!----></dataset-icon-container-modern><!----><!----><!----><!----><!----><!----></span><!----></div><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.nextRefresh" class="col col-next-refresh ng-star-inserted" title="N/D" style="width: 168px; min-width: 168px;" data-value="1759780674000"><span _ngcontent-ng-c809159652="" class="trimmedTextWithEllipsis">N/D</span><dataset-icon-container-modern _ngcontent-ng-c809159652="" class="col-status-icons ng-star-inserted" _nghost-ng-c2335757646=""><!----><!----><span _ngcontent-ng-c2335757646="" class="datasetNextRefreshIcons ng-star-inserted"><!----><!----></span><!----></dataset-icon-container-modern><!----><!----><!----><!----><!----></span><!----></div><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.endorsement" class="col col-endorsement ng-star-inserted" style="width: 140px; min-width: 140px;"><span _ngcontent-ng-c809159652="" title="Nessuno" class="ng-star-inserted">—</span><!----></span><!----></div><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.sensitivity" class="col col-sensitivity ng-star-inserted" style="width: 160px; min-width: 160px;"><information-protection-label _ngcontent-ng-c809159652="" _nghost-ng-c2371463806=""><span _ngcontent-ng-c2371463806="" class="labelName emptyLabel ng-star-inserted" title="Nessuno"></span><!----><!----></information-protection-label></span><!----><!----></div><!----><!----><!----><!----><div _ngcontent-ng-c3322660467="" role="cell" class="fluent-cell ng-star-inserted"><span _ngcontent-ng-c1234539692="" class="col col-included-in-app ng-star-inserted"><!----></span><!----><!----></div><!----><!----><!----><!----><!----></div>

# <span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.lastRefresh" class="col col-last-refresh ng-star-inserted" data-value="1759480790313" title="03/10/2025, 10:39:50" style="width: 168px; min-width: 168px;"><span _ngcontent-ng-c809159652="" class="trimmedTextWithEllipsis">03/10/2025, 10:39:50</span><dataset-icon-container-modern _ngcontent-ng-c809159652="" class="col-status-icons ng-star-inserted" _nghost-ng-c2335757646=""><!----><span _ngcontent-ng-c2335757646="" class="datasetRefreshIcons ng-star-inserted"><spinner _ngcontent-ng-c2335757646="" _nghost-ng-c1297321065="" class="ng-star-inserted"><div _ngcontent-ng-c1297321065="" class="powerbi-spinner xsmall shown"><div _ngcontent-ng-c1297321065="" data-testid="spinner" class="spinner"><div _ngcontent-ng-c1297321065="" class="circle"></div><div _ngcontent-ng-c1297321065="" class="circle"></div><div _ngcontent-ng-c1297321065="" class="circle"></div><div _ngcontent-ng-c1297321065="" class="circle"></div><div _ngcontent-ng-c1297321065="" class="circle"></div></div></div></spinner><!----><!----><!----><!----><!----><!----><!----></span><!----><!----></dataset-icon-container-modern><!----><!----><!----><!----><!----><!----></span>
# <span _ngcontent-ng-c809159652="" cdkmonitorelementfocus="" data-testid="fluentListCell.lastRefresh" class="col col-last-refresh ng-star-inserted" data-value="1759480728810" title="03/10/2025, 10:38:48" style="width: 168px; min-width: 168px;"><span _ngcontent-ng-c809159652="" class="trimmedTextWithEllipsis">03/10/2025, 10:38:48</span><dataset-icon-container-modern _ngcontent-ng-c809159652="" class="col-status-icons ng-star-inserted" _nghost-ng-c2335757646=""><!----><span _ngcontent-ng-c2335757646="" class="datasetRefreshIcons ng-star-inserted"><!----><!----><button _ngcontent-ng-c2335757646="" tabindex="0" aria-label="Si è verificato un errore nel set di dati. Selezionare l'icona di avviso per visualizzare i dettagli dell'errore." class="ng-star-inserted" pbi-focus-tracker-idx="10"><i _ngcontent-ng-c2335757646="" class="warning glyphicon pbi-glyph-warning glyph-small"></i></button><!----><!----><!----><!----><!----></span><!----><!----></dataset-icon-container-modern><!----><!----><!----><!----><!----><!----></span>
