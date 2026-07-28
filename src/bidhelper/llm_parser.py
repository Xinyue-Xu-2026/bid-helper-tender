"""Kimi（Moonshot）大模型招标要求抽取。"""
import json

from openai import OpenAI

API_BASE_URL = "https://api.moonshot.cn/v1"
CODING_API_BASE_URL = "https://api.kimi.com/coding/v1"
DEFAULT_MODEL = "kimi-k2.6"
CODING_DEFAULT_MODEL = "k3"
CODING_MODELS = ("k3", "k3-256k", "kimi-for-coding", "kimi-for-coding-highspeed")

VALID_CATEGORIES = ("资质门槛", "评分项", "废标项", "格式要求", "时间节点", "其他")
VALID_CONFIDENCES = ("高", "中", "低")

SYSTEM_PROMPT = """你是一名招标文件要求抽取专家。从用户提供的招标文件全文中，抽取出投标人需要响应或关注的所有要求，以 JSON 格式输出。

分类标准（category 只能取以下六个值之一）：
- 资质门槛：投标人资格条件、必须提交的资格证明文件（尤其是带★标记的必备项，逐条列出）、信用要求
- 评分项：评标办法、评分标准、各评分细项及其分值（逐条列出，含业绩、人员、证书等加分项）
- 废标项：无效投标、废标、拒收投标文件、取消中标资格的情形
- 格式要求：投标文件的编制、签署、盖章、密封、装订、份数、电子文件等格式性要求
- 时间节点：投标确认函截止、澄清截止、保证金截止、投标截止、开标时间、投标有效期等（content 中含具体日期时刻）
- 其他：不属于以上类别但投标人必须知晓的重要要求（如保证金金额与缴纳方式、最高限价、人员配备与驻场要求、服务承诺要求、费用与代理费要求）

抽取要求：
1. 必须完整覆盖：评分细则（逐条细项，含分值）、资格证明文件（带★的逐条）、投标保证金（金额、缴纳方式、账户、截止要求）、所有时间节点、最高限价、人员配备与驻场要求。
2. 每条 content 保留原文关键表述，可适度精简但不改变含义，不超过 200 字。
3. source 填写该要求所在的章节号或章节标题（如"第一章 三"、"第五章 2.2"、"第三章 (5)"）。
4. confidence 表示你对该条目分类与内容准确性的自信程度：高/中/低。
5. 忽略：合同通用条款的纯定义性文字、附件模板中的签字盖章占位行、目录页、无实质要求的过渡文字。
6. 只输出 JSON 对象，格式：{"requirements": [{"category": "...", "content": "...", "source": "...", "confidence": "..."}]}，不要输出任何其他文字。"""


class LLMParseError(Exception):
    """LLM 解析失败（调用方据此回退到规则解析）。"""


def is_coding_key(api_key: str) -> bool:
    """Kimi 编程订阅 Key（sk-kimi- 前缀）使用编程网关，而非 Moonshot 开放平台端点。"""
    return api_key.startswith("sk-kimi-")


def _make_client(api_key: str, timeout: float = 300.0) -> OpenAI:
    base_url = CODING_API_BASE_URL if is_coding_key(api_key) else API_BASE_URL
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=2)


def parse_with_llm(text: str, api_key: str, model: str = DEFAULT_MODEL, client=None) -> list:
    """调用 Kimi API 抽取招标要求；任何失败抛 LLMParseError。client 参数用于测试注入。"""
    if not api_key:
        raise LLMParseError("未配置 API Key")
    if is_coding_key(api_key) and model not in CODING_MODELS:
        model = CODING_DEFAULT_MODEL
    client = client or _make_client(api_key)
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=4096,
        )
    except Exception as exc:
        raise LLMParseError(f"API 调用失败：{exc}") from exc

    if not completion.choices:
        raise LLMParseError("API 返回缺少 choices")
    choice = completion.choices[0]
    if choice.finish_reason == "length":
        raise LLMParseError("输出被截断（finish_reason=length）")
    try:
        data = json.loads(choice.message.content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMParseError(f"返回内容不是合法 JSON：{exc}") from exc

    items = data.get("requirements") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise LLMParseError("返回 JSON 缺少 requirements 数组")

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        category = str(item.get("category", "")).strip()
        if category not in VALID_CATEGORIES:
            category = "其他"
        confidence = str(item.get("confidence", "")).strip()
        if confidence not in VALID_CONFIDENCES:
            confidence = "中"
        results.append({
            "category": category,
            "content": content,
            "source": str(item.get("source", "")).strip(),
            "confidence": confidence,
            "status": "待响应",
        })

    if not results:
        raise LLMParseError("LLM 未抽取出任何要求")
    return results
