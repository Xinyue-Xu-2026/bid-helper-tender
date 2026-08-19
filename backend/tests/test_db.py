from app.db import Database


def make_db(db_path):
    db = Database(db_path)
    db.init_schema()
    return db


def test_project_crud(db_path):
    db = make_db(db_path)
    pid = db.create_project("测试项目", client="某单位", bid_date="2026-09-01")
    p = db.get_project(pid)
    assert p["name"] == "测试项目" and p["tender_file_path"] == ""
    db.update_project(pid, tender_file_path="data/uploads/a.pdf")
    assert db.get_project(pid)["tender_file_path"] == "data/uploads/a.pdf"
    assert len(db.get_projects()) == 1
    db.delete_project(pid)
    assert db.get_project(pid) is None


def test_requirement_filter(db_path):
    db = make_db(db_path)
    pid = db.create_project("p")
    db.create_requirement(pid, "废标项", "未密封将废标")
    db.create_requirement(pid, "评分项", "业绩加分 10 分")
    assert len(db.get_requirements(pid)) == 2
    assert len(db.get_requirements(pid, category="废标项")) == 1
    assert len(db.get_requirements(pid, q="业绩")) == 1
    assert len(db.get_requirements(pid, status="待响应")) == 2


def test_asset_and_expiry(db_path):
    db = make_db(db_path)
    from datetime import date, timedelta
    soon = (date.today() + timedelta(days=10)).isoformat()
    far = (date.today() + timedelta(days=90)).isoformat()
    db.create_asset("credit", "营业执照", fields={"发证机关": "市监局"}, expiry_date=soon)
    db.create_asset("credit", "资质证书A", expiry_date=far)
    db.create_asset("person", "张三", fields={"职称": "高工"})
    assert len(db.get_assets("credit")) == 2
    assert len(db.get_assets("person")) == 1
    assets = db.get_assets("credit")
    assert assets[1]["fields"]["发证机关"] == "市监局"  # DESC: assets[0] 为资质证书A
    expiring = db.get_expiring_assets(days=30)
    assert len(expiring) == 1 and expiring[0]["name"] == "营业执照"
    assert expiring[0]["days_left"] == 10


def test_compliance_upsert(db_path):
    db = make_db(db_path)
    pid = db.create_project("p")
    rid = db.create_requirement(pid, "废标项", "x")
    db.set_check(pid, rid, True)
    db.set_check(pid, rid, False)  # upsert 不重复插行
    checks = db.get_checks(pid)
    assert len(checks) == 1 and checks[rid]["checked"] == 0
