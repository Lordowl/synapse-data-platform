# Struttura Test Suite

Organizzazione completa della suite di test per SDP API.

## Struttura Directory

```
sdp-api/
├── tests/
│   ├── __init__.py                 # Marker package Python
│   ├── conftest.py                 # Fixtures comuni e configurazione
│   ├── README.md                   # Guida utente completa
│   ├── TEST_STRUCTURE.md           # Questo file
│   ├── test_auth.py                # Test autenticazione (8 test)
│   ├── test_users.py               # Test gestione utenti (17 test)
│   ├── test_banks.py               # Test gestione banche (10 test)
│   ├── test_flows.py               # Test flussi lavoro (16 test)
│   └── test_reportistica.py        # Test reportistica (16 test)
├── pytest.ini                      # Configurazione pytest
├── run_tests.bat                   # Script Windows per eseguire test
├── run_tests.sh                    # Script Unix/Linux/Mac per eseguire test
├── TESTING_SUMMARY.md              # Riepilogo stato test
└── requirements.txt                # Dipendenze (incluse pytest, httpx, etc.)
```

## File Principali

### conftest.py
File centrale che contiene tutte le fixtures condivise:

- **Database Fixtures**
  - `db_session`: Database SQLite in memoria per ogni test
  - `client`: TestClient FastAPI

- **Auth Fixtures**
  - `test_bank`: Banca di test
  - `test_user`: Utente normale di test
  - `test_user_token`: Token JWT per utente
  - `authenticated_client`: Client con autenticazione

- **Data Fixtures**
  - `test_flow`: Flow di test
  - `sample_log_entry`: Log di esempio

### test_auth.py
Test per endpoint di autenticazione:

**Classe: TestAuthenticationEndpoints (8 test)**
- Login con successo
- Login con credenziali errate (password, username, bank)
- Validazione campi obbligatori
- Formato token JWT

**Coverage: 100%** ✅

### test_users.py
Test per gestione utenti:

**Classe: TestUserEndpoints (3 test)**
- Recupero utente corrente
- Test autenticazione e autorizzazione

**Classe: TestAdminUserEndpoints (14 test)**
- CRUD completo utenti
- Gestione permessi admin
- Cambio password
- Validazione constraints

**Coverage: 100%** ✅

### test_banks.py
Test per gestione banche:

**Classe: TestBanksEndpoints (10 test)**
- Recupero lista banche
- Aggiunta nuove banche
- Cambio banca corrente
- Validazione accessi pubblici vs autenticati

**Coverage: 60%** ⚠️ (alcuni test necessitano aggiustamenti)

### test_flows.py
Test per flussi di lavoro:

**Classe: TestFlowsEndpoints (13 test)**
- Recupero flows da JSON
- Storico esecuzioni
- Dettagli esecuzioni
- Ricerca e filtri
- Debug endpoints

**Classe: TestAdminFlowsEndpoints (3 test)**
- Cancellazione log (solo admin)
- Controllo permessi

**Coverage: 100%** ✅

### test_reportistica.py
Test per reportistica:

**Classe: TestReportisticaEndpoints (10 test)**
- Recupero items reportistica
- Filtri (anno, settimana, package)
- Paginazione (skip, limit)
- Isolamento per banca

**Classe: TestReportisticaPackageEndpoints (1 test)**
- Struttura dati package

**Classe: TestReportisticaWebSocketEndpoints (1 test)**
- Esistenza endpoint WebSocket

**Classe: TestReportisticaErrorHandling (4 test)**
- Gestione errori e validazione input

**Coverage: 40%** ⚠️ (alcuni test necessitano fix modello database)

## Fixtures Avanzate

### Database in Memoria
Ogni test ottiene un database SQLite pulito in memoria:

```python
@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)
```

### Client Autenticato
Pattern riutilizzabile per test che richiedono autenticazione:

```python
@pytest.fixture
def authenticated_client(client, test_user_token):
    client.headers = {
        "Authorization": f"Bearer {test_user_token}"
    }
    return client
```

