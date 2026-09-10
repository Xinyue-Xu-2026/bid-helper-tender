"""商务标底稿内容编辑（方案 A）API 测试：document 读/写回显 + 无底稿 404/422。"""
import pytest
from fastapi.testclient import TestClient

from app.db import Database
from app.deps import get_db
from app.main import app

from tests.test_api_bid_draft import _generate, _make_project, _upload_tender


@pytest.fixture()
def client(db_path):
    def override():
        db = Database(db_path)
        db.init_schema()
        yield db
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def _table_snapshot(tbl):
    return [[c["text"] if c["origin"] else "" for c in row]
            for row in tbl["rows"]]


def test_document_edit_roundtrip(client, tmp_path):
    pid = _make_project(client)
    _upload_tender(client, pid, tmp_path, tenderer="某中心")
    _generate(client, pid)

    r = client.get(f"/api/projects/{pid}/bid-draft/document")
    assert r.status_code == 200
    blocks = r.json()["blocks"]
    tables = [b for b in blocks if b["kind"] == "table"]
    paras = [b for b in blocks if b["kind"] == "paragraph"]
    assert tables and paras

    para_idx = paras[0]["index"]
    tbl = tables[0]
    table_idx = tbl["index"]
    new_rows = _table_snapshot(tbl)
    new_rows[0][0] = "改后的格子"

    body = {"paragraphs": {para_idx: "改后的段落"},
            "tables": {table_idx: new_rows},
            "clones": []}
    r2 = client.post(f"/api/projects/{pid}/bid-draft/document", json=body)
    assert r2.status_code == 200
    assert r2.json()["ok"] is True

    blocks3 = client.get(f"/api/projects/{pid}/bid-draft/document").json()["blocks"]
    p = next(b for b in blocks3 if b["kind"] == "paragraph" and b["index"] == para_idx)
    assert p["text"] == "改后的段落"
    t3 = next(b for b in blocks3 if b["kind"] == "table" and b["index"] == table_idx)
    assert t3["rows"][0][0]["text"] == "改后的格子"


def test_document_requires_draft(client):
    pid = _make_project(client)
    assert client.get(f"/api/projects/{pid}/bid-draft/document").status_code == 404
    assert client.post(f"/api/projects/{pid}/bid-draft/document", json={}).status_code == 422
