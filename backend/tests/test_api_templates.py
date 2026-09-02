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
        files=[("files", ("t.docx", _docx_bytes(),
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )


def _first_id(resp):
    return resp.json()["items"][0]["id"]


def test_upload_list_delete(client):
    r = _upload(client)
    assert r.status_code == 200
    assert r.json()["errors"] == []
    tid = _first_id(r)
    lst = client.get("/api/templates").json()
    assert any(t["id"] == tid and t["name"] == "测试模板" for t in lst)
    assert client.delete(f"/api/templates/{tid}").json() == {"ok": True}
    assert not any(t["id"] == tid for t in client.get("/api/templates").json())


def test_upload_reject_non_docx(client):
    r = client.post("/api/templates", params={"name": "x"},
                    files=[("files", ("a.pdf", b"%PDF-1.4", "application/pdf"))])
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert len(body["errors"]) == 1
    assert body["errors"][0]["filename"] == "a.pdf"


def test_upload_multi_mixed(client):
    r = client.post(
        "/api/templates",
        files=[
            ("files", ("a.docx", _docx_bytes(),
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("b.docx", _docx_bytes(),
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("bad.txt", b"nope", "text/plain")),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["errors"] == [{"filename": "bad.txt", "reason": "仅支持 .docx 模板"}]
    ids = {it["id"] for it in body["items"]}
    lst = client.get("/api/templates").json()
    assert ids <= {t["id"] for t in lst}


def test_upload_legacy_single_file_field(client):
    r = client.post(
        "/api/templates",
        params={"name": "旧版模板"},
        files={"file": ("t.docx", _docx_bytes(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1 and body["errors"] == []


def test_analyze_mocked(client, monkeypatch):
    monkeypatch.setattr("app.services.write_service.get_api_key", lambda: "sk-test")
    monkeypatch.setattr("app.services.write_service.get_model", lambda: "kimi-k3")
    monkeypatch.setattr("app.services.write_service.analyze_template",
                        lambda path, key, model: "mock画像")
    tid = _first_id(_upload(client))
    r = client.post(f"/api/templates/{tid}/analyze")
    assert r.status_code == 200
    assert r.json()["style_profile"] == "mock画像"
    stored = [t for t in client.get("/api/templates").json() if t["id"] == tid][0]
    assert stored["style_profile"] == "mock画像"


def test_analyze_no_key_returns_400(client, monkeypatch):
    monkeypatch.setattr("app.services.write_service.get_api_key", lambda: "")
    tid = _first_id(_upload(client))
    r = client.post(f"/api/templates/{tid}/analyze")
    assert r.status_code == 400
    assert "API Key" in r.json()["detail"]


def test_analyze_missing_template_404(client):
    assert client.post("/api/templates/999/analyze").status_code == 404
