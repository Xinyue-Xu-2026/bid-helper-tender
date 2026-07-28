"""应用设置存取（API Key、解析模型等），存 data/config.json。"""
import json
import os

from bidhelper import config

SETTINGS_FILE = config.DATA_DIR / "config.json"
DEFAULT_MODEL = "kimi-k2.6"


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(data: dict) -> None:
    config.ensure_dirs()
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_api_key() -> str:
    """环境变量 MOONSHOT_API_KEY 优先，其次 config.json 的 api_key。"""
    return os.environ.get("MOONSHOT_API_KEY", "") or load_settings().get("api_key", "")


def get_model() -> str:
    return load_settings().get("model", DEFAULT_MODEL)
