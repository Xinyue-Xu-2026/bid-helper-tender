import shutil
from datetime import date
from pathlib import Path

from app import config
from app.core.extractor import extract_text
from app.core.llm_parser import LLMParseError, parse_with_llm
from app.core.parser import parse_tender
from app.core.postprocess import dedupe_and_filter
from app.db import Database
from app.settings_store import get_api_key, get_model


class BidService:
    def __init__(self, db_path: str = None):
        self.db = Database(db_path)
        self.db.init_schema()

    def import_tender(self, project_id: int, source_path: str) -> Path:
        config.ensure_dirs()
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("项目不存在")
        src = Path(source_path)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project["name"])
        dest = config.UPLOADS_DIR / f"{safe_name}_{src.name}"
        shutil.copy2(src, dest)
        self.db.update_project(project_id, tender_file_path=str(dest))
        return dest

    def parse_and_save_requirements(self, project_id: int, progress=None) -> dict:
        """解析招标文件并保存要求。progress(stage: str) 回调各阶段进度。"""
        emit = progress or (lambda stage: None)
        project = self.db.get_project(project_id)
        if not project:
            raise ValueError("项目不存在")
        tender_path = project.get("tender_file_path") or ""
        if not tender_path:
            raise ValueError("请先上传招标文件")

        emit("正在抽取文件文本…")
        text = extract_text(tender_path)

        engine = "rule"
        warning = None
        reqs = None
        api_key = get_api_key()
        if api_key:
            emit("正在调用 Kimi AI 解析（通常需要 1-3 分钟）…")
            try:
                reqs = parse_with_llm(text, api_key, get_model())
                engine = "ai"
            except LLMParseError as exc:
                warning = str(exc)
                emit(f"AI 解析失败，回退规则解析：{warning}")
        else:
            emit("未配置 API Key，使用规则解析")
        if reqs is None:
            reqs = parse_tender(text)

        reqs = dedupe_and_filter(reqs)
        emit(f"解析完成，正在保存 {len(reqs)} 条要求…")

        self.db.replace_requirements(project_id, reqs)
        return {"requirements": reqs, "engine": engine, "warning": warning}


# ---------- 商务标：项目维度的拟派人员/企业业绩勾选、证书警告、证书级到期明细 ----------

from app.services.asset_service import normalize_date  # noqa: E402


def _cert_expiry(cert: dict) -> str:
    """证书有效期：统一取"有效期至"键，规范为 YYYY-MM-DD。"""
    cert = cert or {}
    return normalize_date(cert.get("有效期至") or "")


def _cert_name(cert: dict) -> str:
    return cert.get("类型") or "证书"


def cert_warnings(person_fields: dict, bid_date: str, today: date, days: int = 30) -> list:
    """人员证书警告：有效期早于投标日 → expired（最高优先，不再判 soon）；
    否则 0 <= (有效期 - today).days <= days → soon。解析失败/为空跳过。"""
    warnings = []
    bid = None
    norm_bid = normalize_date(bid_date)
    if norm_bid:
        bid = date.fromisoformat(norm_bid)
    for cert in (person_fields or {}).get("证书") or []:
        if not isinstance(cert, dict):
            continue
        expiry = _cert_expiry(cert)
        if not expiry:
            continue
        expiry_date = date.fromisoformat(expiry)
        if bid and expiry_date < bid:
            warnings.append({
                "cert_name": _cert_name(cert),
                "expiry": expiry,
                "level": "expired",
                "message": f"有效期 {expiry} 早于投标日 {norm_bid}",
            })
            continue
        days_left = (expiry_date - today).days
        if 0 <= days_left <= days:
            warnings.append({
                "cert_name": _cert_name(cert),
                "expiry": expiry,
                "level": "soon",
                "days_left": days_left,
                "message": f"剩余 {days_left} 天到期",
            })
    return warnings


