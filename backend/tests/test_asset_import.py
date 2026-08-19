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
