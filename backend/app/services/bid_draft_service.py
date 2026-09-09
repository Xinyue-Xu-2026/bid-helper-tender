"""商务标底稿编排：归一化→裁切→分类→落库；每项目仅保留一条底稿。

preview 合并逻辑：classify_tables 对当前底稿文件实时产出建议（含展示字段
header/confidence/context_heading），已存 bindings 中 confirmed 的项按
table_index 覆盖建议值（前端据此回显用户确认态）；未确认项保持建议态。
"""
import shutil
from pathlib import Path

from docx import Document

from app import config
from app.core.bid_draft import (
    cut_draft, find_format_chapter, list_headings, resolve_heading_index,
)
from app.core.bid_table_classifier import classify_tables
from app.core.bid_template_exporter import _is_toc_paragraph
from app.core.input_convert import ensure_docx
from app.db import Database

# 入库 bindings 的表项仅保留 schema 字段（TableBindingIn 对齐）；
# header/confidence/context_heading 等展示字段由 preview 实时分类供给
_BINDING_KEYS = ("table_index", "role", "columns", "person_scope",
                 "perf_scope", "label_kind", "person", "header_rows",
                 "confirmed")

_TOC_WARNING = "底稿含目录页，导出后请在 Word 中更新页码（F9）"


def _normalize_binding(item: dict) -> dict:
    """分类建议项 → bindings schema 字段（confirmed 恒 false）。"""
    return {k: item.get(k) for k in _BINDING_KEYS}


