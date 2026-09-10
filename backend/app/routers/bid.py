"""商务标：项目维度的拟派人员/企业业绩勾选查询、保存与导出（设计文档 §5.1–5.3）。"""
import json
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import config
from app import settings_store
from app.core.bid_draft_exporter import fill_draft
from app.core.bid_exporter import build_bid_docx, build_bid_xlsx
from app.core.bid_template_exporter import build_bid_docx_from_template
from app.db import Database
from app.deps import get_db
from app.services import bid_service

router = APIRouter()


class TemplatePersonPick(BaseModel):
    asset_id: int
    is_lead: bool = False
    certs: list[int] | None = None


class TemplateContractPick(BaseModel):
    asset_id: int
    section: int = 1


class PersonPick(BaseModel):
    asset_id: int
    role: str = ""
    is_lead: bool = False
    certs: list[int] | None = None  # None=全部证书；数组=勾选的证书下标


class BidAssetsIn(BaseModel):
    persons: list[PersonPick] = []
    # 兼容旧格式裸 id（section 视为 1）
    contracts: list[int | TemplateContractPick] = []


class BidTemplateExportIn(BaseModel):
    persons: list[TemplatePersonPick] = []
    contracts: list[TemplateContractPick] = []
    project_no: str = ""      # 项目编号（空则不替换模板残留编号）
    project_name: str = ""    # 项目名称覆盖（空则用数据库项目名）
    doc_date: str = ""        # 文档日期 YYYY-MM-DD（空则不替换模板残留日期）
    tenderer: str = ""        # 招标人名称（空则不填充"招标人：____"空白）
    bidder_name: str = ""     # 投标人名称（空则不填充"投标人名称：____"空白）
    legal_rep_id: int | None = None   # 法定代表人（legal 资产 id）
    agent_id: int | None = None       # 委托代理人（legal 资产 id）
    section_name: str = ""   # 标段名称（空则不填充"标段名称：____/（标段名称）"占位）
    section_no: str = ""     # 标段编号（空则不填充"标段编号：____"占位）


def _legal_person(db: Database, asset_id: int | None) -> dict | None:
    """把 legal 资产解析成授权页填充所需字典（{name, 身份证号, 正反面扫描件}）。"""
    if asset_id is None:
        return None
    a = db.get_asset(asset_id)
    if not a or a.get("type") != "legal":
        return None
    fields = a.get("fields") or {}
    return {
        "name": str(a.get("name") or ""),
        "身份证号": str(fields.get("身份证号") or ""),
        "身份证正面扫描件": str(fields.get("身份证正面扫描件") or ""),
        "身份证反面扫描件": str(fields.get("身份证反面扫描件") or ""),
    }


def _get_project_or_404(db: Database, project_id: int) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project


@router.get("/projects/{project_id}/bid-assets")
def get_bid_assets(project_id: int, db: Database = Depends(get_db)):
    _get_project_or_404(db, project_id)
    return bid_service.get_bid_assets(db, project_id)


@router.put("/projects/{project_id}/bid-assets")
def save_bid_assets(project_id: int, body: BidAssetsIn,
                    db: Database = Depends(get_db)):
    _get_project_or_404(db, project_id)
    persons = [p.model_dump() for p in body.persons]
    contracts = [c.model_dump() if isinstance(c, TemplateContractPick) else c
                 for c in body.contracts]
    try:
        bid_service.save_bid_assets(db, project_id, persons, contracts)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"ok": True, "persons": len(persons), "contracts": len(contracts)}


@router.get("/projects/{project_id}/bid-assets/export")
def export_bid_assets(project_id: int, background_tasks: BackgroundTasks,
                      format: str = "xlsx", db: Database = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    if format not in ("xlsx", "docx"):
        raise HTTPException(400, "format 仅支持 xlsx|docx")
    data = bid_service.get_bid_assets(db, project_id)
    if not data["persons"] and not data["contracts"]:
        raise HTTPException(422, "请先勾选人员或业绩")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project["name"])
    dest = Path(tempfile.gettempdir()) / f"{safe}_{uuid.uuid4().hex[:8]}_商务标.{format}"
    if format == "xlsx":
        build_bid_xlsx(project["name"], data["persons"], data["contracts"], str(dest))
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        build_bid_docx(project["name"], data["persons"], data["contracts"], str(dest))
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    background_tasks.add_task(Path(dest).unlink, missing_ok=True)
    filename = quote(dest.name)
    return FileResponse(
        str(dest),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename}"},
    )


