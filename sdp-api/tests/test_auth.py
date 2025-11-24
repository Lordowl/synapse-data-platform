import pytest
from fastapi import status


class TestAuthenticationEndpoints:
    """Test per gli endpoint di autenticazione"""

    def test_login_success(self, client, test_user, test_bank):
        """Test login con credenziali corrette"""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "testuser",
                "password": "testpassword123",
                "bank": "TestBank"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    def test_login_wrong_password(self, client, test_user, test_bank):
        """Test login con password errata"""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "testuser",
                "password": "wrongpassword",
                "bank": "TestBank"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect username, password, or bank" in response.json()["detail"]

    def test_login_wrong_username(self, client, test_bank):
        """Test login con username inesistente"""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "nonexistent",
                "password": "testpassword123",
                "bank": "TestBank"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_wrong_bank(self, client, test_user, test_bank):
        """Test login con banca errata"""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "testuser",
                "password": "testpassword123",
                "bank": "WrongBank"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_missing_bank(self, client, test_user):
        """Test login senza specificare la banca"""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "testuser",
                "password": "testpassword123",
                "bank": ""
            }
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Bank must be specified" in response.json()["detail"]

    def test_login_missing_username(self, client, test_bank):
        """Test login senza username"""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "password": "testpassword123",
                "bank": "TestBank"
            }
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_missing_password(self, client, test_bank):
        """Test login senza password"""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "testuser",
                "bank": "TestBank"
            }
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_token_format(self, client, test_user, test_bank):
        """Test che il token sia nel formato corretto"""
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "testuser",
                "password": "testpassword123",
                "bank": "TestBank"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        token = response.json()["access_token"]

        # JWT ha 3 parti separate da punti
        parts = token.split(".")
        assert len(parts) == 3
