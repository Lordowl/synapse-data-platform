"""
Modulo per tracciare l'esecuzione delle operazioni di publish nella tabella sync_runs.

La tabella sync_runs ha questa struttura:
  CREATE TABLE IF NOT EXISTS sync_runs (
      id INTEGER PRIMARY KEY,
      operation_type TEXT NOT NULL,
      start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      end_time TIMESTAMP,
      update_interval INTEGER DEFAULT 5,
      files_processed INTEGER DEFAULT 0,
      files_copied INTEGER DEFAULT 0,
      files_skipped INTEGER DEFAULT 0,
      files_failed INTEGER DEFAULT 0,
      error_details TEXT
  )

Note:
- ID fisso = 2 per tutte le operazioni di publish
- operation_type = 'publish' sempre
- ID = 1 è riservato al progetto sync (NON toccare)
- Timezone: CURRENT_TIMESTAMP (UTC)
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ID fisso per le operazioni di publish
PUBLISH_RUN_ID = 2
OPERATION_TYPE = "publish"
MIN_UPDATE_INTERVAL = 5


def start_publish_run(db: Session, update_interval: int = 5, phase: str = "precheck") -> bool:
    """
    Avvia una nuova operazione di publish.

    Args:
        db: Sessione database SQLAlchemy
        update_interval: Intervallo di aggiornamento in minuti (minimo 5)
        phase: Fase della pubblicazione ("precheck" o "production")

    Returns:
        True se l'operazione è stata avviata con successo
        False se c'è già un publish in corso
    """
    try:
        # Assicura che update_interval sia almeno 5 minuti
        if update_interval < MIN_UPDATE_INTERVAL:
            update_interval = MIN_UPDATE_INTERVAL
            logger.warning(f"update_interval impostato a {MIN_UPDATE_INTERVAL} minuti (valore minimo)")

        # Controlla se publish è già in corso
        check_sql = text("""
            SELECT end_time FROM sync_runs
            WHERE id = :id AND operation_type = :operation_type
        """)
        result = db.execute(check_sql, {
            "id": PUBLISH_RUN_ID,
            "operation_type": OPERATION_TYPE
        }).fetchone()

        # Se esiste un record con end_time NULL, publish è già in corso
        if result and result[0] is None:
            logger.warning(f"Publish già in corso (ID={PUBLISH_RUN_ID})")
            return False

        # Se il record esiste, aggiorna; altrimenti inserisci
        if result:
            # Record esiste, UPDATE
            update_sql = text("""
                UPDATE sync_runs
                SET start_time = CURRENT_TIMESTAMP,
                    end_time = NULL,
                    update_interval = :update_interval,
                    files_processed = 0,
                    files_copied = 0,
                    files_skipped = 0,
                    files_failed = 0,
                    error_details = :phase
                WHERE id = :id AND operation_type = :operation_type
            """)
            db.execute(update_sql, {
                "id": PUBLISH_RUN_ID,
                "operation_type": OPERATION_TYPE,
                "update_interval": update_interval,
                "phase": phase
            })
        else:
            # Record non esiste, INSERT
            insert_sql = text("""
                INSERT INTO sync_runs
                (id, operation_type, start_time, end_time, update_interval,
                 files_processed, files_copied, files_skipped, files_failed, error_details)
                VALUES
                (:id, :operation_type, CURRENT_TIMESTAMP, NULL, :update_interval,
                 0, 0, 0, 0, :phase)
            """)
            db.execute(insert_sql, {
                "id": PUBLISH_RUN_ID,
                "operation_type": OPERATION_TYPE,
                "update_interval": update_interval,
                "phase": phase
            })

        db.commit()
        logger.info(f"Publish run avviato (ID={PUBLISH_RUN_ID}, interval={update_interval}min)")
        return True

    except Exception as e:
        logger.error(f"Errore nell'avvio publish run: {e}")
        db.rollback()
        return False


def start_publish_run_force(db: Session, update_interval: int = 5, phase: str = "precheck") -> bool:
    """
    Avvia una nuova operazione di publish FORZATA (ignora controllo se già in corso).
    Usare per modalità continua/loop.

    Args:
        db: Sessione database SQLAlchemy
        update_interval: Intervallo di aggiornamento in minuti (minimo 5)
        phase: Fase della pubblicazione ("precheck" o "production")

    Returns:
        True se l'operazione è stata avviata con successo
        False in caso di errore
    """
    try:
        # Assicura che update_interval sia almeno 5 minuti
        if update_interval < MIN_UPDATE_INTERVAL:
            update_interval = MIN_UPDATE_INTERVAL
            logger.warning(f"update_interval impostato a {MIN_UPDATE_INTERVAL} minuti (valore minimo)")

        # Controlla se il record esiste
        check_sql = text("""
            SELECT id FROM sync_runs
            WHERE id = :id AND operation_type = :operation_type
        """)
        result = db.execute(check_sql, {
            "id": PUBLISH_RUN_ID,
            "operation_type": OPERATION_TYPE
        }).fetchone()

        if result:
            # Record esiste, UPDATE
            update_sql = text("""
                UPDATE sync_runs
                SET start_time = CURRENT_TIMESTAMP,
                    end_time = NULL,
                    update_interval = :update_interval,
                    files_processed = 0,
                    files_copied = 0,
                    files_skipped = 0,
                    files_failed = 0,
                    error_details = :phase
                WHERE id = :id AND operation_type = :operation_type
            """)
            db.execute(update_sql, {
                "id": PUBLISH_RUN_ID,
                "operation_type": OPERATION_TYPE,
                "update_interval": update_interval,
                "phase": phase
            })
        else:
            # Record non esiste, INSERT
            insert_sql = text("""
                INSERT INTO sync_runs
                (id, operation_type, start_time, end_time, update_interval,
                 files_processed, files_copied, files_skipped, files_failed, error_details)
                VALUES
                (:id, :operation_type, CURRENT_TIMESTAMP, NULL, :update_interval,
                 0, 0, 0, 0, :phase)
            """)
            db.execute(insert_sql, {
                "id": PUBLISH_RUN_ID,
                "operation_type": OPERATION_TYPE,
                "update_interval": update_interval,
                "phase": phase
            })

        db.commit()
        logger.info(f"Publish run avviato FORZATO (ID={PUBLISH_RUN_ID}, interval={update_interval}min)")
        return True

    except Exception as e:
        logger.error(f"Errore nell'avvio publish run forzato: {e}")
        db.rollback()
        return False


def update_publish_run(
    db: Session,
    files_processed: int = 0,
    files_copied: int = 0,
    files_skipped: int = 0,
    files_failed: int = 0
) -> bool:
    """
    Aggiorna i contatori della publish run corrente.

    Args:
        db: Sessione database SQLAlchemy
        files_processed: Numero di file processati
        files_copied: Numero di file copiati
        files_skipped: Numero di file saltati
        files_failed: Numero di file falliti

    Returns:
        True se l'aggiornamento è riuscito
        False in caso di errore
    """
    try:
        update_sql = text("""
            UPDATE sync_runs
            SET files_processed = :files_processed,
                files_copied = :files_copied,
                files_skipped = :files_skipped,
                files_failed = :files_failed
            WHERE id = :id AND operation_type = :operation_type
        """)

        result = db.execute(update_sql, {
            "id": PUBLISH_RUN_ID,
            "operation_type": OPERATION_TYPE,
            "files_processed": files_processed,
            "files_copied": files_copied,
            "files_skipped": files_skipped,
            "files_failed": files_failed
        })

        db.commit()

        if result.rowcount == 0:
            logger.warning(f"Nessuna publish run trovata da aggiornare (ID={PUBLISH_RUN_ID})")
            return False

        logger.debug(f"Publish run aggiornato: processed={files_processed}, copied={files_copied}, "
                    f"skipped={files_skipped}, failed={files_failed}")
        return True

    except Exception as e:
        logger.error(f"Errore nell'aggiornamento publish run: {e}")
        db.rollback()
        return False


def end_publish_run(db: Session, error_details: str = None) -> bool:
    """
    Termina l'operazione di publish corrente.

    Args:
        db: Sessione database SQLAlchemy
        error_details: Dettagli dell'errore (opzionale)

    Returns:
        True se la chiusura è riuscita
        False in caso di errore
    """
    try:
        update_sql = text("""
            UPDATE sync_runs
            SET end_time = CURRENT_TIMESTAMP,
                error_details = :error_details
            WHERE id = :id AND operation_type = :operation_type
        """)

        result = db.execute(update_sql, {
            "id": PUBLISH_RUN_ID,
            "operation_type": OPERATION_TYPE,
            "error_details": error_details
        })

        db.commit()

        if result.rowcount == 0:
            logger.warning(f"Nessuna publish run trovata da chiudere (ID={PUBLISH_RUN_ID})")
            return False

        if error_details:
            logger.info(f"Publish run terminato con errori (ID={PUBLISH_RUN_ID})")
        else:
            logger.info(f"Publish run terminato con successo (ID={PUBLISH_RUN_ID})")
        return True

    except Exception as e:
        logger.error(f"Errore nella chiusura publish run: {e}")
        db.rollback()
        return False


def is_publish_running(db: Session) -> bool:
    """
    Verifica se c'è un publish in corso.
    Un publish è in corso se end_time IS NULL e la differenza tra ora e end_time
    è minore di update_interval (in minuti).

    Args:
        db: Sessione database SQLAlchemy

    Returns:
        True se publish è in corso
        False altrimenti
    """
    try:
        check_sql = text("""
            SELECT end_time, update_interval, start_time
            FROM sync_runs
            WHERE id = :id AND operation_type = :operation_type
        """)
        result = db.execute(check_sql, {
            "id": PUBLISH_RUN_ID,
            "operation_type": OPERATION_TYPE
        }).fetchone()

        if not result:
            return False

        end_time_str, update_interval, start_time_str = result

        # Se end_time è NULL, il publish è in corso
        if end_time_str is None:
            return True

        # Altrimenti verifica il tempo trascorso
        if not end_time_str or not update_interval:
            return False

        end_time = datetime.fromisoformat(end_time_str)
        now = datetime.utcnow()
        time_diff = (now - end_time).total_seconds()
        interval_seconds = update_interval * 60

        return time_diff < interval_seconds

    except Exception as e:
        logger.error(f"Errore nella verifica publish status: {e}")
        return False
