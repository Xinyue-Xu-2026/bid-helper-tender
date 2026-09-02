# -*- coding: utf-8 -*-
"""保格式仿写路由：plan（规划编辑指令）/ apply（应用并校验）/ download。"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import config
from app.core.llm_parser import LLMParseError
from app.db import Database
from app.deps import get_db
from app.services.mimic_service import MimicService

router = APIRouter()


class PlanRequest(BaseModel):
    template_id: int


class ApplyRequest(BaseModel):
    template_id: int
    ops: list


@router.post("/projects/{project_id}/mimic/plan")
def mimic_plan(project_id: int, body: PlanRequest, db: Database = Depends(get_db)):
    svc = MimicService(db.db_path)
    try:
        return svc.build_plan(project_id, body.template_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except LLMParseError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.post("/projects/{project_id}/mimic/apply")
def mimic_apply(project_id: int, body: ApplyRequest, db: Database = Depends(get_db)):
    svc = MimicService(db.db_path)
    try:
        return svc.apply_plan(project_id, body.template_id, body.ops)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/projects/{project_id}/mimic/download")
def mimic_download(project_id: int, file: str):
    if not file or any(sep in file for sep in ("/", "\\", "..")):
        raise HTTPException(400, "非法文件名")
    path = config.FILES_DIR / "mimic_outputs" / file
    if not path.is_file():
        raise HTTPException(404, "文件不存在")
    filename = quote(path.name)
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename}"},
    )
