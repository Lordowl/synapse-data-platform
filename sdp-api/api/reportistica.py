from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
import asyncio
import subprocess
import sys
import os
import traceback
import logging
import json
import re

from db import get_db, crud, schemas
import db.models as models
from db.models import User
from core.security import get_current_user


# Configura logger per questo modulo
logger = logging.getLogger(__name__)

router = APIRouter()

# Schema per i package pronti
class PackageReady(BaseModel):
    package: str
    ws_precheck: Optional[str] = None
    ws_produzione: Optional[str] = None
    user: str = "N/D"
    data_esecuzione: Optional[datetime] = None
    pre_check: bool = False
    prod: bool = False
    log: str = "In attesa di elaborazione"

@router.get("/")
def get_reportistica_items(
    skip: int = 0,
    limit: int = 100,
    anno: Optional[int] = Query(None, description="Filtra per anno"),
    settimana: Optional[int] = Query(None, description="Filtra per settimana"),
    package: Optional[str] = Query(None, description="Filtra per package"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera tutti gli elementi di reportistica della banca dell'utente loggato
    includendo il tipo_reportistica mappato da ReportMapping.

    Filtri opzionali: anno, settimana, package
    """
    from sqlalchemy import func
    from sqlalchemy.orm import aliased

    try:
        from sqlalchemy import text
        import logging
        logger = logging.getLogger(__name__)

        # Usa query SQL diretta per bypassare problemi PyInstaller con modelli SQLAlchemy
        # FORCE REBUILD 2025-10-28 16:11 - Fixed disponibilita_server boolean
        logger.info("USANDO QUERY SQL DIRETTA - VERSION 16:00")

        sql = text("""
            SELECT id, banca, tipo_reportistica, anno, settimana, mese, nome_file, package,
                   finalita, disponibilita_server, ultima_modifica, dettagli,
                   created_at, updated_at
            FROM reportistica
            WHERE LOWER(banca) = LOWER(:banca)
            {anno_filter}
            {settimana_filter}
            {package_filter}
            LIMIT :limit OFFSET :skip
        """.format(
            anno_filter="AND anno = :anno" if anno else "",
            settimana_filter="AND settimana = :settimana" if settimana else "",
            package_filter="AND package = :package" if (package and package.lower() != "tutti") else ""
        ))

        params = {"banca": current_user.bank, "limit": limit, "skip": skip}
        if anno:
            params["anno"] = anno
        if settimana:
            params["settimana"] = settimana
        if package and package.lower() != "tutti":
            params["package"] = package

        logger.info(f"Executing SQL with params: {params}")
        result = db.execute(sql, params)
        rows = result.fetchall()
        logger.info(f"Got {len(rows)} rows, first row: {rows[0] if rows else 'none'}")

        # Costruisci dict da righe SQL
        return [
            {
                "id": row[0],
                "banca": row[1],
                "tipo_reportistica": row[2],
                "anno": row[3],
                "settimana": row[4],
                "mese": row[5],
                "nome_file": row[6],
                "package": row[7],
                "finalita": row[8],
                "disponibilita_server": bool(row[9]) if row[9] is not None else None,
                "ultima_modifica": row[10],
                "dettagli": row[11],
                "created_at": row[12],
                "updated_at": row[13]
            }
            for row in rows
        ]

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Errore nel recupero reportistica: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Errore nel recupero dati reportistica: {str(e)}")

@router.get("/is-sync-running")
def is_sync_running(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verifica se c'è un sync in corso nella tabella sync_runs.
    Un sync è attivo se la differenza tra il timestamp corrente e end_time
    è minore di update_interval secondi.
    Restituisce {"is_running": true/false}
    """
    try:
        from datetime import datetime, timedelta

        # Prendi il record ID=1 (quello usato da reposync)
        sql = text("SELECT end_time, update_interval FROM sync_runs WHERE id = 1")
        result = db.execute(sql).fetchone()

        if not result:
            return {"is_running": False}

        end_time_str, update_interval = result

        if not end_time_str or not update_interval:
            return {"is_running": False}

        # Converti end_time in datetime
        end_time = datetime.fromisoformat(end_time_str)
        # Usa UTC per confrontare con timestamp salvati in UTC
        now = datetime.utcnow()

        # Calcola la differenza in secondi
        time_diff = (now - end_time).total_seconds()

        # update_interval è in MINUTI, convertiamo in secondi per il confronto
        interval_seconds = update_interval * 60

        # Se la differenza è minore di update_interval (in secondi), il sync è attivo
        is_active = time_diff < interval_seconds

        logger.debug(f"Sync status check: end_time={end_time}, now={now}, diff={time_diff}s, interval={update_interval}min ({interval_seconds}s), active={is_active}")

        return {
            "is_running": is_active,
            "update_interval": update_interval
        }
    except Exception as e:
        logger.error(f"Errore nel verificare sync status: {e}")
        return {"is_running": False, "update_interval": 5}


@router.get("/publish-status")
def get_publish_status(
    db: Session = Depends(get_db)
):
    """
    Recupera lo stato dell'operazione di publish dalla tabella sync_runs (ID=2).
    Restituisce informazioni su publish in corso, contatori e tempi.
    Endpoint pubblico per permettere il monitoraggio in tempo reale.
    """
    try:
        from datetime import datetime

        # Prendi il record ID=2 (quello per le operazioni di publish)
        sql = text("""
            SELECT start_time, end_time, update_interval,
                   files_processed, files_copied, files_skipped, files_failed,
                   error_details
            FROM sync_runs
            WHERE id = 2 AND operation_type = 'publish'
        """)
        result = db.execute(sql).fetchone()

        if not result:
            return {
                "is_running": False,
                "data": None
            }

        start_time_str, end_time_str, update_interval, files_processed, files_copied, files_skipped, files_failed, error_details = result

        # Determina se il publish è in corso
        is_running = end_time_str is None

        # Se il publish è in corso, error_details contiene la fase (precheck/production)
        # Altrimenti contiene eventuali errori
        phase = None
        actual_error = None
        if is_running and error_details in ["precheck", "production"]:
            phase = error_details
        else:
            actual_error = error_details

        # Se end_time esiste, calcola durata
        duration_seconds = None
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            if end_time_str:
                end_time = datetime.fromisoformat(end_time_str)
                duration_seconds = (end_time - start_time).total_seconds()
            else:
                # Ancora in corso, calcola tempo trascorso
                now = datetime.utcnow()
                duration_seconds = (now - start_time).total_seconds()

        return {
            "is_running": is_running,
            "data": {
                "start_time": start_time_str,
                "end_time": end_time_str,
                "duration_seconds": duration_seconds,
                "update_interval": update_interval,
                "files_processed": files_processed or 0,
                "files_copied": files_copied or 0,
                "files_skipped": files_skipped or 0,
                "files_failed": files_failed or 0,
                "phase": phase,
                "error_details": actual_error,
                "has_errors": (files_failed or 0) > 0 or actual_error is not None
            }
        }
    except Exception as e:
        logger.error(f"Errore nel recupero publish status: {e}")
        return {
            "is_running": False,
            "data": None
        }


@router.post("/trigger-sync")
def trigger_sync(
      db: Session = Depends(get_db),
      current_user: User = Depends(get_current_user)
  ):
      try:
          from datetime import datetime

          # Controlla SOLO il record ID=1 (quello che usa reposync)
          # Un sync è attivo se la differenza tra ora e end_time è minore di update_interval
          sql = text("SELECT end_time, update_interval FROM sync_runs WHERE id = 1")
          result = db.execute(sql).fetchone()

          if result:
              end_time_str, update_interval = result

              if end_time_str and update_interval:
                  end_time = datetime.fromisoformat(end_time_str)
                  # Usa UTC per confrontare con timestamp salvati in UTC
                  now = datetime.utcnow()
                  time_diff = (now - end_time).total_seconds()

                  # update_interval è in MINUTI, convertiamo in secondi
                  interval_seconds = update_interval * 60

                  # Se la differenza è minore di update_interval (in secondi), il sync è già attivo
                  if time_diff < interval_seconds:
                      return {
                          "success": False,
                          "message": "Un sync è già in corso",
                          "is_running": True
                      }

          # Path venv
          from core.config import config_manager
          base_folder = config_manager.get_setting("SETTINGS_PATH")
          if not base_folder:
              raise HTTPException(status_code=500, detail="SETTINGS_PATH non configurato")

          venv_path = os.path.join(base_folder, "App", "Dashboard", "vreposync")
          venv_python = os.path.join(venv_path, "Scripts", "python.exe")
          sync_command = [venv_python, "-m", "reposync", "-c"]

          if not os.path.exists(venv_python):
              raise HTTPException(status_code=404, detail=f"Python venv non trovato: {venv_python}")

          # ❌ RIMUOVI QUESTA PARTE - NON creare il record!
          # sql_insert = text("""
          #     INSERT INTO sync_runs ...
          # """)
          # db.execute(sql_insert, {"bank": current_user.bank})
          # db.commit()

          # Lancia il comando (reposync creerà il record con ID=1)
          work_dir = os.path.join(base_folder, "App", "Dashboard")
          process = subprocess.Popen(
              sync_command,
              cwd=work_dir,
              stdout=subprocess.PIPE,
              stderr=subprocess.PIPE,
              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
          )

          logger.info(f"Sync avviato da {current_user.username}, PID: {process.pid}")

          return {
              "success": True,
              "message": "Sync avviato con successo",
              "is_running": True,
              "pid": process.pid
          }

      except HTTPException:
          raise
      except Exception as e:
          logger.error(f"Errore sync: {e}", exc_info=True)
          raise HTTPException(status_code=500, detail=str(e))

@router.get("/publication-logs/latest")
def get_latest_publication_logs(
    publication_type: Optional[str] = Query(None, description="Filtra per tipo: precheck o production"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera l'ultimo log di pubblicazione per ogni package della banca dell'utente.
    Restituisce i dati pronti per popolare la tabella di pubblicazione.
    """
    from sqlalchemy import func

    try:
        # Se il modello non esiste nel runtime, fai fallback a SQL diretto
        if not hasattr(models, "PublicationLog"):
            logger.error("PublicationLog model missing; falling back to raw SQL")
            # Verifica che la tabella esista
            tbl = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='publication_logs'")).fetchone()
            if not tbl:
                logger.error("Table publication_logs not found")
                return []

            # Costruisci query semplice; filtra per bank e, se richiesto, per publication_type
            base_sql = """
                SELECT workspace, bank, publication_type, status, output, error, packages, timestamp, anno, settimana, mese
                FROM publication_logs
                WHERE LOWER(bank) = LOWER(:bank)
            """
            params = {"bank": current_user.bank}
            if publication_type:
                base_sql += " AND publication_type = :ptype"
                params["ptype"] = publication_type
            base_sql += " ORDER BY timestamp DESC LIMIT 200"

            rows = db.execute(text(base_sql), params).fetchall()
            if not rows:
                return []

            # Raggruppa per package (più recente per package)
            latest_by_package = {}
            for r in rows:
                workspace, _, ptype, status, output, error, packages, ts, anno, settimana, mese = r
                # packages può essere JSON string → normalizza
                pkg_list = []
                try:
                    if isinstance(packages, str):
                        pkg_list = json.loads(packages)
                    elif isinstance(packages, (list, tuple)):
                        pkg_list = list(packages)
                except Exception:
                    pkg_list = []

                for package in pkg_list or []:
                    # Se non presente, memorizza la riga più recente
                    if package not in latest_by_package:
                        latest_by_package[package] = {
                            "workspace": workspace,
                            "publication_type": ptype,
                            "status": status,
                            "output": output,
                            "error": error,
                            "timestamp": ts,
                            "anno": anno,
                            "settimana": settimana,
                            "mese": mese
                        }

            result = []
            for package, info in latest_by_package.items():
                log_text = info["output"] if info["status"] == "success" else info["error"]
                package_message = log_text

                # Prova a estrarre il messaggio specifico per package se log è JSON
                if log_text:
                    try:
                        log_dict = json.loads(log_text) if isinstance(log_text, str) else log_text
                        if isinstance(log_dict, dict) and package in log_dict:
                            package_message = log_dict[package]
                    except Exception:
                        package_message = log_text

                # Determina lo stato in base al messaggio e allo status
                pre_check_status = False
                prod_status = False

                if info["publication_type"] == "precheck":
                    if info["status"] == "success" and package_message and "successo" in package_message.lower():
                        pre_check_status = True
                    elif package_message and "timeout" in package_message.lower():
                        pre_check_status = "timeout"
                    elif info["status"] == "error" or (package_message and ("errore" in package_message.lower() or "error" in package_message.lower())):
                        pre_check_status = "error"
                elif info["publication_type"] == "production":
                    if info["status"] == "success" and package_message and "successo" in package_message.lower():
                        prod_status = True
                    elif package_message and "timeout" in package_message.lower():
                        prod_status = "timeout"
                    elif info["status"] == "error" or (package_message and ("errore" in package_message.lower() or "error" in package_message.lower())):
                        prod_status = "error"

                result.append({
                    "package": package,
                    "workspace": info["workspace"],
                    "user": "N/D",
                    "data_esecuzione": info["timestamp"],
                    "pre_check": pre_check_status,
                    "prod": prod_status,
                    "log": package_message,
                    "status": info["status"],
                    "anno": info["anno"],
                    "settimana": info["settimana"],
                    "mese": info["mese"]
                })

            return result

        # Percorso normale con ORM se il modello esiste
        query = db.query(models.PublicationLog).filter(
            func.lower(models.PublicationLog.bank) == func.lower(current_user.bank)
        )
        if publication_type:
            query = query.filter(models.PublicationLog.publication_type == publication_type)

        logs = query.order_by(desc(models.PublicationLog.timestamp)).all()
        if not logs:
            return []

        latest_by_package = {}
        for log in logs:
            for package in log.packages:
                if package not in latest_by_package:
                    latest_by_package[package] = log

        result = []
        for package, log in latest_by_package.items():
            log_text = log.output if log.status == "success" else log.error
            package_message = log_text
            if log_text:
                try:
                    log_dict = json.loads(log_text) if isinstance(log_text, str) else log_text
                    if isinstance(log_dict, dict) and package in log_dict:
                        package_message = log_dict[package]
                except (json.JSONDecodeError, TypeError, KeyError):
                    package_message = log_text

            # Determina lo stato in base al messaggio e allo status
            pre_check_status = False
            prod_status = False

            if log.publication_type == "precheck":
                if log.status == "success" and package_message and "successo" in package_message.lower():
                    pre_check_status = True
                elif package_message and "timeout" in package_message.lower():
                    pre_check_status = "timeout"
                elif log.status == "error" or (package_message and ("errore" in package_message.lower() or "error" in package_message.lower())):
                    pre_check_status = "error"
            elif log.publication_type == "production":
                if log.status == "success" and package_message and "successo" in package_message.lower():
                    prod_status = True
                elif package_message and "timeout" in package_message.lower():
                    prod_status = "timeout"
                elif log.status == "error" or (package_message and ("errore" in package_message.lower() or "error" in package_message.lower())):
                    prod_status = "error"

            result.append({
                "package": package,
                "workspace": log.workspace,
                "user": "N/D",
                "data_esecuzione": log.timestamp,
                "pre_check": pre_check_status,
                "prod": prod_status,
                "log": package_message,
                "status": log.status
            })
        return result
    except Exception as e:
        logger.error("get_latest_publication_logs failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/packages-ready-test")
def get_packages_ready_test():
    """Test endpoint completamente pubblico"""
    from db import SessionLocal
    db = SessionLocal()
    try:
        query = db.query(
            models.ReportMapping.package,
            models.ReportMapping.ws_precheck,
            models.ReportMapping.ws_production,
            models.ReportMapping.bank
        ).filter(
            models.ReportMapping.Type_reportisica == "Settimanale"
        )
        results = query.all()
        return {"count": len(results), "data": [{"package": r[0], "ws": r[1], "bank": r[3]} for r in results if r[0]]}
    except Exception as e:
        logger.error(f"packages_ready_test failed: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()

@router.get("/test-packages-v2")
def get_packages_ready(
    type_reportistica: Optional[str] = Query(None, description="Filtra per tipo: Settimanale o Mensile"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Recupera i package pronti dalla tabella report_mapping filtrati per banca utente con stato da publication_logs"""
    from sqlalchemy import func, and_
    import json

    logger.info(f"test-packages-v2 endpoint called for user: {current_user.username}, bank: {current_user.bank}, type: {type_reportistica}")

    try:
        # Filtra per banca dell'utente corrente (case-insensitive)
        query = db.query(
            models.ReportMapping.package,
            models.ReportMapping.ws_precheck,
            models.ReportMapping.ws_production,
            models.ReportMapping.bank,
            models.ReportMapping.Type_reportisica
        ).filter(
            func.lower(models.ReportMapping.bank) == func.lower(current_user.bank)
        )

        # Filtra per tipo di reportistica se specificato
        if type_reportistica:
            query = query.filter(models.ReportMapping.Type_reportisica == type_reportistica)

        results = query.all()
        logger.debug(f"Found {len(results)} packages for bank {current_user.bank}")

        # Per ogni package, cerca l'ultimo log in publication_logs
        packages_with_status = []
        for r in results:
            if not r[0]:  # Skip se package è None
                continue

            package_name = r[0]

            # Cerca tutti i log recenti per questa banca con publication_type='precheck'
            all_logs = db.query(models.PublicationLog).filter(
                and_(
                    func.lower(models.PublicationLog.bank) == func.lower(current_user.bank),
                    models.PublicationLog.publication_type == 'precheck'
                )
            ).order_by(models.PublicationLog.timestamp.desc()).limit(50).all()

            pre_check_status = False
            dettagli = "In attesa di elaborazione"
            data_esecuzione = None
            user = "N/D"

            # Cerca il log che contiene questo package specifico
            for log in all_logs:
                try:
                    packages_list = log.packages if isinstance(log.packages, list) else json.loads(log.packages)

                    # Se questo log contiene il package che stiamo cercando
                    if package_name in packages_list:
                        data_esecuzione = log.timestamp
                        user = "Sistema" if not log.user_id else f"User #{log.user_id}"

                        # Prendi il messaggio dall'output o dall'error
                        message = log.output if log.output else (log.error if log.error else "")

                        # Determina lo stato in base al CONTENUTO del messaggio
                        if "successo" in message.lower():
                            pre_check_status = True  # Verde
                            dettagli = message
                        elif "timeout" in message.lower():
                            pre_check_status = "timeout"  # Giallo/Arancione
                            dettagli = message
                        elif "errore" in message.lower() or "error" in message.lower():
                            pre_check_status = "error"  # Rosso
                            dettagli = message
                        else:
                            # Fallback sul campo status del log
                            if log.status == 'success':
                                pre_check_status = True
                                dettagli = message if message else "Aggiornamento completato con successo"
                            else:
                                pre_check_status = False
                                dettagli = message if message else "Errore durante l'aggiornamento"

                        # Abbiamo trovato il log per questo package, usiamo il più recente
                        break
                except Exception as e:
                    logger.warning(f"Error parsing publication log for {package_name}: {e}")
                    continue

            packages_with_status.append({
                "package": package_name,
                "ws_precheck": r[1],
                "ws_produzione": r[2],
                "bank": r[3],
                "type_reportistica": r[4],
                "user": user,
                "data_esecuzione": data_esecuzione,
                "pre_check": pre_check_status,
                "prod": False,  # TODO: implementare logica per production
                "dettagli": dettagli
            })

        return packages_with_status

    except Exception as e:
        logger.error(f"test-packages-v2 failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{reportistica_id}", response_model=schemas.ReportisticaInDB)
def get_reportistica_item(
    reportistica_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera un elemento di reportistica specifico per ID della propria banca.

    Note:
        - Può visualizzare solo elementi della propria banca
    """
    item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # ✅ Verifica che l'elemento appartenga alla banca dell'utente
    if item.banca != current_user.bank:
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per visualizzare questo elemento (appartiene a un'altra banca)"
        )

    return item

@router.post("/", response_model=schemas.ReportisticaInDB)
def create_reportistica_item(
    reportistica: schemas.ReportisticaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un nuovo elemento di reportistica per la banca dell'utente loggato.

    Note:
        - banca viene automaticamente settata a current_user.bank
        - La coppia (nome_file, banca) deve essere unica
    """
    logger.info(f"Creating reportistica item for bank: {current_user.bank}, file: {reportistica.nome_file}")

    # ✅ Verifica che la coppia (nome_file, banca utente) non esista già
    existing_item = crud.get_reportistica_by_nome_file(
        db=db,
        nome_file=reportistica.nome_file,
        banca=current_user.bank  # ✅ Usa la banca dell'utente loggato
    )
    if existing_item:
        raise HTTPException(
            status_code=400,
            detail=f"Un elemento con nome file '{reportistica.nome_file}' esiste già per la tua banca"
        )

    # ✅ Passa la banca dell'utente loggato
    return crud.create_reportistica(
        db=db,
        reportistica=reportistica,
        banca=current_user.bank  # ✅ Automatico
    )

@router.put("/{reportistica_id}", response_model=schemas.ReportisticaInDB)
def update_reportistica_item(
    reportistica_id: int,
    reportistica_data: schemas.ReportisticaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna un elemento di reportistica della banca dell'utente loggato.

    Note:
        - Può modificare solo elementi della propria banca
        - Se viene modificato nome_file, verifica che non esista già nella banca
    """
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # ✅ Verifica che l'elemento appartenga alla banca dell'utente (case-insensitive)
    if existing_item.banca.lower() != current_user.bank.lower():
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per modificare questo elemento (appartiene a un'altra banca)"
        )

    # ✅ Se il nome file viene cambiato, verifica che non esista già nella stessa banca
    if reportistica_data.nome_file and reportistica_data.nome_file != existing_item.nome_file:
        existing_with_name = crud.get_reportistica_by_nome_file(
            db=db,
            nome_file=reportistica_data.nome_file,
            banca=current_user.bank  # ✅ Verifica solo nella banca dell'utente
        )
        if existing_with_name and existing_with_name.id != reportistica_id:
            raise HTTPException(
                status_code=400,
                detail=f"Un elemento con nome file '{reportistica_data.nome_file}' esiste già per la tua banca"
            )

    return crud.update_reportistica(db=db, reportistica_id=reportistica_id, reportistica_data=reportistica_data)

@router.delete("/{reportistica_id}")
def delete_reportistica_item(
    reportistica_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Elimina un elemento di reportistica della banca dell'utente loggato.

    Note:
        - Può eliminare solo elementi della propria banca
    """
    # ✅ Prima verifica che l'elemento esista e appartenga alla banca dell'utente
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # ✅ Verifica che l'elemento appartenga alla banca dell'utente
    if existing_item.banca != current_user.bank:
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per eliminare questo elemento (appartiene a un'altra banca)"
        )

    item = crud.delete_reportistica(db=db, reportistica_id=reportistica_id)
    return {"message": "Elemento reportistica eliminato con successo"}

@router.patch("/{reportistica_id}/disponibilita", response_model=schemas.ReportisticaInDB)
def toggle_disponibilita_server(
    reportistica_id: int,
    disponibilita: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna solo lo stato di disponibilità server per un elemento della propria banca.

    Note:
        - Può modificare solo elementi della propria banca
    """
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # ✅ Verifica che l'elemento appartenga alla banca dell'utente (case-insensitive)
    if existing_item.banca.lower() != current_user.bank.lower():
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per modificare questo elemento (appartiene a un'altra banca)"
        )

    update_data = schemas.ReportisticaUpdate(disponibilita_server=disponibilita)
    return crud.update_reportistica(db=db, reportistica_id=reportistica_id, reportistica_data=update_data)

@router.post("/publish-precheck")
async def publish_precheck(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    import traceback
    from sqlalchemy import func
    from db import publish_tracker

    logger.info(f"publish_precheck called for user: {current_user.username}, bank: {current_user.bank}")

    try:
        # Recupera anno, settimana e mese da repo_update_info per questo utente
        repo_info_query = db.query(models.RepoUpdateInfo).filter(
            func.lower(models.RepoUpdateInfo.bank) == func.lower(current_user.bank)
        ).first()

        anno = repo_info_query.anno if repo_info_query else 2025
        settimana = repo_info_query.settimana if repo_info_query else None
        mese = repo_info_query.mese if repo_info_query else None

        logger.info(f"Publishing for period: anno={anno}, settimana={settimana}, mese={mese}")

        # Avvia il tracking della publish run
        if not publish_tracker.start_publish_run(db, update_interval=5):
            raise HTTPException(
                status_code=409,
                detail="Un'operazione di pubblicazione è già in corso. Attendere il completamento."
            )
        # Prendi i dati dalla tabella report_mapping filtrati per banca dell'utente (case-insensitive)
        query = db.query(
            models.ReportMapping.ws_precheck,
            models.ReportMapping.package
        ).filter(
            models.ReportMapping.Type_reportisica == "Settimanale",
            func.lower(models.ReportMapping.bank) == func.lower(current_user.bank)
        )

        results = query.all()
        logger.debug(f"Found {len(results)} records from report_mapping")

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Nessun package trovato per la banca {current_user.bank}"
            )

        # Estrai workspace (dovrebbe essere lo stesso per tutti i package della stessa banca)
        workspace = results[0][0]

        # Estrai lista dei package
        pbi_packages = [row[1] for row in results if row[1]]

        logger.info(f"Workspace: {workspace}")
        logger.info(f"Packages to publish: {pbi_packages}")

        # Importa e chiama direttamente lo script invece di usare subprocess
        # Questo permette di usare le dipendenze incluse nel bundle PyInstaller
        def run_script():
            import io
            import contextlib

            # Cattura stdout/stderr
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()

            try:
                with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                    # Importa il modulo scripts.main
                    from scripts import main as script_main

                    # Chiama la funzione main direttamente
                    status = script_main.main(workspace, pbi_packages)

                    # Stampa il risultato come JSON per mantenere il formato originale
                    import json
                    print("\n[RESULT]")
                    print(json.dumps(status, indent=2))

                return 0, stdout_capture.getvalue(), stderr_capture.getvalue()
            except Exception as e:
                import traceback
                stderr_capture.write(traceback.format_exc())
                return 1, stdout_capture.getvalue(), stderr_capture.getvalue()

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        returncode, stdout, stderr = await loop.run_in_executor(None, run_script)

        logger.info(f"Script completed with return code: {returncode}")
        logger.debug(f"Script stdout: {stdout}")
        if stderr:
            logger.warning(f"Script stderr: {stderr}")

        # Parse dello stdout per estrarre il JSON dei risultati
        import json
        import re

        packages_details = {}
        try:
            # Cerca il JSON nel formato [RESULT]\n{...}
            match = re.search(r'\[RESULT\]\s*(\{.*\})', stdout, re.DOTALL)
            if match:
                json_str = match.group(1)
                packages_details = json.loads(json_str)
                logger.debug(f"Parsed packages details: {packages_details}")
            else:
                logger.debug("No [RESULT] JSON found in output")
        except Exception as e:
            logger.warning(f"Error parsing packages details: {e}")

        # Salva un log per ogni package con il suo dettaglio specifico
        for package_name in pbi_packages:
            package_detail = packages_details.get(package_name, stdout if returncode == 0 else stderr)

            log_entry = models.PublicationLog(
                bank=current_user.bank,
                workspace=workspace,
                packages=[package_name],  # Un package per volta
                publication_type="precheck",
                status="success" if returncode == 0 and "successo" in package_detail.lower() else "error",
                output=package_detail if returncode == 0 or "successo" in package_detail.lower() else None,
                error=package_detail if returncode != 0 or "errore" in package_detail.lower() or "timeout" in package_detail.lower() else None,
                user_id=current_user.id,
                anno=anno,
                settimana=settimana,
                mese=mese
            )
            db.add(log_entry)

        db.commit()

        # Aggiorna i contatori della publish run
        total_packages = len(pbi_packages)
        success_count = sum(1 for pkg in pbi_packages if "successo" in packages_details.get(pkg, "").lower())
        failed_count = total_packages - success_count

        publish_tracker.update_publish_run(
            db=db,
            files_processed=total_packages,
            files_copied=success_count,
            files_skipped=0,
            files_failed=failed_count
        )

        if returncode != 0:
            # Chiudi la publish run con errore
            publish_tracker.end_publish_run(db=db, error_details=stderr[:500] if stderr else None)
            raise HTTPException(
                status_code=500,
                detail=f"Errore nell'esecuzione dello script: {stderr}"
            )

        # Chiudi la publish run con successo
        publish_tracker.end_publish_run(db=db, error_details=None)

        return {
            "status": "success",
            "message": "Pre-check pubblicato con successo",
            "workspace": workspace,
            "packages": pbi_packages,
            "output": stdout,
            "packages_details": packages_details
        }

    except HTTPException as http_exc:
        # Chiudi la publish run con errore se è stata avviata
        try:
            publish_tracker.end_publish_run(db=db, error_details=str(http_exc.detail)[:500])
        except:
            pass
        raise
    except Exception as e:
        logger.error(f"Exception in publish_precheck: {e}", exc_info=True)

        # Chiudi la publish run con errore
        try:
            publish_tracker.end_publish_run(db=db, error_details=str(e)[:500])
        except:
            pass

        # Salva anche gli errori nel database
        try:
            log_entry = models.PublicationLog(
                bank=current_user.bank if current_user else "unknown",
                workspace=workspace if 'workspace' in locals() else "unknown",
                packages=pbi_packages if 'pbi_packages' in locals() else [],
                publication_type="precheck",
                status="error",
                output=None,
                error=str(e),
                user_id=current_user.id if current_user else None,
                anno=anno if 'anno' in locals() else None,
                settimana=settimana if 'settimana' in locals() else None,
                mese=mese if 'mese' in locals() else None
            )
            db.add(log_entry)
            db.commit()
        except Exception as db_error:
            logger.error(f"Failed to save error log to database: {db_error}")

        raise HTTPException(status_code=500, detail=str(e))