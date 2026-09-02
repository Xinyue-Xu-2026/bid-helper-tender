"""共享文件夹资料识别入库：设置、扫描、确认。"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import settings_store
from app.db import Database
from app.deps import get_db
from app.services import import_service
from app.services.import_service import DEFAULT_CONTRACT_MAPPING, DEFAULT_PERSON_MAPPING

router = APIRouter()


class ImportSettings(BaseModel):
    shared_folder: str = ""
    person_mapping: dict = Field(default_factory=lambda: dict(DEFAULT_PERSON_MAPPING))
    contract_mapping: dict = Field(default_factory=lambda: dict(DEFAULT_CONTRACT_MAPPING))
    llm_extract_enabled: bool = False


class RecognitionItem(BaseModel):
    id: str = ""
    source: str = "excel"
    file_name: str = ""
    asset_type: str = "person"
    action: str = "new"
    fields: dict = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    highlight: bool = False


class ConfirmBody(BaseModel):
    items: List[RecognitionItem]


def _load_import_settings() -> dict:
    s = settings_store.load_settings().get("import") or {}
    return {
        "shared_folder": s.get("shared_folder", ""),
        "person_mapping": s.get("person_mapping") or dict(DEFAULT_PERSON_MAPPING),
        "contract_mapping": s.get("contract_mapping") or dict(DEFAULT_CONTRACT_MAPPING),
        "llm_extract_enabled": bool(s.get("llm_extract_enabled", False)),
    }


@router.get("/settings")
def get_import_settings():
    return _load_import_settings()


@router.put("/settings")
def save_import_settings(body: ImportSettings):
    all_settings = settings_store.load_settings()
    all_settings["import"] = body.model_dump()
    settings_store.save_settings(all_settings)
    return _load_import_settings()


@router.post("/scan")
def scan(db: Database = Depends(get_db)):
    return import_service.scan_folder_assets(db, _load_import_settings())


@router.post("/confirm")
def confirm(body: ConfirmBody, db: Database = Depends(get_db)):
    return import_service.confirm_items(db, [i.model_dump() for i in body.items])
