import os
import secrets
import logging
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field,validator
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
ACCESS_TOKEN_EXPIRE_MINUTES=30

# === DATABASE ===
DATABASE_URL=sqlite:///./sdp.db

# === LOGGING ===
LOG_LEVEL=INFO

# === SERVER ===
HOST=127.0.0.1
PORT=8000

# === AGGIORNAMENTI ===
AUTO_UPDATE_CHECK=true
GITHUB_REPO=Lordowl/synapse-data-platform

# === CORS ===
CORS_ORIGINS=["*"]
"""
        env_file.write_text(content)
        print(f"[INFO] Configurazione creata")
    
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

class Settings(BaseSettings):
    # === SICUREZZA JWT ===
    SECRET_KEY: str = Field(default="temp-secret-key-will-be-replaced")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    
    # === DATABASE ===
    DATABASE_URL: str = Field(default="sqlite:///./sdp.db")
    
    # === LOGGING ===
    LOG_LEVEL: str = Field(default="INFO")
    
    # === SERVER ===
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
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