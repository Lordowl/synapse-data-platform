import pytest
import json
from pathlib import Path
from datetime import datetime
from fastapi import status


@pytest.fixture
def flows_json_file(tmp_path):
    """Crea un file flows.json temporaneo per i test"""
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    flows_data = {
        "flows": [
            {"id": "flow1", "name": "Test Flow 1", "description": "First test flow"},
            {"id": "flow2", "name": "Test Flow 2", "description": "Second test flow"},
        ]
    }

    flows_file = data_dir / "flows.json"
    with open(flows_file, "w", encoding="utf-8") as f:
        json.dump(flows_data, f)

    yield flows_file

    # Cleanup
    if flows_file.exists():
        flows_file.unlink()


@pytest.fixture
def flow_execution_history(db_session, test_user):
    """Crea dati di storico esecuzione flow"""
    from db import models

    history_entries = []
    for i in range(3):
        entry = models.FlowExecutionHistory(
            flow_id_str=f"flow{i+1}",
            log_key=f"log_key_{i+1}",
            status="success" if i % 2 == 0 else "failed",
            timestamp=datetime.now(),
            bank=test_user.bank,
            anno=2024,
            settimana=10 + i,
            duration_seconds=60 + i * 10,
            details={"processed_records": 100 + i * 50}
        )
        db_session.add(entry)
        history_entries.append(entry)

    db_session.commit()
    for entry in history_entries:
        db_session.refresh(entry)

    return history_entries


@pytest.fixture
def flow_execution_details(db_session, test_user):
    """Crea dettagli esecuzione flow"""
    from db import models

    details_entries = []
    for i in range(3):
        detail = models.FlowExecutionDetail(
            element_id=f"element_{i+1}",
            log_key=f"log_key_{i+1}",
            result="OK" if i % 2 == 0 else "ERROR",
            timestamp=datetime.now(),
            bank=test_user.bank,
            anno=2024,
            settimana=10 + i,
            error_lines=None if i % 2 == 0 else "Error line 1\nError line 2"
        )
        db_session.add(detail)
        details_entries.append(detail)

    db_session.commit()
    for detail in details_entries:
        db_session.refresh(detail)

    return details_entries


