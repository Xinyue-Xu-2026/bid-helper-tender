"""编写工作台业务编排：模板画像、目录大纲、单节生成。"""
import re
import shutil
import uuid
from pathlib import Path

from app import config
from app.core.extractor import extract_text
from app.core.llm_parser import LLMParseError
from app.core.outline_generator import generate_outline
from app.core.section_writer import build_section_prompt, stream_section
from app.core.template_analyzer import analyze_template
from app.core.template_outline import build_tree, parse_outline, section_target_chars
from app.core.template_strategy import ExampleReferenceStrategy
from app.core.title_adapter import adapt_titles
from app.db import Database
from app.settings_store import get_api_key, get_model

# 章节标题去噪（与前端 WriteView 旧 matchedReqs 一致）：去掉编号/级别字后按空格分词
_TITLE_NOISE_RE = re.compile(r"[第章节一二三四五六七八九十\d.（）()、\s]")


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
        return self.db.replace_sections(project_id, outline)

    # ---------- 模板章节树 ----------
    def sections_from_template(self, project_id: int, template_id: int) -> list:
        """解析模板 docx 章节树并覆盖项目 sections，返回嵌套树。

        项目/模板不存在抛 ValueError；模板无标题结构抛 TemplateOutlineError。
        """
        if not self.db.get_project(project_id):
            raise ValueError("项目不存在")
        template = self.db.get_template(template_id)
        if not template:
            raise ValueError("模板不存在")
        path = template.get("file_path") or ""
        if not path or not Path(path).exists():
            raise ValueError("模板文件不存在")
        outline = parse_outline(path)
        return self.db.replace_sections(project_id, build_tree(outline))

    # ---------- 标题改写 ----------
    def adapt_section_titles(self, project_id: int) -> list:
        """AI 把当前章节树标题项目化改写并逐节点落库，返回最新嵌套树。

        项目不存在抛 ValueError；LLM 失败/数量不一致抛 LLMParseError（不改原标题）。
        """
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("项目不存在")
        flat = self.db.get_sections_flat(project_id)
        if not flat:
            return []
        api_key = get_api_key()
        if not api_key:
            raise LLMParseError("未配置 API Key")
        requirements = self.db.get_requirements(project_id)
        req_summary = "\n".join(r["content"] for r in requirements)
        titles = [f"{'　' * (s['level'] - 1)}{s['title']}" for s in flat]
        new_titles = adapt_titles(titles, project.get("name") or "", req_summary,
                                  api_key, get_model())
        for s, t in zip(flat, new_titles):
            self.db.update_section(s["id"], title=t)
        return self.db.get_sections_tree(project_id)

    # ---------- 单节生成 ----------
    def _pick_template(self, template_id=None):
        """按前端选定的 templateId 取模板；未给或找不到时回退最新一条模板保持兼容。"""
        if template_id:
            template = self.db.get_template(template_id)
            if template:
                return template
        templates = self.db.get_templates()
        return templates[0] if templates else None

    def get_child_sections(self, section: dict) -> list:
        """章节的直接子节列表（sort_order 序），用于逐小节生成。"""
        return [s for s in self.db.get_sections(section["project_id"])
                if s["parent_id"] == section["id"]]

    @staticmethod
    def _project_info_text(project: dict) -> str:
        """projects 表信息格式化为 prompt 开头注入文本；无有效字段返回空串。"""
        if not project:
            return ""
        lines = []
        if project.get("name"):
            lines.append(f"项目名称：{project['name']}")
        if project.get("client"):
            lines.append(f"招标人/客户：{project['client']}")
        if project.get("project_type"):
            lines.append(f"项目类型：{project['project_type']}")
        if project.get("bid_date"):
            lines.append(f"投标截止/开标日期：{project['bid_date']}")
        if project.get("notes"):
            lines.append(f"项目备注：{project['notes']}")
        return ("项目信息：\n" + "\n".join(lines)) if lines else ""

    @staticmethod
    def _match_requirements(requirements: list, title: str) -> list:
        """按章节标题自动匹配招标要求：标题去噪分词（≥2 字）匹配 requirements.content；
        无有效词时返回全部要求（与前端旧 matchedReqs 逻辑一致）。"""
        cleaned = _TITLE_NOISE_RE.sub(" ", title or "")
        tokens = [t for t in cleaned.split(" ") if len(t) >= 2]
        if not tokens:
            return list(requirements)
        return [r for r in requirements
                if any(t in (r.get("content") or "") for t in tokens)]

    def assemble_section_prompt(self, project_id: int, section_id: int,
                                asset_ids: list, material_ids: list, req_ids: list,
                                template_id=None) -> str:
        """组装单节生成 prompt：项目信息 + 目录链 + 自动匹配要求 + 风格画像 + 篇幅要求 + 资产/素材。

        req_ids 保留兼容但忽略——要求按章节标题自动匹配。
        """
        section = self.db.get_section(section_id)
        if not section:
            raise ValueError("章节不存在")
        flat = self.db.get_sections_flat(project_id)
        outline_titles = [f"{'　' * (s['level'] - 1)}{s['title']}" for s in flat]
        requirements = self.db.get_requirements(project_id)
        selected = self._match_requirements(requirements, section["title"])
        project_info = self._project_info_text(self.db.get_project(project_id) or {})
        style_text = ""
        target_chars = 0
        template = self._pick_template(template_id)
        if template:
            style_text = ExampleReferenceStrategy().build_prompt(template)
            target_chars = self._section_target_chars(template, section)
        assets_text = self._assets_excerpt(asset_ids, material_ids)
        return build_section_prompt(section["title"], outline_titles, selected,
                                    style_text, assets_text, target_chars, project_info)

    @staticmethod
    def _section_target_chars(template: dict, section: dict) -> int:
        """统计模板中对应章节的正文实测字数；非 docx / 解析失败时返回 0（不注入篇幅要求）。"""
        path = template.get("file_path") or ""
        if not path or Path(path).suffix.lower() != ".docx" or not Path(path).exists():
            return 0
        try:
            return section_target_chars(path, section["title"], section.get("level"))
        except Exception:
            return 0

    @staticmethod
    def _format_asset_fields(fields: dict) -> str:
        """资产字段格式化为可读文本；值为 dict 列表（如"业绩"数组）时逐条展开为
        "1. 项目名称：X，年份：Y…"，不再用 Python repr。"""
        lines = []
        for k, v in fields.items():
            if isinstance(v, list) and v and all(isinstance(i, dict) for i in v):
                lines.append(f"{k}：")
                for n, item in enumerate(v, 1):
                    entry = "，".join(f"{ik}：{iv}" for ik, iv in item.items())
                    lines.append(f"  {n}. {entry}")
            elif isinstance(v, list):
                lines.append(f"{k}：" + "；".join(str(i) for i in v))
            elif isinstance(v, dict):
                lines.append(f"{k}：" + "；".join(f"{ik}：{iv}" for ik, iv in v.items()))
            else:
                lines.append(f"{k}：{v}")
        return "\n".join(lines)

    def _assets_excerpt(self, asset_ids: list, material_ids: list) -> str:
        """结构化资产按字段拼接；素材 PDF/Word 经 extractor 抽文本（截断 5000 字），Excel/图片仅注入文件名。"""
        parts = []
        for aid in asset_ids:
            a = self.db.get_asset(aid)
            if not a:
                continue
            fields = a.get("fields") or {}
            parts.append(f"【{a['name']}】\n{self._format_asset_fields(fields)}")
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
