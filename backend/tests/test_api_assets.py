from datetime import date, timedelta

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


def test_asset_crud(client):
    r = client.post("/api/assets", json={
        "type": "credit", "name": "营业执照",
        "fields": {"发证机关": "市监局"}, "expiry_date": "2027-01-01"})
    aid = r.json()["id"]
    items = client.get("/api/assets", params={"type": "credit"}).json()
    assert items[0]["fields"]["发证机关"] == "市监局"
    client.put(f"/api/assets/{aid}", json={"expiry_date": "2027-06-01"})
    assert client.get(f"/api/assets/{aid}").json()["expiry_date"] == "2027-06-01"
    client.delete(f"/api/assets/{aid}")
    assert client.get(f"/api/assets/{aid}").status_code == 404


def test_expiring_endpoint(client):
    soon = (date.today() + timedelta(days=5)).isoformat()
    client.post("/api/assets", json={"type": "person", "name": "张三", "expiry_date": soon})
    client.post("/api/assets", json={"type": "credit", "name": "无期限证书"})
    items = client.get("/api/assets/expiring", params={"days": 30}).json()
    assert len(items) == 1 and items[0]["name"] == "张三" and items[0]["days_left"] == 5


def test_asset_file_upload(client):
    aid = client.post("/api/assets", json={"type": "credit", "name": "资质证书"}).json()["id"]
    r = client.post(f"/api/assets/{aid}/file",
                    files={"file": ("cert.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200
    assert r.json()["file_path"].endswith(".png")


def test_legal_asset_crud(client):
    """法人/代理人（legal）资产：姓名=name，fields 含身份证号；不受 person 归一化污染。"""
    r = client.post("/api/assets", json={
        "type": "legal", "name": "张三",
        "fields": {"身份证号": "320000199001011234", "职务": "法定代表人"}})
    assert r.status_code == 200
    aid = r.json()["id"]

    items = client.get("/api/assets", params={"type": "legal"}).json()
    assert any(a["id"] == aid and a["name"] == "张三" for a in items)
    # _normalize_out 只对 person 特判：legal 不被注入"业绩"、不固化"证书"
    one = client.get(f"/api/assets/{aid}").json()
    assert one["fields"]["身份证号"] == "320000199001011234"
    assert "业绩" not in one["fields"]
    assert "证书" not in one["fields"]

    # 未知类型仍 400（既有的 _check_type 覆盖）
    assert client.post("/api/assets", json={"type": "nope", "name": "x"}).status_code == 400


def test_legal_asset_id_card_faces(client):
    """legal 资产身份证正/反面图片上传 + 预览。"""
    aid = client.post("/api/assets", json={"type": "legal", "name": "李四"}).json()["id"]
    for cat in ("身份证正面", "身份证反面"):
        r = client.post(f"/api/assets/{aid}/person-image",
                        files={"file": ("id.png", b"\x89PNG fake", "image/png")},
                        data={"category": cat})
        assert r.status_code == 200, cat
        assert r.json()["file_path"].endswith(".png")
        assert cat in r.json()["file_path"]
    # 预览两个分类
    for cat in ("身份证正面", "身份证反面"):
        r = client.get(f"/api/assets/{aid}/image/{cat}")
        assert r.status_code == 200, cat
    # 非法分类仍 400
    r = client.post(f"/api/assets/{aid}/person-image",
                    files={"file": ("id.png", b"\x89PNG fake", "image/png")},
                    data={"category": "驾驶证"})
    assert r.status_code == 400


def test_person_id_card_single_upload_unregressed(client):
    """person 既有单张"身份证"上传不回归。"""
    aid = client.post("/api/assets", json={"type": "person", "name": "王五"}).json()["id"]
    r = client.post(f"/api/assets/{aid}/person-image",
                    files={"file": ("id.png", b"\x89PNG fake", "image/png")},
                    data={"category": "身份证"})
    assert r.status_code == 200
    assert client.get(f"/api/assets/{aid}/image/身份证").status_code == 200
