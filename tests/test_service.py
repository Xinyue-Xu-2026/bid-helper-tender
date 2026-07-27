from pathlib import Path
from bidhelper.service import BidService
from bidhelper.db import Database


def test_import_and_parse(tmp_path):
    db_path = tmp_path / "app.db"
    service = BidService(str(db_path))
    pid = service.create_project("测试", "单位", "2026-08-15", "审计类", "")

    fixture = Path(__file__).parent / "fixtures" / "sample_tender.docx"
    service.import_tender(pid, str(fixture))

    service.parse_and_save_requirements(pid)
    reqs = service.db.get_requirements(pid)
    assert len(reqs) > 0


def test_export_requirements_excel(tmp_path):
    db_path = tmp_path / "app.db"
    service = BidService(str(db_path))
    pid = service.create_project("导出项目", "单位", "2026-08-15", "审计类", "")
    service.db.create_requirement(pid, "废标项", "必须签字", "第四章", "高", "待响应")

    dest = str(tmp_path / "清单.xlsx")
    result = service.export_requirements_excel(pid, dest)
    assert Path(result).exists()


def test_export_requirements_excel_project_not_found(tmp_path):
    service = BidService(str(tmp_path / "app.db"))
    try:
        service.export_requirements_excel(999, str(tmp_path / "x.xlsx"))
        assert False, "should raise ValueError"
    except ValueError:
        pass
