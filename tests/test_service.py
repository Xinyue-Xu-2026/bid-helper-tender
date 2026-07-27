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
