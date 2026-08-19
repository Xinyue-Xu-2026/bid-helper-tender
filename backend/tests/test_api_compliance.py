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


def test_compliance_flow(client, db_path):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    db = Database(db_path)
    r1 = db.create_requirement(pid, "废标项", "未密封将废标")
    db.create_requirement(pid, "资质门槛", "须具备甲级资质")
    db.create_requirement(pid, "评分项", "业绩加分")  # 不进入核对清单
    data = client.get(f"/api/projects/{pid}/compliance").json()
    assert data["total"] == 2 and data["checked"] == 0
    assert data["items"][0]["checked"] is False
    client.put(f"/api/compliance/{r1}", json={"checked": True})
    data = client.get(f"/api/projects/{pid}/compliance").json()
    assert data["checked"] == 1
    assert data["items"][0]["checked"] is True


def test_ai_check_placeholder(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/compliance/ai-check")
    assert r.status_code == 501