class BidDraftService:
    def __init__(self, db_path: str = None):
        self.db = Database(db_path)
        self.db.init_schema()

    def _project(self, project_id: int) -> dict:
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("项目不存在")
        return project

    def tender_docx(self, project: dict) -> Path:
        """project["tender_file_path"] 经 input_convert.ensure_docx 归一化
        （缓存目录用 UPLOADS_DIR）；未上传招标 → ValueError("请先上传招标文件")。"""
        src = (project or {}).get("tender_file_path") or ""
        if not src:
            raise ValueError("请先上传招标文件")
        return ensure_docx(src, str(config.UPLOADS_DIR))

    def headings(self, project_id: int) -> dict:
        """{"headings": [...], "suggested": {"start","end"}|None}，
        suggested 来自 find_format_chapter。"""
        project = self._project(project_id)
        docx = self.tender_docx(project)
        headings = list_headings(str(docx))
        chapter = find_format_chapter(headings)
        suggested = None
        if chapter:
            suggested = {
                "start": chapter["start"]["title"],
                "end": chapter["end"]["title"] if chapter["end"] else "",
            }
        return {"headings": headings, "suggested": suggested}

    # ---------- 内部 ----------

    @staticmethod
    def _scan_file(file_path: str):
        """对底稿文件实时产出 (outline, toc_paragraphs, suggestions)。"""
        outline = [(h["level"], h["title"]) for h in list_headings(file_path)]
        toc_paragraphs = sum(
            1 for p in Document(file_path).paragraphs if _is_toc_paragraph(p))
        return outline, toc_paragraphs, classify_tables(file_path)

    def _drop_old_draft(self, project_id: int) -> None:
        """删旧底稿行 + 旧文件（文件可能已被手工删，容错）。
        须在写新底稿文件之前调用（新旧文件同路径，先删后写）。"""
        old = self.db.get_project_bid_template(project_id)
        if not old:
            return
        self.db.delete_bid_template(old["id"])
        old_path = old.get("file_path") or ""
        if old_path:
            try:
                Path(old_path).unlink(missing_ok=True)
            except OSError:
                pass

    def _store(self, project: dict, source: str, source_path: str,
               cut_start: str, cut_end: str, outline: list,
               toc_paragraphs: int, suggestions: list) -> dict:
        """落库新底稿行并返回预览结构（调用方须已 _drop_old_draft）。"""
        name = f"{project['name']}_商务标底稿"
        file_path = str(config.BID_DRAFTS_DIR
                        / f"project_{project['id']}_商务标底稿.docx")
        bindings = {"tables": [_normalize_binding(s) for s in suggestions],
                    "swap_toc": toc_paragraphs > 0}
        row_id = self.db.create_bid_template(
            project["id"], name, file_path, source=source,
            source_path=source_path, cut_start=cut_start, cut_end=cut_end,
            bindings=bindings)
        warnings = [_TOC_WARNING] if toc_paragraphs > 0 else []
        return {"id": row_id, "name": name, "cut_start": cut_start,
                "cut_end": cut_end, "source": source, "warnings": warnings,
                "outline": outline, "tables": suggestions,
                "bindings": bindings, "swap_toc": bindings["swap_toc"]}

    # ---------- 生成 / 上传 ----------

    def generate(self, project_id: int, start_heading: str = "",
                 end_heading: str = "", start_index: int = None,
                 end_index: int = None) -> dict:
        """裁切 → classify_tables → 删旧底稿 → 建行 → 返回预览结构。

        起止定位两路：
        - 索引直达：start_index 非 None 时直接用索引裁切（越界 → ValueError；
          end_index 同理，<=0 表示裁到文档末尾），标题仅用于存
          cut_start/cut_end 展示；
        - 标题解析（索引为 None）：空 start 自动定位 find_format_chapter
          （无命中 → ValueError），重名标题按 resolve_heading_index 的
          内容跟随启发式解析。
        """
        project = self._project(project_id)
        docx = self.tender_docx(project)
        headings = list_headings(str(docx))
        doc = Document(str(docx))  # 供重名启发式/索引越界校验的块级上下文
        start_heading = (start_heading or "").strip()
        end_heading = (end_heading or "").strip()
        if start_index is not None:
            body_len = len(list(doc.element.body))
            if not isinstance(start_index, int) \
                    or not 0 <= start_index < body_len:
                raise ValueError("起始标题索引越界")
            if end_index is not None and end_index > 0 and (
                    not isinstance(end_index, int) or end_index > body_len
                    or start_index >= end_index):
                raise ValueError("结束标题索引越界")
            title_by_index = {h["index"]: h["title"] for h in headings}
            start_body_index = start_index
            cut_start = title_by_index.get(start_index) or start_heading
            eff_end = end_index if end_index is not None else -1
            cut_end = (title_by_index.get(end_index) or end_heading) \
                if eff_end > 0 else ""
        else:
            if start_heading:
                start_body_index = resolve_heading_index(
                    headings, start_heading, doc=doc)
                cut_start = start_heading
            else:
                chapter = find_format_chapter(headings)
                if not chapter:
                    raise ValueError(
                        "未识别到投标文件格式章节，请手动选择起止标题")
                start_body_index = chapter["start"]["index"]
                cut_start = chapter["start"]["title"]
                if not end_heading and chapter["end"]:
                    end_heading = chapter["end"]["title"]
            if end_heading:
                eff_end = resolve_heading_index(headings, end_heading, doc=doc)
                cut_end = end_heading
            else:
                eff_end = -1
                cut_end = ""

        config.ensure_dirs()
        dest = config.BID_DRAFTS_DIR / f"project_{project_id}_商务标底稿.docx"
        self._drop_old_draft(project_id)  # 先删旧行/旧文件，再写新文件
        stats = cut_draft(str(docx), str(dest), start_body_index, eff_end)
        suggestions = classify_tables(str(dest))
        return self._store(project, source="tender-cut", source_path=str(docx),
                           cut_start=cut_start, cut_end=cut_end,
                           outline=stats["outline"],
                           toc_paragraphs=stats["toc_paragraphs"],
                           suggestions=suggestions)

    def upload_draft(self, project_id: int, src_path: str,
                     filename: str) -> dict:
        """手动上传底稿（仅 .docx）：复制到 BID_DRAFTS_DIR → classify_tables
        → 建行（source="upload"，cut_start/cut_end=""）→ 返回预览结构。"""
        project = self._project(project_id)
        config.ensure_dirs()
        dest = config.BID_DRAFTS_DIR / f"project_{project_id}_商务标底稿.docx"
        self._drop_old_draft(project_id)  # 先删旧行/旧文件，再写新文件
        shutil.copy2(src_path, dest)
        outline, toc_paragraphs, suggestions = self._scan_file(str(dest))
        return self._store(project, source="upload", source_path=filename,
                           cut_start="", cut_end="", outline=outline,
                           toc_paragraphs=toc_paragraphs,
                           suggestions=suggestions)

    # ---------- 预览 ----------

    def preview(self, project_id: int):
        """当前底稿 + 已存 bindings + classify 建议按 table_index 合并
        （confirmed 项覆盖建议值，前端据此回显）。无底稿 → None。"""
        self._project(project_id)
        row = self.db.get_project_bid_template(project_id)
        if not row:
            return None
        file_path = row.get("file_path") or ""
        outline, toc_paragraphs, suggestions = ([], 0, [])
        if Path(file_path).exists():
            outline, toc_paragraphs, suggestions = self._scan_file(file_path)
        stored = row.get("bindings") or {}
        stored_tables = {t.get("table_index"): t
                         for t in stored.get("tables") or []
                         if isinstance(t, dict)}
        merged = []
        for sug in suggestions:
            item = dict(sug)
            saved = stored_tables.get(sug["table_index"])
            if saved and saved.get("confirmed"):
                for key in _BINDING_KEYS:
                    if key in saved:
                        item[key] = saved[key]
            merged.append(item)
        warnings = [_TOC_WARNING] if toc_paragraphs > 0 else []
        return {"id": row["id"], "name": row["name"],
                "cut_start": row.get("cut_start") or "",
                "cut_end": row.get("cut_end") or "",
                "source": row.get("source") or "", "warnings": warnings,
                "outline": outline, "tables": merged, "bindings": stored,
                "swap_toc": bool(stored.get("swap_toc"))}
