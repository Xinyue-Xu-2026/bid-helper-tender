from pathlib import Path
from bidhelper.service import BidService
from bidhelper.db import Database


def test_import_and_parse(tmp_path):
    db_path = tmp_path / "app.db"
    service = BidService(str(db_path))
    pid = service.create_project("测试", "单位", "2026-08-15", "审计类", "")

    fixture = Path(__file__).parent / "fixtures" / "sample_tender.docx"
    service.import_tender(pid, str(fixture))

    result = service.parse_and_save_requirements(pid)
    assert result["engine"] == "rule"
    assert result["warning"] is None
    assert len(result["requirements"]) > 0
    reqs = service.db.get_requirements(pid)
    assert len(reqs) == len(result["requirements"])


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


def _fake_llm_success(text, api_key, model="kimi-k2.6", client=None):
    return [
        {"category": "评分项", "content": "价格分 10 分", "source": "第五章", "confidence": "高", "status": "待响应"},
        {"category": "废标项", "content": "应交未交投标保证金的按无效投标处理", "source": "第五章 3.4", "confidence": "高", "status": "待响应"},
    ]


def _fake_llm_failure(text, api_key, model="kimi-k2.6", client=None):
    from bidhelper.llm_parser import LLMParseError
    raise LLMParseError("API 调用失败：模拟超时")


def test_parse_engine_ai_success(tmp_path, monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-fake")
    monkeypatch.setattr("bidhelper.service.parse_with_llm", _fake_llm_success)
    service = BidService(str(tmp_path / "app.db"))
    pid = service.create_project("测试", "单位", "2026-08-15", "审计类", "")
    service.import_tender(pid, str(Path(__file__).parent / "fixtures" / "sample_tender.docx"))

    result = service.parse_and_save_requirements(pid)
    assert result["engine"] == "ai"
    assert result["warning"] is None
    assert [r["content"] for r in result["requirements"]] == ["价格分 10 分", "应交未交投标保证金的按无效投标处理"]
    assert len(service.db.get_requirements(pid)) == 2


def test_parse_engine_fallback_on_llm_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-fake")
    monkeypatch.setattr("bidhelper.service.parse_with_llm", _fake_llm_failure)
    service = BidService(str(tmp_path / "app.db"))
    pid = service.create_project("测试", "单位", "2026-08-15", "审计类", "")
    service.import_tender(pid, str(Path(__file__).parent / "fixtures" / "sample_tender.docx"))

    result = service.parse_and_save_requirements(pid)
    assert result["engine"] == "rule"
    assert "模拟超时" in result["warning"]
    assert len(result["requirements"]) > 0  # 规则解析兜底有结果


def test_parse_engine_rule_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setattr("bidhelper.service.get_api_key", lambda: "")
    called = []
    monkeypatch.setattr("bidhelper.service.parse_with_llm", lambda *a, **kw: called.append(1))
    service = BidService(str(tmp_path / "app.db"))
    pid = service.create_project("测试", "单位", "2026-08-15", "审计类", "")
    service.import_tender(pid, str(Path(__file__).parent / "fixtures" / "sample_tender.docx"))

    result = service.parse_and_save_requirements(pid)
    assert result["engine"] == "rule"
    assert result["warning"] is None
    assert called == []  # 无 Key 时不得调用 LLM
