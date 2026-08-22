"""编写工作台业务编排：模板画像、目录大纲、单节生成。"""
import shutil
import uuid
from pathlib import Path

from app import config
from app.core.extractor import extract_text
from app.core.llm_parser import LLMParseError
from app.core.outline_generator import generate_outline
from app.core.section_writer import build_section_prompt, stream_section
from app.core.template_analyzer import analyze_template
from app.core.template_strategy import ExampleReferenceStrategy
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
        dest = config.TEMPLATES_DIR / f"{safe_name}_{uuid.uuid4().hex[:8]}{src.suffix.lower()}"
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

    # ---------- 目录大纲 ----------
    def generate_outline_and_save(self, project_id: int) -> list:
        """AI 生成目录初稿并落库（覆盖旧章节）；项目/要求缺失抛 ValueError，未配 Key 抛 LLMParseError。"""
        if not self.db.get_project(project_id):
            raise ValueError("项目不存在")
        requirements = self.db.get_requirements(project_id)
        if not requirements:
            raise ValueError("该项目暂无要求清单，请先解析招标文件")
        api_key = get_api_key()
        if not api_key:
            raise LLMParseError("未配置 API Key")
        outline = generate_outline(requirements, api_key, get_model())
        self.db.delete_sections_by_project(project_id)
        counter = {"n": 0}

        def flatten(nodes, parent_id):
            for node in nodes:
                counter["n"] += 1
                sid = self.db.create_section(
                    project_id, parent_id, node["title"], node["level"], counter["n"])
                flatten(node.get("children", []), sid)

        flatten(outline, 0)
        return self.db.get_sections_tree(project_id)

    # ---------- 单节生成 ----------
    def assemble_section_prompt(self, project_id: int, section_id: int,
                                asset_ids: list, material_ids: list, req_ids: list) -> str:
        """组装单节生成 prompt：目录链 + 关联要求 + 风格画像 + 资产/素材文本。"""
        section = self.db.get_section(section_id)
        if not section:
            raise ValueError("章节不存在")
        flat = self.db.get_sections_flat(project_id)
        outline_titles = [f"{'　' * (s['level'] - 1)}{s['title']}" for s in flat]
        requirements = self.db.get_requirements(project_id)
        selected = [r for r in requirements if r["id"] in req_ids]
        style_text = ""
        templates = self.db.get_templates()
        if templates:
            style_text = ExampleReferenceStrategy().build_prompt(templates[0])
        assets_text = self._assets_excerpt(asset_ids, material_ids)
        return build_section_prompt(section["title"], outline_titles, selected, style_text, assets_text)

    def _assets_excerpt(self, asset_ids: list, material_ids: list) -> str:
        """结构化资产按字段拼接；素材 PDF/Word 经 extractor 抽文本（截断 5000 字），Excel/图片仅注入文件名。"""
        parts = []
        for aid in asset_ids:
            a = self.db.get_asset(aid)
            if not a:
                continue
            fields = a.get("fields") or {}
            field_txt = "；".join(f"{k}: {v}" for k, v in fields.items())
            parts.append(f"【{a['name']}】{field_txt}")
        for mid in material_ids:
            m = self.db.get_material(mid)
            if not m:
                continue
            ft = (m.get("file_type") or "").lower()
            if ft in ("pdf", "docx", "doc"):
                try:
                    parts.append(extract_text(m["file_path"])[:5000])
                except Exception:
                    parts.append(f"【素材文件】{Path(m['file_path']).name}")
            else:
                parts.append(f"【素材文件（{ft}）】{Path(m['file_path']).name}（图片/表格内容请人工参考）")
        return "\n\n".join(parts)

    def stream_section_text(self, prompt: str):
        """读设置注入 key/model，流式生成单节正文。"""
        return stream_section(prompt, get_api_key(), get_model())
