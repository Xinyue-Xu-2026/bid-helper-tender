"""导出路由测试（xlsx 要求清单 + Word 标书导出，后者依赖 Task 6 的 sections 路由）。"""
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


@pytest.fixture()
def word_client():
    with TestClient(app) as c:
        yield c


def _project(client):
    return client.post("/api/projects", json={"name": "导出测试项目"}).json()["id"]


def _seed_section(client, pid, title, level, content=""):
    sid = client.post(f"/api/projects/{pid}/sections",
                      json={"title": title, "level": level}).json()["id"]
    if content:
        client.put(f"/api/sections/{sid}", json={"content": content})
    return sid


def test_export_word_empty_400(word_client):
    pid = _project(word_client)
    assert word_client.get(f"/api/projects/{pid}/export").status_code == 400


def test_export_word_ok(word_client):
    pid = _project(word_client)
    _seed_section(word_client, pid, "第一章 资格审查", 1, "正文")
    r = word_client.get(f"/api/projects/{pid}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml")
    assert r.content[:2] == b"PK"          # docx 是 zip 包


def test_export_word_missing_project_404(word_client):
    assert word_client.get("/api/projects/999/export").status_code == 404