class TestFlowsEndpoints:
    """Test per gli endpoint dei flows"""

    def test_get_all_flows_with_file(self, client, flows_json_file):
        """Test recupero tutti i flows quando il file esiste"""
        response = client.get("/api/v1/flows/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "flow1"
        assert data[1]["id"] == "flow2"

    def test_get_all_flows_without_file(self, client):
        """Test recupero flows quando il file non esiste"""
        # Assicurati che il file non esista
        flows_file = Path(__file__).parent.parent / "data" / "flows.json"
        if flows_file.exists():
            flows_file.unlink()

        response = client.get("/api/v1/flows/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "non trovato" in response.json()["detail"].lower()

    def test_get_flows_history_latest(self, authenticated_client, flow_execution_details):
        """Test recupero ultimo storico per ogni element_id"""
        response = authenticated_client.get("/api/v1/flows/historylatest")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)
        # Dovremmo avere un'entry per ogni element_id univoco
        assert len(data) >= 1

    def test_get_flows_history_latest_requires_auth(self, client):
        """Test che historylatest richieda autenticazione"""
        response = client.get("/api/v1/flows/historylatest")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_execution_history(self, authenticated_client, flow_execution_details):
        """Test recupero storico completo esecuzioni"""
        response = authenticated_client.get("/api/v1/flows/history")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        if len(data) > 0:
            assert "timestamp" in data[0]
            assert "result" in data[0]
            assert "element_id" in data[0]

    def test_get_execution_history_filtered_by_bank(
        self, authenticated_client, db_session, test_user, flow_execution_details
    ):
        """Test che lo storico sia filtrato per banca"""
        from db import models

        # Crea un detail per un'altra banca
        other_detail = models.FlowExecutionDetail(
            element_id="other_element",
            log_key="other_log",
            result="OK",
            timestamp=datetime.now(),
            bank="OtherBank",
            anno=2024,
            settimana=15
        )
        db_session.add(other_detail)
        db_session.commit()

        response = authenticated_client.get("/api/v1/flows/history")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verifica che non ci siano dati di altre banche
        for entry in data:
            assert entry["element_id"] != "other_element"

    def test_get_execution_logs(self, authenticated_client, flow_execution_history):
        """Test recupero log di esecuzione"""
        response = authenticated_client.get("/api/v1/flows/logs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        if len(data) > 0:
            assert "id" in data[0]
            assert "timestamp" in data[0]
            assert "element_id" in data[0]
            assert "status" in data[0]

    def test_get_execution_logs_with_limit(self, authenticated_client, flow_execution_history):
        """Test recupero log con limite"""
        response = authenticated_client.get("/api/v1/flows/logs?limit=1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) <= 1

    def test_get_execution_logs_requires_auth(self, client):
        """Test che logs richieda autenticazione"""
        response = client.get("/api/v1/flows/logs")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_execution_logs(self, authenticated_client, flow_execution_history):
        """Test ricerca log con filtri"""
        search_params = {
            "flow_id": "flow1",
            "limit": 10
        }

        response = authenticated_client.post(
            "/api/v1/flows/logs/search",
            json=search_params
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_search_execution_logs_by_status(self, authenticated_client, flow_execution_history):
        """Test ricerca log per status"""
        search_params = {
            "status": "success",
            "limit": 10
        }

        response = authenticated_client.post(
            "/api/v1/flows/logs/search",
            json=search_params
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Tutti i risultati dovrebbero avere status success
        for entry in data:
            assert entry["status"] == "success"

    def test_get_debug_counts(self, authenticated_client, flow_execution_history, flow_execution_details):
        """Test endpoint di debug per conteggi"""
        response = authenticated_client.get("/api/v1/flows/debug/counts")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "bank" in data
        assert "history_count" in data
        assert "detail_count" in data
        assert "sample_history" in data
        assert "sample_details" in data
        assert isinstance(data["history_count"], int)
        assert isinstance(data["detail_count"], int)

    def test_get_debug_counts_requires_auth(self, client):
        """Test che debug counts richieda autenticazione"""
        response = client.get("/api/v1/flows/debug/counts")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdminFlowsEndpoints:
    """Test per gli endpoint admin dei flows"""

    @pytest.fixture
    def admin_user(self, db_session, test_bank):
        """Crea un utente admin di test"""
        from db import models
        from core import security

        hashed_password = security.get_password_hash("adminpassword123")
        admin = models.User(
            username="flowadmin",
            hashed_password=hashed_password,
            bank=test_bank.label,
            role="admin"
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
        return admin

    @pytest.fixture
    def admin_token(self, admin_user):
        """Genera token per admin"""
        from datetime import timedelta
        from core import security

        access_token = security.create_access_token(
            data={"sub": admin_user.username, "bank": admin_user.bank},
            expires_delta=timedelta(minutes=30)
        )
        return access_token

    @pytest.fixture
    def authenticated_admin_client(self, client, admin_token):
        """Client autenticato come admin"""
        client.headers = {
            **client.headers,
            "Authorization": f"Bearer {admin_token}"
        }
        return client

    def test_clear_execution_logs_as_admin(
        self, authenticated_admin_client, flow_execution_history, db_session
    ):
        """Test cancellazione log come admin"""
        from db import models

        # Verifica che ci siano log prima della cancellazione
        count_before = db_session.query(models.FlowExecutionHistory).count()
        assert count_before > 0

        response = authenticated_admin_client.delete("/api/v1/flows/logs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "deleted_count" in data
        assert data["deleted_count"] == count_before

        # Verifica che i log siano stati cancellati
        count_after = db_session.query(models.FlowExecutionHistory).count()
        assert count_after == 0

    def test_clear_execution_logs_as_regular_user(self, authenticated_client):
        """Test che utente normale non possa cancellare log"""
        response = authenticated_client.delete("/api/v1/flows/logs")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_clear_execution_logs_requires_auth(self, client):
        """Test che cancellazione log richieda autenticazione"""
        response = client.delete("/api/v1/flows/logs")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
