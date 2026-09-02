from datetime import datetime

import pytest
from openpyxl import Workbook

from app.db import Database
from app.services.asset_service import import_assets_excel


@pytest.fixture()
def db(db_path):
    d = Database(db_path)
    d.init_schema()
    return d


def _xlsx(path, headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_import_credit(db, tmp_path):
    f = tmp_path / "certs.xlsx"
    _xlsx(f, ["证书名称", "发证机关", "有效期至"], [
        ["营业执照", "市监局", datetime(2027, 1, 1)],
        ["资质证书A", "住建厅", "2027/6/30"],
        ["", "缺名行", "2027-01-01"],  # 无名称 → 记入 errors
    ])
    result = import_assets_excel(db, "credit", str(f))
    assert result["imported"] == 2
    assert len(result["errors"]) == 1 and result["errors"][0]["row"] == 4
    assets = db.get_assets("credit")
    assert assets[1]["expiry_date"] == "2027-01-01"
    assert assets[0]["expiry_date"] == "2027-06-30"
    assert assets[1]["fields"]["发证机关"] == "市监局"


def test_import_person(db, tmp_path):
    f = tmp_path / "persons.xlsx"
    _xlsx(f, ["姓名", "职称", "证书有效期至"], [["张三", "高工", "2026.12.31"]])
    result = import_assets_excel(db, "person", str(f))
    assert result["imported"] == 1
    p = db.get_assets("person")[0]
    assert p["expiry_date"] == "2026-12-31" and p["fields"]["职称"] == "高工"


def test_import_person_new_template_multi_row_merge(db, tmp_path):
    """新模板表头：点号/非点号混用；同一人两行合并为多证书；
    点号日期字符串与数字编号规范化。"""
    f = tmp_path / "persons.xlsx"
    _xlsx(f, ["姓名", "部门", "职称", "联系方式", "类型", "证书.编号",
              "专业", "执业时间", "证书.有效期至"], [
        ["张三", "造价部", "高工", "13800000000", "一级造价师", 32092664,
         "土建", "2013.7.23", "2029.5.28"],
        ["张三", None, None, None, "一级建造师", "A123",
         "建筑工程", datetime(2016, 3, 1), datetime(2027, 12, 31)],
    ])
    result = import_assets_excel(db, "person", str(f))
    assert result["imported"] == 2
    assert result["errors"] == []
    p = db.get_assets("person")[0]
    assert p["fields"]["部门"] == "造价部" and p["fields"]["职称"] == "高工"
    certs = p["fields"]["证书"]
    assert len(certs) == 2
    c1 = next(c for c in certs if c["类型"] == "一级造价师")
    assert c1["编号"] == "32092664"  # 数字编号转字符串
    assert c1["专业"] == "土建"
    assert c1["执业时间"] == "2013-07-23"  # 点号日期规范化
    assert c1["有效期至"] == "2029-05-28"
    c2 = next(c for c in certs if c["类型"] == "一级建造师")
    assert c2["编号"] == "A123"
    assert c2["执业时间"] == "2016-03-01"
    assert c2["有效期至"] == "2027-12-31"
    assert p["expiry_date"] == "2027-12-31"  # 最早有效期


def test_import_person_dotted_cert_headers(db, tmp_path):
    """证书列全点号表头；浮点整数编号去小数点；斜杠日期规范化。"""
    f = tmp_path / "persons2.xlsx"
    _xlsx(f, ["姓名", "证书.类型", "证书.编号", "证书.专业",
              "证书.执业时间", "证书.有效期至"], [
        ["李四", "监理工程师", 456.0, "市政公用", datetime(2020, 1, 15), "2030/3/31"],
    ])
    result = import_assets_excel(db, "person", str(f))
    assert result["imported"] == 1
    cert = db.get_assets("person")[0]["fields"]["证书"][0]
    assert cert["类型"] == "监理工程师"
    assert cert["编号"] == "456"  # 浮点整数形态去小数点
    assert cert["专业"] == "市政公用"
    assert cert["执业时间"] == "2020-01-15"
    assert cert["有效期至"] == "2030-03-31"
