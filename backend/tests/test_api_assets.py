from datetime import date, timedelta

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


def test_asset_crud(client):
    r = client.post("/api/assets", json={
        "type": "credit", "name": "营业执照",
        "fields": {"发证机关": "市监局"}, "expiry_date": "2027-01-01"})
    aid = r.json()["id"]
    items = client.get("/api/assets", params={"type": "credit"}).json()
    assert items[0]["fields"]["发证机关"] == "市监局"
    client.put(f"/api/assets/{aid}", json={"expiry_date": "2027-06-01"})
    assert client.get(f"/api/assets/{aid}").json()["expiry_date"] == "2027-06-01"
    client.delete(f"/api/assets/{aid}")
    assert client.get(f"/api/assets/{aid}").status_code == 404


def test_expiring_endpoint(client):
    soon = (date.today() + timedelta(days=5)).isoformat()
    client.post("/api/assets", json={"type": "person", "name": "张三", "expiry_date": soon})
    client.post("/api/assets", json={"type": "credit", "name": "无期限证书"})
    items = client.get("/api/assets/expiring", params={"days": 30}).json()
    assert len(items) == 1 and items[0]["name"] == "张三" and items[0]["days_left"] == 5


def test_asset_file_upload(client):
    aid = client.post("/api/assets", json={"type": "credit", "name": "资质证书"}).json()["id"]
    r = client.post(f"/api/assets/{aid}/file",
                    files={"file": ("cert.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200
    assert r.json()["file_path"].endswith(".png")
