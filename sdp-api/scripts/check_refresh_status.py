"""
Diagnostica NON distruttiva dei modelli semantici Power BI.

Apre il workspace con lo stesso flusso FluentX usato dalla pubblicazione, ma
NON clicca mai "Aggiorna adesso": per ogni package legge solo la riga e riporta

  - se la riga viene trovata (il nome nella mappatura combacia con Power BI);
  - quali pulsanti quick-action esistono nella riga, prima e dopo l'hover;
  - se "Aggiorna adesso" e' presente, visibile e abilitato;
  - cosa si trova davvero sotto il punto in cui l'hover atterrerebbe;
  - la data di ultimo aggiornamento letta da fluentListCell.lastRefresh.

In piu', con --reload-test riproduce il refresh periodico (keep-alive) che
main.py esegue sui package lenti e ri-scansiona i package indicati a intervalli
crescenti: serve a verificare se dopo il reload i pulsanti quick-action
spariscono e dopo quanto tornano disponibili.

Uso:
    cd sdp-api
    venv\\Scripts\\python.exe -m scripts.check_refresh_status --bank Sparkasse
    venv\\Scripts\\python.exe -m scripts.check_refresh_status --bank Sparkasse --reload-test
    venv\\Scripts\\python.exe -m scripts.check_refresh_status --bank Sparkasse --fase production
"""
import argparse
import logging
import sys
import time
from os.path import basename

from openpyxl import load_workbook
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from fluentx.flow_executor import run_flow
from fluentx.utility import get_general_config

from scripts.main import (
    _resolve_flow_path,
    _scroll_to_package,
    _read_last_refresh,
    _fmt_ts,
    _wait_page_ready,
)

logger = logging.getLogger(__name__)

# Package su cui, nel giro del 21/09, il click su "Aggiorna adesso" e' fallito.
SOSPETTI_DEFAULT = [
    "Raccolta Indiretta",
    "Agribusiness",
    "Coralita_Raccolta Indiretta",
    "Coralita_Agribusiness",  # controllo: nello stesso giro ha funzionato
]

ROW_ANCESTOR = '/ancestor::*[@data-testid="workspace-list-content-view-row"]'

# Restituisce il tag/aria-label dell'elemento che si trova sotto il centro della
# riga: se non appartiene alla riga stessa, l'hover di Selenium atterra altrove
# e i pulsanti quick-action non compaiono mai.
JS_ELEMENT_AT_CENTER = """
var el = arguments[0];
var r = el.getBoundingClientRect();
var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
var top = document.elementFromPoint(cx, cy);
var inRow = false;
var row = el.closest('[data-testid="workspace-list-content-view-row"]');
if (top && row) { inRow = row.contains(top); }
return {
    rect: {x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)},
    viewportH: window.innerHeight,
    inViewport: r.top >= 0 && r.bottom <= window.innerHeight,
    topTag: top ? top.tagName.toLowerCase() : null,
    topLabel: top ? (top.getAttribute('aria-label') || top.getAttribute('data-testid') || '') : '',
    hoverHitsRow: inRow
};
"""


# Stile calcolato del pulsante: dice se e' nascosto per opacity/visibility/display
# oppure se ha dimensione zero. Serve a capire perche' is_displayed() torna False.
JS_BTN_STYLE = """
var el = arguments[0];
var cs = window.getComputedStyle(el);
var r = el.getBoundingClientRect();
return {
    opacity: cs.opacity, visibility: cs.visibility, display: cs.display,
    w: Math.round(r.width), h: Math.round(r.height),
    cls: (el.className || '').toString().slice(0, 120)
};
"""

# Hover simulato via eventi DOM: funziona se Power BI reagisce a onMouseEnter in JS,
# NON se i pulsanti sono rivelati dalla pseudo-classe CSS :hover.
JS_HOVER_EVENTS = """
var el = arguments[0];
var row = el.closest('[data-testid="workspace-list-content-view-row"]') || el;
['pointerover','mouseover','pointerenter','mouseenter','mousemove'].forEach(function(t) {
    row.dispatchEvent(new MouseEvent(t, {bubbles: true, cancelable: true, view: window}));
});
"""

