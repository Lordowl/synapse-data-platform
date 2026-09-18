"""
Diagnostica NON distruttiva dei modelli semantici Power BI.

Apre il workspace con lo stesso flusso FluentX usato dalla pubblicazione, ma
NON clicca mai "Aggiorna adesso": per ogni package legge solo la riga e riporta

  - se la riga viene trovata (il nome nella mappatura combacia con Power BI);
  - se il pulsante "Aggiorna adesso" e' presente;
  - la data di ultimo aggiornamento letta da fluentListCell.lastRefresh.

Serve a due cose:
  1. verificare che la lettura del timestamp introdotta in main.py funzioni sul
     DOM reale, prima di affidarle l'esito delle pubblicazioni;
  2. capire quali modelli sono fermi indietro nel tempo.

Uso:
    cd sdp-api
    venv\\Scripts\\python.exe -m scripts.check_refresh_status --bank Sparkasse
    venv\\Scripts\\python.exe -m scripts.check_refresh_status --bank Sparkasse --fase production
"""
import argparse
import logging
import sys
from os.path import basename

from openpyxl import load_workbook
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from fluentx.flow_executor import run_flow
from fluentx.utility import get_general_config

from scripts.main import _resolve_flow_path, _scroll_to_package, _read_last_refresh, _fmt_ts

logger = logging.getLogger(__name__)


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


def has_refresh_button(driver, package: str) -> bool:
    xpath = f'//span[@data-value="{package}"]//button[@aria-label="Aggiorna adesso"]'
    try:
        driver.find_element(By.XPATH, xpath)
        return True
    except NoSuchElementException:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bank", required=True, help="Sparkasse | CiviBank")
    parser.add_argument("--periodicity", default="Settimanale", help="Settimanale (default) | Mensile")
    parser.add_argument("--fase", default="precheck", choices=["precheck", "production"])
    parser.add_argument("--workspace", default=None, help="Forza il workspace invece di leggerlo dal DB")
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
    print("Filtro sui modelli semantici...")
    data_chains["chains"] = {c: data[c] for c in ["Filtro MS"]}
    actions, _, _, log = run_flow(modules, flow_name, data_chains, workbook=workbook, actions=actions)

    driver = actions.driver

    print("\n" + "=" * 96)
    print(f"{'PACKAGE':<32} {'RIGA':<8} {'PULSANTE':<10} {'ULTIMO AGGIORNAMENTO':<24} NOTE")
    print("=" * 96)

    problemi = []
    for package, obbligatorio in packages:
        trovato = _scroll_to_package(driver, package)
        if not trovato:
            print(f"{package:<32} {'NO':<8} {'-':<10} {'-':<24} nome non presente nel workspace")
            problemi.append(f"{package}: riga non trovata")
            continue

        bottone = has_refresh_button(driver, package)
        ts = _read_last_refresh(driver, package)
        note = []
        if not bottone:
            note.append("pulsante 'Aggiorna adesso' assente")
            problemi.append(f"{package}: pulsante di refresh assente")
        if ts is None:
            note.append("TIMESTAMP NON LEGGIBILE")
            problemi.append(f"{package}: timestamp non leggibile")
        if obbligatorio:
            note.append("package finale (Obbligatorio=Y)")

        print(f"{package:<32} {'si':<8} {('si' if bottone else 'NO'):<10} {_fmt_ts(ts):<24} {'; '.join(note)}")

    print("=" * 96)
    if problemi:
        print("\nPROBLEMI RILEVATI:")
        for p in problemi:
            print(f"  - {p}")
        print(
            "\nSe compare 'TIMESTAMP NON LEGGIBILE' su tutte le righe, il selettore\n"
            "fluentListCell.lastRefresh non corrisponde piu' al DOM di Power BI: in quel\n"
            "caso la verifica in main.py marcherebbe tutto come non verificabile."
        )
    else:
        print("\nNessun problema: righe trovate, pulsanti presenti, timestamp leggibili.")

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
