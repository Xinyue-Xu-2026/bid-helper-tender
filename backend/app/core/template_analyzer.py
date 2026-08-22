"""模板风格画像：模板上传时一次性 LLM 分析，结果存 templates.style_profile。"""
from app.core.extractor import extract_text
from app.core.llm_parser import (
    CODING_DEFAULT_MODEL,
    CODING_MODELS,
    LLMParseError,
    _friendly_api_error,
    _make_client,
    is_coding_key,
)

PROFILE_PROMPT = """你是一名标书写作风格分析专家。用户提供一份既往标书模板的全文，请提炼其「风格画像」，供 AI 后续仿写新标书时参考。输出纯文本，包含四部分：
1. 整体风格：语气、人称、正式程度
2. 常用句式：高频套话/承转句式（列 5-10 条原文例句）
3. 结构特征：章节组织习惯、标题命名风格、编号方式
4. 样式描述：标题层级、段落长度、列表使用习惯
只输出画像文本本身，不要输出任何其他内容。"""

MAX_TEMPLATE_CHARS = 30000


def analyze_template(template_path: str, api_key: str, model: str, client=None) -> str:
    """分析模板 docx 的风格画像；任何失败抛 LLMParseError。client 参数用于测试注入。"""
    text = extract_text(template_path)
    if not text.strip():
        raise LLMParseError("模板内容为空")
    if is_coding_key(api_key) and model not in CODING_MODELS:
        model = CODING_DEFAULT_MODEL
    client = client or _make_client(api_key)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": PROFILE_PROMPT},
            {"role": "user", "content": text[:MAX_TEMPLATE_CHARS]},
        ],
        "max_tokens": 4096,
    }
    # 与 parse_with_llm 一致：coding 网关禁传 temperature，公众平台 0.2
    if not is_coding_key(api_key):
        kwargs["temperature"] = 0.2
    try:
        completion = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMParseError(_friendly_api_error(exc)) from exc
    if not completion.choices:
        raise LLMParseError("API 返回缺少 choices")
    profile = (completion.choices[0].message.content or "").strip()
    if not profile:
        raise LLMParseError("画像分析返回空内容")
    return profile
