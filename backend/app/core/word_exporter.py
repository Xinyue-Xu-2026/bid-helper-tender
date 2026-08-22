"""Word 导出：以模板样式库建新文档，章节树映射标题样式，文首插 TOC 域。"""
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def _clear_body(doc):
    """清空正文（保留 sectPr），用于在模板文档基础上重建内容。"""
    body = doc.element.body
    for el in list(body):
        if el.tag.endswith("}sectPr"):
            continue
        body.remove(el)


def _insert_toc_field(doc):
    """在文首插入 Word 原生 TOC 域（用户在 Word 中「更新域」生成目录）。"""
    para = doc.add_paragraph()
    run = para.add_run()
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    separate = OxmlElement("w:fldChar"); separate.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    run._r.append(begin); run._r.append(instr); run._r.append(separate); run._r.append(end)


def export_word(project: dict, template: dict, sections: list, dest_path: str) -> str:
    """导出标书 Word。sections 为空抛 ValueError；模板缺失回退默认样式。返回写出路径。"""
    if not sections:
        raise ValueError("章节树为空，无法导出")
    template_path = (template or {}).get("file_path") or ""
    if template_path and Path(template_path).exists():
        doc = Document(template_path)   # 继承模板 styles.xml（标题/正文样式保真）
    else:
        doc = Document()                # 回退 python-docx 默认样式
    _clear_body(doc)
    _insert_toc_field(doc)
    for s in sections:
        level = int(s.get("level") or 1)
        if level > 3:
            level = 3
        elif level < 1:
            level = 1
        doc.add_heading(s["title"], level=level)
        content = (s.get("content") or "").strip()
        if content:
            doc.add_paragraph(content)
    doc.save(dest_path)
    return dest_path
