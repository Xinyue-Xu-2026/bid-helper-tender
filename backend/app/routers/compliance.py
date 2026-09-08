from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.llm_parser import LLMParseError
from app.db import Database
from app.deps import get_db
from app.services import compliance_service as cs
from app.services.compliance_service import CHECK_CATEGORIES

router = APIRouter()


class CheckIn(BaseModel):
    checked: bool


@router.get("/projects/{project_id}/compliance")
def get_compliance(project_id: int, db: Database = Depends(get_db)):
    if not db.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    items = cs.auto_check(db, project_id)
    checks = db.get_checks(project_id)
    for r in items:
        c = checks.get(r["id"])
        r["checked"] = bool(c and c["checked"])
        r["checked_at"] = c["checked_at"] if c else None
    return {"items": items, "total": len(items),
            "checked": sum(1 for i in items if i["checked"])}


@router.put("/compliance/{requirement_id}")
def set_compliance(requirement_id: int, body: CheckIn, db: Database = Depends(get_db)):
    req = db.get_requirement(requirement_id)
    if not req:
        raise HTTPException(404, "要求不存在")
    db.set_check(req["project_id"], requirement_id, body.checked)
    return {"ok": True}


class AICheckIn(BaseModel):
    requirement_ids: list[int] = []


@router.post("/projects/{project_id}/compliance/ai-check")
def ai_check(project_id: int, body: AICheckIn | None = None,
             db: Database = Depends(get_db)):
    if not db.get_project(project_id):
        raise HTTPException(404, "项目不存在")
    try:
        ids = body.requirement_ids if body else None
        results = cs.ai_check(db, project_id, ids or None)
    except LLMParseError as exc:
        raise HTTPException(502, str(exc))
    return {"results": results}
