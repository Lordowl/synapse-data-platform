import os
import secrets
import logging
import json
import configparser
import re
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from dotenv import load_dotenv

# PRIMA DI TUTTO: Assicuriamoci che esista una configurazione
def ensure_config_exists():
    """Assicura che esista una configurazione PRIMA dell'inizializzazione di Pydantic"""
    config_dir = Path.home() / ".sdp-api"
    env_file = config_dir / ".env"
    
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
        print(f"[INFO] Creata directory di configurazione: {config_dir}")
    
    if not env_file.exists():
        print(f"[INFO] Creazione configurazione: {env_file}")
        secret_key = secrets.token_urlsafe(32)
        
        content = f"""# Synapse Data Platform API - Configurazione
# Generata automaticamente

# === SICUREZZA JWT ===
SECRET_KEY={secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=11520
REFRESH_TOKEN_EXPIRE_DAYS=8

# === DATABASE ===
DATABASE_URL=sqlite:///./sdp.db

# === LOGGING ===
LOG_LEVEL=INFO

# === SERVER ===
HOST=127.0.0.1
PORT=9123

# === AGGIORNAMENTI ===
AUTO_UPDATE_CHECK=true
GITHUB_REPO=Lordowl/synapse-data-platform

# === CORS ===
CORS_ORIGINS=["*"]
"""
        env_file.write_text(content)
        print(f"[INFO] Configurazione creata")
    
    # IMPORTANTE: Correggi HOST se è impostato su 0.0.0.0 (richiede permessi admin)
    if env_file.exists():
        content = env_file.read_text()
        if "HOST=0.0.0.0" in content:
            print(f"[INFO] Correzione HOST da 0.0.0.0 a 127.0.0.1 per evitare errori di permessi")
            content = content.replace("HOST=0.0.0.0", "HOST=127.0.0.1")
            env_file.write_text(content)

    # Carica IMMEDIATAMENTE il file .env
    load_dotenv(env_file, override=True)

    return env_file


# Rileva se siamo durante l'installazione
import traceback
stack = traceback.extract_stack()
is_during_setup = any('setup.py' in frame.filename or 'setuptools' in frame.filename for frame in stack)

# Solo se non siamo durante l'installazione
if not is_during_setup:
    ensure_config_exists()


def get_banks_from_config(banks_config):
    """
    Estrae l'array delle banche dalla configurazione, supportando sia il formato
    vecchio (array diretto) che il nuovo (oggetto con chiave 'banks').

    Args:
        banks_config: Configurazione caricata da banks_default.json (list o dict)

    Returns:
        list: Array delle banche, oppure [] se il formato non è riconosciuto
    """
    if isinstance(banks_config, list):
        # Formato vecchio: array diretto di banche
        return banks_config
    elif isinstance(banks_config, dict) and "banks" in banks_config:
        # Formato nuovo: oggetto con chiave 'banks'
        return banks_config["banks"]
    else:
        # Formato non riconosciuto
        logging.warning(f"Formato banks_default.json non riconosciuto: {type(banks_config)}")
        return []


def get_database_path_from_config() -> str:
    """
    Legge il settings_path dal file banks_default.json o config.json
    e restituisce il percorso del database in settings_path/App/Dashboard/sdp.db
    """
    import sys

    # Prova prima config.json (runtime), poi banks_default.json (default)
    config_dir = Path.home() / ".sdp-api"
    config_json = config_dir / "config.json"

    # Gestisci PyInstaller: quando buildato, i file sono in sys._MEIPASS
    if getattr(sys, 'frozen', False):
        # Eseguito come exe PyInstaller
        base_path = Path(sys._MEIPASS)
    else:
        # Eseguito come script Python normale
        base_path = Path(__file__).parent.parent

    banks_default = base_path / "config" / "banks_default.json"

    settings_path = None

    # Prova config.json
    if config_json.exists():
        try:
            with open(config_json, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                settings_path = config_data.get("settings_path")
        except Exception as e:
            logging.warning(f"Errore lettura config.json: {e}")

    # Se non trovato, prova banks_default.json
    if not settings_path and banks_default.exists():
        try:
            with open(banks_default, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                settings_path = config_data.get("settings_path")
        except Exception as e:
            logging.warning(f"Errore lettura banks_default.json: {e}")

    # Se trovato settings_path, costruisci il percorso del database
    if settings_path:
        db_path = Path(settings_path) / "App" / "Dashboard" / "sdp.db"
        return f"sqlite:///{db_path}"

    # Fallback: usa home directory
    fallback_path = Path.home() / ".sdp-api" / "sdp.db"
    return f"sqlite:///{fallback_path}"


class Settings(BaseSettings):
    # === SICUREZZA JWT ===
    SECRET_KEY: str = Field(default="temp-secret-key-will-be-replaced")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=11520)  # 8 giorni in minuti (8 * 24 * 60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=8)

    # === DATABASE ===
    DATABASE_URL: str = Field(default_factory=get_database_path_from_config)
    
    # === LOGGING ===
    LOG_LEVEL: str = Field(default="INFO")
    
    # === SERVER ===
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=9123)
    
    # === AGGIORNAMENTI ===
    auto_update_check: bool = Field(default=True)
    github_repo: str = Field(default="Lordowl/synapse-data-platform")
    
    # === CORS ===
    cors_origins: List[str] = Field(default=["*"])

    model_config = {
        # Punta al file .env nella directory di configurazione globale
        "env_file": str(Path.home() / ".sdp-api" / ".env"),
        "case_sensitive": True,
        "extra": "ignore"
    }


