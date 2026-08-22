"""编写工作台业务编排：模板画像、目录大纲、单节生成。"""
import shutil
from pathlib import Path

from app import config
from app.core.llm_parser import LLMParseError
from app.core.template_analyzer import analyze_template
from app.db import Database
from app.settings_store import get_api_key, get_model


class WriteService:
    def __init__(self, db_path: str = None):
        self.db = Database(db_path)
        self.db.init_schema()

    def import_template(self, source_path: str, name: str) -> int:
        """模板文件复制入 data/templates/ 并登记，返回模板 id。"""
        config.ensure_dirs()
        src = Path(source_path)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        dest = config.TEMPLATES_DIR / f"{safe_name}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        return self.db.create_template(name, str(dest))

    def analyze_template_profile(self, template_id: int) -> str:
        """分析模板风格画像并入库；模板不存在抛 ValueError，未配 Key/分析失败抛 LLMParseError。"""
        template = self.db.get_template(template_id)
        if not template:
            raise ValueError("模板不存在")
        api_key = get_api_key()
        if not api_key:
            raise LLMParseError("未配置 API Key")
        profile = analyze_template(template["file_path"], api_key, get_model())
        self.db.update_template(template_id, style_profile=profile)
        return profile
