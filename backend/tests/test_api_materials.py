"""项目资料路由测试。"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _project(client):
    return client.post("/api/projects", json={"name": "资料测试项目"}).json()["id"]


def test_upload_list_delete_material(client):
    pid = _project(client)
    r = client.post(f"/api/projects/{pid}/materials",
                    files={"file": ("业绩证明.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 200
    mid = r.json()["id"]
    path = r.json()["file_path"]
    assert Path(path).exists()
    lst = client.get(f"/api/projects/{pid}/materials").json()
    assert len(lst) == 1 and lst[0]["file_type"] == "pdf"
    assert client.delete(f"/api/materials/{mid}").json() == {"ok": True}
    assert not Path(path).exists()  # 删除时清理文件
    assert client.get(f"/api/projects/{pid}/materials").json() == []


def test_upload_reject_bad_type(client):
    pid = _project(client)
    r = client.post(f"/api/projects/{pid}/materials",
                    files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400


def test_upload_missing_project_404(client):
    r = client.post("/api/projects/999/materials",
                    files={"file": ("m.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 404
