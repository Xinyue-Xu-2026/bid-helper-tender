"""章节标题 AI 项目化改写：把模板章节标题改写为贴合本项目的标题（保持层级语义与数量）。"""
import json

from app.core.llm_parser import (
    CODING_DEFAULT_MODEL,
    CODING_MODELS,
    LLMParseError,
    _friendly_api_error,
    _make_client,
    is_coding_key,
)

ADAPT_TITLES_PROMPT = """你是投标文件编制专家。用户提供投标文件章节标题列表（按层级组织，全角空格缩进表示层级）、项目名称与招标要求摘要。请把每个标题改写为与本项目贴合的项目化标题。
规则：
1. 改写应融入项目名称或项目具体对象（如"工程概况"→"GZ659商业综合体项目概况"），保持层级语义不变；
2. 保留原有编号前缀（如"第一章""1.1""（一）"）；
3. 数量与顺序必须与输入标题一一对应，不得增删；
4. 只输出 JSON 对象：{"titles": ["改写后标题1", "改写后标题2", ...]}（不含缩进空格），不要输出任何其他文字。"""

MAX_SUMMARY_CHARS = 3000


def parse_adapted_titles(content: str, expected_count: int) -> list:
    """解析 LLM 返回的标题 JSON；数量不一致或含空标题抛 LLMParseError。"""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMParseError(f"返回内容不是合法 JSON：{exc}") from exc
    items = data.get("titles") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise LLMParseError("返回 JSON 缺少 titles 数组")
    titles = [str(t).strip() for t in items]
    if len(titles) != expected_count:
        raise LLMParseError(f"改写标题数量（{len(titles)}）与原章节数（{expected_count}）不一致")
    if any(not t for t in titles):
        raise LLMParseError("改写结果含空标题")
    return titles


def adapt_titles(titles: list, project_name: str, requirements_summary: str,
                 api_key: str, model: str, client=None) -> list:
    """标题项目化改写；失败抛 LLMParseError。client 用于测试注入。"""
    if not titles:
        return []
    if is_coding_key(api_key) and model not in CODING_MODELS:
        model = CODING_DEFAULT_MODEL
    client = client or _make_client(api_key)
    user_text = (
        f"项目名称：{project_name}\n\n"
        f"招标要求摘要：\n{(requirements_summary or '（无）')[:MAX_SUMMARY_CHARS]}\n\n"
        f"章节标题列表（共 {len(titles)} 条）：\n" + "\n".join(titles)
    )
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": ADAPT_TITLES_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 4096,
    }
    if not is_coding_key(api_key):
        kwargs["temperature"] = 0.2
    try:
        completion = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMParseError(_friendly_api_error(exc)) from exc
    if not completion.choices:
        raise LLMParseError("API 返回缺少 choices")
    return parse_adapted_titles(completion.choices[0].message.content, len(titles))
