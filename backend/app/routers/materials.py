import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

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
def upload_material(
    project_id: int,
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
    db: Database = Depends(get_db),
):
    if not db.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    uploads: list[UploadFile] = list(files or [])
    if file is not None:
        uploads.append(file)
    if not uploads:
        raise HTTPException(400, "未收到文件，请使用 files 字段上传")

    config.ensure_dirs()
    items: list[dict] = []
    errors: list[dict] = []
    for up in uploads:
        filename = up.filename or ""
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_MATERIAL_SUFFIXES:
            errors.append({
                "filename": filename,
                "reason": f"不支持的文件类型 {suffix or '(无扩展名)'}，仅支持 PDF/Word/Excel/图片",
            })
            continue
        safe_name = Path(filename or "material").name
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in safe_name)
        dest = config.UPLOADS_DIR / f"material_{project_id}_{uuid.uuid4().hex[:8]}_{safe_name}"
        with dest.open("wb") as f:
            shutil.copyfileobj(up.file, f)
        mid = db.create_material(project_id, str(dest), suffix.lstrip("."))
        items.append({"id": mid, "file_path": str(dest)})
    return {"items": items, "errors": errors}


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Database = Depends(get_db)):
    material = db.get_material(material_id)
    if material and material.get("file_path"):
        Path(material["file_path"]).unlink(missing_ok=True)
    db.delete_material(material_id)
    return {"ok": True}
