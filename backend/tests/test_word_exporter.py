"""Word 导出测试。"""
import pytest
from docx import Document

from app.core.word_exporter import export_word


SECTIONS = [
    {"title": "第一章 资格审查", "level": 1, "content": "正文一"},
    {"title": "1.1 营业执照", "level": 2, "content": "正文二"},
    {"title": "1.1.1 副本", "level": 3, "content": ""},
    {"title": "超深章", "level": 5, "content": ""},
]


def test_export_word_toc_and_headings(tmp_path):
    dest = tmp_path / "out.docx"
    export_word({"name": "测试项目"}, None, SECTIONS, str(dest))
    assert dest.exists()
    doc = Document(str(dest))
    xml = doc.element.body.xml
    assert "instrText" in xml and "TOC" in xml          # TOC 域存在
    heads = [p for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert heads[0].text == "第一章 资格审查"
    assert heads[0].style.name == "Heading 1"
    assert heads[1].style.name == "Heading 2"
    assert heads[2].style.name == "Heading 3"
    assert heads[3].style.name == "Heading 3"           # 超深章截断到 3 级


def test_export_word_empty_sections(tmp_path):
    with pytest.raises(ValueError, match="章节树为空"):
        export_word({"name": "x"}, None, [], str(tmp_path / "e.docx"))


def test_export_word_with_template(tmp_path):
    tpl = tmp_path / "tpl.docx"
    Document().save(str(tpl))
    dest = tmp_path / "out.docx"
    export_word({"name": "x"}, {"file_path": str(tpl)},
                [{"title": "A", "level": 1, "content": "B"}], str(dest))
    doc = Document(str(dest))
    heads = [p for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert heads[0].text == "A"
