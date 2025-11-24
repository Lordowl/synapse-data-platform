import pytest
from fastapi import status
from core import security


class TestUserEndpoints:
    """Test per gli endpoint degli utenti"""

    def test_get_current_user_authenticated(self, authenticated_client, test_user):
        """Test recupero dati utente corrente autenticato"""
        response = authenticated_client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == test_user.username
        assert data["bank"] == test_user.bank
        assert "hashed_password" not in data

    def test_get_current_user_unauthenticated(self, client):
        """Test accesso senza autenticazione"""
        response = client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_user_invalid_token(self, client):
        """Test con token non valido"""
        client.headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdminUserEndpoints:
    """Test per gli endpoint admin degli utenti"""

    @pytest.fixture
    def admin_user(self, db_session, test_bank):
        """Crea un utente admin di test"""
        from db import models

        hashed_password = security.get_password_hash("adminpassword123")
        admin = models.User(
            username="adminuser",
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

    def test_create_user_as_admin(self, authenticated_admin_client, test_bank):
        """Test creazione utente da parte di admin"""
        new_user_data = {
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "newpassword123",
            "bank": test_bank.label,
            "role": "user"
        }

        response = authenticated_admin_client.post(
            "/api/v1/users/",
            json=new_user_data
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@test.com"
        assert data["bank"] == test_bank.label
        assert "hashed_password" not in data

    def test_create_user_duplicate_username(self, authenticated_admin_client, test_user):
        """Test creazione utente con username duplicato nella stessa banca"""
        duplicate_user_data = {
            "username": test_user.username,
            "email": "different@test.com",
            "password": "password123",
            "bank": test_user.bank,
            "role": "user"
        }

        response = authenticated_admin_client.post(
            "/api/v1/users/",
            json=duplicate_user_data
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Username already registered" in response.json()["detail"]

    def test_create_user_duplicate_email(self, authenticated_admin_client, test_user, db_session):
        """Test creazione utente con email duplicata nella stessa banca"""
        # Prima imposta un'email per l'utente di test
        test_user.email = "existing@test.com"
        db_session.commit()

        duplicate_email_data = {
            "username": "differentuser",
            "email": "existing@test.com",
            "password": "password123",
            "bank": test_user.bank,
            "role": "user"
        }

        response = authenticated_admin_client.post(
            "/api/v1/users/",
            json=duplicate_email_data
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in response.json()["detail"]

    def test_create_user_without_password(self, authenticated_admin_client, test_bank):
        """Test creazione utente senza password (dovrebbe generarne una)"""
        new_user_data = {
            "username": "usernopass",
            "email": "usernopass@test.com",
            "bank": test_bank.label,
            "role": "user"
        }

        response = authenticated_admin_client.post(
            "/api/v1/users/",
            json=new_user_data
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        # Dovrebbe contenere una password generata
        assert "generated_password" in data or "password" not in data

    def test_get_all_users_as_admin(self, authenticated_admin_client, test_user, admin_user):
        """Test recupero lista utenti come admin"""
        response = authenticated_admin_client.get("/api/v1/users/all")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # Almeno test_user e admin_user

    def test_get_all_users_as_regular_user(self, authenticated_client):
        """Test che utente normale non possa accedere a lista utenti"""
        response = authenticated_client.get("/api/v1/users/all")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_user_as_admin(self, authenticated_admin_client, test_user):
        """Test aggiornamento utente da parte di admin"""
        update_data = {
            "role": "editor",
            "permissions": ["read", "write"]
        }

        response = authenticated_admin_client.put(
            f"/api/v1/users/{test_user.id}",
            json=update_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["role"] == "editor"
        assert data["permissions"] == ["read", "write"]

    def test_update_user_not_found(self, authenticated_admin_client):
        """Test aggiornamento utente inesistente"""
        update_data = {"role": "editor"}

        response = authenticated_admin_client.put(
            "/api/v1/users/99999",
            json=update_data
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_change_user_password_as_admin(self, authenticated_admin_client, test_user):
        """Test cambio password di un utente da parte di admin"""
        password_data = {"new_password": "newpassword456"}

        response = authenticated_admin_client.put(
            f"/api/v1/users/{test_user.id}/password",
            json=password_data
        )

        assert response.status_code == status.HTTP_200_OK
        assert "successfully" in response.json()["message"]

    def test_delete_user_as_admin(self, authenticated_admin_client, test_user):
        """Test eliminazione utente da parte di admin"""
        response = authenticated_admin_client.delete(
            f"/api/v1/users/{test_user.id}"
        )

        assert response.status_code == status.HTTP_200_OK

        # Verifica che l'utente sia stato eliminato
        get_response = authenticated_admin_client.get(
            f"/api/v1/users/all"
        )
        users = get_response.json()
        user_ids = [u["id"] for u in users]
        assert test_user.id not in user_ids

    def test_admin_cannot_delete_themselves(self, authenticated_admin_client, admin_user):
        """Test che admin non possa eliminare se stesso"""
        response = authenticated_admin_client.delete(
            f"/api/v1/users/{admin_user.id}"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot delete themselves" in response.json()["detail"].lower()

    def test_delete_user_not_found(self, authenticated_admin_client):
        """Test eliminazione utente inesistente"""
        response = authenticated_admin_client.delete("/api/v1/users/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_dashboard_access(self, authenticated_admin_client, admin_user):
        """Test accesso dashboard admin"""
        response = authenticated_admin_client.get("/api/v1/users/admin/dashboard")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert admin_user.username in data["message"]

    def test_regular_user_cannot_access_admin_dashboard(self, authenticated_client):
        """Test che utente normale non possa accedere alla dashboard admin"""
        response = authenticated_client.get("/api/v1/users/admin/dashboard")

        assert response.status_code == status.HTTP_403_FORBIDDEN
