import os
import logging
import pandas as pd

logger = logging.getLogger(__name__)

_MAPPING_FILENAME = "SPK_CVB mappatura_DEV.xlsx"
_PCHECK_SHEET = "PCHECK SPK_CVB REPORT POWERBI"
_PROD_SHEET = "PROD SPK_CVB REPORT POWERBI"


def _find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    """Restituisce il primo nome di colonna che inizia con uno dei candidati (case-insensitive)."""
    for name in df.columns:
        for c in candidates:
            if name.strip().lower().startswith(c.lower()):
                return name
    return None


def init_report_mapping_from_file(settings_path: str) -> None:
    """
    Sincronizza la tabella report_mapping dal file Excel di mappatura.
    Esegue un replace completo: elimina tutti i record esistenti e reinserisce
    quelli letti dal file, così le eliminazioni nel file si riflettono nel DB.
    """
    from . import SessionLocal, models

    if not settings_path:
        logger.warning("[INIT_REPORT_MAPPING] settings_path non configurato, skip.")
        return

    excel_path = os.path.join(settings_path, "App", "Dashboard", _MAPPING_FILENAME)
    if not os.path.exists(excel_path):
        logger.warning(f"[INIT_REPORT_MAPPING] File non trovato: {excel_path}")
        return

    try:
        df_pcheck = pd.read_excel(excel_path, sheet_name=_PCHECK_SHEET, dtype=str).fillna("")
        df_prod = pd.read_excel(excel_path, sheet_name=_PROD_SHEET, dtype=str).fillna("")
    except Exception as e:
        logger.error(f"[INIT_REPORT_MAPPING] Errore lettura Excel: {e}", exc_info=True)
        return

    records: dict[tuple, dict] = {}

    # --- Leggi foglio PCHECK (ws_precheck) ---
    col_tipo = _find_col(df_pcheck, "Tipo Reportistica")
    col_bank = _find_col(df_pcheck, "BANCA")
    col_pkg = _find_col(df_pcheck, "Pakage", "Package")
    col_ws_pre = _find_col(df_pcheck, "Workspace")
    col_fin = _find_col(df_pcheck, "Finalit")
    col_df = _find_col(df_pcheck, "Datafactory")
    col_obl = _find_col(df_pcheck, "Obbligatorio")

    if not all([col_tipo, col_bank, col_pkg]):
        logger.error(f"[INIT_REPORT_MAPPING] Colonne obbligatorie mancanti nel foglio '{_PCHECK_SHEET}'.")
        return

    for _, row in df_pcheck.iterrows():
        tipo = row[col_tipo].strip()
        bank = row[col_bank].strip()
        pkg = row[col_pkg].strip()
        if not tipo or not bank or not pkg:
            continue
        key = (tipo, bank, pkg)
        records[key] = {
            "Type_reportisica": tipo,
            "bank": bank,
            "package": pkg,
            "ws_precheck": row[col_ws_pre].strip() or None if col_ws_pre else None,
            "ws_production": None,
            "finality": row[col_fin].strip() or None if col_fin else None,
            "datafactory": row[col_df].strip() or None if col_df else None,
            "obbligatorio": row[col_obl].strip() or None if col_obl else None,
        }

    # --- Leggi foglio PROD (ws_production) ---
    col_tipo_p = _find_col(df_prod, "Tipo Reportistica")
    col_bank_p = _find_col(df_prod, "BANCA")
    col_pkg_p = _find_col(df_prod, "Pakage", "Package")
    col_ws_prod = _find_col(df_prod, "Workspace")
    col_df_p = _find_col(df_prod, "Datafactory")
    col_obl_p = _find_col(df_prod, "Obbligatorio")

    if col_tipo_p and col_bank_p and col_pkg_p:
        for _, row in df_prod.iterrows():
            tipo = row[col_tipo_p].strip()
            bank = row[col_bank_p].strip()
            pkg = row[col_pkg_p].strip()
            if not tipo or not bank or not pkg:
                continue
            key = (tipo, bank, pkg)
            ws_prod = row[col_ws_prod].strip() or None if col_ws_prod else None
            if key in records:
                records[key]["ws_production"] = ws_prod
            else:
                records[key] = {
                    "Type_reportisica": tipo,
                    "bank": bank,
                    "package": pkg,
                    "ws_precheck": None,
                    "ws_production": ws_prod,
                    "finality": None,
                    "datafactory": row[col_df_p].strip() or None if col_df_p else None,
                    "obbligatorio": row[col_obl_p].strip() or None if col_obl_p else None,
                }

    if not records:
        logger.warning("[INIT_REPORT_MAPPING] Nessun record trovato nel file Excel, skip.")
        return

    db = SessionLocal()
    try:
        db.query(models.ReportMapping).delete()
        for rec in records.values():
            db.add(models.ReportMapping(**rec))
        db.commit()
        logger.info(f"[INIT_REPORT_MAPPING] Sincronizzati {len(records)} record da {excel_path}")
    except Exception as e:
        db.rollback()
        logger.error(f"[INIT_REPORT_MAPPING] Errore durante il salvataggio nel DB: {e}", exc_info=True)
    finally:
        db.close()
