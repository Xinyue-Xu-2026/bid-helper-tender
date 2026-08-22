import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi import BackgroundTasks
from fastapi.responses import FileResponse
from urllib.parse import quote

from app.core.excel_exporter import export_requirements
from app.core.word_exporter import export_word
from app.db import Database
from app.deps import get_db

router = APIRouter()


@router.get("/projects/{project_id}/requirements/export")
def export_xlsx(project_id: int, db: Database = Depends(get_db)):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    requirements = db.get_requirements(project_id)
    dest = Path(tempfile.gettempdir()) / f"{project['name']}_要求清单.xlsx"
    export_requirements(project, requirements, str(dest))
    filename = quote(dest.name)
    return FileResponse(
        str(dest),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename}"},
    )


@router.get("/projects/{project_id}/export")
def export_word_doc(project_id: int, template_id: int = None,
                    background_tasks: BackgroundTasks = None,
                    db: Database = Depends(get_db)):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    template = db.get_template(template_id) if template_id else None
    sections = db.get_sections_flat(project_id)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project["name"])
    dest = Path(tempfile.gettempdir()) / f"{safe}_标书.docx"
    try:
        export_word(project, template, sections, str(dest))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    background_tasks.add_task(Path(dest).unlink, missing_ok=True)
    filename = quote(dest.name)
    return FileResponse(
        str(dest),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename}"},
    )