@router.post("/projects/{project_id}/bid-assets/export-template")
def export_bid_template(project_id: int, body: BidTemplateExportIn,
                        background_tasks: BackgroundTasks,
                        db: Database = Depends(get_db)):
    """模板式商务标导出：项目有底稿（bid_templates）走绑定驱动新管线
    （fill_draft + X-Fill-Report 头），否则回退旧模板路径
    （data/商务标模板.docx + build_bid_docx_from_template，行为不变）。"""
    project = _get_project_or_404(db, project_id)
    if not body.persons and not body.contracts:
        raise HTTPException(422, "请先勾选人员或业绩")
    # 标段字段非空时持久化到 projects（下次导出可回显）
    section_update = {}
    if (body.section_name or "").strip():
        section_update["section_name"] = body.section_name.strip()
    if (body.section_no or "").strip():
        section_update["section_no"] = body.section_no.strip()
    if section_update:
        db.update_project(project_id, **section_update)
    effective_name = (body.project_name or "").strip() or project["name"]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in effective_name)
    dest = Path(tempfile.gettempdir()) / f"{safe}_{uuid.uuid4().hex[:8]}_商务标.docx"
    filename = quote(f"{effective_name}_商务标.docx")
    headers = {"Content-Disposition": f"attachment; filename*=utf-8''{filename}"}

    bt = db.get_project_bid_template(project_id)
    draft_path = (bt.get("edited_path") or bt.get("file_path")) if bt else ""
    if bt and Path(draft_path or "").exists():
        # 新管线：底稿（编辑版优先）+ 用户确认 bindings 填充，附填充/校验报告。
        # 手动编辑版优先：若存在编辑版，跳过表格自动填充（避免覆盖手动内容、
        # 重复克隆、克隆后下标错位），但仍做封面占位符替换与授权页填充；
        # 想恢复自动填充 → 重新生成底稿即清空编辑版。
        edited = bool(bt.get("edited_path")) and Path(bt["edited_path"]).exists()
        bindings = {} if edited else (bt.get("bindings") or {})
        data = bid_service.assemble_bid_draft_data(
            db, project_id,
            [p.model_dump() for p in body.persons],
            [c.model_dump() for c in body.contracts])
        auth = {"legal_rep": _legal_person(db, body.legal_rep_id),
                "agent": _legal_person(db, body.agent_id),
                "doc_date": (body.doc_date or "").strip()}
        report = fill_draft(draft_path, str(dest), bindings, data,
                            project_no=(body.project_no or "").strip(),
                            project_name=effective_name,
                            doc_date=(body.doc_date or "").strip(),
                            tenderer=(body.tenderer or "").strip(),
                            bidder_name=(body.bidder_name or "").strip(),
                            auth=auth,
                            section_name=(body.section_name or "").strip(),
                            section_no=(body.section_no or "").strip(),
                            synonyms=settings_store.get_placeholder_synonyms())
        headers["X-Fill-Report"] = quote(
            json.dumps(report, ensure_ascii=False))
    else:
        # 旧路径：固定模板填充（无底稿时保持原有行为）
        template = config.BID_TEMPLATE_PATH
        if not template.exists():
            raise HTTPException(503, "商务标模板未配置（data/商务标模板.docx 缺失）")
        data = bid_service.assemble_bid_template_data(
            db,
            [p.model_dump() for p in body.persons],
            [c.model_dump() for c in body.contracts],
        )
        data["project_no"] = (body.project_no or "").strip()
        data["project_name"] = effective_name
        data["doc_date"] = (body.doc_date or "").strip()
        build_bid_docx_from_template(str(template), str(dest), data)

    background_tasks.add_task(Path(dest).unlink, missing_ok=True)
    return FileResponse(
        str(dest),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
