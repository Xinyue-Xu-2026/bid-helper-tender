"""模板路由测试（画像分析 mock，零网络）。"""
import io

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _docx_bytes(text="模板内容"):
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _upload(client, name="测试模板"):
    return client.post(
        "/api/templates",
        params={"name": name},
        files={"file": ("t.docx", _docx_bytes(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )


def test_upload_list_delete(client):
    r = _upload(client)
    assert r.status_code == 200
    tid = r.json()["id"]
    lst = client.get("/api/templates").json()
    assert any(t["id"] == tid and t["name"] == "测试模板" for t in lst)
    assert client.delete(f"/api/templates/{tid}").json() == {"ok": True}
    assert not any(t["id"] == tid for t in client.get("/api/templates").json())


def test_upload_reject_non_docx(client):
    r = client.post("/api/templates", params={"name": "x"},
                    files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 400


def test_analyze_mocked(client, monkeypatch):
    monkeypatch.setattr("app.services.write_service.get_api_key", lambda: "sk-test")
    monkeypatch.setattr("app.services.write_service.get_model", lambda: "kimi-k3")
    monkeypatch.setattr("app.services.write_service.analyze_template",
                        lambda path, key, model: "mock画像")
    tid = _upload(client).json()["id"]
    r = client.post(f"/api/templates/{tid}/analyze")
    assert r.status_code == 200
    assert r.json()["style_profile"] == "mock画像"
    stored = [t for t in client.get("/api/templates").json() if t["id"] == tid][0]
    assert stored["style_profile"] == "mock画像"


def test_analyze_no_key_returns_400(client, monkeypatch):
    monkeypatch.setattr("app.services.write_service.get_api_key", lambda: "")
    tid = _upload(client).json()["id"]
    r = client.post(f"/api/templates/{tid}/analyze")
    assert r.status_code == 400
    assert "API Key" in r.json()["detail"]


def test_analyze_missing_template_404(client):
    assert client.post("/api/templates/999/analyze").status_code == 404
