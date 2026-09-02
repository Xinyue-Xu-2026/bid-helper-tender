"""统一字段配置 + 一人多证 + 共享文件夹导入适配的冒烟测试。"""
import pytest
from fastapi.testclient import TestClient

from app.db import Database
from app.deps import get_db
from app.main import app
from app.services import import_service


@pytest.fixture()
def db(db_path):
    d = Database(db_path)
    d.init_schema()
    return d


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------- 字段配置 ----------

def test_field_config_defaults(client):
    cfg = client.get("/api/assets/field-config").json()
    person_keys = [f["key"] for f in cfg["person"]]
    contract_keys = [f["key"] for f in cfg["contract"]]
    # 姓名内置为资产 name 列，person 字段列表不含姓名/身份证号
    assert person_keys == ["部门", "职称", "联系方式", "类型"]
    assert contract_keys == ["项目名称", "类型", "合同金额", "年份", "甲方", "项目经理"]
    person_type = next(f for f in cfg["person"] if f["key"] == "类型")
    assert person_type["type"] == "dropdown"
    assert person_type["options"] == ["一级造价师", "二级造价师", "一级建造师",
                                      "二级建筑师", "监理工程师"]
    contract_type = next(f for f in cfg["contract"] if f["key"] == "类型")
    assert contract_type["options"] == ["编标", "审标", "跟踪", "结算"]


def test_field_config_put_echo(client):
    custom = {
        # 调序 + 给 dropdown 加选项 + 新增 date 字段 + 姓名（应被剔除）
        "person": [
            {"key": "姓名", "type": "text", "options": []},
            {"key": "类型", "type": "dropdown",
             "options": ["一级造价师", "咨询工程师"]},
            {"key": "部门", "type": "text", "options": []},
            {"key": "入职日期", "type": "date", "options": []},
        ],
        "contract": [
            {"key": "类型", "type": "dropdown", "options": ["编标", "审标", "跟踪", "结算", "其他"]},
            {"key": "项目名称", "type": "text", "options": []},
        ],
    }
    r = client.put("/api/assets/field-config", json=custom)
    assert r.status_code == 200
    echoed = client.get("/api/assets/field-config").json()
    assert [f["key"] for f in echoed["person"]] == ["类型", "部门", "入职日期"]
    assert echoed["person"][0]["options"] == ["一级造价师", "咨询工程师"]
    assert echoed["person"][2]["type"] == "date"
    assert echoed["contract"][0]["options"][-1] == "其他"


# ---------- 一人多证 ----------

def test_person_multi_certs_create_and_get(client):
    r = client.post("/api/assets", json={
        "type": "person", "name": "张三",
        "fields": {
            "职称": "高工",
            "证书": [
                {"类型": "一级建造师", "证书名称": "一级建造师执业资格证",
                 "有效期至": "2027-06-30", "编号": "A001"},
                {"类型": "一级造价师", "证书名称": "一级造价工程师证",
                 "有效期至": "2026-01-15", "编号": "B002"},
            ],
        }})
    aid = r.json()["id"]
    got = client.get(f"/api/assets/{aid}").json()
    certs = got["fields"]["证书"]
    assert len(certs) == 2
    assert got["expiry_date"] == "2026-01-15"  # 最早有效期
    # 列表输出同样保证证书数组
    listed = client.get("/api/assets", params={"type": "person"}).json()
    assert len(listed[0]["fields"]["证书"]) == 2


def test_person_legacy_lazy_migration(client, db):
    # 直接写库模拟旧结构单值
    aid = db.create_asset("person", "李四", {
        "职称": "工程师", "证书名称": "二级造价工程师证", "证书有效期至": "2026.12.31",
    }, expiry_date="2026-12-31")
    got = client.get(f"/api/assets/{aid}").json()
    certs = got["fields"]["证书"]
    assert len(certs) == 1
    assert certs[0]["证书名称"] == "二级造价工程师证"
    assert certs[0]["有效期至"] == "2026.12.31"
    assert "证书名称" not in got["fields"] or isinstance(got["fields"].get("证书"), list)
    assert got["expiry_date"] == "2026-12-31"


def test_person_put_solidifies(client, db):
    aid = db.create_asset("person", "王五", {"证书名称": "监理工程师证", "证书有效期至": "2027-01-01"})
    client.put(f"/api/assets/{aid}", json={"fields": {
        "证书": [{"类型": "监理工程师", "证书名称": "监理工程师证",
                  "有效期至": "2027-01-01", "编号": "J001"}]}})
    raw = db.get_asset(aid)
    assert isinstance(raw["fields"].get("证书"), list)
    assert "证书名称" not in raw["fields"]
    assert raw["expiry_date"] == "2027-01-01"


# ---------- 共享文件夹导入 confirm：同人两证不覆盖 ----------

def test_confirm_same_person_two_certs_no_overwrite(db):
    items = [
        {"asset_type": "person", "action": "new", "fields": {
            "姓名": "赵六", "职称": "高工",
            "类型": "一级建造师", "证书名称": "一级建造师执业资格证",
            "证书有效期至": "2027-03-01", "编号": "A1"}},
        {"asset_type": "person", "action": "update", "fields": {
            "姓名": "赵六",
            "类型": "一级造价师", "证书名称": "一级造价工程师证",
            "证书有效期至": "2026-05-01", "编号": "B1"}},
    ]
    result = import_service.confirm_items(db, items)
    assert result["created"] == 1 and result["updated"] == 1
    person = db.get_assets("person")[0]
    certs = person["fields"]["证书"]
    assert len(certs) == 2
    names = {c["证书名称"] for c in certs}
    assert names == {"一级建造师执业资格证", "一级造价工程师证"}
    assert person["expiry_date"] == "2026-05-01"  # 最早有效期


def test_confirm_same_cert_merges_not_duplicates(db):
    item = {"asset_type": "person", "action": "new", "fields": {
        "姓名": "孙七", "类型": "一级建造师", "证书名称": "一级建造师执业资格证",
        "证书有效期至": "2027-03-01"}}
    import_service.confirm_items(db, [item])
    # 同类型同证书名再次 confirm → 更新而非追加
    item2 = {"asset_type": "person", "action": "update", "fields": {
        "姓名": "孙七", "类型": "一级建造师", "证书名称": "一级建造师执业资格证",
        "证书有效期至": "2028-03-01", "编号": "NEW1"}}
    import_service.confirm_items(db, [item2])
    certs = db.get_assets("person")[0]["fields"]["证书"]
    assert len(certs) == 1
    assert certs[0]["有效期至"] == "2028-03-01" and certs[0]["编号"] == "NEW1"


def test_dedup_check_same_type_and_name_only(db):
    db.create_asset("person", "赵六", {
        "证书": [{"类型": "一级建造师", "证书名称": "一级建造师执业资格证",
                  "有效期至": "2027-03-01", "编号": "A1"}]})
    items = [
        {"id": "1", "asset_type": "person", "file_name": "a.pdf", "warnings": [],
         "fields": {"姓名": "赵六", "类型": "一级造价师", "证书名称": "一级造价工程师证"}},
        {"id": "2", "asset_type": "person", "file_name": "b.pdf", "warnings": [],
         "fields": {"姓名": "赵六", "类型": "一级建造师", "证书名称": "一级建造师执业资格证"}},
    ]
    import_service._dedup_check(db, items)
    assert items[0]["warnings"] == []  # 同人不同类型不同证 → 不算重复
    assert any("疑似重复" in w for w in items[1]["warnings"])  # 同人同类型同证 → 疑似重复
