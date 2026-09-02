"""商务标：项目维度的拟派人员/企业业绩勾选查询、保存与导出（设计文档 §5.1–5.3）。"""
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.bid_exporter import build_bid_docx, build_bid_xlsx
from app.db import Database
from app.deps import get_db
from app.services import bid_service

router = APIRouter()


class PersonPick(BaseModel):
    asset_id: int
    role: str = ""


class BidAssetsIn(BaseModel):
    persons: list[PersonPick] = []
    contracts: list[int] = []


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
    try:
        bid_service.save_bid_assets(db, project_id, persons, body.contracts)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"ok": True, "persons": len(persons), "contracts": len(body.contracts)}


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
