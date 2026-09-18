from os.path import *
import sys
import time
import logging
from fluentx.flow_executor import run_flow
from fluentx.utility import get_general_config
from openpyxl import load_workbook
from scripts.utility import extract_information, check_and_move, get_download_path, get_destination_path, extract_error, get_resource_path, get_flow_path, get_users_list, get_config_from_sharepoint, get_users_from_sharepoint, get_flow_from_sharepoint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException, InvalidSessionIdException

logger = logging.getLogger(__name__)


def _wait_spinner_gone(driver: webdriver.Chrome, package_name: str, timeout: int = 86400) -> bool:
    """
    Attende che lo spinner di aggiornamento scompaia dalla riga del package.
    Usa un polling loop che ri-scrolla attivamente per mantenere la riga nel DOM
    (CDK virtual scroll rimuove dal DOM le righe fuori viewport).
    Doppia verifica: lo spinner deve essere assente per 2 check consecutivi
    prima di dichiarare l'aggiornamento completato.
    Restituisce True se lo spinner è sparito, False se timeout.
    """
    row_xpath = f'//span[@data-value="{package_name}"]/ancestor::*[@data-testid="workspace-list-content-view-row"]'
    spinner_xpath = row_xpath + '//spinner'
    start = time.time()
    gone_count = 0  # contatore check consecutivi senza spinner

    while time.time() - start < timeout:
        _scroll_to_package(driver, package_name)  # mantieni la riga nel DOM (no-op se già visibile)
        time.sleep(2)  # attesa post-scroll per stabilizzare il render Angular
        try:
            driver.find_element(By.XPATH, spinner_xpath)
            gone_count = 0  # spinner ancora presente, reset contatore
            time.sleep(4)
        except NoSuchElementException:
            gone_count += 1
            if gone_count >= 4:
                # Spinner assente per 4 check consecutivi (~24s): aggiornamento completato
                # Attesa extra per dare a Power BI il tempo di renderizzare lo stato finale
                time.sleep(3)
                return True
            time.sleep(4)  # attendi prima del check successivo
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


def _scroll_to_package(driver: webdriver.Chrome, package_name: str, timeout: int = 15) -> bool:
    """
    Porta il package nella viewport del CDK virtual scroll di Power BI.
    Power BI usa virtual scrolling: gli elementi fuori dalla viewport non esistono nel DOM.
    Tenta prima senza scrollare (l'elemento potrebbe già essere visibile); solo se non trovato
    riparte dalla cima e scrolla incrementalmente. Questo evita di rimettere in DOM
    da capo l'elemento ad ogni chiamata, che causa falsi positivi nel check spinner.
    Restituisce True se trovato, False se non trovato entro il timeout.
    """
    xpath = f'//span[@data-value="{package_name}"]'

    # Prima tenta senza scrollare: evita di rimuovere il row dal DOM inutilmente
    try:
        driver.find_element(By.XPATH, xpath)
        return True
    except NoSuchElementException:
        pass

    # Elemento non in viewport: riparte dalla cima e scrolla incrementalmente
    driver.execute_script("""
        var vp = document.querySelector('cdk-virtual-scroll-viewport');
        if (vp) vp.scrollTop = 0;
    """)
    time.sleep(0.5)

    start = time.time()
    scroll_step = 250  # pixel per step

    while time.time() - start < timeout:
        try:
            driver.find_element(By.XPATH, xpath)
            return True
        except NoSuchElementException:
            at_bottom = driver.execute_script("""
                var vp = document.querySelector('cdk-virtual-scroll-viewport');
                if (!vp) return true;
                vp.scrollTop += arguments[0];
                return vp.scrollTop + vp.clientHeight >= vp.scrollHeight - 5;
            """, scroll_step)
            time.sleep(0.3)
            if at_bottom:
                try:
                    driver.find_element(By.XPATH, xpath)
                    return True
                except NoSuchElementException:
                    return False

    return False


