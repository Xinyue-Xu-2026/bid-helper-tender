"""Minor 清债后端测试。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _project(client):
    return client.post("/api/projects", json={"name": "Minor测试项目"}).json()["id"]


def test_put_requirement_rejects_bad_category(client):
    from app.db import Database
    pid = _project(client)
    db = Database(); db.init_schema()
    rid = db.create_requirement(pid, "格式要求", "内容")
    r = client.put(f"/api/requirements/{rid}", json={"category": "不存在的分类"})
    assert r.status_code == 400
    assert "分类" in r.json()["detail"]


def test_replace_requirements_atomic(client):
    from app.db import Database
    pid = _project(client)
    db = Database(); db.init_schema()
    db.create_requirement(pid, "格式要求", "旧要求")
    db.replace_requirements(pid, [
        {"category": "评分项", "content": "新要求1", "source": "", "confidence": "高", "status": "待响应"},
        {"category": "废标项", "content": "新要求2", "source": "", "confidence": "高", "status": "待响应"},
    ])
    reqs = db.get_requirements(pid)
    assert [r["content"] for r in reqs] == ["新要求1", "新要求2"]


def test_ai_check_missing_project_404(client):
    assert client.post("/api/projects/999/compliance/ai-check").status_code == 404


def test_delete_asset_cleans_file(client):
    from pathlib import Path
    from app import config
    from app.db import Database
    config.ensure_dirs()
    f = config.FILES_DIR / "orphan_test.png"
    f.write_bytes(b"x")
    db = Database(); db.init_schema()
    aid = db.create_asset("material", "孤儿文件", file_path=str(f))
    assert client.delete(f"/api/assets/{aid}").json() == {"ok": True}
    assert not Path(f).exists()
