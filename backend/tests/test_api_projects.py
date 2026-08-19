import pytest
from fastapi.testclient import TestClient

from app.db import Database
from app.deps import get_db
from app.main import app


@pytest.fixture()
def client(db_path):
    def override():
        db = Database(db_path)
        db.init_schema()
        yield db
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_project_crud_api(client):
    r = client.post("/api/projects", json={"name": "测试项目", "client": "某单位"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert client.get("/api/projects").json()[0]["name"] == "测试项目"
    r = client.put(f"/api/projects/{pid}", json={"client": "另一单位"})
    assert r.status_code == 200
    assert client.get(f"/api/projects/{pid}").json()["client"] == "另一单位"
    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_upload_tender_rejects_bad_type(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/tender",
                    files={"file": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_settings_roundtrip(client):
    r = client.put("/api/settings", json={"api_key": "sk-test-123", "model": "kimi-k2.6"})
    assert r.status_code == 200
    data = client.get("/api/settings").json()
    assert data["api_key"] == "sk-test-123" and data["model"] == "kimi-k2.6"
