"""招标文件输入归一化：.docx 原样；.doc 走 Word COM；文本型 PDF 走 pdf2docx。
转换结果按内容缓存（dest_dir/<sha1>.docx），重复调用不重复转换。"""
import hashlib
import shutil
from pathlib import Path


class InputConvertError(Exception):
    """输入文件无法归一化为 docx（路由据此返回 400）。"""


def _cache_key(src: Path) -> str:
    """缓存键：sha1(绝对路径|大小|mtime_ns)，内容或时间戳变化即换键。"""
    st = src.stat()
    raw = f"{src.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _convert_doc(src: Path, dest: Path) -> None:
    """.doc → .docx：Word COM 自动化。任何失败（如 pywin32 缺失）统一转为 InputConvertError。
    COM 需在线程内显式 CoInitialize（API 工作线程中二次转换否则失败）。"""
    _err = "无法转换 .doc 文件：需要本机安装 Microsoft Word，或将文件另存为 .docx 后重新上传"
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise InputConvertError(_err) from exc
    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(src), ReadOnly=True)
        try:
            doc.SaveAs2(str(dest), FileFormat=16)  # 16 = wdFormatXMLDocument
        finally:
            doc.Close(False)
    except Exception as exc:
        raise InputConvertError(_err) from exc
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _convert_pdf(src: Path, dest: Path) -> None:
    """文本型 PDF → .docx：先按平均每页文字量判定扫描版，再走 pdf2docx。"""
    import fitz

    with fitz.open(str(src)) as doc:
        page_count = doc.page_count
        total_chars = sum(len(page.get_text()) for page in doc)
    if page_count == 0 or total_chars / page_count < 50:
        raise InputConvertError(
            "扫描版 PDF 无法提取格式章节，请上传 Word 版招标文件，"
            "或在商务标面板手动上传底稿 docx")
    try:
        from pdf2docx import Converter
        cv = Converter(str(src))
        try:
            cv.convert(str(dest))
        finally:
            cv.close()
    except InputConvertError:
        raise
    except Exception as exc:
        raise InputConvertError(
            f"PDF 转换失败：{exc}，建议上传 Word 版招标文件") from exc


def ensure_docx(src_path: str, dest_dir: str) -> Path:
    """把招标文件归一化为 docx 并返回路径；转换结果按内容缓存。"""
    src = Path(src_path)
    suffix = src.suffix.lower()
    if suffix == ".docx":
        return src
    if suffix not in (".doc", ".pdf"):
        raise InputConvertError(f"不支持的文件类型 {suffix}")
    dest_dir_path = Path(dest_dir)
    dest_dir_path.mkdir(parents=True, exist_ok=True)
    dest = dest_dir_path / f"{_cache_key(src)}.docx"
    if dest.exists():
        return dest
    if suffix == ".doc":
        _convert_doc(src, dest)
    else:
        _convert_pdf(src, dest)
    return dest
