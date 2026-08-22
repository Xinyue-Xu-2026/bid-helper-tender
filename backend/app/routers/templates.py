import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.db import Database
from app.deps import get_db
from app.services.write_service import WriteService

router = APIRouter()


@router.get("")
def list_templates(db: Database = Depends(get_db)):
    return db.get_templates()


@router.post("")
def upload_template(name: str, file: UploadFile, db: Database = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(400, "仅支持 .docx 模板")
    svc = WriteService(db.db_path)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        tid = svc.import_template(tmp_path, name)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return {"id": tid}


@router.post("/{template_id}/analyze")
def analyze(template_id: int, db: Database = Depends(get_db)):
    svc = WriteService(db.db_path)
    try:
        profile = svc.analyze_template_profile(template_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))
    return {"style_profile": profile}


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Database = Depends(get_db)):
    template = db.get_template(template_id)
    if template and template.get("file_path"):
        Path(template["file_path"]).unlink(missing_ok=True)
    db.delete_template(template_id)
    return {"ok": True}
