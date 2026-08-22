"""编写工作台路由测试（大纲/单节生成 mock，零网络）。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _project(client):
    return client.post("/api/projects", json={"name": "编写测试项目"}).json()["id"]


def test_sections_crud(client):
    pid = _project(client)
    root = client.post(f"/api/projects/{pid}/sections",
                       json={"title": "第一章", "level": 1}).json()["id"]
    child = client.post(f"/api/projects/{pid}/sections",
                        json={"parent_id": root, "title": "1.1 子节", "level": 2}).json()["id"]
    tree = client.get(f"/api/projects/{pid}/sections").json()
    assert tree[0]["title"] == "第一章"
    assert tree[0]["children"][0]["title"] == "1.1 子节"
    client.put(f"/api/sections/{child}", json={"content": "正文", "gen_status": "已生成"})
    assert client.delete(f"/api/sections/{root}").json() == {"ok": True}  # 递归删子节
    assert client.get(f"/api/projects/{pid}/sections").json() == []


def test_outline_mock(client, monkeypatch):
    from app.db import Database
    pid = _project(client)
    db = Database(); db.init_schema()
    db.create_requirement(pid, "格式要求", "投标文件应包含资质材料")
    monkeypatch.setattr("app.services.write_service.get_api_key", lambda: "sk-test")
    monkeypatch.setattr("app.services.write_service.get_model", lambda: "kimi-k3")
    monkeypatch.setattr(
        "app.services.write_service.generate_outline",
        lambda reqs, key, model: [
            {"title": "第一章 资格审查", "level": 1, "children": [
                {"title": "1.1 营业执照", "level": 2, "children": []}]}])
    tree = client.post(f"/api/projects/{pid}/outline").json()
    assert tree[0]["title"] == "第一章 资格审查"
    assert tree[0]["children"][0]["title"] == "1.1 营业执照"


def test_generate_section_sse(client, monkeypatch):
    pid = _project(client)
    sid = client.post(f"/api/projects/{pid}/sections",
                      json={"title": "1.1 营业执照", "level": 2}).json()["id"]
    monkeypatch.setattr("app.services.write_service.get_api_key", lambda: "sk-test")
    monkeypatch.setattr("app.services.write_service.get_model", lambda: "kimi-k3")
    monkeypatch.setattr("app.services.write_service.stream_section",
                        lambda prompt, key, model: iter(["我", "方", "承诺"]))
    r = client.get(f"/api/projects/{pid}/sections/{sid}/generate")
    assert r.status_code == 200
    assert "event: chunk" in r.text
    assert "event: done" in r.text
    assert "data: 我方承诺" in r.text
    stored = client.get(f"/api/projects/{pid}/sections").json()[0]
    assert stored["content"] == "我方承诺"
    assert stored["gen_status"] == "已生成"


def test_generate_section_error_strips_newline(client, monkeypatch):
    pid = _project(client)
    sid = client.post(f"/api/projects/{pid}/sections",
                      json={"title": "1.1", "level": 2}).json()["id"]
    monkeypatch.setattr("app.services.write_service.get_api_key", lambda: "sk-test")
    monkeypatch.setattr("app.services.write_service.get_model", lambda: "kimi-k3")

    def boom(prompt, key, model):
        raise Exception("第一行\n第二行")
        yield  # pragma: no cover
    monkeypatch.setattr("app.services.write_service.stream_section", boom)
    r = client.get(f"/api/projects/{pid}/sections/{sid}/generate")
    assert "event: error" in r.text
    assert "第一行 第二行" in r.text
    assert "\n第二行" not in r.text


def test_generate_section_missing_404(client):
    pid = _project(client)
    assert client.get(f"/api/projects/{pid}/sections/999/generate").status_code == 404


def test_generate_section_multiline_sse(client, monkeypatch):
    pid = _project(client)
    sid = client.post(f"/api/projects/{pid}/sections",
                      json={"title": "1.1", "level": 2}).json()["id"]
    monkeypatch.setattr("app.services.write_service.get_api_key", lambda: "sk-test")
    monkeypatch.setattr("app.services.write_service.get_model", lambda: "kimi-k3")
    monkeypatch.setattr("app.services.write_service.stream_section",
                        lambda prompt, key, model: iter(["第一行\n第二行", "第三行"]))
    r = client.get(f"/api/projects/{pid}/sections/{sid}/generate")
    assert r.status_code == 200
    assert "data: 第一行\ndata: 第二行" in r.text
    stored = client.get(f"/api/projects/{pid}/sections").json()[0]
    assert stored["content"] == "第一行\n第二行第三行"
    assert stored["gen_status"] == "已生成"


def test_generate_section_cross_project_404(client):
    pid_a = _project(client)
    pid_b = client.post("/api/projects", json={"name": "另一个项目"}).json()["id"]
    sid = client.post(f"/api/projects/{pid_b}/sections",
                      json={"title": "1.1", "level": 2}).json()["id"]
    assert client.get(f"/api/projects/{pid_a}/sections/{sid}/generate").status_code == 404
