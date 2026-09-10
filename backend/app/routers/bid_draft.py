"""商务标底稿 API：章节定位 / 生成（裁切）/ 手动上传 / 预览回显 / 绑定确认 /
占位符预览。路由层只做参数校验与错误码映射，业务编排在 BidDraftService。"""
import tempfile
from pathlib import Path

from docx import Document
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app import config, settings_store
from app.core.bid_draft import BidDraftError
from app.core.bid_table_classifier import ROLES
from app.core.bid_template_exporter import scan_placeholders
from app.core.doc_blocks import apply_edits, read_blocks
from app.core.input_convert import InputConvertError
from app.db import Database
from app.deps import get_db
from app.services.bid_draft_service import BidDraftService

router = APIRouter()


class GenerateDraftIn(BaseModel):
    start_heading: str = ""
    end_heading: str = ""
    # 索引直达（重名标题可区分；body 子元素下标，headings 端点产出）
    start_index: int | None = None
    end_index: int | None = None


class TableBindingIn(BaseModel):
    table_index: int
    role: str
    columns: dict = {}
    person_scope: str = "all"
    perf_scope: str = "all"
    label_kind: str = ""
    person: str = ""
    header_rows: int = 1   # 表头行数（两行表头=2，填充时保留并以其后首行为 donor）
    mode: str = ""         # "per_person"=一人一表整表克隆（resume_each）；空=单份填充
    confirmed: bool = False


class BindingsIn(BaseModel):
    tables: list[TableBindingIn] = []
    swap_toc: bool = False


class PlaceholderPreviewIn(BaseModel):
    """占位符预览参数（全可选，默认空——空值不参与规则）。"""
    project_no: str = ""
    project_name: str = ""
    doc_date: str = ""
    tenderer: str = ""
    bidder_name: str = ""
    section_name: str = ""
    section_no: str = ""


class DocumentEditIn(BaseModel):
    """底稿内容编辑（方案 A 结构保真编辑器）：全量快照。
    paragraphs: {段落序: 文本}；tables: {表序: [[文本,...]]（按 read_blocks rows 对齐）}；
    clones: [{"table_index": 源表序, "count": 复制份数}]。"""
    paragraphs: dict[int, str] = {}
    tables: dict[int, list] = {}
    clones: list = []


def _project_or_404(db: Database, project_id: int) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project


def _svc(db: Database) -> BidDraftService:
    return BidDraftService(db.db_path)


@router.get("/projects/{project_id}/bid-draft/headings")
def get_bid_draft_headings(project_id: int, db: Database = Depends(get_db)):
    _project_or_404(db, project_id)
    try:
        return _svc(db).headings(project_id)
    except (ValueError, InputConvertError) as exc:
        raise HTTPException(400, str(exc))


@router.post("/projects/{project_id}/bid-draft/generate")
def generate_bid_draft(project_id: int, body: GenerateDraftIn,
                       db: Database = Depends(get_db)):
    _project_or_404(db, project_id)
    try:
        return _svc(db).generate(project_id, body.start_heading,
                                 body.end_heading,
                                 start_index=body.start_index,
                                 end_index=body.end_index)
    except (ValueError, BidDraftError, InputConvertError) as exc:
        raise HTTPException(422, str(exc))


@router.post("/projects/{project_id}/bid-draft/upload")
def upload_bid_draft(project_id: int, file: UploadFile,
                     db: Database = Depends(get_db)):
    _project_or_404(db, project_id)
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".docx":
        raise HTTPException(400, "仅支持 .docx 底稿")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        return _svc(db).upload_draft(project_id, tmp_path, filename)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("/projects/{project_id}/bid-draft")
def get_bid_draft(project_id: int, db: Database = Depends(get_db)):
    _project_or_404(db, project_id)
    preview = _svc(db).preview(project_id)
    if preview is None:
        return {"draft": None}
    return preview


@router.put("/projects/{project_id}/bid-draft/bindings")
def save_bid_draft_bindings(project_id: int, body: BindingsIn,
                            db: Database = Depends(get_db)):
    _project_or_404(db, project_id)
    row = db.get_project_bid_template(project_id)
    if not row:
        raise HTTPException(422, "尚无底稿，请先生成或上传底稿")
    for t in body.tables:
        if t.role not in ROLES:
            raise HTTPException(422, f"非法表格角色：{t.role}")
        if t.table_index < 0:
            raise HTTPException(422, "table_index 必须 ≥ 0")
        if not 1 <= t.header_rows <= 4:
            raise HTTPException(422, "header_rows 必须在 1..4 之间")
        if t.mode not in ("", "per_person"):
            raise HTTPException(422, f"非法填充模式：{t.mode}")
    db.update_bid_template(row["id"], bindings=body.model_dump())
    return {"ok": True}


@router.post("/projects/{project_id}/bid-draft/placeholders")
def preview_placeholders(project_id: int, body: PlaceholderPreviewIn = None,
                         db: Database = Depends(get_db)):
    """占位符预览（V1.2）：对当前底稿跑 scan_placeholders（规则唯一来源
    在 core，路由不复制），同义词取全局设置。无底稿 → 404。
    返回 {"matched":[{label,value,count,kind}], "suspicious":[{text}]}。"""
    _project_or_404(db, project_id)
    row = db.get_project_bid_template(project_id)
    if not row or not Path(row.get("file_path") or "").exists():
        raise HTTPException(404, "尚无底稿，请先生成或上传底稿")
    doc = Document(row["file_path"])
    params = body.model_dump() if body else {}
    return scan_placeholders(
        doc, params, synonyms=settings_store.get_placeholder_synonyms())


@router.get("/projects/{project_id}/bid-draft/document")
def get_bid_document(project_id: int, db: Database = Depends(get_db)):
    """读取底稿块序列（编辑版优先）。无底稿/文件缺失 → 404。"""
    _project_or_404(db, project_id)
    row = db.get_project_bid_template(project_id)
    if not row:
        raise HTTPException(404, "尚无底稿，请先生成或上传底稿")
    path = row.get("edited_path") or row.get("file_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "底稿文件不存在")
    return read_blocks(str(path))


@router.post("/projects/{project_id}/bid-draft/document")
def save_bid_document(project_id: int, body: DocumentEditIn,
                      db: Database = Depends(get_db)):
    """保存底稿内容编辑：以原始底稿为基准，复制表 + 原位写文本，落为
    「编辑版底稿」；导出/校验改走编辑版。返回回显块序列。"""
    _project_or_404(db, project_id)
    row = db.get_project_bid_template(project_id)
    if not row or not Path(row.get("file_path") or "").exists():
        raise HTTPException(422, "尚无底稿，请先生成或上传底稿")
    base = row.get("edited_path") or row.get("file_path")
    out = config.BID_DRAFTS_DIR / f"project_{project_id}_edited.docx"
    tmp = config.BID_DRAFTS_DIR / f"project_{project_id}_edited.tmp.docx"
    try:
        apply_edits(str(base), str(tmp),
                    paragraphs=body.paragraphs, tables=body.tables,
                    clones=body.clones)
        Path(tmp).replace(out)
    except ValueError as exc:
        Path(tmp).unlink(missing_ok=True)
        raise HTTPException(400, str(exc))
    db.update_bid_template(row["id"], edited_path=str(out))
    return {"ok": True, "blocks": read_blocks(str(out))["blocks"]}