STRATEGIE_HOVER = ["diretto", "parcheggio+target", "offset-jitter", "js-events"]


def applica_hover(driver, span, strategia: str):
    """Modi diversi di portare il mouse sulla riga, per capire quale rivela i pulsanti."""
    if strategia == "diretto":
        # Quello che fa oggi _click_refresh_button.
        ActionChains(driver).move_to_element(span).perform()
    elif strategia == "parcheggio+target":
        # Prima parcheggia il puntatore altrove: garantisce un mousemove reale
        # anche se il puntatore era gia' sulle coordinate della riga.
        body = driver.find_element(By.TAG_NAME, "body")
        ActionChains(driver).move_to_element_with_offset(body, 3, 3).perform()
        time.sleep(0.3)
        ActionChains(driver).move_to_element(span).perform()
    elif strategia == "offset-jitter":
        ActionChains(driver).move_to_element_with_offset(span, 4, 4).perform()
        time.sleep(0.2)
        ActionChains(driver).move_to_element(span).perform()
    elif strategia == "js-events":
        driver.execute_script(JS_HOVER_EVENTS, span)


def _labels(elements):
    """aria-label (o title, o testo) dei pulsanti, senza sollevare su elementi stale."""
    out = []
    for el in elements:
        try:
            label = el.get_attribute("aria-label") or el.get_attribute("title") or (el.text or "").strip()
            disabled = el.get_attribute("disabled") is not None or el.get_attribute("aria-disabled") == "true"
            out.append(("%s%s" % (label or "?", "[disabled]" if disabled else "")))
        except StaleElementReferenceException:
            out.append("<stale>")
    return out


def probe_row(driver, package: str, hover: bool = True) -> dict:
    """
    Fotografa lo stato della riga di un package senza cliccare nulla.
    Se hover=True simula il passaggio del mouse come fa _click_refresh_button.
    """
    name_xpath = '//span[@data-value="%s"]' % package
    btn_xpath = name_xpath + '//button[@aria-label="Aggiorna adesso"]'
    info = {
        "riga": False, "btn_pre": [], "btn_post": [], "aggiorna": None,
        "visibile": None, "abilitato": None, "ts": None, "geo": None, "errore": None,
    }

    _scroll_to_package(driver, package)
    try:
        span = driver.find_element(By.XPATH, name_xpath)
    except NoSuchElementException:
        return info
    info["riga"] = True
    info["ts"] = _read_last_refresh(driver, package)

    # Pulsanti presenti nella riga PRIMA di qualunque hover.
    try:
        row = driver.find_element(By.XPATH, name_xpath + ROW_ANCESTOR)
        info["btn_pre"] = _labels(row.find_elements(By.XPATH, ".//button"))
    except NoSuchElementException:
        info["btn_pre"] = _labels(span.find_elements(By.XPATH, ".//button"))

    if hover:
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", span
            )
            time.sleep(0.5)
            info["geo"] = driver.execute_script(JS_ELEMENT_AT_CENTER, span)
            ActionChains(driver).move_to_element(span).perform()
            time.sleep(0.8)
        except Exception as e:
            info["errore"] = "%s durante l'hover" % type(e).__name__

        try:
            row = driver.find_element(By.XPATH, name_xpath + ROW_ANCESTOR)
            info["btn_post"] = _labels(row.find_elements(By.XPATH, ".//button"))
        except NoSuchElementException:
            pass

    # Stato specifico di "Aggiorna adesso", lo stesso elemento che cerca main.py.
    try:
        btn = driver.find_element(By.XPATH, btn_xpath)
        info["aggiorna"] = True
        info["visibile"] = btn.is_displayed()
        info["abilitato"] = btn.is_enabled() and btn.get_attribute("aria-disabled") != "true"
    except NoSuchElementException:
        info["aggiorna"] = False

    return info