def _log_debug_html(driver: webdriver.Chrome, package_name: str, context: str) -> None:
    """Logga l'HTML della riga del package (o del viewport) per diagnosticare rotture UI di Power BI."""
    row_xpath = f'//span[@data-value="{package_name}"]/ancestor::*[@data-testid="workspace-list-content-view-row"]'
    try:
        row_el = driver.find_element(By.XPATH, row_xpath)
        html = row_el.get_attribute("outerHTML") or ""
        logger.debug(f"[DEBUG HTML] {context} | riga '{package_name}': {html[:1000]}")
    except NoSuchElementException:
        try:
            vp = driver.find_element(By.CSS_SELECTOR, "cdk-virtual-scroll-viewport")
            html = vp.get_attribute("innerHTML") or ""
            logger.debug(f"[DEBUG HTML] {context} | riga '{package_name}' non in DOM, viewport: {html[:1000]}")
        except Exception:
            logger.debug(f"[DEBUG HTML] {context} | viewport non trovato")


# Tolleranza per lo sfasamento fra orologio locale e timestamp restituiti da Power BI.
_CLOCK_SKEW_MS = 5 * 60 * 1000


def _fmt_ts(epoch_ms) -> str:
    """Formatta un timestamp epoch in millisecondi in data/ora leggibile."""
    if not epoch_ms:
        return "N/D"
    try:
        return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(epoch_ms / 1000))
    except (TypeError, ValueError, OSError):
        return str(epoch_ms)


def _click_refresh_button(driver: webdriver.Chrome, package: str, attempts: int = 3) -> bool:
    """
    Clicca "Aggiorna adesso" sulla riga del package usando Selenium diretto.

    Serve come rete di sicurezza quando il click pilotato da FluentX fallisce: i
    pulsanti quick-action di Power BI compaiono all'hover, e fra il MOVE TO sulla riga
    e il CLICK sul pulsante l'hover puo' perdersi o il pulsante puo' non aver finito di
    renderizzare. Qui hover e click sono consecutivi, si attende che il pulsante sia
    cliccabile (non solo presente) e si ripiega sul click JavaScript se un overlay lo
    intercetta.

    Restituisce True se il click e' andato a segno.
    """
    name_xpath = f'//span[@data-value="{package}"]'
    button_xpath = name_xpath + '//button[@aria-label="Aggiorna adesso"]'

    for attempt in range(1, attempts + 1):
        try:
            _scroll_to_package(driver, package)
            name_el = driver.find_element(By.XPATH, name_xpath)
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", name_el
            )
            time.sleep(0.5)

            # L'hover fa comparire i pulsanti quick-action sulla riga.
            ActionChains(driver).move_to_element(name_el).perform()
            time.sleep(0.5)

            button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, button_xpath))
            )
            try:
                button.click()
            except Exception as click_err:
                # Overlay o tooltip sopra il pulsante: click via JS, che li ignora.
                logger.debug(f"Click diretto fallito per '{package}' ({click_err}), provo via JavaScript.")
                driver.execute_script("arguments[0].click();", button)

            logger.info(f"Click 'Aggiorna adesso' riuscito per '{package}' al tentativo {attempt}.")
            return True

        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
            logger.warning(
                f"Tentativo {attempt}/{attempts} di click su '{package}' non riuscito: {type(e).__name__}."
            )
            time.sleep(2)

    _log_debug_html(driver, package, "click di recupero fallito su tutti i tentativi")
    return False


