"""共享文件夹扫描识别与确认入库编排。

扫描结果不落库（前端持有），confirm 才写入 assets 表。
- 人员证书 → assets type=person
- 企业资质证书 → type=credit
- 合同业绩 → assets type=contract（name=项目名称，fields 含"项目经理"）；
  同（项目名称, 年份）去重合并；项目经理不存在时自动新建 person 占位并标 highlight
"""
import uuid
from pathlib import Path
from typing import Callable, List, Optional

from app import settings_store
from app.core import field_extractor, folder_scanner
from app.db import Database
from app.services.asset_service import (
    CERT_ITEM_KEYS,
    earliest_expiry,
    merge_certs,
    normalize_date,
    person_certs,
    solidify_person_fields,
)

# 非证书类人员字段：confirm 时仍可覆盖更新
PERSON_INFO_FIELDS = ("身份证号", "职称", "联系方式")
PERF_FIELDS = ("项目名称", "类型", "合同金额", "年份", "甲方", "项目经理")

DEFAULT_PERSON_MAPPING = {
    "姓名": "姓名", "证书名称": "证书名称", "职称": "职称",
    "有效期": "证书有效期至", "身份证号": "身份证号", "类型": "类型",
}
DEFAULT_CONTRACT_MAPPING = {
    "项目名称": "项目名称", "项目经理": "项目经理", "合同金额": "合同金额",
    "签订年份": "年份", "年份": "年份", "甲方": "甲方", "类型": "类型",
}


def _contract_keys() -> List[str]:
    """合同业绩字段集合与顺序：由合同字段配置驱动（含项目经理）。"""
    keys = [f["key"] for f in settings_store.get_field_config()["contract"]]
    return keys or list(PERF_FIELDS)


def _new_item(source: str, file_name: str, asset_type: str, action: str,
              fields: dict, warnings: Optional[List[str]] = None, highlight: bool = False) -> dict:
    return {
        "id": uuid.uuid4().hex,
        "source": source,
        "file_name": file_name,
        "asset_type": asset_type,
        "action": action,
        "fields": fields,
        "warnings": warnings or [],
        "highlight": highlight,
    }


def _person_names(db: Database) -> dict:
    return {a["name"]: a for a in db.get_assets(type="person")}


def _existing_person_certs(db: Database) -> set:
    """{(姓名, 类型, 证书名称)}，用于疑似重复检测（同人同类型同证书名才算重复）。"""
    result = set()
    for a in db.get_assets(type="person"):
        for cert in person_certs(a.get("fields") or {}):
            if cert.get("证书名称"):
                result.add((a["name"], cert.get("类型", ""), cert["证书名称"]))
    return result


# ---------- 扫描 ----------

def _process_excel(db: Database, path: Path, settings: dict) -> List[dict]:
    persons, contracts, warnings = field_extractor.parse_excel(
        str(path),
        settings.get("person_mapping") or DEFAULT_PERSON_MAPPING,
        settings.get("contract_mapping") or DEFAULT_CONTRACT_MAPPING,
    )
    known = _person_names(db)
    items: List[dict] = []
    for fields in persons:
        name = fields.get("姓名", "")
        items.append(_new_item(
            "excel", path.name, "person",
            "update" if name in known else "new", fields,
            warnings=list(warnings) if warnings else [],
        ))
        warnings = []  # sheet 级警告只挂到首个 item，避免刷屏

    # 合同业绩：一行一个 contract item（confirm 时按 项目名称+年份 去重合并）
    contract_keys = _contract_keys()
    contract_names = {a["name"] for a in db.get_assets(type="contract")}
    for row in contracts:
        pm = row.get("项目经理", "").strip()
        entry = {k: row[k] for k in contract_keys if row.get(k)}
        if not entry.get("项目名称"):
            continue
        item_warnings = []
        highlight = False
        if not pm:
            highlight = True
            item_warnings.append("该业绩缺少项目经理，请人工补充后再确认")
        elif pm not in known:
            highlight = True
            item_warnings.append(f"项目经理「{pm}」在资产库中不存在，确认后将自动新建人员")
        items.append(_new_item(
            "excel", path.name, "contract",
            "update" if entry["项目名称"] in contract_names else "new",
            entry, warnings=item_warnings, highlight=highlight,
        ))
    return items


