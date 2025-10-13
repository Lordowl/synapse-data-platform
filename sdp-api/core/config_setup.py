"""
Modulo per la gestione della configurazione iniziale
Copia i file di default dalla directory di installazione a ~/.sdp-api/
"""
import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def get_install_dir():
    """Ottiene la directory di installazione (dove si trova l'eseguibile)"""
    import sys

    # Se è bundled con PyInstaller
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)

    # Se è un eseguibile compilato
    if hasattr(sys, 'frozen'):
        return Path(sys.executable).parent

    # Se è eseguito come script
    if sys.argv and sys.argv[0]:
        exe_path = Path(sys.argv[0]).resolve()
        if exe_path.is_file():
            return exe_path.parent

    # Fallback alla directory corrente
    return Path.cwd()

def setup_config_files():
    """
    Copia i file di configurazione di default dalla directory di installazione a ~/.sdp-api/
    se non esistono già.

    File gestiti:
    - repo_update_default.json
    - banks_default.json (opzionale, se presente nella dir di installazione)
    """
    config_dir = Path.home() / ".sdp-api"
    config_dir.mkdir(exist_ok=True)

    install_dir = get_install_dir()
    logger.info(f"[CONFIG_SETUP] Directory installazione: {install_dir}")

    # File da copiare (nome file, sorgente relativa, destinazione)
    files_to_copy = [
        ("repo_update_default.json", "config/repo_update_default.json", config_dir / "repo_update_default.json"),
        ("repo_update_default.json", "repo_update_default.json", config_dir / "repo_update_default.json"),  # fallback
        ("banks_default.json", "config/banks_default.json", config_dir / "banks_default.json"),
        ("banks_default.json", "banks_default.json", config_dir / "banks_default.json"),  # fallback
    ]

    copied_files = []

    for file_name, source_rel, destination in files_to_copy:
        # Se il file di destinazione esiste già, skip
        if destination.exists():
            logger.info(f"[CONFIG_SETUP] File già esistente, skip: {destination.name}")
            continue

        # Cerca il file sorgente
        source = install_dir / source_rel

        if not source.exists():
            logger.debug(f"[CONFIG_SETUP] File sorgente non trovato: {source}")
            continue

        try:
            shutil.copy2(source, destination)
            logger.info(f"[CONFIG_SETUP] File copiato: {source.name} -> {destination}")
            copied_files.append(destination.name)
        except Exception as e:
            logger.error(f"[CONFIG_SETUP] Errore copia {source.name}: {e}")

    if copied_files:
        logger.info(f"[CONFIG_SETUP] File di configurazione inizializzati: {', '.join(copied_files)}")
    else:
        logger.debug("[CONFIG_SETUP] Nessun file di configurazione da inizializzare")

    return len(copied_files) > 0

def get_banks_json_path():
    """
    Restituisce il path del file banks_default.json cercando in ordine:
    1. Nella struttura App/Ingestion/ (se SETTINGS_PATH è configurato)
    2. Nella directory di installazione (config/banks_default.json)
    3. Nella directory ~/.sdp-api/
    """
    from core.config import config_manager

    # 1. Cerca nella struttura App/Ingestion/
    settings_path = config_manager.get_setting("SETTINGS_PATH")
    if settings_path:
        banks_file = Path(settings_path) / "App" / "Ingestion" / "banks_default.json"
        if banks_file.exists():
            logger.debug(f"[CONFIG_SETUP] banks_default.json trovato in: {banks_file}")
            return banks_file

    # 2. Cerca nella directory di installazione
    install_dir = get_install_dir()
    for rel_path in ["config/banks_default.json", "banks_default.json"]:
        banks_file = install_dir / rel_path
        if banks_file.exists():
            logger.info(f"[CONFIG_SETUP] banks_default.json trovato in: {banks_file}")
            return banks_file

    # 3. Cerca in ~/.sdp-api/
    banks_file = Path.home() / ".sdp-api" / "banks_default.json"
    if banks_file.exists():
        logger.info(f"[CONFIG_SETUP] banks_default.json trovato in: {banks_file}")
        return banks_file

    logger.warning("[CONFIG_SETUP] banks_default.json non trovato in nessuna posizione")
    return None
