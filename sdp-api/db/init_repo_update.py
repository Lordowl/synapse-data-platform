import json
import os
import logging
from sqlalchemy.orm import Session
from . import models

logger = logging.getLogger(__name__)

def init_repo_update_from_file(repo_update_data: list = None):
    """
    Inizializza la tabella repo_update_info con i dati dal JSON.
    Se repo_update_data è None, legge dal file repo_update_default.json
    """
    from . import SessionLocal

    if SessionLocal is None:
        logger.warning("[INIT_REPO_UPDATE] Database non inizializzato, skip.")
        return

    # Se non sono stati passati dati, leggi dal file JSON
    if repo_update_data is None:
        json_path = os.path.join(os.path.dirname(__file__), "repo_update_default.json")

        if not os.path.exists(json_path):
            logger.warning(f"[INIT_REPO_UPDATE] File {json_path} non trovato.")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                repo_update_data = json.load(f)
        except Exception as e:
            logger.error(f"[INIT_REPO_UPDATE] Errore lettura JSON: {e}")
            return

    db = SessionLocal()
    try:
        for entry in repo_update_data:
            bank_name = entry.get("bank")
            settimana = entry.get("settimana")
            anno = entry.get("anno")
            semaforo = entry.get("semaforo", 0)

            if not bank_name:
                logger.warning(f"[INIT_REPO_UPDATE] Entry senza bank, skip: {entry}")
                continue

            # Verifica se esiste già un record per questa banca
            existing = db.query(models.RepoUpdateInfo).filter(
                models.RepoUpdateInfo.bank == bank_name
            ).first()

            if existing:
                logger.info(f"[INIT_REPO_UPDATE] Record già presente per banca '{bank_name}', skip.")
                continue

            # Crea nuovo record
            new_record = models.RepoUpdateInfo(
                settimana=settimana,
                anno=anno,
                semaforo=semaforo,
                bank=bank_name,
                log_key=None,
                details=None
            )
            db.add(new_record)
            logger.info(f"[INIT_REPO_UPDATE] Creato record per banca '{bank_name}': anno={anno}, settimana={settimana}")

        db.commit()
        logger.info("[INIT_REPO_UPDATE] Inizializzazione completata con successo.")

    except Exception as e:
        logger.error(f"[INIT_REPO_UPDATE] Errore durante l'inizializzazione: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
