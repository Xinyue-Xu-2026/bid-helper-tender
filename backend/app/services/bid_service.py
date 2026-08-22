import shutil
from pathlib import Path

from app import config
from app.core.extractor import extract_text
from app.core.llm_parser import LLMParseError, parse_with_llm
from app.core.parser import parse_tender
from app.core.postprocess import dedupe_and_filter
from app.db import Database
from app.settings_store import get_api_key, get_model


class BidService:
    def __init__(self, db_path: str = None):
        self.db = Database(db_path)
        self.db.init_schema()

    def import_tender(self, project_id: int, source_path: str) -> Path:
        config.ensure_dirs()
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("项目不存在")
        src = Path(source_path)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project["name"])
        dest = config.UPLOADS_DIR / f"{safe_name}_{src.name}"
        shutil.copy2(src, dest)
        self.db.update_project(project_id, tender_file_path=str(dest))
        return dest

    def parse_and_save_requirements(self, project_id: int, progress=None) -> dict:
        """解析招标文件并保存要求。progress(stage: str) 回调各阶段进度。"""
        emit = progress or (lambda stage: None)
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("项目不存在")
        tender_path = project.get("tender_file_path") or ""
        if not tender_path:
            raise ValueError("请先上传招标文件")

        emit("正在抽取文件文本…")
        text = extract_text(tender_path)

        engine = "rule"
        warning = None
        reqs = None
        api_key = get_api_key()
        if api_key:
            emit("正在调用 Kimi AI 解析（通常需要 1-3 分钟）…")
            try:
                reqs = parse_with_llm(text, api_key, get_model())
                engine = "ai"
            except LLMParseError as exc:
                warning = str(exc)
                emit(f"AI 解析失败，回退规则解析：{warning}")
        else:
            emit("未配置 API Key，使用规则解析")
        if reqs is None:
            reqs = parse_tender(text)

        reqs = dedupe_and_filter(reqs)
        emit(f"解析完成，正在保存 {len(reqs)} 条要求…")

        self.db.replace_requirements(project_id, reqs)
        return {"requirements": reqs, "engine": engine, "warning": warning}
