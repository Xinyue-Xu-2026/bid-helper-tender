import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.db import Database
from app.deps import get_db
from app.services.bid_service import BidService

router = APIRouter()

ALLOWED_TENDER_SUFFIXES = {".pdf", ".docx", ".doc"}


class ProjectIn(BaseModel):
    name: str
    client: str = ""
    bid_date: str = ""
    project_type: str = "其他"
    notes: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    client: str | None = None
    bid_date: str | None = None
    project_type: str | None = None
    notes: str | None = None


@router.get("")
def list_projects(db: Database = Depends(get_db)):
    return db.get_projects()


@router.post("")
def create_project(body: ProjectIn, db: Database = Depends(get_db)):
    pid = db.create_project(body.name, body.client, body.bid_date, body.project_type, body.notes)
    return {"id": pid}


@router.get("/{project_id}")
def get_project(project_id: int, db: Database = Depends(get_db)):
    p = db.get_project(project_id)
    if not p:
        raise HTTPException(404, "项目不存在")
    return p


@router.put("/{project_id}")
def update_project(project_id: int, body: ProjectUpdate, db: Database = Depends(get_db)):
    if not db.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    db.update_project(project_id, **{k: v for k, v in body.model_dump().items() if v is not None})
    return {"ok": True}


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Database = Depends(get_db)):
    db.delete_project(project_id)
    return {"ok": True}


@router.post("/{project_id}/tender")
def upload_tender(project_id: int, file: UploadFile, db: Database = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_TENDER_SUFFIXES:
        raise HTTPException(400, f"不支持的文件类型 {suffix}，仅支持 PDF/DOCX")
    svc = BidService(db.db_path)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    dest = svc.import_tender(project_id, tmp_path)
    # import_tender 用的是临时文件名，重命名回原始文件名更友好
    return {"tender_file_path": str(dest)}
