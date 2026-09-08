"""合规自动核对：把商务标已选人员/业绩与要求清单的废标项/资质门槛做规则化比对。"""
import json
import re

from app.services import bid_service
from app.services.asset_service import normalize_date
from app.core import llm_parser
from app.core.llm_parser import LLMParseError
from app.settings_store import get_api_key, get_model

CHECK_CATEGORIES = ("废标项", "资质门槛")

# 证书类型关键词（长词在前，避免"造价工程师"误吞"一级造价工程师"）
_CERT_TYPE_KWS = ["一级造价工程师", "一级注册造价工程师", "二级造价师", "二级造价工程师",
                  "一级建造师", "二级建造师", "监理工程师", "注册监理工程师",
                  "咨询工程师", "造价工程师", "建造师"]
# 专业别名 → 规范简称（证书"专业"字段用的简称）
_MAJOR_ALIASES = [
    ("土木建筑工程", "土建"), ("土木工程", "土建"), ("土建", "土建"),
    ("安装工程", "安装"), ("安装", "安装"),
    ("水利水电", "水利"), ("水利", "水利"),
    ("公路", "公路"), ("道路", "公路"), ("交通", "交通"),
    ("市政", "市政"), ("电力", "电力"), ("机电", "机电"),
]
_SERVICE_KWS = ["跟踪审计", "结算审核", "跟踪", "结算", "编标", "审标", "水利审计"]
# 承诺/格式/材料类关键词（规则无法判定，标 manual）
_MANUAL_KWS = ["联合体", "中小企业", "声明", "承诺", "盖章", "密封", "装订", "保证金",
               "信用", "截止", "份数", "原件", "扫描", "缴纳", "社保", "发票", "付款"]


def _norm_cert_type(t):
    t = t.replace("注册", "")
    for kw in _CERT_TYPE_KWS:
        if kw in t:
            return kw
    return t


def _norm_major(t):
    for alias, norm in _MAJOR_ALIASES:
        if alias in t:
            return norm
    return t


def _lead_person(persons):
    for p in persons:
        role = str(p.get("role") or "")
        if "负责" in role or "经理" in role:
            return p
    return persons[0] if persons else None


def _certs(p):
    return [c for c in ((p.get("fields") or {}).get("证书") or []) if isinstance(c, dict)]


def _year_of(c):
    y = str((c.get("fields") or {}).get("年份") or "").strip()
    m = re.match(r"(\d{4})", y)
    return int(m.group(1)) if m else None


def _check_one(content, persons, contracts, lead, bid_date):
    """单条要求的规则化判定，返回 (verdict, reason)。"""
    # 1) 人数
    m = re.search(r"(?:不少于|至少|按|配备|配置)\s*(\d+)\s*人", content)
    if m:
        n = int(m.group(1))
        if len(persons) >= n:
            return "pass", f"已选 {len(persons)} 人 ≥ {n} 人"
        return "fail", f"已选 {len(persons)} 人，少于要求的 {n} 人"

    # 2) 证书类型/专业/有效期
    cert_reqs = {_norm_cert_type(kw) for kw in _CERT_TYPE_KWS if kw in content}
    major_reqs = {_norm_major(a) for a, _ in _MAJOR_ALIASES if a in content}
    if cert_reqs or major_reqs:
        targets = persons
        if "项目负责人" in content or "项目经理" in content:
            targets = [lead] if lead else persons
        for p in targets:
            for c in _certs(p):
                if cert_reqs and _norm_cert_type(str(c.get("类型") or "")) not in cert_reqs:
                    continue
                if major_reqs and _norm_major(str(c.get("专业") or "")) not in major_reqs:
                    continue
                if "有效期" in content and bid_date:
                    exp = normalize_date(c.get("有效期至") or "")
                    bid = normalize_date(bid_date)
                    if exp and bid and exp < bid:
                        return "fail", (f"{p['name']} 的{c.get('类型') or '证书'}有效期 {exp} "
                                        f"早于投标日 {bid}")
                return "pass", f"{p['name']} 具备匹配证书"
        return "fail", ("未找到满足要求的证书（需 "
                        + "、".join(sorted(cert_reqs | major_reqs)) + "）")

    # 3) 职称
    targets = persons
    if "项目负责人" in content:
        targets = [lead] if lead else persons
    if "高级工程师" in content or "高级职称" in content or "高级及以上" in content:
        for p in targets:
            if "高级" in str((p.get("fields") or {}).get("职称") or ""):
                return "pass", f"{p['name']} 为高级工程师"
        return "fail", "人员职称未达高级工程师"
    if "工程师" in content:
        for p in targets:
            if "工程师" in str((p.get("fields") or {}).get("职称") or ""):
                return "pass", f"{p['name']} 为工程师"
        return "fail", "人员职称未达工程师"

    # 4) 业绩
    if re.search(r"20\d{2}\s*年", content) and any(
            k in content for k in ("业绩", "跟踪", "结算", "编标", "审标", "承担", "类似", "中标")):
        years = [int(y) for y in re.findall(r"(20\d{2})\s*年", content)]
        threshold = min(years)
        type_reqs = [k for k in _SERVICE_KWS if k in content]
        matched = 0
        for c in contracts:
            ctype = str((c.get("fields") or {}).get("类型") or "")
            if type_reqs and not any(k in ctype for k in type_reqs):
                continue
            year = _year_of(c)
            if year is None or year < threshold:
                continue
            matched += 1
        if matched >= 1:
            return "pass", f"已选 {matched} 份相关业绩"
        return "fail", "未选到满足条件的业绩"

    # 5) 承诺/材料类
    if any(k in content for k in _MANUAL_KWS):
        return "manual", "属承诺/材料/格式类，需人工核对"

    # 6) 兜底
    return "manual", ""