def probe_hover(driver, package: str, strategia: str) -> dict:
    """
    Applica una strategia di hover e riporta se il pulsante "Aggiorna adesso"
    diventa visibile. Non clicca nulla.
    """
    name_xpath = '//span[@data-value="%s"]' % package
    btn_xpath = name_xpath + '//button[@aria-label="Aggiorna adesso"]'
    esito = {"presente": False, "visibile": None, "stile": None, "errore": None}

    if not _scroll_to_package(driver, package):
        return esito
    try:
        span = driver.find_element(By.XPATH, name_xpath)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", span)
        time.sleep(0.4)
        applica_hover(driver, span, strategia)
        time.sleep(0.8)
    except Exception as e:
        esito["errore"] = type(e).__name__
        return esito

    try:
        btn = driver.find_element(By.XPATH, btn_xpath)
    except NoSuchElementException:
        return esito
    esito["presente"] = True
    esito["visibile"] = btn.is_displayed()
    try:
        esito["stile"] = driver.execute_script(JS_BTN_STYLE, btn)
    except Exception:
        pass
    return esito


def riga_hover_output(package: str, e: dict) -> str:
    if not e["presente"]:
        return "%-30s %-10s %s" % (package, "assente", e["errore"] or "pulsante non nel DOM")
    st = e["stile"] or {}
    return "%-30s %-10s opacity=%s visibility=%s display=%s %sx%s" % (
        package, "VISIBILE" if e["visibile"] else "nascosto",
        st.get("opacity"), st.get("visibility"), st.get("display"), st.get("w"), st.get("h"),
    )


def riga_output(package: str, info: dict) -> str:
    if not info["riga"]:
        return "%-30s %-6s %-10s %-10s %-22s %s" % (package, "NO", "-", "-", "-", "riga non trovata")
    if info["aggiorna"]:
        stato = "si"
        note = "visibile=%s abilitato=%s" % (info["visibile"], info["abilitato"])
    else:
        stato = "NO"
        note = "pulsanti riga: %s" % (", ".join(info["btn_post"] or info["btn_pre"]) or "nessuno")
    geo = info.get("geo") or {}
    if geo and not geo.get("hoverHitsRow", True):
        note += " | HOVER FUORI RIGA -> %s %s" % (geo.get("topTag"), geo.get("topLabel"))
    if geo and not geo.get("inViewport", True):
        note += " | riga fuori viewport y=%s h=%s" % (geo.get("rect", {}).get("y"), geo.get("viewportH"))
    if info["errore"]:
        note += " | %s" % info["errore"]
    return "%-30s %-6s %-10s %-10s %-22s %s" % (
        package, "si", stato, str(len(info["btn_pre"])), _fmt_ts(info["ts"]), note
    )


def intestazione():
    print("=" * 130)
    print("%-30s %-6s %-10s %-10s %-22s %s" % ("PACKAGE", "RIGA", "AGGIORNA", "N.BTN", "ULTIMO AGG.", "NOTE"))
    print("=" * 130)