class ConfigManager:
    """Gestisce la configurazione dell'applicazione"""
    
    def __init__(self):
        self.config_dir = Path.home() / ".sdp-api"
        self.env_file = self.config_dir / ".env"
    
    def get_config_path(self) -> Path:
        """Restituisce il percorso del file di configurazione"""
        return self.env_file
    
    def regenerate_secret_key(self) -> str:
        """Rigenera la SECRET_KEY nel file di configurazione"""
        try:
            new_secret = secrets.token_urlsafe(32)
            
            if self.env_file.exists():
                # Leggi il contenuto esistente
                content = self.env_file.read_text()
                lines = content.split('\n')
                
                # Sostituisci la linea SECRET_KEY
                updated_lines = []
                secret_updated = False
                
                for line in lines:
                    if line.startswith('SECRET_KEY='):
                        updated_lines.append(f'SECRET_KEY={new_secret}')
                        secret_updated = True
                    else:
                        updated_lines.append(line)
                
                # Se SECRET_KEY non esisteva, aggiungila
                if not secret_updated:
                    updated_lines.insert(1, f'SECRET_KEY={new_secret}')
                
                # Scrivi il file aggiornato
                self.env_file.write_text('\n'.join(updated_lines))
                logging.info(f"SECRET_KEY rigenerata nel file {self.env_file}")
                return new_secret
            else:
                logging.error("File di configurazione non trovato")
                return None
                
        except Exception as e:
            logging.error(f"Errore nella rigenerazione della SECRET_KEY: {e}")
            return None
    
    def update_setting(self, key: str, value: str) -> bool:
        """Aggiorna una singola impostazione nel file di configurazione"""
        try:
            if not self.env_file.exists():
                logging.error("File di configurazione non trovato")
                return False
            
            content = self.env_file.read_text()
            lines = content.split('\n')
            updated_lines = []
            setting_updated = False
            
            for line in lines:
                if line.startswith(f'{key}='):
                    updated_lines.append(f'{key}={value}')
                    setting_updated = True
                else:
                    updated_lines.append(line)
            
            # Se l'impostazione non esisteva, aggiungila
            if not setting_updated:
                updated_lines.append(f'{key}={value}')
            
            self.env_file.write_text('\n'.join(updated_lines))
            logging.info(f"Impostazione {key} aggiornata")
            return True
            
        except Exception as e:
            logging.error(f"Errore nell'aggiornamento dell'impostazione {key}: {e}")
            return False

    def get_setting(self, key: str) -> str | None:
        """Legge il valore di una chiave dal file di configurazione .env"""
        try:
            if not self.env_file.exists():
                logging.error("File di configurazione non trovato")
                return None
            
            content = self.env_file.read_text().splitlines()
            for line in content:
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
            
            return None
        except Exception as e:
            logging.error(f"Errore nel recupero dell'impostazione {key}: {e}")
            return None

    def get_ini_contents(self) -> dict:
        """
        Legge tutti i file INI delle banche partendo dal folder impostato
        in SETTINGS_PATH e restituisce un dizionario simile a quello
        usato nel frontend (/folder/ini).
        """
        folder_path = self.get_setting("SETTINGS_PATH")
        if not folder_path:
            logging.warning("SETTINGS_PATH non configurato, impossibile leggere INI")
            return {}

        banks_file = Path(folder_path) / "App" / "Ingestion" / "banks_default.json"
        if not banks_file.exists():
            logging.warning(f"File banks_default.json non trovato: {banks_file}")
            return {}

        try:
            with open(banks_file, "r", encoding="utf-8") as f:
                banks_config = json.load(f)
                banks_data = get_banks_from_config(banks_config)
        except Exception as e:
            logging.error(f"Errore caricamento JSON banche: {e}")
            return {}

        ini_contents = {}
        for bank in banks_data:
            ini_path = Path(folder_path) / "App" / "Ingestion" / bank["ini_path"]
            if ini_path.exists():
                config = configparser.ConfigParser(allow_no_value=True)
                config.read(ini_path, encoding="utf-8")

                def expand_env_vars(d):
                    def expand_value(v):
                        if v is None:
                            return None
                        # Converti ${VAR} in %VAR% per Windows
                        v = re.sub(r'\$\{(\w+)\}', r'%\1%', v)
                        return os.path.expandvars(v)
                    return {k: expand_value(v) for k, v in d.items()}

                bank_ini = {"DEFAULT": expand_env_vars(config.defaults())}
                for section in config.sections():
                    bank_ini[section] = expand_env_vars(dict(config[section]))
                ini_contents[bank["label"]] = {"ini_path": str(ini_path), "data": bank_ini}
            else:
                ini_contents[bank["label"]] = {"ini_path": str(ini_path), "data": None}

        return ini_contents


# Creiamo le istanze che verranno importate
try:
    settings = Settings()
    config_manager = ConfigManager()
    
    # Se stiamo usando la chiave temporanea durante l'esecuzione normale, avvisa
    if not is_during_setup and settings.SECRET_KEY == "temp-secret-key-will-be-replaced":
        print("[WARNING] Usando SECRET_KEY temporanea - verifica la configurazione")
        
    # Configura il logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
except Exception as e:
    if not is_during_setup:
        print(f"[ERROR] Errore nel caricamento configurazione: {e}")
    # Fallback con configurazione minimale
    settings = Settings()
    config_manager = ConfigManager()
