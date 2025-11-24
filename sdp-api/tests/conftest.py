import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Aggiungi il parent directory al path per importare i moduli
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from db.models import Base
from db import get_db, get_db_optional
from core import security
from core.config import settings


# Database di test in memoria
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Crea un database di test pulito per ogni test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Client di test FastAPI con database di test"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_optional] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_bank(db_session):
    """Crea una banca di test"""
    from db import models

    bank = models.Bank(
        label="TestBank",
        ini_path="test/path/test.ini",
        is_current=True
    )
    db_session.add(bank)
    db_session.commit()
    db_session.refresh(bank)
    return bank


@pytest.fixture
def test_user(db_session, test_bank):
    """Crea un utente di test"""
    from db import models

    hashed_password = security.get_password_hash("testpassword123")
    user = models.User(
        username="testuser",
        hashed_password=hashed_password,
        bank=test_bank.label
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_token(test_user):
    """Genera un token JWT valido per l'utente di test"""
    from datetime import timedelta

    access_token = security.create_access_token(
        data={"sub": test_user.username, "bank": test_user.bank},
        expires_delta=timedelta(minutes=30)
    )
    return access_token


@pytest.fixture
def authenticated_client(client, test_user_token):
    """Client autenticato con token"""
    client.headers = {
        **client.headers,
        "Authorization": f"Bearer {test_user_token}"
    }
    return client


@pytest.fixture
def test_flow(db_session, test_bank):
    """Crea un flow di test"""
    from db import models

    flow = models.Flow(
        name="Test Flow",
        bank=test_bank.label,
        selected_flows=["flow1", "flow2"]
    )
    db_session.add(flow)
    db_session.commit()
    db_session.refresh(flow)
    return flow


@pytest.fixture
def sample_log_entry(db_session):
    """Crea una voce di log di esempio"""
    from db import models
    from datetime import datetime

    log = models.LogSettimanale(
        date=datetime.now(),
        tipo="test",
        nomefiliale="Test Branch",
        titolo="Test Title",
        link="http://test.com",
        folder="test_folder",
        bank="TestBank"
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return log
