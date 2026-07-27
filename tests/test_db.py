import pytest
from bidhelper.db import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    database.init_schema()
    return database


def test_create_and_get_project(db):
    pid = db.create_project("测试项目", "招标单位", "2026-08-15", "审计类", "备注")
    assert pid == 1
    project = db.get_project(pid)
    assert project["name"] == "测试项目"


def test_update_project(db):
    pid = db.create_project("旧名称", "A单位", "2026-08-15", "审计类", "")
    db.update_project(pid, name="新名称")
    project = db.get_project(pid)
    assert project["name"] == "新名称"


def test_delete_project(db):
    pid = db.create_project("待删除", "A单位", "2026-08-15", "审计类", "")
    db.delete_project(pid)
    assert db.get_project(pid) is None


def test_requirement_crud(db):
    pid = db.create_project("项目", "单位", "2026-08-15", "审计类", "")
    rid = db.create_requirement(pid, "废标项", "必须签字", "第四章", "高", "待响应")
    reqs = db.get_requirements(pid)
    assert len(reqs) == 1
    assert reqs[0]["content"] == "必须签字"
    db.update_requirement(rid, status="已响应")
    reqs = db.get_requirements(pid)
    assert reqs[0]["status"] == "已响应"
    db.delete_requirement(rid)
    assert len(db.get_requirements(pid)) == 0


def test_delete_project_cascades_requirements(db):
    pid = db.create_project("级联测试", "单位", "2026-08-15", "审计类", "")
    db.create_requirement(pid, "废标项", "必须签字", "第四章", "高", "待响应")
    db.create_requirement(pid, "格式要求", "A4打印", "2.5", "中", "待响应")
    db.delete_project(pid)
    assert db.get_requirements(pid) == []
