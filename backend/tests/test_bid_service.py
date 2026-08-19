import pytest

from app.db import Database
from app.services.bid_service import BidService


@pytest.fixture()
def svc(db_path):
    db = Database(db_path)
    db.init_schema()
    return BidService(db_path), db


def _make_docx(path, text):
    from docx import Document
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)


def test_import_tender_sets_path(svc, tmp_path):
    service, db = svc
    pid = db.create_project("某某项目")
    src = tmp_path / "招标文件.docx"
    _make_docx(src, "投标人资格条件：具备独立法人资格")
    dest = service.import_tender(pid, str(src))
    assert dest.exists()
    assert "招标文件" in db.get_project(pid)["tender_file_path"]


def test_import_tender_project_missing(svc, tmp_path):
    service, _ = svc
    with pytest.raises(ValueError):
        service.import_tender(999, str(tmp_path / "x.docx"))


def test_parse_rule_fallback_without_key(svc, tmp_path, monkeypatch):
    service, db = svc
    monkeypatch.setattr("app.services.bid_service.get_api_key", lambda: "")
    pid = db.create_project("某某项目")
    src = tmp_path / "招标文件.docx"
    _make_docx(src, "第一章 总则\n投标人资格条件：具备独立法人资格\n未按要求密封的投标文件将作废标处理")
    service.import_tender(pid, str(src))
    stages = []
    result = service.parse_and_save_requirements(pid, progress=stages.append)
    assert result["engine"] == "rule"
    assert len(result["requirements"]) >= 1
    assert any("规则" in s or "API Key" in s for s in stages)
    assert len(db.get_requirements(pid)) == len(result["requirements"])


def test_parse_without_tender_raises(svc):
    service, db = svc
    pid = db.create_project("空项目")
    with pytest.raises(ValueError, match="招标文件"):
        service.parse_and_save_requirements(pid)
