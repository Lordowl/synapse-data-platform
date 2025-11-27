from setuptools import setup, find_packages
from setuptools.command.install import install
import os
import secrets
from pathlib import Path

class PostInstallCommand(install):
    """Comando personalizzato per post-installazione"""
    def run(self):
        install.run(self)
        self.create_config_files()
    
    def create_config_files(self):
        # Directory di configurazione nella home dell'utente
        config_dir = Path.home() / ".sdp-api"
        config_dir.mkdir(exist_ok=True)
        
        # Crea file .env se non esiste
        env_file = config_dir / ".env"
        if not env_file.exists():
            # Genera SECRET_KEY sicura automaticamente
            secret_key = secrets.token_urlsafe(32)
            
            env_content = f"""# Synapse Data Platform API - Configurazione
# Generata automaticamente durante l'installazione

# Sicurezza JWT
SECRET_KEY={secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=11520
REFRESH_TOKEN_EXPIRE_DAYS=8

# Database (opzionale - modifica se necessario)
DATABASE_URL=sqlite:///./sdp.db

# Logging
LOG_LEVEL=INFO

# Server
HOST=127.0.0.1
PORT=9123

# Aggiornamenti
AUTO_UPDATE_CHECK=true
GITHUB_REPO=Lordowl/synapse-data-platform

# CORS
CORS_ORIGINS=["*"]
"""
            env_file.write_text(env_content)
            print(f"[OK] File di configurazione creato in: {env_file}")
            print("[INFO] Puoi modificare le impostazioni editando il file sopra")
        else:
            print(f"[INFO] Configurazione esistente trovata in: {env_file}")

setup(
    name='sdp-api',
    version='0.2.29',
    packages=find_packages(),
    py_modules=['main'],  # Includi i moduli necessari
    include_package_data=True,
    install_requires=[
        'fastapi>=0.100.0',
        'uvicorn[standard]>=0.20.0',
        'sqlalchemy>=2.0.0',
        'pydantic>=2.0.0',
        'pydantic[email]>=2.0.0',
        'pydantic-settings>=2.0.0',
        'python-jose[cryptography]>=3.3.0',
        'passlib[bcrypt]>=1.7.4',
        'python-multipart>=0.0.6',
        'bcrypt== 3.2.2',
        'requests>=2.31.0',
        'python-dotenv>=1.0.0',
        'pandas',
        'openpyxl',

    ],
    cmdclass={
        'install': PostInstallCommand,
    },
    entry_points={
        'console_scripts': [
            'sdp-api=main:main',
        ],
    },
    python_requires='>=3.11.8',
    author='Your Name',
    author_email='your.email@example.com',
    description='Synapse Data Platform API',
    long_description='API per la Synapse Data Platform.',
    url='https://github.com/Lordowl/synapse-data-platform',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)