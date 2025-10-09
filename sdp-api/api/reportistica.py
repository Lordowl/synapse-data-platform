from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from db import get_db
from db import crud, schemas, models
from core.security import get_current_user
from db.models import User
import asyncio
import subprocess
import sys
import os
import traceback
from pydantic import BaseModel
from datetime import datetime

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

@router.get("/", response_model=List[schemas.ReportisticaInDB])
def get_reportistica_items(
    skip: int = 0,
    limit: int = 100,
    banca: Optional[str] = Query(None, description="Filtra per banca"),
    anno: Optional[int] = Query(None, description="Filtra per anno"),
    settimana: Optional[int] = Query(None, description="Filtra per settimana"),
    package: Optional[str] = Query(None, description="Filtra per package"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera tutti gli elementi di reportistica con filtri opzionali.
    """
    if banca or anno or settimana or package:
        # Usa filtri se specificati
        items = crud.get_reportistica_by_filters(
            db=db,
            banca=banca,
            anno=anno,
            settimana=settimana,
            package=package
        )
    else:
        # Recupera tutti gli elementi
        items = crud.get_reportistica_items(db=db, skip=skip, limit=limit)

    return items

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
        # Query per ottenere l'ultimo log per la banca dell'utente
        query = db.query(models.PublicationLog).filter(
            func.lower(models.PublicationLog.bank) == func.lower(current_user.bank)
        )

        if publication_type:
            query = query.filter(models.PublicationLog.publication_type == publication_type)

        # Recupera tutti i log più recenti (uno per package)
        # Raggruppa per package e prendi il più recente di ogni gruppo
        from sqlalchemy import desc

        # Query tutti i log della banca ordinati per timestamp
        logs = query.order_by(desc(models.PublicationLog.timestamp)).all()

        if not logs:
            return []

        # Raggruppa per package (prendi il più recente per ogni package)
        latest_by_package = {}
        for log in logs:
            for package in log.packages:
                if package not in latest_by_package:
                    latest_by_package[package] = log

        # Crea la risposta
        result = []
        for package, log in latest_by_package.items():
            # Estrai il messaggio specifico per questo package
            log_text = log.output if log.status == "success" else log.error
            package_message = log_text

            # Se il log è un dizionario/JSON, estrai solo il messaggio per questo package
            if log_text:
                try:
                    import json
                    # Prova a parsare come JSON
                    log_dict = json.loads(log_text) if isinstance(log_text, str) else log_text

                    if isinstance(log_dict, dict) and package in log_dict:
                        # Estrai solo il messaggio per questo package
                        package_message = log_dict[package]
                except (json.JSONDecodeError, TypeError, KeyError):
                    # Se non è un JSON valido o non contiene il package, usa il log originale
                    package_message = log_text

            result.append({
                "package": package,
                "workspace": log.workspace,
                "user": "N/D",  # Potresti join con users.username se vuoi
                "data_esecuzione": log.timestamp,
                "pre_check": log.publication_type == "precheck" and log.status == "success",
                "prod": log.publication_type == "production" and log.status == "success",
                "log": package_message,  # Solo il messaggio specifico del package
                "status": log.status
            })

        return result

    except Exception as e:
        print(f"[ERROR] get_latest_publication_logs: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/packages-ready-test")
def get_packages_ready_test():
    """Test endpoint completamente pubblico"""
    from db import SessionLocal
    db = SessionLocal()
    try:
        query = db.query(
            models.ReportData.package,
            models.ReportData.ws_precheck,
            models.ReportData.ws_production,
            models.ReportData.bank
        ).filter(
            models.ReportData.Type_reportisica == "Settimanale"
        )
        results = query.all()
        return {"count": len(results), "data": [{"package": r[0], "ws": r[1], "bank": r[3]} for r in results if r[0]]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()

@router.get("/test-packages-v2")
def get_packages_ready(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Recupera i package pronti dalla tabella report_data filtrati per banca utente"""
    from sqlalchemy import func

    print(f"[DEBUG] packages-ready endpoint called for user: {current_user.username}, bank: {current_user.bank}")

    try:
        # Filtra per banca dell'utente corrente (case-insensitive)
        query = db.query(
            models.ReportData.package,
            models.ReportData.ws_precheck,
            models.ReportData.ws_production,
            models.ReportData.bank
        ).filter(
            models.ReportData.Type_reportisica == "Settimanale",
            func.lower(models.ReportData.bank) == func.lower(current_user.bank)
        )

        results = query.all()
        print(f"[DEBUG] Found {len(results)} packages for bank {current_user.bank}")

        return [
            {
                "package": r[0],
                "ws_precheck": r[1],
                "ws_produzione": r[2],
                "bank": r[3],
                "user": "N/D",
                "data_esecuzione": None,
                "pre_check": False,
                "prod": False,
                "log": "In attesa di elaborazione"
            }
            for r in results if r[0]
        ]
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{reportistica_id}", response_model=schemas.ReportisticaInDB)
def get_reportistica_item(
    reportistica_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recupera un elemento di reportistica specifico per ID.
    """
    item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")
    return item

@router.post("/", response_model=schemas.ReportisticaInDB)
def create_reportistica_item(
    reportistica: schemas.ReportisticaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un nuovo elemento di reportistica.
    """
    # Verifica che il nome file non esista già
    existing_item = crud.get_reportistica_by_nome_file(db=db, nome_file=reportistica.nome_file)
    if existing_item:
        raise HTTPException(status_code=400, detail="Un elemento con questo nome file esiste già")

    return crud.create_reportistica(db=db, reportistica=reportistica)

@router.put("/{reportistica_id}", response_model=schemas.ReportisticaInDB)
def update_reportistica_item(
    reportistica_id: int,
    reportistica_data: schemas.ReportisticaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna un elemento di reportistica esistente.
    """
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    # Se il nome file viene cambiato, verifica che non esista già
    if reportistica_data.nome_file and reportistica_data.nome_file != existing_item.nome_file:
        existing_with_name = crud.get_reportistica_by_nome_file(db=db, nome_file=reportistica_data.nome_file)
        if existing_with_name:
            raise HTTPException(status_code=400, detail="Un elemento con questo nome file esiste già")

    return crud.update_reportistica(db=db, reportistica_id=reportistica_id, reportistica_data=reportistica_data)

@router.delete("/{reportistica_id}")
def delete_reportistica_item(
    reportistica_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Elimina un elemento di reportistica.
    """
    item = crud.delete_reportistica(db=db, reportistica_id=reportistica_id)
    if not item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    return {"message": "Elemento reportistica eliminato con successo"}

@router.patch("/{reportistica_id}/disponibilita", response_model=schemas.ReportisticaInDB)
def toggle_disponibilita_server(
    reportistica_id: int,
    disponibilita: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Aggiorna solo lo stato di disponibilità server per un elemento.
    """
    existing_item = crud.get_reportistica_by_id(db=db, reportistica_id=reportistica_id)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Elemento reportistica non trovato")

    update_data = schemas.ReportisticaUpdate(disponibilita_server=disponibilita)
    return crud.update_reportistica(db=db, reportistica_id=reportistica_id, reportistica_data=update_data)

@router.post("/publish-precheck")
async def publish_precheck(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    import traceback
    from sqlalchemy import func

    print(f"[DEBUG] publish_precheck called for user: {current_user.username}, bank: {current_user.bank}")

    try:
        # Prendi i dati dalla tabella report_data filtrati per banca dell'utente (case-insensitive)
        query = db.query(
            models.ReportData.ws_precheck,
            models.ReportData.package
        ).filter(
            models.ReportData.Type_reportisica == "Settimanale",
            func.lower(models.ReportData.bank) == func.lower(current_user.bank)
        )

        results = query.all()
        print(f"[DEBUG] Found {len(results)} records from report_data")

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Nessun package trovato per la banca {current_user.bank}"
            )

        # Estrai workspace (dovrebbe essere lo stesso per tutti i package della stessa banca)
        workspace = results[0][0]

        # Estrai lista dei package
        pbi_packages = [row[1] for row in results if row[1]]

        print(f"[DEBUG] Workspace: {workspace}")
        print(f"[DEBUG] Packages: {pbi_packages}")

        script_dir = os.path.join(os.path.dirname(__file__), "..", "scripts")
        script_path = os.path.join(script_dir, "main.py")
        print(f"[DEBUG] script_path: {script_path} exists={os.path.exists(script_path)}")

        venv_dir = os.path.join(os.path.dirname(__file__), "..", "venv")
        python_exe = (
            os.path.join(venv_dir, "Scripts", "python.exe")
            if os.name == "nt"
            else os.path.join(venv_dir, "bin", "python")
        )
        if not os.path.exists(python_exe):
            python_exe = sys.executable
        print(f"[DEBUG] python_exe: {python_exe} exists={os.path.exists(python_exe)}")

        # Use subprocess.Popen instead of asyncio.create_subprocess_exec for Windows compatibility
        def run_script():
            # Su Windows, apri una nuova finestra CMD per vedere l'esecuzione
            if os.name == 'nt':
                CREATE_NEW_CONSOLE = 0x00000010
                process = subprocess.Popen(
                    [
                        python_exe,
                        script_path,
                        "--workspace", workspace,
                        "--packages", ",".join(pbi_packages)
                    ],
                    creationflags=CREATE_NEW_CONSOLE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                process = subprocess.Popen(
                    [
                        python_exe,
                        script_path,
                        "--workspace", workspace,
                        "--packages", ",".join(pbi_packages)
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        returncode, stdout, stderr = await loop.run_in_executor(None, run_script)

        print("[DEBUG] Script return code:", returncode)
        print("[DEBUG] Script stdout:", stdout)
        print("[DEBUG] Script stderr:", stderr)

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
                print(f"[DEBUG] Parsed packages details: {packages_details}")
            else:
                print("[DEBUG] No [RESULT] JSON found in output")
        except Exception as e:
            print(f"[DEBUG] Error parsing packages details: {e}")

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
                user_id=current_user.id
            )
            db.add(log_entry)

        db.commit()

        if returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Errore nell'esecuzione dello script: {stderr}"
            )

        return {
            "status": "success",
            "message": "Pre-check pubblicato con successo",
            "workspace": workspace,
            "packages": pbi_packages,
            "output": stdout,
            "packages_details": packages_details
        }

    except HTTPException:
        raise
    except Exception as e:
        print("[DEBUG] Exception caught in publish_precheck:")
        traceback.print_exc()

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
                user_id=current_user.id if current_user else None
            )
            db.add(log_entry)
            db.commit()
        except:
            pass

        raise HTTPException(status_code=500, detail=str(e))