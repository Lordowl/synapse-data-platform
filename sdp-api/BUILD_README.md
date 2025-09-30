# Synapse Data Platform API - Build Instructions

Questa guida spiega come creare un eseguibile standalone del backend SDP-API.

## 📋 Prerequisiti

- **Python 3.11+** installato sul sistema
- **Windows** (il script è ottimizzato per Windows, ma puoi adattarlo per Linux/macOS)

## 🚀 Build Rapida

### Metodo 1: Script Automatico (Consigliato)

1. Apri un terminale nella cartella `sdp-api`:
   ```bash
   cd C:\Users\EmanueleDeFeo\Documents\Projects\Synapse-Data-Platform\sdp-api
   ```

2. Esegui lo script di build:
   ```bash
   build.bat
   ```

3. L'eseguibile sarà creato in `dist\sdp-api.exe`

### Metodo 2: Build Manuale

Se preferisci avere più controllo:

1. **Crea virtual environment** (opzionale ma consigliato):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. **Installa dipendenze**:
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

3. **Build con PyInstaller**:
   ```bash
   pyinstaller sdp-api.spec
   ```

## 📦 Struttura dei File Generati

```
sdp-api/
├── build/          # File temporanei (puoi eliminare)
├── dist/           # Contiene l'eseguibile finale
│   └── sdp-api.exe # ← Eseguibile standalone
└── sdp-api.spec    # Configurazione PyInstaller
```

## ▶️ Esecuzione dell'Eseguibile

### Esecuzione Base
```bash
cd dist
sdp-api.exe
```

L'API sarà disponibile su `http://localhost:8000`

### Opzioni Avanzate
```bash
# Specifica host e porta
sdp-api.exe --host 0.0.0.0 --port 8080

# Modalità reload (per sviluppo)
sdp-api.exe --reload

# Mostra configurazione
sdp-api.exe --config

# Rigenera SECRET_KEY
sdp-api.exe --regenerate-secret

# Disabilita controllo aggiornamenti
sdp-api.exe --no-update-check
```

## ⚙️ Configurazione

L'eseguibile cerca il file di configurazione in:
- **Windows**: `C:\Users\<username>\.sdp-api\.env`
- **Linux/macOS**: `~/.sdp-api/.env`

### Esempio `.env`:
```env
# Sicurezza JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database
DATABASE_URL=sqlite:///./sdp.db

# Server
HOST=0.0.0.0
PORT=8000

# Aggiornamenti
AUTO_UPDATE_CHECK=true
GITHUB_REPO=Lordowl/synapse-data-platform
```

## 🐛 Troubleshooting

### Errore: "Python non trovato"
- Verifica che Python sia installato: `python --version`
- Aggiungi Python al PATH di sistema

### Errore: "Modulo 'X' non trovato"
- Aggiungi il modulo a `hiddenimports` in `sdp-api.spec`
- Esempio: `'nome_modulo',`

### Eseguibile troppo grande
- Rimuovi dipendenze non necessarie da `requirements.txt`
- Usa `--exclude-module` in PyInstaller
- Considera di usare `--onedir` invece di `--onefile` (più veloce)

### Errore all'avvio dell'eseguibile
- Esegui in modalità debug: `sdp-api.exe --debug`
- Controlla i log in `~/.sdp-api/logs/`

## 📝 Note Importanti

### File Esterni
L'eseguibile **NON include**:
- ❌ Database SQLite (devi distribuirlo separatamente)
- ❌ File di configurazione `.env`
- ❌ File INI delle banche
- ❌ File di log

Questi devono essere presenti nella cartella di esecuzione o nei percorsi configurati.

### Dipendenze di Sistema
Su Windows, l'eseguibile richiede:
- **Microsoft Visual C++ Redistributable** (solitamente già installato)

### Dimensione Eseguibile
- **Dimensione tipica**: ~80-120 MB
- Include Python runtime completo e tutte le dipendenze

## 🔧 Personalizzazione Build

### Modificare l'icona
Edita `sdp-api.spec`:
```python
exe = EXE(
    ...
    icon='path/to/icon.ico',  # Aggiungi questa riga
)
```

### Escludere moduli
Edita `sdp-api.spec`:
```python
a = Analysis(
    ...
    excludes=['tkinter', 'matplotlib'],  # Moduli da escludere
)
```

### Build per directory (più veloce)
Cambia in `sdp-api.spec`:
```python
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,  # Cambia a True
    ...
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='sdp-api',
)
```

## 📤 Distribuzione

Per distribuire l'applicazione:

1. **Copia** la cartella `dist/` (o solo `sdp-api.exe`)
2. **Includi**:
   - File `.env` di esempio (senza dati sensibili)
   - Documentazione
   - Script di setup iniziale

3. **Istruzioni per l'utente**:
   ```
   1. Estrai i file in una cartella
   2. Configura il file .env
   3. Esegui sdp-api.exe
   4. Apri browser su http://localhost:8000/docs
   ```

## 🔄 Alternative a PyInstaller

### cx_Freeze
```bash
pip install cx_Freeze
python setup.py build
```

### Nuitka (più veloce)
```bash
pip install nuitka
python -m nuitka --standalone --onefile main.py
```

### Docker (consigliato per produzione)
```bash
docker build -t sdp-api .
docker run -p 8000:8000 sdp-api
```

## 📞 Supporto

Per problemi o domande:
- GitHub Issues: https://github.com/Lordowl/synapse-data-platform/issues
- Documentazione: https://github.com/Lordowl/synapse-data-platform/wiki

---

**Ultima modifica**: 2025-09-30
**Versione**: 0.1.0