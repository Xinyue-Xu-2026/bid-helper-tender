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


def _seed(client, db_path):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    db = Database(db_path)
    rid = db.create_requirement(pid, "废标项", "未密封将废标", source="第一章")
    return pid, rid


def test_requirements_query_and_update(client, db_path):
    pid, rid = _seed(client, db_path)
    items = client.get(f"/api/projects/{pid}/requirements").json()
    assert len(items) == 1 and items[0]["category"] == "废标项"
    assert client.get(f"/api/projects/{pid}/requirements", params={"q": "密封"}).json()
    assert not client.get(f"/api/projects/{pid}/requirements", params={"category": "评分项"}).json()
    r = client.put(f"/api/requirements/{rid}", json={"status": "已响应"})
    assert r.status_code == 200
    assert client.get(f"/api/projects/{pid}/requirements").json()[0]["status"] == "已响应"
    assert client.delete(f"/api/requirements/{rid}").status_code == 200
    assert not client.get(f"/api/projects/{pid}/requirements").json()


def test_parse_sse_no_tender(client):
    pid = client.post("/api/projects", json={"name": "p"}).json()["id"]
    with client.stream("GET", f"/api/projects/{pid}/parse") as r:
        body = "".join(r.iter_text())
    assert "event: error" in body
    assert "招标文件" in body
