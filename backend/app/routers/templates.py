import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.db import Database
from app.deps import get_db
from app.services.write_service import WriteService

router = APIRouter()


@router.get("")
def list_templates(db: Database = Depends(get_db)):
    return db.get_templates()


@router.post("")
def upload_template(
    name: str | None = None,
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
    db: Database = Depends(get_db),
):
    uploads: list[UploadFile] = list(files or [])
    if file is not None:
        uploads.append(file)
    if not uploads:
        raise HTTPException(400, "未收到文件，请使用 files 字段上传")

    svc = WriteService(db.db_path)
    items: list[dict] = []
    errors: list[dict] = []
    for up in uploads:
        filename = up.filename or ""
        if not filename.lower().endswith(".docx"):
            errors.append({"filename": filename, "reason": "仅支持 .docx 模板"})
            continue
        tpl_name = name or Path(filename).stem or "未命名模板"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(up.file.read())
            tmp_path = tmp.name
        try:
            tid = svc.import_template(tmp_path, tpl_name)
        except Exception as exc:
            errors.append({"filename": filename, "reason": str(exc)})
            continue
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        items.append({"id": tid})
    return {"items": items, "errors": errors}


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
