"""解析结果后处理：规范化去重 + 模板噪音过滤（两种解析引擎输出共用）。"""
import re
import unicodedata

MIN_CONTENT_LEN = 6

# 只含签字/盖章/日期占位的附件模板行
_TEMPLATE_PATTERNS = [
    re.compile(r"^(法定代表人|授权代表|被授权人|投标人|供应商|承诺单位|单位)?(名称)?[：:]?[（(]?(公章|盖章|签字|签字或盖章)[）)]?[：:]?$"),
    re.compile(r"^(法定代表人|授权代表|被授权人)[（(]?(签字|盖章|签字或盖章)[）)]?[：:]?$"),
    re.compile(r"^(法定代表人或授权代表|法定代表人及主要负责人)[：:]?[（(]?(签字|盖章|签字或盖章)[）)]?[：:]?$"),
    re.compile(r"^(签字|盖章|签字或盖章|公章)[：:]?$"),
    re.compile(r"^日?\s*期[：:]?\s*$"),
    re.compile(r"^[\s年月日]+$"),
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", "", text)


def _is_template_noise(content: str) -> bool:
    text = (content or "").strip()
    if len(text) < MIN_CONTENT_LEN:
        return True
    compact = text.replace(" ", "")
    return any(p.match(compact) for p in _TEMPLATE_PATTERNS)


def dedupe_and_filter(reqs: list) -> list:
    """规范化去重（保留先出现者）并过滤模板噪音行，保持输入顺序。"""
    seen = set()
    results = []
    for req in reqs:
        content = (req.get("content") or "").strip()
        if _is_template_noise(content):
            continue
        key = _normalize(content)
        if key in seen:
            continue
        seen.add(key)
        results.append(req)
    return results
