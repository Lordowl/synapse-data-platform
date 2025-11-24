# Test Suite - Synapse Data Platform API

Suite di test completa per l'API Synapse Data Platform utilizzando pytest.

## Struttura Test

```
tests/
├── conftest.py              # Fixtures comuni e configurazione
├── test_auth.py            # Test autenticazione e token
├── test_users.py           # Test gestione utenti
├── test_banks.py           # Test gestione banche
├── test_flows.py           # Test flussi di lavoro
├── test_reportistica.py    # Test reportistica
└── README.md               # Questo file
```

## Installazione Dipendenze

Prima di eseguire i test, installare le dipendenze di testing:

```bash
# Dalla directory sdp-api/
pip install -r requirements.txt
```

Le dipendenze di testing includono:
- pytest (framework di testing)
- pytest-asyncio (supporto test asincroni)
- pytest-cov (code coverage)
- httpx (client HTTP per test API)

## Eseguire i Test

### Eseguire tutti i test

```bash
# Dalla directory sdp-api/
pytest
```

### Eseguire test specifici

```bash
# Test di un singolo file
pytest tests/test_auth.py

# Test di una singola classe
pytest tests/test_users.py::TestAdminUserEndpoints

# Test di una singola funzione
pytest tests/test_auth.py::TestAuthenticationEndpoints::test_login_success

# Test che matchano un pattern
pytest -k "login"
```

### Opzioni Utili

```bash
# Verbose output (più dettagli)
pytest -v

# Mostra print statements
pytest -s

# Stop al primo fallimento
pytest -x

# Esegui solo gli ultimi test falliti
pytest --lf

# Esegui test in parallelo (richiede pytest-xdist)
pytest -n auto

# Genera report HTML di coverage
pytest --cov=. --cov-report=html

# Mostra i 10 test più lenti
pytest --durations=10
```

## Markers

I test sono organizzati con markers per categorizzazione:

```bash
# Test di autenticazione
pytest -m auth

# Test unitari
pytest -m unit

# Test di integrazione
pytest -m integration

# Test API
pytest -m api

# Test database
pytest -m database
```

Per vedere tutti i markers disponibili:
```bash
pytest --markers
```

## Coverage

Per generare un report di code coverage:

```bash
# Report in terminale
pytest --cov=. --cov-report=term-missing

# Report HTML (visualizza in browser)
pytest --cov=. --cov-report=html
# Apri htmlcov/index.html nel browser
```

## Struttura Fixtures

Le fixtures principali sono definite in `conftest.py`:

- `db_session`: Database SQLite in memoria per ogni test
- `client`: Client TestClient FastAPI
- `test_bank`: Banca di test
- `test_user`: Utente normale di test
- `test_user_token`: Token JWT per utente normale
- `authenticated_client`: Client con autenticazione
- `test_flow`: Flow di test
- `sample_log_entry`: Log di esempio

## Best Practices

### 1. Isolamento dei Test
Ogni test utilizza un database in memoria pulito grazie alla fixture `db_session` con scope "function".

### 2. Naming Convention
- File: `test_*.py`
- Classi: `Test*`
- Funzioni: `test_*`

### 3. Organizzazione
I test sono organizzati in classi per raggruppare test correlati:
```python
class TestAuthenticationEndpoints:
    def test_login_success(self, client, test_user):
        # Test login
        pass
```

### 4. Asserzioni Chiare
```python
# Buono
assert response.status_code == status.HTTP_200_OK
assert "access_token" in data

# Evitare
assert response.status_code == 200
assert data.get("access_token") is not None
```

## Debugging Test

### Eseguire un test con debugger

```bash
# Con pdb
pytest --pdb tests/test_auth.py

# Con pdb su fallimento
pytest --pdb --pdbcls=IPython.terminal.debugger:Pdb
```

### Vedere output completo

```bash
# Mostra tutti i print statements e log
pytest -s -v tests/test_auth.py

# Mostra variabili locali su fallimento
pytest -l tests/test_auth.py
```

## CI/CD Integration

Per integrare i test in CI/CD pipeline:

```yaml
# Esempio GitHub Actions
- name: Run tests
  run: |
    cd sdp-api
    pip install -r requirements.txt
    pytest --cov=. --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### Problema: Import errors
```bash
# Soluzione: Assicurati di essere nella directory corretta
cd sdp-api
pytest
```

### Problema: Database locked
```bash
# Soluzione: I test usano SQLite in memoria, ma se hai problemi
# verifica che non ci siano connessioni attive al database reale
```

### Problema: Test lenti
```bash
# Soluzione: Esegui in parallelo
pip install pytest-xdist
pytest -n auto
```

### Problema: Test intermittenti
I test utilizzano database in memoria isolati, ma se hai test che falliscono
in modo intermittente, verifica:
- Dipendenze tra test (dovrebbero essere indipendenti)
- Stato globale condiviso
- Race conditions in test asincroni

## Aggiungere Nuovi Test

### Template per nuovo test file

```python
import pytest
from fastapi import status


class TestNewFeature:
    """Test per la nuova feature"""

    def test_basic_functionality(self, authenticated_client):
        """Test funzionalità base"""
        response = authenticated_client.get("/api/v1/new-endpoint")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "expected_field" in data
```

### Template per fixture personalizzata

```python
# In conftest.py o nel file di test
@pytest.fixture
def custom_fixture(db_session, test_user):
    """Crea dati custom per i test"""
    # Setup
    data = create_test_data()

    yield data

    # Teardown (opzionale)
    cleanup_test_data()
```

## Risorse

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/14/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)

## Contatti

Per problemi o domande sui test, contattare il team di sviluppo.
