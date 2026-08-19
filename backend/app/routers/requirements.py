import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db import Database
from app.deps import get_db
from app.services.bid_service import BidService

router = APIRouter()


class RequirementUpdate(BaseModel):
    category: str | None = None
    content: str | None = None
    source: str | None = None
    confidence: str | None = None
    status: str | None = None


@router.get("/projects/{project_id}/requirements")
def list_requirements(project_id: int, category: str = None, status: str = None,
                      q: str = None, db: Database = Depends(get_db)):
    return db.get_requirements(project_id, category=category, status=status, q=q)


@router.put("/requirements/{requirement_id}")
def update_requirement(requirement_id: int, body: RequirementUpdate,
                       db: Database = Depends(get_db)):
    if not db.get_requirement(requirement_id):
        raise HTTPException(404, "要求不存在")
    db.update_requirement(requirement_id,
                          **{k: v for k, v in body.model_dump().items() if v is not None})
    return {"ok": True}


@router.delete("/requirements/{requirement_id}")
def delete_requirement(requirement_id: int, db: Database = Depends(get_db)):
    db.delete_requirement(requirement_id)
    return {"ok": True}


@router.get("/projects/{project_id}/parse")
def parse_stream(project_id: int, db: Database = Depends(get_db)):
    q: queue.Queue = queue.Queue()

    def run():
        try:
            svc = BidService(db.db_path)
            result = svc.parse_and_save_requirements(
                project_id, progress=lambda s: q.put(("progress", s)))
            q.put(("done", {
                "count": len(result["requirements"]),
                "engine": result["engine"],
                "warning": result["warning"],
            }))
        except Exception as exc:
            q.put(("error", str(exc)))
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is None:
                break
            event, data = item
            payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
            yield f"event: {event}\ndata: {payload}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