def get_bid_assets(db: Database, project_id: int) -> dict:
    """设计文档 §5.1：已选人员（含 role/is_lead/certs 与证书警告）与已选业绩（含 section）。
    项目存在性由路由层校验。旧格式存储由 db 层归一化（is_lead=false/certs=null/section=1）。"""
    project = db.get_project(project_id)
    bid_date = (project or {}).get("bid_date") or ""
    today = date.today()
    persons = []
    for row in db.get_project_assets(project_id, asset_type="person"):
        fields = row.get("fields") or {}
        persons.append({
            "asset_id": row["asset_id"],
            "role": row.get("role") or "",
            "is_lead": bool(row.get("is_lead")),
            "certs": row.get("certs"),
            "name": row["name"],
            "fields": fields,
            "expiry_date": row.get("expiry_date") or "",
            "cert_warnings": cert_warnings(fields, bid_date, today, days=30),
        })
    contracts = [
        {"asset_id": row["asset_id"], "section": row.get("section") or 1,
         "name": row["name"], "fields": row.get("fields") or {}}
        for row in db.get_project_assets(project_id, asset_type="contract")
    ]
    return {"persons": persons, "contracts": contracts}


def save_bid_assets(db: Database, project_id: int, persons: list, contracts: list) -> None:
    """校验后覆盖式保存勾选：asset_id 必须存在且类型匹配（persons→person，contracts→contract）。
    persons 条目可含 is_lead/certs；contracts 兼容裸 id 与 {asset_id, section}。"""
    person_ids = [p["asset_id"] for p in persons]
    contract_ids = [c["asset_id"] if isinstance(c, dict) else c for c in contracts]
    found = {}
    for aid in set(person_ids + contract_ids):
        asset = db.get_asset(aid)
        if asset:
            found[aid] = asset
    missing = sorted({aid for aid in person_ids + contract_ids if aid not in found})
    if missing:
        raise ValueError(f"资产不存在: {missing}")
    mismatched = sorted(
        {aid for aid in person_ids if found[aid]["type"] != "person"}
        | {aid for aid in contract_ids if found[aid]["type"] != "contract"})
    if mismatched:
        raise ValueError(f"资产类型不匹配: {mismatched}")
    db.replace_project_assets(project_id, persons, contracts)


def expiring_detail(db: Database, days: int = 30) -> list:
    """设计文档 §5.4：证书级到期明细。person 逐本证书一行；credit 用其 expiry_date。
    含已到期（days_left < 0）与 days 天内到期，按 days_left 升序。"""
    today = date.today()
    rows = []
    for asset in db.get_assets(type="person"):
        certs = (asset.get("fields") or {}).get("证书") or []
        for cert in certs:
            if not isinstance(cert, dict):
                continue
            expiry = _cert_expiry(cert)
            if not expiry:
                continue
            days_left = (date.fromisoformat(expiry) - today).days
            if days_left > days:
                continue
            rows.append({
                "type": "person",
                "asset_name": asset["name"],
                "cert_type": cert.get("类型") or "",
                "cert_name": _cert_name(cert),
                "expiry_date": expiry,
                "days_left": days_left,
            })
    for asset in db.get_assets(type="credit"):
        raw = (asset.get("expiry_date") or "").strip()
        if not raw:
            continue
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            continue
        days_left = (d - today).days
        if days_left > days:
            continue
        rows.append({
            "type": "credit",
            "asset_name": asset["name"],
            "cert_type": "",
            "cert_name": asset["name"],
            "expiry_date": raw,
            "days_left": days_left,
        })
    return sorted(rows, key=lambda r: r["days_left"])


# ---------- 模板式商务标导出：数据组装 ----------

# 合同 fields["类型"] → 服务类型表述
SERVICE_TYPE_MAP = {
    "跟踪": "跟踪审计",
    "结算": "结算审核",
    "编标": "编标（清单及控制价编制）",
    "审标": "审标",
    "水利审计": "水利审计",
    "中标通知书": "中标",
}


def service_type_label(contract_fields: dict) -> str:
    t = str((contract_fields or {}).get("类型") or "").strip()
    return SERVICE_TYPE_MAP.get(t, t)