def _read_last_refresh(driver: webdriver.Chrome, package_name: str):
    """
    Legge il timestamp (epoch ms) dell'ultimo aggiornamento dalla riga del package.
    Power BI lo espone nell'attributo data-value della cella 'fluentListCell.lastRefresh'.
    Restituisce None se la riga non e' nel DOM o il valore non e' leggibile.
    """
    xpath = (
        f'//span[@data-value="{package_name}"]'
        '/ancestor::*[@data-testid="workspace-list-content-view-row"]'
        '//span[@data-testid="fluentListCell.lastRefresh"]'
    )
    try:
        raw = driver.find_element(By.XPATH, xpath).get_attribute("data-value")
    except (NoSuchElementException, StaleElementReferenceException):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _verify_refresh(driver: webdriver.Chrome, package: str, baseline_ts, run_start_ms: int, context: str) -> str:
    """
    Determina l'esito REALE dell'aggiornamento di un package.

    Il successo richiede una prova positiva: assenza di icona di errore E avanzamento
    del timestamp di ultimo aggiornamento. Controllare solo l'icona di errore, come
    faceva la versione precedente, marcava "completato con successo" anche i package
    il cui refresh non era mai partito: nessun errore da mostrare, perche' l'ultimo
    aggiornamento riuscito risaliva a settimane prima.
    """
    row_xpath = f'//span[@data-value="{package}"]/ancestor::*[@data-testid="workspace-list-content-view-row"]'
    error_icon_xpath = row_xpath + '//button[.//i[contains(@class, "pbi-glyph-warning")]]'

    # 1. Icona di errore: se presente, l'esito e' gia' deciso.
    try:
        err_btn = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, error_icon_xpath)))
        err_btn.click()
        details = estrai_dettagli_errore(driver)
        if details:
            main_error = details.get("Errore dell'origine dati", "sconosciuto")
            activity_id = details.get("ID attività", "N/D")
            logger.error(f"Errore per '{package}': {main_error} (ID: {activity_id})")
            return f"Aggiornamento non completato, errore: {main_error} (ID Attività: {activity_id})"
        logger.error(f"Errore per '{package}': dettagli non disponibili.")
        return "Aggiornamento non completato, errore rilevato ma dettagli non disponibili."
    except TimeoutException:
        pass  # nessuna icona di errore: non basta, serve la prova che il refresh sia avvenuto

    # 2. Timestamp di ultimo aggiornamento.
    _scroll_to_package(driver, package)
    current_ts = _read_last_refresh(driver, package)
    logger.info(
        f"[{package}] ultimo aggiornamento: prima={_fmt_ts(baseline_ts)} dopo={_fmt_ts(current_ts)} "
        f"(inizio run={_fmt_ts(run_start_ms)})"
    )

    if current_ts is None:
        _log_debug_html(driver, package, f"{context}: timestamp ultimo aggiornamento non leggibile")
        return "Esito non verificabile: timestamp di ultimo aggiornamento non leggibile."

    # Confronto fra due timestamp Power BI: immune allo sfasamento di orologio.
    advanced = baseline_ts is not None and current_ts > baseline_ts
    # Fallback: baseline non letta, oppure refresh gia' concluso prima del nostro arrivo.
    within_run = current_ts >= (run_start_ms - _CLOCK_SKEW_MS)

    if not advanced and not within_run:
        _log_debug_html(driver, package, f"{context}: timestamp invariato")
        return (
            f"Refresh non eseguito: timestamp di ultimo aggiornamento invariato "
            f"({_fmt_ts(current_ts)}). Il modello semantico non risulta aggiornato."
        )

    logger.info(f"OK: '{package}' aggiornato realmente ({_fmt_ts(current_ts)}).")
    return f"Aggiornamento completato con successo ({_fmt_ts(current_ts)})."


def _wait_page_ready(driver: webdriver.Chrome, timeout: int = 30) -> None:
    """Attende che la pagina sia pronta dopo un refresh: contenitore lista presente + rendering icone."""
    wait = WebDriverWait(driver, timeout)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "cdk-virtual-scroll-viewport")))
    time.sleep(3)


def _resolve_flow_path(bank: str = None):
    """
    Percorso del flusso FluentX da usare: App/Flows/<banca>.xlsm.
    Fallback su 'Sparkasse.xlsm' se il flusso specifico della banca non esiste, cosi'
    le installazioni con un solo flusso continuano a funzionare.
    Restituisce (percorso, nome_flusso_effettivo).
    """
    tried = []
    for name in ([bank] if bank else []) + ["Sparkasse"]:
        if not name or name in tried:
            continue
        tried.append(name)
        try:
            return get_flow_path(name), name
        except FileNotFoundError:
            logger.warning(f"Flusso FluentX '{name}.xlsm' non trovato in App/Flows.")
    raise FileNotFoundError(
        f"Nessun flusso FluentX utilizzabile in App/Flows (provati: {tried})"
    )


