import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app import config
from app.db import Database
from app.deps import get_db

router = APIRouter()

ALLOWED_MATERIAL_SUFFIXES = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".png", ".jpg", ".jpeg",
}


@router.get("/projects/{project_id}/materials")
def list_materials(project_id: int, db: Database = Depends(get_db)):
    return db.get_materials(project_id)


@router.post("/projects/{project_id}/materials")
def upload_material(project_id: int, file: UploadFile, db: Database = Depends(get_db)):
    if not db.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_MATERIAL_SUFFIXES:
        raise HTTPException(400, f"不支持的文件类型 {suffix}，仅支持 PDF/Word/Excel/图片")
    config.ensure_dirs()
    safe_name = Path(file.filename or "material").name
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in safe_name)
    dest = config.UPLOADS_DIR / f"material_{project_id}_{uuid.uuid4().hex[:8]}_{safe_name}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    mid = db.create_material(project_id, str(dest), suffix.lstrip("."))
    return {"id": mid, "file_path": str(dest)}


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Database = Depends(get_db)):
    material = db.get_material(material_id)
    if material and material.get("file_path"):
        Path(material["file_path"]).unlink(missing_ok=True)
    db.delete_material(material_id)
    return {"ok": True}
