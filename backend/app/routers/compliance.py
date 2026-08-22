from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import Database
from app.deps import get_db

router = APIRouter()

CHECK_CATEGORIES = ("废标项", "资质门槛")


class CheckIn(BaseModel):
    checked: bool


@router.get("/projects/{project_id}/compliance")
def get_compliance(project_id: int, db: Database = Depends(get_db)):
    if not db.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    reqs = [r for r in db.get_requirements(project_id) if r["category"] in CHECK_CATEGORIES]
    checks = db.get_checks(project_id)
    items = []
    for r in reqs:
        c = checks.get(r["id"])
        items.append({**r, "checked": bool(c and c["checked"]),
                      "checked_at": c["checked_at"] if c else None})
    return {"items": items, "total": len(items),
            "checked": sum(1 for i in items if i["checked"])}


@router.put("/compliance/{requirement_id}")
def set_compliance(requirement_id: int, body: CheckIn, db: Database = Depends(get_db)):
    req = db.get_requirement(requirement_id)
    if not req:
        raise HTTPException(404, "要求不存在")
    db.set_check(req["project_id"], requirement_id, body.checked)
    return {"ok": True}


@router.post("/projects/{project_id}/compliance/ai-check")
def ai_check_placeholder(project_id: int, db: Database = Depends(get_db)):
    if not db.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    raise HTTPException(501, "AI 自动比对将在后续版本提供")
