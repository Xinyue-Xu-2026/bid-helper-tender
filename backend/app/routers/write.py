"""编写工作台路由：章节树 CRUD、目录大纲生成、单节正文 SSE 生成。"""
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db import Database
from app.deps import get_db
from app.services.write_service import WriteService

router = APIRouter()


class SectionCreate(BaseModel):
    parent_id: int = 0
    title: str
    level: int = 1
    sort_order: int = 0


class SectionUpdate(BaseModel):
    parent_id: int | None = None
    title: str | None = None
    level: int | None = None
    content: str | None = None
    gen_status: str | None = None
    sort_order: int | None = None


def _sse_lines(text: str) -> str:
    """把一段文本按 SSE 规范展开为多个 data: 行，多行正文不破坏事件分帧。"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(f"data: {line}" for line in normalized.split("\n"))


@router.get("/projects/{project_id}/sections")
def list_sections(project_id: int, db: Database = Depends(get_db)):
    return db.get_sections_tree(project_id)


@router.post("/projects/{project_id}/sections")
def create_section(project_id: int, body: SectionCreate, db: Database = Depends(get_db)):
    return {"id": db.create_section(project_id, body.parent_id, body.title,
                                    body.level, body.sort_order)}


@router.put("/sections/{section_id}")
def update_section(section_id: int, body: SectionUpdate, db: Database = Depends(get_db)):
    if not db.get_section(section_id):
        raise HTTPException(404, "章节不存在")
    db.update_section(section_id, **{k: v for k, v in body.model_dump().items() if v is not None})
    return {"ok": True}


@router.delete("/sections/{section_id}")
def delete_section(section_id: int, db: Database = Depends(get_db)):
    db.delete_section(section_id)  # 递归删除子章节
    return {"ok": True}


@router.post("/projects/{project_id}/outline")
def generate_outline(project_id: int, db: Database = Depends(get_db)):
    svc = WriteService(db.db_path)
    try:
        return svc.generate_outline_and_save(project_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.get("/projects/{project_id}/sections/{section_id}/generate")
def generate_section(project_id: int, section_id: int,
                     asset_ids: str = "", material_ids: str = "", req_ids: str = "",
                     db: Database = Depends(get_db)):
    section = db.get_section(section_id)
    if not section:
        raise HTTPException(404, "章节不存在")
    if section["project_id"] != project_id:
        raise HTTPException(404, "章节不存在")
    svc = WriteService(db.db_path)
    q: queue.Queue = queue.Queue()

    def _ids(s):
        return [int(x) for x in s.split(",") if x.strip().isdigit()]

    def run():
        try:
            prompt = svc.assemble_section_prompt(
                project_id, section_id, _ids(asset_ids), _ids(material_ids), _ids(req_ids))
            full = []
            for delta in svc.stream_section_text(prompt):
                full.append(delta)
                q.put(("chunk", delta))
            db.update_section(section_id, content="".join(full), gen_status="已生成")
            q.put(("done", "".join(full)))
        except Exception as exc:
            # SSE 契约：error 载荷剥离换行符，防分帧破坏
            msg = str(exc).replace("\r", " ").replace("\n", " ")
            q.put(("error", msg))
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is None:
                break
            event, data = item
            yield f"event: {event}\n{_sse_lines(data)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
