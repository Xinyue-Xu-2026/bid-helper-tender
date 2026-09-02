import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app import config, settings_store
from app.db import ASSET_TYPES, Database
from app.deps import get_db
from app.services import bid_service
from app.services.asset_service import (
    build_import_template,
    earliest_expiry,
    import_assets_excel,
    normalize_person_asset,
    person_perfs,
    solidify_person_fields,
    validate_contract_subtype,
)

router = APIRouter()


class AssetIn(BaseModel):
    type: str
    name: str
    fields: dict = {}
    file_path: str = ""
    expiry_date: str = ""


class AssetUpdate(BaseModel):
    name: str | None = None
    fields: dict | None = None
    file_path: str | None = None
    expiry_date: str | None = None


class FieldConfigIn(BaseModel):
    person: list = []
    contract: list = []


def _check_type(t: str):
    if t not in ASSET_TYPES:
        raise HTTPException(400, f"非法资产类型 {t}，可选：{'/'.join(ASSET_TYPES)}")


def _normalize_out(asset: dict, db: Database) -> dict:
    """GET 输出：person 资产保证 fields 含"证书"数组（懒迁移），
    并实时注入关联 contract 资产组装的"业绩"数组（只读，不落库）。"""
    if asset.get("type") == "person":
        a = normalize_person_asset(asset)
        a["fields"]["业绩"] = person_perfs(db, a["name"])
        return a
    return asset


def _prepare_person_write(fields: dict, expiry_date: str) -> tuple:
    """写入前固化证书新结构；有证书时 expiry_date 列取最早有效期。"""
    fields = solidify_person_fields(fields)
    computed = earliest_expiry(fields["证书"])
    return fields, (computed or expiry_date)


# 注意：/expiring、/field-config、/import-template 必须在 /{asset_id} 之前注册
@router.get("/expiring")
def expiring(days: int = 30, db: Database = Depends(get_db)):
    return [_normalize_out(a, db) for a in db.get_expiring_assets(days=days)]


@router.get("/expiring-detail")
def expiring_detail_endpoint(days: int = 30, db: Database = Depends(get_db)):
    return bid_service.expiring_detail(db, days)


@router.get("/field-config")
def get_field_config():
    return settings_store.get_field_config()


@router.put("/field-config")
def save_field_config(body: FieldConfigIn):
    return settings_store.save_field_config(body.model_dump())


_TEMPLATE_FILENAMES = {"person": "人员导入模板.xlsx", "contract": "合同导入模板.xlsx"}


def _check_subtype(subtype: str | None) -> None:
    if subtype is None:
        return
    try:
        validate_contract_subtype(subtype)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/import-template")
def import_template(type: str, subtype: str | None = None):
    if type not in _TEMPLATE_FILENAMES:
        raise HTTPException(400, "仅支持 type=person|contract")
    _check_subtype(subtype)
    if subtype is not None and type != "contract":
        raise HTTPException(400, "仅合同模板支持 subtype 参数")
    content = build_import_template(type, subtype)
    base = _TEMPLATE_FILENAMES[type]
    if subtype:
        base = base.replace(".xlsx", f"-{subtype}.xlsx")
    filename = quote(base)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/import")
def import_assets(type: str, file: UploadFile, subtype: str | None = None,
                  db: Database = Depends(get_db)):
    _check_type(type)
    if type not in ("credit", "person", "contract"):
        raise HTTPException(400, "仅资信证书/常用人员/合同业绩支持 Excel 导入")
    if subtype is not None and type != "contract":
        raise HTTPException(400, "仅合同导入支持 subtype 参数")
    _check_subtype(subtype)
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "仅支持 .xlsx 文件")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        return import_assets_excel(db, type, tmp_path, subtype=subtype)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("")
def list_assets(type: str | None = None, db: Database = Depends(get_db)):
    return [_normalize_out(a, db) for a in db.get_assets(type=type)]


@router.post("")
def create_asset(body: AssetIn, db: Database = Depends(get_db)):
    _check_type(body.type)
    fields, expiry = body.fields, body.expiry_date
    if body.type == "person":
        fields, expiry = _prepare_person_write(fields, expiry)
    return {"id": db.create_asset(body.type, body.name, fields,
                                  body.file_path, expiry)}


@router.get("/{asset_id}")
def get_asset(asset_id: int, db: Database = Depends(get_db)):
    a = db.get_asset(asset_id)
    if not a:
        raise HTTPException(404, "资产不存在")
    return _normalize_out(a, db)


@router.put("/{asset_id}")
def update_asset(asset_id: int, body: AssetUpdate, db: Database = Depends(get_db)):
    asset = db.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "资产不存在")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if asset.get("type") == "person" and "fields" in updates:
        fields, expiry = _prepare_person_write(
            updates["fields"], updates.get("expiry_date") or asset.get("expiry_date") or "")
        updates["fields"] = fields
        if expiry:
            updates["expiry_date"] = expiry
    db.update_asset(asset_id, **updates)
    return {"ok": True}


@router.delete("/{asset_id}")
def delete_asset(asset_id: int, db: Database = Depends(get_db)):
    asset = db.get_asset(asset_id)
    if asset and asset.get("file_path"):
        Path(asset["file_path"]).unlink(missing_ok=True)
    db.delete_asset(asset_id)
    return {"ok": True}


@router.post("/{asset_id}/file")
def upload_asset_file(asset_id: int, file: UploadFile, db: Database = Depends(get_db)):
    asset = db.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "资产不存在")
    config.ensure_dirs()
    suffix = Path(file.filename or "").suffix.lower()
    dest = config.FILES_DIR / f"asset_{asset_id}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    db.update_asset(asset_id, file_path=str(dest))
    return {"file_path": str(dest)}
