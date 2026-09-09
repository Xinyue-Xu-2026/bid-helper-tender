"""商务标底稿（bid_templates）数据层测试。"""
import sqlite3

from app.db import Database


def test_bid_templates_tenderer_column_migration(tmp_path):
    """P3 迁移回归：老库 bid_templates 无 tenderer 列 → init_schema 幂等补列，
    旧行 tenderer 默认 ''；重复 init_schema 不炸。"""
    db_file = tmp_path / "old.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "CREATE TABLE bid_templates ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,"
        "name TEXT NOT NULL, file_path TEXT DEFAULT '',"
        "source TEXT DEFAULT 'tender-cut', source_path TEXT DEFAULT '',"
        "cut_start TEXT DEFAULT '', cut_end TEXT DEFAULT '',"
        "bindings TEXT DEFAULT '{}',"
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("INSERT INTO bid_templates (project_id, name) VALUES (1, '旧底稿')")
    conn.commit()
    conn.close()
    db = Database(str(db_file))
    db.init_schema()
    db.init_schema()  # 幂等
    row = db.get_project_bid_template(1)
    assert row["tenderer"] == ""
    # 新列可写
    db.update_bid_template(row["id"], tenderer="某某中心")
    assert db.get_project_bid_template(1)["tenderer"] == "某某中心"


def test_bid_template_tenderer_roundtrip(db_path):
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    bid = db.create_bid_template(pid, "底稿", "f.docx", tenderer="某服务中心")
    assert db.get_bid_template(bid)["tenderer"] == "某服务中心"


def test_bid_template_roundtrip(db_path):
    """create + get_project_bid_template 往返，bindings dict 正确解析。"""
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    bid = db.create_bid_template(
        pid, "商务标底稿", "files/bid.docx",
        source_path="uploads/tender.docx",
        cut_start="第四章 商务部分", cut_end="第五章",
        bindings={"project_name": "测试项目", "amount": "100万元"})
    assert isinstance(bid, int)
    t = db.get_project_bid_template(pid)
    assert t["id"] == bid
    assert t["project_id"] == pid
    assert t["name"] == "商务标底稿"
    assert t["file_path"] == "files/bid.docx"
    assert t["source"] == "tender-cut"
    assert t["source_path"] == "uploads/tender.docx"
    assert t["cut_start"] == "第四章 商务部分"
    assert t["cut_end"] == "第五章"
    assert t["bindings"] == {"project_name": "测试项目", "amount": "100万元"}
    # get_bid_template 按 id 取同一行
    assert db.get_bid_template(bid)["bindings"]["amount"] == "100万元"
    # 无项目底稿返回 None
    assert db.get_project_bid_template(db.create_project("空项目")) is None
    assert db.get_bid_template(99999) is None


def test_get_project_bid_template_returns_latest(db_path):
    """每项目多条时 get_project_bid_template 返回 id 最大者。"""
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    first = db.create_bid_template(pid, "旧底稿", "old.docx")
    second = db.create_bid_template(pid, "新底稿", "new.docx")
    t = db.get_project_bid_template(pid)
    assert t["id"] == second
    assert t["name"] == "新底稿"
    assert first != second


def test_update_bid_template(db_path):
    """update bindings（dict 传入）→ 读回一致；非法字段被忽略。"""
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    bid = db.create_bid_template(pid, "底稿", "a.docx",
                                 source="upload", bindings={"k1": "v1"})
    assert db.get_bid_template(bid)["source"] == "upload"
    db.update_bid_template(bid, name="改名", cut_start="第一章",
                           bindings={"k2": 2},
                           project_id=12345, source="hack", bogus="x")
    t = db.get_bid_template(bid)
    assert t["name"] == "改名"
    assert t["cut_start"] == "第一章"
    assert t["bindings"] == {"k2": 2}
    # 非法字段被忽略
    assert t["project_id"] == pid
    assert t["source"] == "upload"
    assert "bogus" not in t


def test_delete_bid_template_and_cascade(db_path):
    """delete_bid_template 生效；删项目级联删底稿（FK CASCADE）。"""
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    bid1 = db.create_bid_template(pid, "A", "a.docx")
    db.delete_bid_template(bid1)
    assert db.get_bid_template(bid1) is None
    bid2 = db.create_bid_template(pid, "B", "b.docx")
    db.delete_project(pid)
    assert db.get_bid_template(bid2) is None


def test_bid_template_bad_json_fallback(db_path):
    """bindings 列存入坏 JSON（直接 SQL 写）→ _bid_template_row 回退 {}。"""
    db = Database(db_path)
    db.init_schema()
    pid = db.create_project("测试项目")
    bid = db.create_bid_template(pid, "底稿", "a.docx")
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE bid_templates SET bindings = ? WHERE id = ?",
                     ("{不是合法JSON", bid))
    assert db.get_bid_template(bid)["bindings"] == {}