def main(workspace: str, PBI_packages: list, final_packages: list = None, blocked_by: list = None, bank: str = None):
    """
    Aggiorna i modelli semantici Power BI del workspace indicato.

    PBI_packages   : package "normali", aggiornati per primi.
    final_packages : package che aggregano i dati degli altri (Obbligatorio = Y nella
                     mappatura, oggi solo 'Homepage'). Vengono aggiornati SOLO se tutti
                     i package normali sono andati a buon fine.
    blocked_by     : package gia' in errore a DB per lo stesso periodo e non rilanciati
                     in questa run. Bloccano i final_packages come un errore corrente.
    """
    logger.info(f"=== INIZIO ELABORAZIONE ===")
    logger.info(f"Workspace: {workspace}")
    logger.info(f"Banca: {bank or 'non specificata'}")

    # I due elenchi devono essere disgiunti: se un chiamante passa la lista completa
    # in PBI_packages, i final_packages vengono comunque estratti da li'.
    final_packages = list(final_packages or [])
    PBI_packages = [pkg for pkg in PBI_packages if pkg not in final_packages]
    blocked_by = list(blocked_by or [])

    logger.info(f"Packages: {PBI_packages}")
    logger.info(f"Packages finali (dopo gli altri): {final_packages}")
    if blocked_by:
        logger.warning(f"Package gia' in errore a DB per questo periodo: {blocked_by}")

    # Istante di avvio: soglia per stabilire se un timestamp di ultimo aggiornamento
    # appartiene a questa esecuzione.
    run_start_ms = int(time.time() * 1000)
    modules = ["web", "windows app", "file", "sharepoint"]
    # modelli_semantici = ["Breve_Termine", "Flussi Esterni", "Flussi Netti", "Impieghi", "ML_Termine", "Raccolta Indiretta", "Raccolta_Diretta"]   # "Bonifico_istantaneo", "Homepage_Pre_Check",
    login_chain = ["Login"]
    ms_chain = ["Filtro MS"]
    update_chain = ["Aggiorna MS"]
    app_chain = ["Aggiorna app"]
    workspace_chain = ["Cambia workspace"]

    # Carica il flusso .xlsx o .xlsm per FluentX dalla cartella App/Flows.
    # Nessun try/except: senza workbook le righe successive fallirebbero comunque,
    # con un NameError che nasconde la causa reale.
    _FLOW_PATH, _flow_bank = _resolve_flow_path(bank)
    _FLOW_NAME = basename(_FLOW_PATH).split(".")[0]
    workbook = load_workbook(_FLOW_PATH, data_only=True)
    logger.info(f"Flusso FluentX caricato: {_FLOW_PATH}")
    if bank and _flow_bank != bank:
        logger.warning(
            f"Flusso specifico per '{bank}' non presente in App/Flows: uso '{_flow_bank}.xlsm'."
        )

    data, data_chains = get_general_config(workbook)
    logger.debug(f"Data: {data}")
    logger.debug(f"Data chains: {data_chains}")

    # Login
    logger.info("Fase Login in corso...")
    data_chains["chains"] = {chain: data[chain] for chain in login_chain}
    actions, _, _, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook)
    logger.info(f"Login log: {log}")
    for task_name, l in log["Login"]["Login"].items():
        if l["status"] == "error":
            # Ignora l'errore per il task "premere si su rimanere connessi" (opzionale)
            if "rimanere connessi" in task_name.lower():
                logger.debug(f"Task '{task_name}' fallito ma ignorato (opzionale)")
                continue
            error_msg = l.get('error') or l.get('message', 'Errore sconosciuto')
            logger.error(f"ERROR durante login nel task '{task_name}': {error_msg}")

    # Workspace
    if workspace != "Engage-PRE CHECK":
        logger.info(f"Cambio workspace in {workspace}...")
        workbook["Cambia workspace"]["B5"].value = f'//button[contains(@data-testid, "workspace-item-btn") and contains(@title, "{workspace}")]'    # da modificare
        data_chains["chains"] = {chain: data[chain] for chain in workspace_chain}
        actions, _, _, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
        if log["Cambia workspace"]["Cambia workspace"]["Selezionare workspace"]["status"] == "error":
            logger.error(f"ERROR: non sono riuscito a trovare il workspace '{workspace}'. Controlla che il nome sia corretto.")
            sys.exit(f"ERROR: non sono riuscito a trovare il workspace '{workspace}'. Controlla che il nome sia corretto.")
    
    # Filtro MS
    data_chains["chains"] = {chain: data[chain] for chain in ms_chain}
    actions, _, _, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions) 
    for key, value in log["Filtro MS"]["Filtro MS"].items():
        # print(f"{key}: {value['status']}") 
        if value['status'] == "error":
            sys.exit(f"ERROR: non sono riuscito a filtrare i Modelli Semantici.")

    packages_status = {}

    def _process_packages(pkg_list):
        # 'actions' viene riassegnato dai run_flow interni e deve sopravvivere
        # fra la chiamata sui package normali e quella sui package finali.
        nonlocal actions
        for package in pkg_list:
            logger.info(f"=== Aggiornamento package: {package} ===")

            row_xpath = f'//span[@data-value="{package}"]/ancestor::*[@data-testid="workspace-list-content-view-row"]'
            spinner_xpath = row_xpath + '//spinner'

            # Porta il package nel DOM (virtual scroll)
            found = _scroll_to_package(actions.driver, package)
            if not found:
                logger.warning(f"Package '{package}' non trovato nella lista dopo scrolling completo.")
                packages_status[package] = "Modello Semantico non trovato."
                continue

            driver = actions.driver

            # Timestamp di partenza: serve a provare che il refresh sia davvero avvenuto.
            baseline_ts = _read_last_refresh(driver, package)
            logger.info(f"[{package}] ultimo aggiornamento prima del refresh: {_fmt_ts(baseline_ts)}")

            try:
                # Controlla se il package è già in aggiornamento (side-effect da package precedente)
                try:
                    driver.find_element(By.XPATH, spinner_xpath)
                    logger.info(f"Package '{package}' già in aggiornamento (side-effect). Skip click, attendo completamento...")
                    already_spinning = True
                except NoSuchElementException:
                    already_spinning = False

                if not already_spinning:
                    # Clicca "Aggiorna adesso" via FluentX
                    x_path_ms = f'//span[@data-value="{package}"]'
                    x_path_updt = f'//span[@data-value="{package}"]//button[@aria-label="Aggiorna adesso"]'
                    workbook["Aggiorna MS"]["B3"].value = x_path_ms
                    workbook["Aggiorna MS"]["B4"].value = x_path_updt
                    data_chains["chains"] = {chain: data[chain] for chain in update_chain}
                    actions, _, _, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
                    driver = actions.driver
                    logger.debug(f"Log dettagliato: {log}")

                    if log["Aggiorna MS"]["Aggiorna MS"]["Cerco riga MS"]["status"] == "error":
                        # Virtual scroll potrebbe aver spostato la riga — riprova con scroll
                        logger.warning(f"Riga non trovata per '{package}', riprovo con scroll...")
                        _scroll_to_package(driver, package)
                        time.sleep(1)
                        actions, _, _, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
                        driver = actions.driver
                        if log["Aggiorna MS"]["Aggiorna MS"]["Cerco riga MS"]["status"] == "error":
                            # Controlla se side-effect spinner già attivo
                            try:
                                driver.find_element(By.XPATH, spinner_xpath)
                                logger.info(f"Side-effect spinner rilevato per '{package}' dopo fallimento ricerca riga. Attendo completamento...")
                                already_spinning = True
                            except NoSuchElementException:
                                logger.warning(f"Riga '{package}' non trovata dopo retry.")
                                _log_debug_html(driver, package, "Cerco riga MS fallito dopo retry")
                                packages_status[package] = "Modello Semantico non trovato."
                                continue

                    if not already_spinning and log["Aggiorna MS"]["Aggiorna MS"]["Aggiorno MS"]["status"] == "error":
                        # Click fallito — potrebbe essere race condition con side-effect refresh
                        logger.warning(f"Click 'Aggiorna adesso' fallito per '{package}', controllo side-effect spinner...")
                        _scroll_to_package(driver, package)
                        time.sleep(2)
                        try:
                            driver.find_element(By.XPATH, spinner_xpath)
                            logger.info(f"Side-effect spinner rilevato per '{package}' dopo fallimento click. Attendo completamento...")
                            already_spinning = True
                        except NoSuchElementException:
                            # Nessuno spinner: il refresh non e' partito. Prima di arrendersi,
                            # riprova il click con Selenium diretto (hover + attesa di
                            # cliccabilita' + fallback JS), che gestisce i casi in cui il
                            # pulsante quick-action non era ancora interagibile.
                            logger.warning(f"Nessuno spinner per '{package}' dopo fallimento click, riprovo con click diretto...")
                            if _click_refresh_button(driver, package):
                                time.sleep(2)
                            else:
                                # Il refresh non e' partito nemmeno cosi': prosegui comunque,
                                # la verifica del timestamp stabilira' l'esito reale.
                                logger.error(f"Impossibile avviare il refresh di '{package}': click non riuscito.")
                                _log_debug_html(driver, package, "click di recupero fallito — verifico timestamp")

                    # Attendi che lo spinner appaia con polling attivo (mantiene la riga nel DOM)
                    # WebDriverWait statico non funziona: CDK virtual scroll può rimuovere la riga
                    # dal DOM durante l'attesa, rendendo lo spinner invisibile alla query.
                    time.sleep(2)
                    spinner_appeared = False
                    spinner_wait_start = time.time()
                    while time.time() - spinner_wait_start < 60:
                        _scroll_to_package(driver, package)
                        time.sleep(1)
                        try:
                            driver.find_element(By.XPATH, spinner_xpath)
                            spinner_appeared = True
                            logger.info(f"Spinner apparso per '{package}'.")
                            break
                        except NoSuchElementException:
                            pass
                    if not spinner_appeared:
                        logger.warning(f"Spinner non apparso per '{package}' entro 60s. Eseguo refresh e verifico...")

                    if not spinner_appeared:
                        # Spinner non comparso entro 60s: refresh pagina e ri-verifica
                        driver.refresh()
                        _wait_page_ready(driver)
                        data_chains["chains"] = {chain: data[chain] for chain in ms_chain}
                        actions, _, _, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
                        driver = actions.driver
                        _scroll_to_package(driver, package)
                        # Se lo spinner è ora visibile il refresh era già in corso: attendi completamento
                        try:
                            driver.find_element(By.XPATH, spinner_xpath)
                            logger.info(f"Spinner visibile per '{package}' post-refresh: attendo completamento...")
                            finished = _wait_spinner_gone(driver, package, timeout=86400)
                            if not finished:
                                logger.warning(f"Timeout 24h per '{package}' (rilevato post-refresh).")
                            _scroll_to_package(driver, package)
                        except NoSuchElementException:
                            pass  # nessuno spinner post-refresh, procedi al check icona errore
                        # Controlla icona errore e vai al prossimo package (sempre continue)
                        try:
                            row_el = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, row_xpath)))
                        except TimeoutException:
                            packages_status[package] = f"Timeout: riga '{package}' non trovata dopo aggiornamento post-refresh."
                            logger.error(f"Timeout riga post-aggiornamento per '{package}'.")
                            continue
                        packages_status[package] = _verify_refresh(
                            driver, package, baseline_ts, run_start_ms, "post-refresh"
                        )
                        continue

                # Attendi la fine dello spinner con refresh periodico ogni 5 minuti.
                # Evita sessioni Chrome morte su refresh lunghi (>30min).
                logger.info(f"Attendo la fine dello spinner per '{package}'...")
                refresh_interval = 300  # secondi tra un refresh e l'altro
                total_timeout = 86400
                total_start = time.time()
                finished = False

                while time.time() - total_start < total_timeout:
                    chunk = min(refresh_interval, total_timeout - (time.time() - total_start))
                    if chunk <= 0:
                        break
                    done = _wait_spinner_gone(driver, package, timeout=int(chunk))
                    if done:
                        finished = True
                        break
                    # Chunk scaduto, spinner ancora presente: refresh per tenere viva la sessione
                    logger.info(f"Refresh periodico (keep-alive) per '{package}'...")
                    driver.refresh()
                    _wait_page_ready(driver)
                    data_chains["chains"] = {chain: data[chain] for chain in ms_chain}
                    actions, _, _, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
                    driver = actions.driver
                    _scroll_to_package(driver, package)
                    try:
                        driver.find_element(By.XPATH, spinner_xpath)
                        logger.info(f"Spinner ancora presente per '{package}' post-refresh periodico, continuo...")
                    except NoSuchElementException:
                        finished = True
                        break

                if not finished:
                    logger.warning(f"Timeout 24h per '{package}'.")

                # Riporta la riga nel DOM e controlla icona errore
                logger.info(f"Controllo la riga per eventuali errori per '{package}'...")
                _scroll_to_package(driver, package)
                try:
                    row_el = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, row_xpath)))
                except TimeoutException:
                    packages_status[package] = f"Timeout: riga '{package}' non trovata dopo aggiornamento."
                    logger.error(f"Timeout riga post-aggiornamento per '{package}'.")
                    continue

                # Verifica l'esito reale: icona di errore + avanzamento del timestamp.
                packages_status[package] = _verify_refresh(
                    driver, package, baseline_ts, run_start_ms, "ramo principale"
                )

            except TimeoutException:
                packages_status[package] = f"Timeout durante l'aggiornamento di '{package}'."
                logger.error(f"Timeout per '{package}'.")
            except InvalidSessionIdException:
                packages_status[package] = f"Sessione browser chiusa inaspettatamente durante '{package}'."
                logger.error(f"InvalidSessionIdException per '{package}': sessione browser terminata.")
                break

    # 1) Package normali.
    _process_packages(PBI_packages)

    failed_packages = [pkg for pkg, status in packages_status.items() if "successo" not in str(status).lower()]
    # Un package blocca se e' fallito ora oppure se era gia' rosso a DB per lo stesso
    # periodo e non e' stato rilanciato in questa run.
    blockers = failed_packages + [pkg for pkg in blocked_by if pkg not in failed_packages]

    if blockers:
        error_msg = "Pubblicazione bloccata: uno o più modelli semantici non risultano aggiornati."
        logger.error(f"{error_msg} Package con errori: {blockers}")
        for pkg in PBI_packages:
            if pkg not in packages_status:
                packages_status[pkg] = error_msg
        # I package finali aggregano i dati degli altri: aggiornarli ora produrrebbe
        # una vista coerente nella forma ma sbagliata nei numeri.
        for pkg in final_packages:
            packages_status[pkg] = (
                "Non aggiornato: pubblicazione bloccata da package in errore "
                f"({', '.join(blockers)})."
            )
            logger.warning(f"Package finale '{pkg}' non aggiornato: bloccato da {blockers}.")
        return packages_status

    # 2) Package finali: solo ora che tutti gli altri sono verdi.
    if final_packages:
        logger.info(f"Tutti i package sono aggiornati. Procedo con i package finali: {final_packages}")
        _process_packages(final_packages)

        final_failed = [
            pkg for pkg in final_packages
            if "successo" not in str(packages_status.get(pkg, "")).lower()
        ]
        if final_failed:
            logger.error(f"Package finali non aggiornati: {final_failed}. Aggiornamento app saltato.")
            return packages_status

    logger.info("Aggiornamento app in corso...")
    data_chains["chains"] = {chain: data[chain] for chain in app_chain}
    actions, _, _, log = run_flow(modules, _FLOW_NAME, data_chains, workbook=workbook, actions=actions)
    logger.debug(f"App update log: {log}")

    logger.info(f"=== ELABORAZIONE COMPLETATA ===")
    logger.info(f"Riepilogo: {packages_status}")
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
