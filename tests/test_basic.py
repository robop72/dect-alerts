import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_pontosense.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_root_returns_dashboard():
    response = client.get("/")
    assert response.status_code == 200
    assert "Pontosense" in response.text


def test_create_facility():
    response = client.post("/facilities", json={"name": "Test Facility", "location": "AU"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Facility"
    assert data["location"] == "AU"
    return data["id"]


def test_simulate_low_risk_alert():
    fac = client.post("/facilities", json={"name": "Test", "location": "AU"}).json()
    resp = client.post(
        "/alerts/simulate-alert",
        json={"facility_id": fac["id"], "alert_type": "Bed Exit", "room_number": "7", "risk_level": "low"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "acknowledged"
    assert data["risk_level"] == "low"


def test_simulate_ack():
    fac = client.post("/facilities", json={"name": "Test", "location": "AU"}).json()
    alert = client.post(
        "/alerts/simulate-alert",
        json={"facility_id": fac["id"], "alert_type": "Fall", "room_number": "14", "risk_level": "high"},
    ).json()
    ack = client.post(f"/alerts/simulate-ack/{alert['id']}")
    assert ack.status_code == 200


def test_reports_summary():
    resp = client.get("/reports/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "acknowledged" in data