## Pattern di Test Comuni

### 1. Test Endpoint Base
```python
def test_endpoint_success(self, authenticated_client):
    response = authenticated_client.get("/api/v1/endpoint")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "expected_field" in data
```

### 2. Test Autenticazione
```python
def test_requires_auth(self, client):
    response = client.get("/api/v1/protected-endpoint")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

### 3. Test Validazione
```python
def test_validation_error(self, authenticated_client):
    invalid_data = {"field": "invalid_value"}
    response = authenticated_client.post("/api/v1/endpoint", json=invalid_data)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
```

### 4. Test Isolamento Database
```python
def test_filtered_by_bank(self, authenticated_client, test_user):
    # Crea dati per altra banca
    other_bank_data = create_data_for_other_bank()

    # Verifica isolamento
    response = authenticated_client.get("/api/v1/data")
    data = response.json()

    for item in data:
        assert item["bank"] == test_user.bank
```

## Esecuzione Test

### Quick Start
```bash
# Windows
cd sdp-api
run_tests.bat

# Linux/Mac
cd sdp-api
./run_tests.sh
```

### Comandi Utili
```bash
# Test specifico modulo
run_tests.bat auth
run_tests.bat users

# Con coverage
run_tests.bat coverage

# Stop al primo errore
run_tests.bat fast

# Test specifico
pytest tests/test_auth.py::TestAuthenticationEndpoints::test_login_success -v
```

## Metriche Qualità

### Coverage Obiettivi
- **Core Business Logic**: > 90%
- **API Endpoints**: > 80%
- **Error Handlers**: > 70%

### Test Performance
- **Tempo massimo singolo test**: < 2s
- **Tempo suite completa**: < 30s
- **Database setup**: < 100ms per test

## Best Practices Implementate

✅ **Isolamento**: Ogni test è completamente indipendente
✅ **Velocità**: Database in memoria per performance ottimali
✅ **Riusabilità**: Fixtures condivise in conftest.py
✅ **Chiarezza**: Test naming descrittivo e docstrings
✅ **Manutenibilità**: Una classe per gruppo logico di test
✅ **Coverage**: Focus su happy path e edge cases
✅ **CI/CD Ready**: Output compatibile con pipeline

## Estensione Suite

### Aggiungere Nuovo Test File

1. Creare file `tests/test_nuovo.py`
2. Importare fixtures necessarie
3. Seguire naming convention
4. Aggiungere documentazione

Esempio:
```python
import pytest
from fastapi import status


class TestNuovoModulo:
    """Test per nuovo modulo"""

    def test_basic_functionality(self, authenticated_client):
        """Test funzionalità base"""
        response = authenticated_client.get("/api/v1/nuovo")
        assert response.status_code == status.HTTP_200_OK
```

### Aggiungere Nuova Fixture

In `conftest.py`:
```python
@pytest.fixture
def custom_data(db_session):
    """Crea dati custom per test"""
    data = CustomModel(field="value")
    db_session.add(data)
    db_session.commit()
    db_session.refresh(data)
    return data
```

## Troubleshooting

### Test Fallisce Sporadicamente
- Verificare indipendenza da altri test
- Controllare stato condiviso
- Verificare pulizia database

### Test Troppo Lento
- Verificare query N+1
- Ottimizzare fixture setup
- Considerare mock per servizi esterni

### Import Errors
- Verificare `PYTHONPATH`
- Controllare struttura package
- Verificare dipendenze installate

## Risorse

- **pytest**: https://docs.pytest.org/
- **FastAPI Testing**: https://fastapi.tiangolo.com/tutorial/testing/
- **httpx**: https://www.python-httpx.org/

## Contribuire

Quando si aggiungono nuove feature:

1. ✅ Scrivere test PRIMA del codice (TDD)
2. ✅ Mantenere coverage > 80%
3. ✅ Seguire pattern esistenti
4. ✅ Aggiornare documentazione
5. ✅ Verificare che tutti i test passino

---

**Versione**: 1.0
**Data**: November 2025
**Autore**: Claude Code
