from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.llm_parser import CODING_DEFAULT_MODEL
from app.main import app
from app.settings_store import save_settings


@pytest.fixture()
def client():
    return TestClient(app)


def _fake_client(captured):
    def _create(**kwargs):
        captured["create"] = kwargs
        return SimpleNamespace()
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))


def _patch_make_client(monkeypatch, captured):
    def fake_make_client(api_key, timeout=300.0):
        captured["api_key"] = api_key
        captured["timeout"] = timeout
        return _fake_client(captured)
    monkeypatch.setattr("app.routers.settings._make_client", fake_make_client)


def test_test_connection_prefers_form_values(client, monkeypatch):
    # 磁盘旧值 vs 表单新值：请求体优先
    save_settings({"api_key": "sk-disk-old", "model": "kimi-k3"})
    captured = {}
    _patch_make_client(monkeypatch, captured)
    r = client.post("/api/settings/test", json={"api_key": "sk-form-new", "model": "kimi-k3"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert captured["api_key"] == "sk-form-new"
    assert captured["create"]["model"] == "kimi-k3"


def test_test_connection_falls_back_to_disk_values(client, monkeypatch):
    # 不带请求体（旧调用方式）：用磁盘已保存值
    save_settings({"api_key": "sk-disk-saved", "model": "kimi-k3"})
    captured = {}
    _patch_make_client(monkeypatch, captured)
    r = client.post("/api/settings/test")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert captured["api_key"] == "sk-disk-saved"


def test_test_connection_coding_key_model_fallback(client, monkeypatch):
    # sk-kimi- 编程 Key + 非编程模型 → 回退到 CODING_DEFAULT_MODEL
    captured = {}
    _patch_make_client(monkeypatch, captured)
    r = client.post("/api/settings/test", json={"api_key": "sk-kimi-abc123", "model": "kimi-k3"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert captured["create"]["model"] == CODING_DEFAULT_MODEL


# ---------- 占位符同义词库（V1.2 Task 8a） ----------

def test_placeholder_synonyms_get_default(client):
    """GET 默认库：含 采购人→招标人 等内建同义词。"""
    r = client.get("/api/settings/placeholder-synonyms")
    assert r.status_code == 200
    data = r.json()
    assert data["采购人"] == "招标人"
    assert data["工程项目名称"] == "项目名称"


def test_placeholder_synonyms_put_roundtrip(client):
    """PUT 自定义覆盖（空键/空值被清洗）→ 回读一致且默认库仍在。"""
    r = client.put("/api/settings/placeholder-synonyms",
                   json={"甲方": "招标人", "  ": "某标签"})
    assert r.status_code == 200
    assert r.json() == {"甲方": "招标人"}
    data = client.get("/api/settings/placeholder-synonyms").json()
    assert data["甲方"] == "招标人"
    assert data["采购人"] == "招标人"   # 默认库不被覆盖丢失
