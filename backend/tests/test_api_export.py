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


def test_export_xlsx(client, db_path):
    pid = client.post("/api/projects", json={"name": "导出测试"}).json()["id"]
    db = Database(db_path)
    db.create_requirement(pid, "评分项", "业绩加分 10 分")
    r = client.get(f"/api/projects/{pid}/requirements/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument")
    assert len(r.content) > 1000
