import os
import tempfile

import pytest

fd, test_db = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["ATTENDANCE_DB_PATH"] = test_db
os.environ["FLASK_SECRET_KEY"] = "test-secret-key"

from app import app  # noqa: E402

@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"

def test_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200

def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code in (301, 302)
