import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app import config
from app.db import ASSET_TYPES, Database
from app.deps import get_db
from app.services.asset_service import import_assets_excel

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


def _check_type(t: str):
    if t not in ASSET_TYPES:
        raise HTTPException(400, f"非法资产类型 {t}，可选：{'/'.join(ASSET_TYPES)}")


# 注意：/expiring 必须在 /{asset_id} 之前注册
@router.get("/expiring")
def expiring(days: int = 30, db: Database = Depends(get_db)):
    return db.get_expiring_assets(days=days)


@router.post("/import")
def import_assets(type: str, file: UploadFile, db: Database = Depends(get_db)):
    _check_type(type)
    if type not in ("credit", "person"):
        raise HTTPException(400, "仅资信证书/常用人员支持 Excel 导入")
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "仅支持 .xlsx 文件")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    return import_assets_excel(db, type, tmp_path)


@router.get("")
def list_assets(type: str = None, db: Database = Depends(get_db)):
    return db.get_assets(type=type)


@router.post("")
def create_asset(body: AssetIn, db: Database = Depends(get_db)):
    _check_type(body.type)
    return {"id": db.create_asset(body.type, body.name, body.fields,
                                  body.file_path, body.expiry_date)}


@router.get("/{asset_id}")
def get_asset(asset_id: int, db: Database = Depends(get_db)):
    a = db.get_asset(asset_id)
    if not a:
        raise HTTPException(404, "资产不存在")
    return a


@router.put("/{asset_id}")
def update_asset(asset_id: int, body: AssetUpdate, db: Database = Depends(get_db)):
    if not db.get_asset(asset_id):
        raise HTTPException(404, "资产不存在")
    db.update_asset(asset_id, **{k: v for k, v in body.model_dump().items() if v is not None})
    return {"ok": True}


@router.delete("/{asset_id}")
def delete_asset(asset_id: int, db: Database = Depends(get_db)):
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
