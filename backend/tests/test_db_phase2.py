"""二期数据层测试：templates / materials / sections。"""
from app.db import Database


def test_templates_roundtrip(db_path):
    db = Database(db_path)
    db.init_schema()
    tid = db.create_template("市政标书模板", "/tmp/t.docx")
    t = db.get_template(tid)
    assert t["name"] == "市政标书模板"
    assert t["mode"] == "example"
    assert t["style_profile"] is None
    db.update_template(tid, style_profile="风格画像文本")
    assert db.get_template(tid)["style_profile"] == "风格画像文本"
    assert len(db.get_templates()) == 1
    db.delete_template(tid)
    assert db.get_templates() == []


def test_materials_roundtrip_and_cascade(db_path):
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    mid = db.create_material(pid, "/tmp/m.pdf", "pdf")
    m = db.get_material(mid)
    assert m["project_id"] == pid
    assert m["file_type"] == "pdf"
    assert len(db.get_materials(pid)) == 1
    db.delete_project(pid)  # 外键级联删除
    assert db.get_materials(pid) == []


def test_sections_tree_and_flat(db_path):
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    root = db.create_section(pid, 0, "第一章 资格审查", 1, 0)
    child = db.create_section(pid, root, "1.1 营业执照", 2, 0)
    db.update_section(child, content="正文", gen_status="已生成")
    tree = db.get_sections_tree(pid)
    assert len(tree) == 1
    assert tree[0]["title"] == "第一章 资格审查"
    assert tree[0]["children"][0]["title"] == "1.1 营业执照"
    flat = db.get_sections_flat(pid)
    assert [s["title"] for s in flat] == ["第一章 资格审查", "1.1 营业执照"]
    assert "children" not in flat[0]


def test_delete_section_recursive(db_path):
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    root = db.create_section(pid, 0, "第一章", 1, 0)
    db.create_section(pid, root, "1.1 子节", 2, 0)
    db.delete_section(root)  # 子章节连带删除
    assert db.get_sections(pid) == []


def test_delete_sections_by_project(db_path):
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    db.create_section(pid, 0, "A", 1, 0)
    db.create_section(pid, 0, "B", 1, 1)
    db.delete_sections_by_project(pid)
    assert db.get_sections(pid) == []
