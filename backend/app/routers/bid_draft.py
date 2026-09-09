"""商务标底稿 API：章节定位 / 生成（裁切）/ 手动上传 / 预览回显 / 绑定确认。
路由层只做参数校验与错误码映射，业务编排在 BidDraftService。"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.bid_draft import BidDraftError
from app.core.bid_table_classifier import ROLES
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
    confirmed: bool = False


class BindingsIn(BaseModel):
    tables: list[TableBindingIn] = []
    swap_toc: bool = False


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
    db.update_bid_template(row["id"], bindings=body.model_dump())
    return {"ok": True}
