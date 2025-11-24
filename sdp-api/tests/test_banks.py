import pytest
from fastapi import status


class TestBanksEndpoints:
    """Test per gli endpoint delle banche"""

    def test_get_available_banks_with_data(self, client, test_bank):
        """Test recupero banche disponibili quando ci sono banche"""
        response = client.get("/api/v1/banks/available")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "banks" in data
        assert "current_bank" in data
        assert isinstance(data["banks"], list)
        assert len(data["banks"]) > 0
        assert data["current_bank"] == "TestBank"

    def test_get_available_banks_empty_database(self, client, db_session):
        """Test recupero banche con database vuoto"""
        # Rimuovi tutte le banche
        from db import models
        db_session.query(models.Bank).delete()
        db_session.commit()

        response = client.get("/api/v1/banks/available")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["banks"] == []
        assert data["current_bank"] is None

    def test_get_available_banks_is_public(self, client, test_bank):
        """Test che l'endpoint /banks/available sia pubblico (no auth)"""
        # Non dovrebbe richiedere autenticazione
        response = client.get("/api/v1/banks/available")

        assert response.status_code == status.HTTP_200_OK

    def test_add_new_bank(self, authenticated_client):
        """Test aggiunta nuova banca"""
        new_bank_data = {
            "label": "NewBank",
            "ini_path": "path/to/newbank.ini"
        }

        response = authenticated_client.post(
            "/api/v1/banks/add",
            json=new_bank_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["label"] == "NewBank"
        assert data["ini_path"] == "path/to/newbank.ini"

    def test_add_bank_requires_authentication(self, client):
        """Test che l'aggiunta di banche richieda autenticazione"""
        new_bank_data = {
            "label": "NewBank",
            "ini_path": "path/to/newbank.ini"
        }

        response = client.post(
            "/api/v1/banks/add",
            json=new_bank_data
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_current_bank(self, authenticated_client, db_session):
        """Test aggiornamento banca corrente"""
        from db import models

        # Crea una seconda banca
        bank2 = models.Bank(
            label="SecondBank",
            ini_path="path/to/second.ini",
            is_current=False
        )
        db_session.add(bank2)
        db_session.commit()

        update_data = {"label": "SecondBank"}

        response = authenticated_client.post(
            "/api/v1/banks/update",
            json=update_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "SecondBank" in data["message"]

    def test_update_to_nonexistent_bank(self, authenticated_client):
        """Test aggiornamento a banca inesistente"""
        update_data = {"label": "NonExistentBank"}

        response = authenticated_client.post(
            "/api/v1/banks/update",
            json=update_data
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "non trovata" in response.json()["detail"].lower()

    def test_update_bank_requires_authentication(self, client, test_bank):
        """Test che l'aggiornamento banca richieda autenticazione"""
        update_data = {"label": test_bank.label}

        response = client.post(
            "/api/v1/banks/update",
            json=update_data
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_multiple_banks_only_one_current(self, authenticated_client, db_session, test_bank):
        """Test che solo una banca possa essere corrente alla volta"""
        from db import models

        # Crea seconda banca
        bank2 = models.Bank(
            label="SecondBank",
            ini_path="path/to/second.ini",
            is_current=False
        )
        db_session.add(bank2)
        db_session.commit()

        # Imposta SecondBank come corrente
        update_data = {"label": "SecondBank"}
        response = authenticated_client.post(
            "/api/v1/banks/update",
            json=update_data
        )

        assert response.status_code == status.HTTP_200_OK

        # Verifica che solo SecondBank sia is_current
        response = authenticated_client.get("/api/v1/banks/available")
        data = response.json()
        assert data["current_bank"] == "SecondBank"

        # Verifica nel database
        banks = db_session.query(models.Bank).all()
        current_banks = [b for b in banks if b.is_current]
        assert len(current_banks) == 1
        assert current_banks[0].label == "SecondBank"

    def test_bank_label_format(self, authenticated_client):
        """Test formato dati banca"""
        new_bank_data = {
            "label": "TestBankFormat",
            "ini_path": "test/format/bank.ini"
        }

        response = authenticated_client.post(
            "/api/v1/banks/add",
            json=new_bank_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert "label" in data
        assert "ini_path" in data
        assert isinstance(data["id"], int)
        assert isinstance(data["label"], str)
        assert isinstance(data["ini_path"], str)
