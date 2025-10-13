# Configuration Files

Questa cartella contiene i file di configurazione di default per l'applicazione SDP-API.

## File Disponibili

### `banks_default.json`
Definisce le banche supportate e i relativi file di configurazione.

**Formato:**
```json
[
  {
    "label": "Sparkasse",
    "ini_path": "sparkasse.ini"
  },
  {
    "label": "CiviBank",
    "ini_path": "civibank.ini"
  }
]
```

### `repo_update_default.json`
Definisce lo stato iniziale della reportistica per ogni banca.

**Formato:**
```json
[
  {
    "settimana": 1,
    "anno": 2025,
    "semaforo": 0,
    "bank": "Sparkasse"
  },
  {
    "settimana": 1,
    "anno": 2025,
    "semaforo": 0,
    "bank": "CiviBank"
  }
]
```

**Campi:**
- `settimana`: Numero della settimana (1-52)
- `anno`: Anno corrente
- `semaforo`: Stato (0=verde, 1=giallo, 2=rosso)
- `bank`: Nome della banca (deve corrispondere a `label` in banks_default.json)

## Comportamento dell'Applicazione

Al primo avvio, l'applicazione:

1. **Cerca i file in questa cartella** (`config/`) all'interno del bundle PyInstaller
2. **Copia i file** in `~/.sdp-api/` se non esistono già
3. **Utilizza i file** da `~/.sdp-api/` per l'inizializzazione

### Modifica della Configurazione

Per modificare la configurazione:

1. **Prima del primo avvio**: Modifica i file in questa cartella prima di distribuire l'eseguibile
2. **Dopo il primo avvio**: Modifica i file in `~/.sdp-api/` (su Windows: `C:\Users\<username>\.sdp-api\`)

L'applicazione privilegia sempre i file in `~/.sdp-api/` rispetto a quelli nella cartella di installazione.

## Script di Gestione

Per gestire facilmente la configurazione repo_update_info, usa lo script:
```bash
python manage_repo_update_config.py
```

Questo script offre un menu interattivo per:
- Visualizzare la configurazione corrente
- Aggiungere/modificare banche
- Rimuovere banche
- Resettare ai valori di default
