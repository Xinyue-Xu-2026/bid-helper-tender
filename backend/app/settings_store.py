"""应用设置存取（API Key、解析模型等），存 data/config.json。"""
import json
import os

from app import config

DEFAULT_MODEL = "kimi-k3"


def _settings_file():
    return config.DATA_DIR / "config.json"


def load_settings() -> dict:
    f = _settings_file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(data: dict) -> None:
    config.ensure_dirs()
    _settings_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_api_key() -> str:
    """环境变量 MOONSHOT_API_KEY 优先，其次 config.json 的 api_key。"""
    return os.environ.get("MOONSHOT_API_KEY", "") or load_settings().get("api_key", "")


def get_model() -> str:
    return load_settings().get("model", DEFAULT_MODEL)


# ---------- 统一字段配置（人员/合同） ----------

FIELD_TYPES = ("text", "date", "dropdown")

DEFAULT_FIELD_CONFIG = {
    "person": [
        {"key": "部门", "type": "text", "options": []},
        {"key": "职称", "type": "text", "options": []},
        {"key": "联系方式", "type": "text", "options": []},
    ],
    "contract": [
        {"key": "项目名称", "type": "text", "options": []},
        {"key": "类型", "type": "dropdown", "options": ["编标", "审标", "跟踪", "结算"]},
        {"key": "合同金额", "type": "text", "options": []},
        {"key": "年份", "type": "text", "options": []},
        {"key": "甲方", "type": "text", "options": []},
        {"key": "项目经理", "type": "text", "options": []},
    ],
}

# 姓名内置为资产 name 列，字段配置中不允许出现
BUILTIN_FIELD_KEYS = ("姓名",)


def _copy_defaults(kind: str) -> list:
    return [{"key": f["key"], "type": f["type"], "options": list(f["options"])}
            for f in DEFAULT_FIELD_CONFIG[kind]]


def _normalize_field_list(entries) -> list:
    """规范化字段列表：剔除内置字段（姓名）、去空 key、去重（保序）、
    非法 type 回退 text、options 只留非空字符串。"""
    if not isinstance(entries, list):
        return []
    result = []
    seen = set()
    for e in entries:
        if not isinstance(e, dict):
            continue
        key = str(e.get("key") or "").strip()
        if not key or key in seen or key in BUILTIN_FIELD_KEYS:
            continue
        seen.add(key)
        ftype = e.get("type") if e.get("type") in FIELD_TYPES else "text"
        raw_options = e.get("options")
        options = ([str(o).strip() for o in raw_options if str(o).strip()]
                   if isinstance(raw_options, list) else [])
        result.append({"key": key, "type": ftype, "options": options})
    return result


def get_field_config() -> dict:
    """读取统一字段配置；未保存或某类为空时返回该类默认配置。"""
    raw = load_settings().get("field_config") or {}
    result = {}
    for kind in ("person", "contract"):
        entries = _normalize_field_list(raw.get(kind))
        result[kind] = entries if entries else _copy_defaults(kind)
    return result


def save_field_config(cfg: dict) -> dict:
    """保存统一字段配置（存 settings 的 field_config 键），返回规范化后的配置。"""
    normalized = {kind: _normalize_field_list((cfg or {}).get(kind))
                  for kind in ("person", "contract")}
    all_settings = load_settings()
    all_settings["field_config"] = normalized
    save_settings(all_settings)
    return normalized
