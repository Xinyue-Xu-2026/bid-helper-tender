"""目录大纲 AI 初稿：根据招标要求清单生成标书章节树（嵌套结构）。"""
import json

from app.core.llm_parser import (
    CODING_DEFAULT_MODEL,
    CODING_MODELS,
    LLMParseError,
    _friendly_api_error,
    _make_client,
    is_coding_key,
)

OUTLINE_PROMPT = """你是一名投标文件编制专家。用户提供一份招标文件的要求清单（JSON 数组，每条含 category/content/source），请为投标文件设计目录大纲。
规则：
1. 重点依据「格式要求」（投标文件编制/格式规定）与「评分项」（评分办法决定的响应章节）组织章节；
2. 「资质门槛」类要求通常对应资格审查资料章节；「时间节点」不产生独立章节；
3. 输出 1-3 级层级，章节标题简短规范（如"第一章 资格审查资料"、"1.1 营业执照"）；
4. 只输出 JSON 对象：{"outline": [{"title": "...", "children": [...]}]}，children 可为空数组，不要输出任何其他文字。"""

MAX_REQ_CHARS = 20000


def parse_outline(content: str) -> list:
    """解析 LLM 返回的目录 JSON 为嵌套大纲（level 按嵌套深度重算，最深 3 级）。"""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMParseError(f"返回内容不是合法 JSON：{exc}") from exc
    items = data.get("outline") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise LLMParseError("返回 JSON 缺少 outline 数组")
    outline = [o for o in (_normalize(i, 1) for i in items) if o]
    if not outline:
        raise LLMParseError("outline 数组无有效章节")
    return outline


def _normalize(item, level):
    if not isinstance(item, dict):
        return None
    title = str(item.get("title", "")).strip()
    if not title:
        return None
    children = item.get("children")
    kids = []
    if isinstance(children, list) and level < 3:
        kids = [k for k in (_normalize(c, level + 1) for c in children) if k]
    return {"title": title, "level": level, "children": kids}


def generate_outline(requirements: list, api_key: str, model: str, client=None) -> list:
    """根据要求清单生成嵌套目录大纲；失败抛 LLMParseError。client 用于测试注入。"""
    if not requirements:
        raise LLMParseError("该项目暂无要求清单，请先解析招标文件")
    if is_coding_key(api_key) and model not in CODING_MODELS:
        model = CODING_DEFAULT_MODEL
    client = client or _make_client(api_key)
    req_text = json.dumps(requirements, ensure_ascii=False)[:MAX_REQ_CHARS]
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": OUTLINE_PROMPT},
            {"role": "user", "content": req_text},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 8192,
    }
    if not is_coding_key(api_key):
        kwargs["temperature"] = 0.2
    try:
        completion = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMParseError(_friendly_api_error(exc)) from exc
    if not completion.choices:
        raise LLMParseError("API 返回缺少 choices")
    return parse_outline(completion.choices[0].message.content)
