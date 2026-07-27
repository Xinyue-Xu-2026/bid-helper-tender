from pathlib import Path


def extract_pdf_text(path: str) -> str:
    import fitz
    text_parts = []
    with fitz.open(path) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def extract_docx_text(path: str) -> str:
    from docx import Document
    document = Document(path)
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def extract_text(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix in (".docx", ".doc"):
        return extract_docx_text(path)
    raise ValueError(f"Unsupported file type: {suffix}")