def _process_text_file(db: Database, path: Path, settings: dict,
                       llm_func: Optional[Callable] = None) -> List[dict]:
    suffix = path.suffix.lower()
    text, source = field_extractor.extract_text_auto(str(path), suffix)
    if not text.strip():
        return [_new_item(source, path.name, "person", "new", {},
                          warnings=["未能提取到任何文字内容，请人工核对"], highlight=True)]

    fields, warnings = field_extractor.extract_fields_from_text(text)
    asset_type = field_extractor.classify_text(text, fields)

    # LLM 增强（默认关闭，可插拔；失败静默回退正则结果）
    if settings.get("llm_extract_enabled"):
        func = llm_func or field_extractor.extract_with_llm
        llm_result = func(text)
        if llm_result:
            fields.update({k: v for k, v in llm_result["fields"].items() if v})
            if llm_result.get("asset_type"):
                asset_type = llm_result["asset_type"]
            source = "llm"
        else:
            warnings.append("LLM 抽取失败或未配置 API Key，已回退到规则抽取")

    action = "new"
    if asset_type == "person" and fields.get("姓名") in _person_names(db):
        action = "update"
    elif asset_type == "credit":
        credit_name = fields.get("证书名称", "")
        if credit_name and any(a["name"] == credit_name for a in db.get_assets(type="credit")):
            action = "update"
    return [_new_item(source, path.name, asset_type, action, fields, warnings=warnings)]


def _dedup_check(db: Database, items: List[dict]):
    """同人员+同类型+同证书名标"疑似重复"（对照资产库及本次扫描批次），不自动合并。"""
    existing = _existing_person_certs(db)
    seen_in_batch = {}
    for item in items:
        if item["asset_type"] != "person":
            continue
        name = (item["fields"].get("姓名") or "").strip()
        cert = (item["fields"].get("证书名称") or "").strip()
        cert_type = (item["fields"].get("类型") or "").strip()
        if not name or not cert:
            continue
        key = (name, cert_type, cert)
        if key in existing:
            item["warnings"].append(f"疑似重复：与现有人员{name}的{cert}证书相同")
        if key in seen_in_batch:
            other = seen_in_batch[key]
            item["warnings"].append(
                f"疑似重复：与本次扫描文件「{other}」中的{name}{cert}相同")
        else:
            seen_in_batch[key] = item["file_name"]


def scan_folder_assets(db: Database, settings: dict,
                       llm_func: Optional[Callable] = None) -> dict:
    """扫描共享文件夹，返回 {"items": [...], "errors": [...]}。结果不落库。"""
    files, errors = folder_scanner.scan_folder(settings.get("shared_folder", ""))
    items: List[dict] = []
    for path in files:
        try:
            if path.suffix.lower() in (".xlsx", ".xls"):
                items.extend(_process_excel(db, path, settings))
            else:
                items.extend(_process_text_file(db, path, settings, llm_func))
        except RuntimeError as exc:  # OCR 不可用等可预期降级
            errors.append({"filename": path.name, "reason": str(exc)})
        except Exception as exc:
            errors.append({"filename": path.name, "reason": f"解析失败：{exc}"})
    _dedup_check(db, items)
    return {"items": items, "errors": errors}


# ---------- 确认入库 ----------

def _item_certs(fields: dict) -> list:
    """从识别条目 fields 提取证书条目（新结构"证书"数组或旧单值均可）。"""
    result = []
    for cert in person_certs(fields):
        item = dict(cert)
        for key in CERT_ITEM_KEYS:
            item.setdefault(key, "")
        item["有效期至"] = normalize_date(item.get("有效期至") or "")
        if any(v not in (None, "") for v in item.values()):
            result.append(item)
    return result