def auto_check(db, project_id):
    """规则化自动核对：返回按 verdict 排序的核对项（fail 最前、manual 次之、pass 最后）。"""
    project = db.get_project(project_id)
    bid_date = (project or {}).get("bid_date") or ""
    bid = bid_service.get_bid_assets(db, project_id)
    persons = bid["persons"]
    contracts = bid["contracts"]
    lead = _lead_person(persons)
    items = []
    for req in db.get_requirements(project_id):
        if req["category"] not in CHECK_CATEGORIES:
            continue
        verdict, reason = _check_one(req["content"], persons, contracts, lead, bid_date)
        items.append({**req, "verdict": verdict, "reason": reason})
    order = {"fail": 0, "manual": 1, "pass": 2}
    items.sort(key=lambda x: order.get(x["verdict"], 2))
    return items


_AI_SYSTEM_PROMPT = ("你是投标合规核对助手。根据要求与投标方已选人员/业绩，"
                     "判断该要求是否满足。只输出 JSON。")


def _build_ai_payload(persons, contracts, requirements, bid_date):
    """组装 AI 核对的 user 提示词（人员最多 15 人、业绩最多 50 条）。"""
    persons_brief = [{
        "姓名": p.get("name") or "",
        "职称": str((p.get("fields") or {}).get("职称") or ""),
        "证书": [{"类型": c.get("类型") or "", "专业": c.get("专业") or "",
                 "有效期至": c.get("有效期至") or ""} for c in _certs(p)],
    } for p in persons[:15]]
    contracts_brief = [{
        "项目名称": c.get("name") or "",
        "类型": str((c.get("fields") or {}).get("类型") or ""),
        "年份": str((c.get("fields") or {}).get("年份") or ""),
    } for c in contracts[:50]]
    reqs_brief = [{"id": r["id"], "content": r["content"]} for r in requirements]
    return (f"投标日期: {bid_date or '未填'}\n"
            f"已选人员: {json.dumps(persons_brief, ensure_ascii=False)}\n"
            f"已选业绩: {json.dumps(contracts_brief, ensure_ascii=False)}\n"
            f"待核对要求: {json.dumps(reqs_brief, ensure_ascii=False)}\n"
            "请逐条给出 verdict（pass=满足 / fail=不满足 / manual=无法判断）和一句话 reason。\n"
            '只输出：{"results":[{"id":<int>,"verdict":"pass|fail|manual","reason":"..."}]}')


def ai_check(db, project_id, requirement_ids=None):
    """AI 兜底核对：默认只判规则判定为 manual 的要求；requirement_ids 给定则只判这些。"""
    project = db.get_project(project_id)
    bid_date = (project or {}).get("bid_date") or ""
    bid = bid_service.get_bid_assets(db, project_id)
    persons = bid["persons"]
    contracts = bid["contracts"]

    reqs = [r for r in db.get_requirements(project_id) if r["category"] in CHECK_CATEGORIES]
    if requirement_ids:
        wanted = set(requirement_ids)
        reqs = [r for r in reqs if r["id"] in wanted]
    else:
        lead = _lead_person(persons)
        reqs = [r for r in reqs
                if _check_one(r["content"], persons, contracts, lead, bid_date)[0] == "manual"]
    if not reqs:
        return []

    api_key = get_api_key()
    if not api_key:
        raise LLMParseError("未配置 API Key")
    model = get_model() or llm_parser.DEFAULT_MODEL
    if llm_parser.is_coding_key(api_key) and model not in llm_parser.CODING_MODELS:
        model = llm_parser.CODING_DEFAULT_MODEL
    client = llm_parser._make_client(api_key)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": _AI_SYSTEM_PROMPT},
            {"role": "user", "content": _build_ai_payload(persons, contracts, reqs, bid_date)},
        ],
        "response_format": {"type": "json_object"},
        # 编程网关的推理模型思考过程也占输出额度，需更大余量（同 parse_with_llm）
        "max_tokens": 16384 if llm_parser.is_coding_key(api_key) else 8192,
    }
    if not llm_parser.is_coding_key(api_key):
        kwargs["temperature"] = 0.2
    try:
        completion = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMParseError(llm_parser._friendly_api_error(exc)) from exc

    if not completion.choices:
        raise LLMParseError("API 返回缺少 choices")
    choice = completion.choices[0]
    if choice.finish_reason == "length":
        raise LLMParseError("输出被截断（finish_reason=length）")
    try:
        data = json.loads(choice.message.content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMParseError(f"返回内容不是合法 JSON：{exc}") from exc

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise LLMParseError("返回 JSON 缺少 results 数组")

    valid_ids = {r["id"] for r in reqs}
    out = []
    for item in results:
        if not isinstance(item, dict):
            continue
        try:
            rid = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if rid not in valid_ids:
            continue
        verdict = str(item.get("verdict") or "").strip()
        if verdict not in ("pass", "fail", "manual"):
            verdict = "manual"
        out.append({"requirement_id": rid, "verdict": verdict,
                    "reason": str(item.get("reason") or "")})
    return out
