# Come il cruscotto esegue FluentX

---

## Spiegazione semplice

Il cruscotto è un'applicazione web. Quando un utente preme un pulsante per avviare la pubblicazione dei dati, il cruscotto manda una richiesta al server.

Il server riceve la richiesta e avvia uno script Python in background — senza bloccare il resto dell'applicazione. Questo script apre un browser in modo automatico (invisibile all'utente) e simula le stesse azioni che farebbe un operatore manualmente: fa il login su Power BI, seleziona il workspace giusto, clicca "Aggiorna adesso" su ciascun modello, aspetta che finisca, e controlla se ci sono errori.

Le istruzioni su cosa cliccare e dove trovare i bottoni sono scritte in un file Excel (`.xlsm`). FluentX legge quel file e le esegue passo per passo. È come una "ricetta" di automazione browser.

Alla fine, il server risponde al cruscotto con il risultato: quali modelli sono stati aggiornati correttamente e quali hanno avuto errori.

---

## Spiegazione tecnica

### Stack

| Componente | Tecnologia |
|---|---|
| API server | FastAPI (Python) |
| Automazione browser | Selenium + FluentX (libreria interna) |
| File di configurazione flusso | `.xlsm` (Excel con macro) |
| Esecuzione asincrona | `asyncio` + thread pool executor |
| Notifiche real-time | WebSocket (`/ws/updates`) |

---

### Flusso di esecuzione

```
Frontend (cruscotto)
  │
  │  POST /api/v1/reportistica/publish-precheck
  ▼
reportistica.py  (FastAPI router)
  │
  │  asyncio.get_event_loop().run_in_executor(None, run_script)
  │  ↳ esecuzione in thread separato, non blocca il server
  ▼
scripts/main.py → main(workspace, pbi_packages)
  │
  │  1. load_workbook("Sparkasse.xlsm")       ← carica la "ricetta"
  │  2. run_flow(modules, flow_name, chains)  ← FluentX guida Selenium
  │     • Login
  │     • Cambia workspace
  │     • Filtro MS
  │     • Per ogni package:
  │         - Aggiorna MS  (click "Aggiorna adesso")
  │         - Attesa spinner / refresh / check errori
  │     • Aggiorna app
  │
  └─→ restituisce { package: stato, ... }
```

Per la periodicità **mensile**, prima di `scripts/main.py` viene eseguito `scripts/data_factory.py` (stesso schema, file `DataFactory.xlsm`, target Azure Data Factory).

---

### File chiave

| File | Ruolo |
|---|---|
| `sdp-api/api/reportistica.py` | Endpoint FastAPI, orchestrazione, WebSocket |
| `sdp-api/scripts/main.py` | Automazione Power BI (aggiornamento MS + app) |
| `sdp-api/scripts/data_factory.py` | Automazione Azure Data Factory |
| `sdp-api/scripts/utility.py` | Funzioni di supporto (path, download, parsing log) |
| `<SETTINGS_PATH>/App/Flows/Sparkasse.xlsm` | Flusso FluentX per Power BI |
| `<SETTINGS_PATH>/App/Flows/DataFactory.xlsm` | Flusso FluentX per Azure Data Factory |

---

### Come vengono scelti i package da aggiornare

I `pbi_packages` non sono hardcoded nello script: vengono letti dal database (`report_mapping` table) all'interno di `reportistica.py` e filtrati in base alla selezione dell'utente nel cruscotto, prima di essere passati a `scripts/main.py`.

---

### Come FluentX usa il file `.xlsm`

Il workbook Excel contiene un foglio per ogni "chain" (sequenza di azioni). Ogni riga è uno step: tipo di azione (click, attesa elemento, lettura testo…), XPath del target, e parametri aggiuntivi. Prima di eseguire una chain, il codice Python può modificare direttamente le celle del workbook per iniettare valori dinamici (es. nome del workspace, XPath del package corrente).

```python
workbook["Aggiorna MS"]["B3"].value = f'//span[@data-value="{package}"]'
run_flow(modules, flow_name, data_chains, workbook=workbook, actions=actions)
```

Questo permette di riutilizzare lo stesso flusso per tutti i package senza duplicare steps nel file Excel.