def _confirm_person(db: Database, item: dict, known: dict,
                    new_persons: List[str]) -> str:
    """返回 'created' / 'updated' / 'skipped'。"""
    fields = item.get("fields") or {}
    name = (fields.get("姓名") or fields.get("name") or "").strip()
    if not name:
        return "skipped"
    info = {k: v for k, v in fields.items()
            if k in PERSON_INFO_FIELDS and v not in (None, "")}
    new_certs = _item_certs(fields)

    existing = known.get(name)
    if existing:
        merged = solidify_person_fields(existing.get("fields") or {})
        merged.update(info)
        if new_certs:
            # 同人不同证往"证书"数组追加，不再 merged.update 覆盖
            merged["证书"] = merge_certs(merged["证书"], new_certs)
        kwargs: dict = {"name": name, "fields": merged}
        expiry = earliest_expiry(merged["证书"])
        if expiry:
            kwargs["expiry_date"] = expiry  # expiry_date 列取所有证书最早有效期
        db.update_asset(existing["id"], **kwargs)
        existing["fields"] = merged  # 保持 known 新鲜，供同批次后续条目合并
        return "updated"

    new_fields = dict(info)
    new_fields["证书"] = new_certs
    expiry = earliest_expiry(new_certs)
    new_id = db.create_asset("person", name, new_fields, expiry_date=expiry)
    known[name] = {"id": new_id, "name": name, "fields": new_fields}  # 同批次后续条目可引用
    new_persons.append(name)
    return "created"


def _ensure_person(db: Database, name: str, known: dict, new_persons: List[str]):
    """项目经理不存在时自动新建 person 占位。"""
    if name and name not in known:
        new_id = db.create_asset("person", name, {"证书": []})
        known[name] = {"id": new_id, "name": name, "fields": {"证书": []}}
        new_persons.append(name)


def _confirm_contract(db: Database, item: dict, known: dict,
                      new_persons: List[str]) -> str:
    """合同业绩 → contract 资产；同（项目名称, 年份）去重合并。返回 created/updated/skipped。"""
    fields = item.get("fields") or {}
    name = (fields.get("项目名称") or fields.get("name") or "").strip()
    if not name:
        return "skipped"
    entry = {k: v for k, v in fields.items()
             if k not in ("项目名称", "name", "业绩") and v not in (None, "")}
    pm = str(entry.get("项目经理") or "").strip()
    if pm:
        _ensure_person(db, pm, known, new_persons)
    year = str(entry.get("年份", ""))
    for a in db.get_assets(type="contract"):
        if a["name"] == name and str((a.get("fields") or {}).get("年份", "")) == year:
            merged = dict(a.get("fields") or {})
            merged.update(entry)
            db.update_asset(a["id"], fields=merged)
            return "updated"
    db.create_asset("contract", name, entry)
    return "created"


def _confirm_credit(db: Database, item: dict) -> str:
    fields = item.get("fields") or {}
    name = (fields.get("证书名称") or fields.get("名称") or "").strip()
    if not name:
        return "skipped"
    credit_fields = {k: v for k, v in fields.items()
                     if k not in ("证书名称", "名称") and v not in (None, "")}
    expiry = normalize_date(fields.get("有效期至") or fields.get("证书有效期至") or "")
    for a in db.get_assets(type="credit"):
        if a["name"] == name:
            merged = dict(a.get("fields") or {})
            merged.update(credit_fields)
            kwargs: dict = {"fields": merged}
            if expiry:
                kwargs["expiry_date"] = expiry
            db.update_asset(a["id"], **kwargs)
            return "updated"
    db.create_asset("credit", name, credit_fields, expiry_date=expiry)
    return "created"


def confirm_items(db: Database, items: List[dict]) -> dict:
    """人工勾选后的 RecognitionItem 子集写入资产库。"""
    created = updated = 0
    new_persons: List[str] = []
    known = _person_names(db)
    for item in items:
        asset_type = item.get("asset_type")
        if asset_type == "credit":
            result = _confirm_credit(db, item)
        elif asset_type == "contract":
            result = _confirm_contract(db, item, known, new_persons)
        else:
            # 兼容旧条目：person.fields["业绩"] 数组转 contract 资产后再处理人员
            fields = item.get("fields") or {}
            perfs = fields.get("业绩") or []
            if perfs:
                pm = (fields.get("姓名") or fields.get("name") or "").strip()
                for perf in perfs:
                    if not isinstance(perf, dict):
                        continue
                    contract_fields = dict(perf)
                    if pm:
                        contract_fields.setdefault("项目经理", pm)
                    _confirm_contract(db, {"fields": contract_fields}, known, new_persons)
                item = {**item,
                        "fields": {k: v for k, v in fields.items() if k != "业绩"}}
            result = _confirm_person(db, item, known, new_persons)
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1
    return {"created": created, "updated": updated, "new_persons": new_persons}
