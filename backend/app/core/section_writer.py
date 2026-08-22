"""单节正文生成：组装 prompt 并流式调用 LLM。"""
from app.core.llm_parser import (
    CODING_DEFAULT_MODEL,
    CODING_MODELS,
    LLMParseError,
    _friendly_api_error,
    _make_client,
    is_coding_key,
)

SECTION_SYSTEM_PROMPT = """你是资深投标文件编写专家。根据招标要求与参考资料，撰写投标文件某一章节的正文。要求：
1. 只输出本节正文纯文本，不要标题、不要 markdown 标记、不要任何解释；
2. 语言正式专业，语气客观，符合投标文件规范；
3. 逐条响应「本节需响应的招标要求」，内容充实、有针对性；
4. 若提供了模板风格画像或范文节选，模仿其写作风格与句式；
5. 若提供了参考资料，优先采用其中的企业信息、资质、业绩等真实材料。"""


def build_section_prompt(section_title: str, outline_titles: list, requirements: list,
                         style_text: str = "", assets_text: str = "") -> str:
    """组装单节生成 prompt；各部分均可空，缺失时自动省略。"""
    blocks = [f"当前撰写章节：{section_title}"]
    if outline_titles:
        blocks.append("标书完整目录（把握章节位置与前后衔接）：\n" + "\n".join(outline_titles))
    if style_text:
        blocks.append(style_text)
    if requirements:
        req_lines = "\n".join(
            f"- [{r.get('category', '')}] {r.get('content', '')}（来源：{r.get('source', '')}）"
            for r in requirements)
        blocks.append(f"本节需响应的招标要求：\n{req_lines}")
    if assets_text:
        blocks.append(f"可用参考资料：\n{assets_text}")
    return "\n\n".join(blocks)


def stream_section(prompt: str, api_key: str, model: str, client=None):
    """流式生成单节正文，逐段 yield 文本增量；错误抛 LLMParseError。client 用于测试注入。"""
    if not api_key:
        raise LLMParseError("未配置 API Key")
    if is_coding_key(api_key) and model not in CODING_MODELS:
        model = CODING_DEFAULT_MODEL
    client = client or _make_client(api_key, timeout=600.0)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": SECTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "max_tokens": 4096,
    }
    if not is_coding_key(api_key):
        kwargs["temperature"] = 0.2
    try:
        stream = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMParseError(_friendly_api_error(exc)) from exc
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and getattr(delta, "content", None):
            yield delta.content
