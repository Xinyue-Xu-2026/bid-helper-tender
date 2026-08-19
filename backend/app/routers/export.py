import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from urllib.parse import quote

from app.core.excel_exporter import export_requirements
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