def get_packages(bank: str, periodicity: str, fase: str):
    """Legge workspace e package da report_mapping, come fanno gli endpoint di pubblicazione."""
    from sqlalchemy import text
    import db as db_pkg
    from core.config import settings

    db_pkg.init_db(settings.DATABASE_URL)
    session = db_pkg.SessionLocal()
    try:
        ws_column = "ws_production" if fase == "production" else "ws_precheck"
        rows = session.execute(
            text(
                f"""
                SELECT {ws_column}, package, obbligatorio
                FROM report_mapping
                WHERE Type_reportisica = :periodicity
                  AND LOWER(bank) = LOWER(:bank)
                ORDER BY rowid
                """
            ),
            {"periodicity": periodicity, "bank": bank},
        ).fetchall()
    finally:
        session.close()

    if not rows:
        sys.exit(f"Nessun package in report_mapping per banca='{bank}' periodicita='{periodicity}'.")

    workspace = rows[0][0]
    packages = [(r[1], str(r[2] or "").strip().upper() == "Y") for r in rows if r[1]]
    return workspace, packages


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bank", required=True, help="Sparkasse | CiviBank")
    parser.add_argument("--periodicity", default="Settimanale", help="Settimanale (default) | Mensile")
    parser.add_argument("--fase", default="precheck", choices=["precheck", "production"])
    parser.add_argument("--workspace", default=None, help="Forza il workspace invece di leggerlo dal DB")
    parser.add_argument("--reload-test", action="store_true",
                        help="Dopo la scansione ripete il reload keep-alive e ri-scansiona i package sospetti")
    parser.add_argument("--target", nargs="*", default=None,
                        help="Package da usare nel --reload-test (default: quelli falliti il 21/09)")
    parser.add_argument("--checkpoints", nargs="*", type=int, default=[0, 30, 90, 150],
                        help="Secondi dal reload a cui ri-scansionare (default: 0 30 90 150)")
    parser.add_argument("--hover-test", action="store_true",
                        help="Dopo ogni reload prova strategie di hover diverse e dice quale rivela il pulsante")
    parser.add_argument("--solo-hover-test", action="store_true",
                        help="Salta la passata 1 e va dritto all'esperimento sull'hover")
    parser.add_argument("--keep-open", action="store_true",
                        help="Lascia il browser aperto a fine scansione per ispezione manuale")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    workspace, packages = get_packages(args.bank, args.periodicity, args.fase)
    if args.workspace:
        workspace = args.workspace

    print(f"\nBanca     : {args.bank}")
    print(f"Fase      : {args.fase}")
    print(f"Workspace : {workspace}")
    print(f"Package   : {len(packages)}\n")

    modules = ["web", "windows app", "file", "sharepoint"]
    flow_path, flow_bank = _resolve_flow_path(args.bank)
    flow_name = basename(flow_path).split(".")[0]
    workbook = load_workbook(flow_path, data_only=True)
    print(f"Flusso FluentX: {flow_path}")
    if flow_bank != args.bank:
        print(f"  ATTENZIONE: flusso specifico per '{args.bank}' assente, uso '{flow_bank}.xlsm'")

    data, data_chains = get_general_config(workbook)

    # Login
    print("\nLogin in corso...")
    data_chains["chains"] = {c: data[c] for c in ["Login"]}
    actions, _, _, log = run_flow(modules, flow_name, data_chains, workbook=workbook)

    # Workspace
    if workspace != "Engage-PRE CHECK":
        print(f"Apertura workspace '{workspace}'...")
        workbook["Cambia workspace"]["B5"].value = (
            f'//button[contains(@data-testid, "workspace-item-btn") and contains(@title, "{workspace}")]'
        )
        data_chains["chains"] = {c: data[c] for c in ["Cambia workspace"]}
        actions, _, _, log = run_flow(modules, flow_name, data_chains, workbook=workbook, actions=actions)
        if log["Cambia workspace"]["Cambia workspace"]["Selezionare workspace"]["status"] == "error":
            sys.exit(f"Workspace '{workspace}' non trovato.")

    # Filtro sui modelli semantici
    def applica_filtro(act):
        data_chains["chains"] = {c: data[c] for c in ["Filtro MS"]}
        act, _, _, _ = run_flow(modules, flow_name, data_chains, workbook=workbook, actions=act)
        return act

    print("Filtro sui modelli semantici...")
    actions = applica_filtro(actions)
    driver = actions.driver

    # --- Passata 1: pagina ferma ------------------------------------------------
    problemi = []
    if args.solo_hover_test:
        packages_da_scansionare = []
        print("\n### PASSATA 1 saltata (--solo-hover-test)")
    else:
        packages_da_scansionare = packages
        print("\n### PASSATA 1 - pagina stabile (nessun reload)\n")
        intestazione()
    for package, obbligatorio in packages_da_scansionare:
        info = probe_row(driver, package)
        print(riga_output(package, info))
        if not info["riga"]:
            problemi.append(f"{package}: riga non trovata")
        elif not info["aggiorna"]:
            problemi.append(f"{package}: pulsante 'Aggiorna adesso' assente a pagina ferma")
        elif not info["abilitato"]:
            problemi.append(f"{package}: pulsante presente ma disabilitato")
        if info["ts"] is None and info["riga"]:
            problemi.append(f"{package}: timestamp non leggibile")
    print("=" * 130)

    # --- Passata 2: subito dopo il reload keep-alive -----------------------------
    if args.reload_test:
        noti = {p for p, _ in packages}
        target = [p for p in (args.target or SOSPETTI_DEFAULT) if p in noti]
        if not target:
            target = [p for p, _ in packages][:4]

        print("\n### PASSATA 2 - dopo il reload keep-alive (driver.refresh + Filtro MS)")
        print("    Riproduce cio' che main.py fa sui package lenti prima di passare al successivo.")
        print(f"    Package osservati: {', '.join(target)}\n")

        driver.refresh()
        _wait_page_ready(driver)
        actions = applica_filtro(actions)
        driver = actions.driver
        t_reload = time.time()

        for cp in sorted(set(args.checkpoints)):
            attesa = cp - (time.time() - t_reload)
            if attesa > 0:
                time.sleep(attesa)
            trascorsi = int(time.time() - t_reload)
            print(f"\n--- t = {trascorsi}s dal reload ---")
            intestazione()
            for package in target:
                info = probe_row(driver, package)
                print(riga_output(package, info))
                if not info["aggiorna"]:
                    problemi.append(f"{package}: pulsante assente a t={trascorsi}s dal reload")
            print("=" * 130)

    # --- Passata 3: quale hover rivela il pulsante dopo il reload ----------------
    if args.hover_test or args.solo_hover_test:
        noti = {p for p, _ in packages}
        target = [p for p in (args.target or SOSPETTI_DEFAULT) if p in noti]
        if not target:
            target = [p for p, _ in packages][:4]

        print("\n### PASSATA 3 - quale strategia di hover rivela 'Aggiorna adesso' dopo il reload")
        print("    Una ricarica per strategia, cosi' nessuna eredita l'hover della precedente.")
        print(f"    Package osservati: {', '.join(target)}")

        vincenti = {}
        for strategia in STRATEGIE_HOVER:
            driver.refresh()
            _wait_page_ready(driver)
            actions = applica_filtro(actions)
            driver = actions.driver

            print(f"\n--- strategia: {strategia} ---")
            print("%-30s %-10s %s" % ("PACKAGE", "PULSANTE", "STILE CALCOLATO"))
            print("-" * 110)
            visibili = 0
            for package in target:
                e = probe_hover(driver, package, strategia)
                print(riga_hover_output(package, e))
                if e["visibile"]:
                    visibili += 1
            vincenti[strategia] = visibili
            print("-" * 110)
            print(f"  visibili: {visibili}/{len(target)}")

        print("\n### ESITO ESPERIMENTO HOVER")
        for strategia, n in vincenti.items():
            marchio = "  <== FUNZIONA" if n == len(target) else ""
            print(f"  {strategia:<20} {n}/{len(target)}{marchio}")
        if vincenti.get("diretto", 0) < len(target) and max(vincenti.values()) == len(target):
            print(
                "\nConfermato: dopo il reload l'hover attuale non rivela il pulsante, un'altra\n"
                "strategia si'. Il fix va su come viene mosso il puntatore, non sui tentativi."
            )

    # --- Esito ------------------------------------------------------------------
    if problemi:
        print("\nPROBLEMI RILEVATI:")
        for p in problemi:
            print(f"  - {p}")
        print(
            "\nLettura: se il pulsante c'e' nella PASSATA 1 e sparisce subito dopo il reload,\n"
            "la causa e' il rimontaggio della lista e il fix va sull'attesa di stabilizzazione.\n"
            "Se invece manca anche a pagina ferma, il problema e' nello stato del modello su\n"
            "Power BI (permessi/stato) e nessun retry di click potra' risolverlo."
        )
    else:
        print("\nNessun problema: righe trovate, pulsanti presenti e abilitati, timestamp leggibili.")

    if args.keep_open:
        print("\nBrowser lasciato aperto per ispezione manuale. Chiudilo quando hai finito.")
        try:
            input("Premi INVIO per terminare...")
        except EOFError:
            pass
    else:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