def effective_work_years(fields: dict) -> str:
    """专业工作年限列：从业年限 + max(0, 今年 - 从业年限基准年)。"""
    fields = fields or {}
    base = str(fields.get("从业年限") or "").strip()
    if not base:
        return ""
    try:
        base_num = int(float(base))
    except (TypeError, ValueError):
        return base
    base_year_raw = str(fields.get("从业年限基准年") or "").strip()
    effective = base_num
    if base_year_raw:
        try:
            base_year = int(base_year_raw[:4])
            effective = base_num + max(0, date.today().year - base_year)
        except (TypeError, ValueError):
            pass
    return f"{effective}年"


def _cert_qualifications(fields: dict) -> str:
    """执业资格列：逐本证书 "{专业}专业{类型}"，多本换行。"""
    parts = []
    for cert in (fields or {}).get("证书") or []:
        if not isinstance(cert, dict):
            continue
        ctype = str(cert.get("类型") or "").strip()
        if not ctype:
            continue
        major = str(cert.get("专业") or "").strip()
        parts.append(f"{major}专业{ctype}" if major else ctype)
    return "\n".join(parts)


def assemble_bid_template_data(db: Database, person_picks: list,
                               contract_picks: list) -> dict:
    """模板式商务标导出数据组装。person_picks: [{asset_id, is_lead}]；
    contract_picks: [{asset_id, section}]。返回 {"a".."g": 各表数据行（不含表头）}。"""
    persons = []
    for pick in person_picks or []:
        asset = db.get_asset(pick.get("asset_id"))
        if asset and asset.get("type") == "person":
            fields = dict(asset.get("fields") or {})
            # 证书按用户勾选过滤：certs 为选中下标列表；未传（None）则保留全部
            indices = pick.get("certs")
            if indices is not None:
                certs = fields.get("证书") or []
                fields["证书"] = [certs[i] for i in indices
                                  if isinstance(i, int) and 0 <= i < len(certs)]
            persons.append({"name": asset["name"], "fields": fields,
                            "is_lead": bool(pick.get("is_lead"))})
    persons.sort(key=lambda p: not p["is_lead"])  # 负责人排最前（稳定排序）

    contracts = []
    for pick in contract_picks or []:
        asset = db.get_asset(pick.get("asset_id"))
        if asset and asset.get("type") == "contract":
            contracts.append({"name": asset["name"], "fields": asset.get("fields") or {},
                              "section": pick.get("section")})

    def person_row(label: str, p: dict) -> list:
        return [label, p["name"], str(p["fields"].get("职称") or ""),
                effective_work_years(p["fields"]),
                _cert_qualifications(p["fields"])]

    lead = next((p for p in persons if p["is_lead"]), None)
    table_a, table_d = [], []
    for i, p in enumerate(persons, 1):
        if lead is not None and p is lead:
            table_a.append(person_row("1.项目负责人", p))
        else:
            table_a.append(person_row(f"{i}.项目组其他人员", p))
    for j, p in enumerate([p for p in persons if p is not lead], 1):
        table_d.append(person_row(f"{j}.项目组其他人员", p))

    def perf5(i: int, c: dict) -> list:
        return [str(i), c["name"], str(c["fields"].get("委托单位") or ""), "",
                f"提供{c['name']}的{service_type_label(c['fields'])}服务"]

    def perf7(i: int, c: dict) -> list:
        return [str(i), c["name"], str(c["fields"].get("委托单位") or ""),
                str(c["fields"].get("签订日期") or ""), "",
                service_type_label(c["fields"]), ""]

    table_e = [perf5(i, c) for i, c in enumerate(contracts, 1)]
    table_f = [perf7(i, c) for i, c in enumerate(
        [c for c in contracts if c["section"] == 1], 1)]
    table_g = [perf7(i, c) for i, c in enumerate(
        [c for c in contracts if c["section"] == 2], 1)]

    lead_contracts = []
    if lead is not None:
        lead_contracts = [
            c for c in contracts
            if str(c["fields"].get("项目负责人") or "").strip() == lead["name"]]
    table_b = [perf5(i, c) for i, c in enumerate(lead_contracts, 1)]
    table_c = [perf7(i, c) for i, c in enumerate(lead_contracts, 1)]

    return {"a": table_a, "b": table_b, "c": table_c, "d": table_d,
            "e": table_e, "f": table_f, "g": table_g, "persons": persons}
