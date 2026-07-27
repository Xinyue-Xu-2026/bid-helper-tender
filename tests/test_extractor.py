from pathlib import Path
from bidhelper.extractor import extract_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_docx():
    text = extract_text(str(FIXTURES / "sample_tender.docx"))
    assert "A4" in text
    assert "2026年8月13日" in text
