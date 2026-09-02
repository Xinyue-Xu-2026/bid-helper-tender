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
1. 只输出本节正文，不要标题、不要任何解释；除 Markdown 表格外不要使用其他 markdown 标记；
2. 语言正式专业，语气客观，符合投标文件规范；
3. 逐条响应「本节需响应的招标要求」，内容充实、有针对性；
4. 若提供了模板风格画像或范文节选，模仿其写作风格与句式；
5. 若提供了篇幅要求，正文必须达到指定字数；
6. 若提供了项目信息，正文须围绕该项目的名称、对象与特点展开，不要泛泛而谈；
7. 正文中涉及数据对比、清单、参数时，优先使用 Markdown 表格输出（导出端会渲染为真表格）；
8. 若提供了参考资料，优先采用其中的企业信息、资质、业绩等真实材料。"""

MAX_TOKENS = 16384
MAX_CONTINUATIONS = 2  # 输出被长度截断时最多自动续写次数


def build_section_prompt(section_title: str, outline_titles: list, requirements: list,
                         style_text: str = "", assets_text: str = "",
                         target_chars: int = 0, project_info: str = "") -> str:
    """组装单节生成 prompt；各部分均可空，缺失时自动省略。项目信息置于开头。"""
    blocks = []
    if project_info:
        blocks.append(project_info)
    blocks.append(f"当前撰写章节：{section_title}")
    if outline_titles:
        blocks.append("标书完整目录（把握章节位置与前后衔接）：\n" + "\n".join(outline_titles))
    if style_text:
        blocks.append(style_text)
    if target_chars and target_chars > 0:
        blocks.append(f"篇幅要求：本章不少于 {target_chars} 字，与参考模板篇幅相当。")
    if requirements:
        req_lines = "\n".join(
            f"- [{r.get('category', '')}] {r.get('content', '')}（来源：{r.get('source', '')}）"
            for r in requirements)
        blocks.append(f"本节需响应的招标要求：\n{req_lines}")
    if assets_text:
        blocks.append(f"可用参考资料：\n{assets_text}")
    return "\n\n".join(blocks)


def stream_section(prompt: str, api_key: str, model: str, client=None):
    """流式生成单节正文，逐段 yield 文本增量；错误抛 LLMParseError。client 用于测试注入。

    max_tokens 16384；若 finish_reason=length（输出被截断），自动携带已生成内容
    续写拼接，最多续 MAX_CONTINUATIONS 次。
    """
    if not api_key:
        raise LLMParseError("未配置 API Key")
    if is_coding_key(api_key) and model not in CODING_MODELS:
        model = CODING_DEFAULT_MODEL
    client = client or _make_client(api_key, timeout=600.0)
    base_messages = [
        {"role": "system", "content": SECTION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    messages = list(base_messages)
    produced = []
    for attempt in range(MAX_CONTINUATIONS + 1):
        kwargs = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": MAX_TOKENS,
        }
        if not is_coding_key(api_key):
            kwargs["temperature"] = 0.2
        try:
            stream = client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMParseError(_friendly_api_error(exc)) from exc
        finish_reason = None
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if delta and getattr(delta, "content", None):
                produced.append(delta.content)
                yield delta.content
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason
        if finish_reason != "length" or attempt >= MAX_CONTINUATIONS:
            break
        messages = base_messages + [
            {"role": "assistant", "content": "".join(produced)},
            {"role": "user", "content": "继续。直接接着上文输出本章剩余内容，不要重复已输出内容，不要任何解释。"},
        ]
