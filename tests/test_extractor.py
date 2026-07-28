from pathlib import Path
from bidhelper.extractor import extract_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_docx():
    text = extract_text(str(FIXTURES / "sample_tender.docx"))
    assert "A4" in text
    assert "2026年8月13日" in text


def test_extract_docx_includes_tables():
    text = extract_text(str(FIXTURES / "sample_tender_table.docx"))
    assert "正文段落" in text
    assert "评分标准" in text
    assert "价格" in text and "10分" in text
    # 表格内容按文档顺序出现在段落之后
    assert text.index("正文段落") < text.index("评分标准")
