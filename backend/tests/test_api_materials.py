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
                    files=[("files", ("业绩证明.pdf", b"%PDF-1.4", "application/pdf"))])
    assert r.status_code == 200
    assert r.json()["errors"] == []
    item = r.json()["items"][0]
    mid = item["id"]
    path = item["file_path"]
    assert Path(path).exists()
    lst = client.get(f"/api/projects/{pid}/materials").json()
    assert len(lst) == 1 and lst[0]["file_type"] == "pdf"
    assert client.delete(f"/api/materials/{mid}").json() == {"ok": True}
    assert not Path(path).exists()  # 删除时清理文件
    assert client.get(f"/api/projects/{pid}/materials").json() == []


def test_upload_reject_bad_type(client):
    pid = _project(client)
    r = client.post(f"/api/projects/{pid}/materials",
                    files=[("files", ("x.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert len(body["errors"]) == 1
    assert body["errors"][0]["filename"] == "x.exe"
    assert "不支持的文件类型" in body["errors"][0]["reason"]


def test_upload_multi_mixed(client):
    pid = _project(client)
    r = client.post(
        f"/api/projects/{pid}/materials",
        files=[
            ("files", ("招标要求.pdf", b"%PDF-1.4", "application/pdf")),
            ("files", ("截图.png", b"\x89PNG", "image/png")),
            ("files", ("evil.exe", b"MZ", "application/octet-stream")),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert len(body["errors"]) == 1
    assert body["errors"][0]["filename"] == "evil.exe"
    for item in body["items"]:
        assert Path(item["file_path"]).exists()
    lst = client.get(f"/api/projects/{pid}/materials").json()
    assert len(lst) == 2


def test_upload_legacy_single_file_field(client):
    pid = _project(client)
    r = client.post(f"/api/projects/{pid}/materials",
                    files={"file": ("m.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1 and body["errors"] == []


def test_upload_missing_project_404(client):
    r = client.post("/api/projects/999/materials",
                    files=[("files", ("m.pdf", b"%PDF", "application/pdf"))])
    assert r.status_code == 404
