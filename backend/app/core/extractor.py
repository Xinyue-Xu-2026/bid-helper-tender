from pathlib import Path


def extract_pdf_text(path: str) -> str:
    import fitz
    text_parts = []
    with fitz.open(path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def extract_docx_text(path: str) -> str:
    """按文档顺序提取段落与表格文本；表格行以 " | " 连接（合并单元格去重）。"""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(path)
    parts = []
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            para = Paragraph(child, document)
            if para.text.strip():
                parts.append(para.text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                deduped = []
                for c in cells:
                    if not deduped or c != deduped[-1]:
                        deduped.append(c)
                line = " | ".join(deduped).strip()
                if line:
                    parts.append(line)
    return "\n".join(parts)


def extract_text(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix in (".docx", ".doc"):
        return extract_docx_text(path)
    raise ValueError(f"Unsupported file type: {suffix}")
