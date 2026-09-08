"""商务标：项目维度的拟派人员/企业业绩勾选查询、保存与导出（设计文档 §5.1–5.3）。"""
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import config
from app.core.bid_exporter import build_bid_docx, build_bid_xlsx
from app.core.bid_template_exporter import build_bid_docx_from_template
from app.db import Database
from app.deps import get_db
from app.services import bid_service

router = APIRouter()


class TemplatePersonPick(BaseModel):
    asset_id: int
    is_lead: bool = False
    certs: list[int] | None = None


class TemplateContractPick(BaseModel):
    asset_id: int
    section: int = 1


class PersonPick(BaseModel):
    asset_id: int
    role: str = ""
    is_lead: bool = False
    certs: list[int] | None = None  # None=全部证书；数组=勾选的证书下标


class BidAssetsIn(BaseModel):
    persons: list[PersonPick] = []
    # 兼容旧格式裸 id（section 视为 1）
    contracts: list[int | TemplateContractPick] = []


class BidTemplateExportIn(BaseModel):
    persons: list[TemplatePersonPick] = []
    contracts: list[TemplateContractPick] = []
    project_no: str = ""      # 项目编号（空则不替换模板残留编号）
    project_name: str = ""    # 项目名称覆盖（空则用数据库项目名）
    doc_date: str = ""        # 文档日期 YYYY-MM-DD（空则不替换模板残留日期）


def _get_project_or_404(db: Database, project_id: int) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project


@router.get("/projects/{project_id}/bid-assets")
def get_bid_assets(project_id: int, db: Database = Depends(get_db)):
    _get_project_or_404(db, project_id)
    return bid_service.get_bid_assets(db, project_id)


@router.put("/projects/{project_id}/bid-assets")
def save_bid_assets(project_id: int, body: BidAssetsIn,
                    db: Database = Depends(get_db)):
    _get_project_or_404(db, project_id)
    persons = [p.model_dump() for p in body.persons]
    contracts = [c.model_dump() if isinstance(c, TemplateContractPick) else c
                 for c in body.contracts]
    try:
        bid_service.save_bid_assets(db, project_id, persons, contracts)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"ok": True, "persons": len(persons), "contracts": len(contracts)}


@router.get("/projects/{project_id}/bid-assets/export")
def export_bid_assets(project_id: int, background_tasks: BackgroundTasks,
                      format: str = "xlsx", db: Database = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    if format not in ("xlsx", "docx"):
        raise HTTPException(400, "format 仅支持 xlsx|docx")
    data = bid_service.get_bid_assets(db, project_id)
    if not data["persons"] and not data["contracts"]:
        raise HTTPException(422, "请先勾选人员或业绩")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project["name"])
    dest = Path(tempfile.gettempdir()) / f"{safe}_{uuid.uuid4().hex[:8]}_商务标.{format}"
    if format == "xlsx":
        build_bid_xlsx(project["name"], data["persons"], data["contracts"], str(dest))
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        build_bid_docx(project["name"], data["persons"], data["contracts"], str(dest))
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    background_tasks.add_task(Path(dest).unlink, missing_ok=True)
    filename = quote(dest.name)
    return FileResponse(
        str(dest),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename}"},
    )


@router.post("/projects/{project_id}/bid-assets/export-template")
def export_bid_template(project_id: int, body: BidTemplateExportIn,
                        background_tasks: BackgroundTasks,
                        db: Database = Depends(get_db)):
    """模板式商务标导出：以 data/商务标模板.docx 为底稿填充两节表格。"""
    project = _get_project_or_404(db, project_id)
    if not body.persons and not body.contracts:
        raise HTTPException(422, "请先勾选人员或业绩")
    template = config.BID_TEMPLATE_PATH
    if not template.exists():
        raise HTTPException(503, "商务标模板未配置（data/商务标模板.docx 缺失）")
    data = bid_service.assemble_bid_template_data(
        db,
        [p.model_dump() for p in body.persons],
        [c.model_dump() for c in body.contracts],
    )
    effective_name = (body.project_name or "").strip() or project["name"]
    data["project_no"] = (body.project_no or "").strip()
    data["project_name"] = effective_name
    data["doc_date"] = (body.doc_date or "").strip()
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in effective_name)
    dest = Path(tempfile.gettempdir()) / f"{safe}_{uuid.uuid4().hex[:8]}_商务标.docx"
    build_bid_docx_from_template(str(template), str(dest), data)
    background_tasks.add_task(Path(dest).unlink, missing_ok=True)
    filename = quote(f"{effective_name}_商务标.docx")
    return FileResponse(
        str(dest),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename}"},
    )
