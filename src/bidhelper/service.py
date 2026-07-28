import shutil
from datetime import datetime
from pathlib import Path

from bidhelper import config
from bidhelper.db import Database
from bidhelper.excel_exporter import export_requirements
from bidhelper.extractor import extract_text
from bidhelper.llm_parser import LLMParseError, parse_with_llm
from bidhelper.parser import parse_tender
from bidhelper.postprocess import dedupe_and_filter
from bidhelper.settings_store import get_api_key, get_model


class BidService:
    def __init__(self, db_path: str = None):
        self.db = Database(db_path)
        self.db.init_schema()

    def create_project(self, name: str, client: str, bid_date: str,
                       project_type: str, notes: str) -> int:
        return self.db.create_project(name, client, bid_date, project_type, notes)

    def import_tender(self, project_id: int, source_path: str) -> Path:
        config.ensure_dirs()
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("Project not found")

        src = Path(source_path)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project["name"])
        dest_name = f"{safe_name}_{src.name}"
        dest = config.IMPORTS_DIR / dest_name
        shutil.copy2(src, dest)

        self.db.update_project(project_id, notes=f"招标文件：{dest}")
        return dest

    def parse_and_save_requirements(self, project_id: int) -> dict:
        """解析招标文件并保存要求。返回 {"requirements": [...], "engine": "ai"|"rule", "warning": str|None}。"""
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        notes = project.get("notes", "")
        if "招标文件：" not in notes:
            raise ValueError("No imported tender file")

        tender_path = notes.split("招标文件：")[-1].strip()
        text = extract_text(tender_path)

        engine = "rule"
        warning = None
        reqs = None
        api_key = get_api_key()
        if api_key:
            try:
                reqs = parse_with_llm(text, api_key, get_model())
                engine = "ai"
            except LLMParseError as exc:
                warning = str(exc)
        if reqs is None:
            reqs = parse_tender(text)

        reqs = dedupe_and_filter(reqs)

        self.db.delete_requirements_by_project(project_id)
        for req in reqs:
            self.db.create_requirement(
                project_id=project_id,
                category=req["category"],
                content=req["content"],
                source=req["source"],
                confidence=req["confidence"],
                status=req["status"],
            )
        return {"requirements": reqs, "engine": engine, "warning": warning}

    def export_requirements_excel(self, project_id: int, dest_path: str) -> Path:
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        requirements = self.db.get_requirements(project_id)
        return export_requirements(project, requirements, dest_path)
