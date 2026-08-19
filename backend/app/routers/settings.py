from fastapi import APIRouter
from pydantic import BaseModel

from app.core.llm_parser import (
    CODING_DEFAULT_MODEL, CODING_MODELS, _friendly_api_error, _make_client, is_coding_key,
)
from app.settings_store import get_api_key, get_model, load_settings, save_settings

router = APIRouter()


class SettingsIn(BaseModel):
    api_key: str | None = None
    model: str | None = None


@router.get("")
def read_settings():
    return {"api_key": get_api_key(), "model": get_model()}


@router.put("")
def write_settings(body: SettingsIn):
    data = load_settings()
    if body.api_key is not None:
        data["api_key"] = body.api_key
    if body.model is not None:
        data["model"] = body.model
    save_settings(data)
    return {"ok": True}


@router.post("/test")
def test_connection(body: SettingsIn | None = None):
    # 请求体（表单当前值）优先，为空/缺省时回退到磁盘已保存值
    api_key = (body.api_key if body else None) or get_api_key()
    if not api_key:
        return {"ok": False, "message": "未配置 API Key"}
    model = (body.model if body else None) or get_model()
    # 与 parse_with_llm 一致：编程订阅 Key 只能走编程模型
    if is_coding_key(api_key) and model not in CODING_MODELS:
        model = CODING_DEFAULT_MODEL
    try:
        client = _make_client(api_key, timeout=30.0)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return {"ok": True, "message": "连接成功"}
    except Exception as exc:
        return {"ok": False, "message": _friendly_api_error(exc)}
