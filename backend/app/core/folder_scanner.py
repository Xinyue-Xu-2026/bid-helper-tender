"""共享文件夹递归遍历与文件类型分发。"""
from pathlib import Path
from typing import List, Tuple

SUPPORTED_EXTS = {".xlsx", ".xls", ".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg"}


def scan_folder(folder: str) -> Tuple[List[Path], List[dict]]:
    """递归收集支持的文件；返回 (files, errors)。路径问题以中文 errors 返回。"""
    if not folder or not folder.strip():
        return [], [{"filename": "", "reason": "未配置共享文件夹路径，请先在设置中填写"}]
    root = Path(folder.strip())
    if not root.exists():
        return [], [{"filename": "", "reason": f"共享文件夹不存在：{folder}"}]
    if not root.is_dir():
        return [], [{"filename": "", "reason": f"共享文件夹路径不是目录：{folder}"}]
    try:
        files = [p for p in sorted(root.rglob("*"))
                 if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    except OSError as exc:
        return [], [{"filename": "", "reason": f"读取共享文件夹失败：{exc}"}]
    if not files:
        return [], [{"filename": "",
                     "reason": "共享文件夹中没有可识别的文件（支持 xlsx/xls/pdf/docx/doc/png/jpg/jpeg）"}]
    return files, []
