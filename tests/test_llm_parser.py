import json
from types import SimpleNamespace

import pytest

from bidhelper.llm_parser import LLMParseError, parse_with_llm

GOOD_PAYLOAD = json.dumps({
    "requirements": [
        {"category": "评分项", "content": "价格分 10 分，低价优先法", "source": "第五章 2.2", "confidence": "高"},
        {"category": "不存在类别", "content": "投标保证金人民币壹万元整", "source": "第一章 九", "confidence": "高"},
        {"category": "废标项", "content": "应交未交投标保证金的按无效投标处理", "source": "第五章 3.4", "confidence": "非法值"},
    ]
}, ensure_ascii=False)


def make_completion(payload, finish_reason="stop"):
    choice = SimpleNamespace(
        message=SimpleNamespace(content=payload),
        finish_reason=finish_reason,
    )
    return SimpleNamespace(choices=[choice])


class FakeCompletions:
    def __init__(self, completion):
        self._completion = completion
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._completion, Exception):
            raise self._completion
        return self._completion


class FakeClient:
    def __init__(self, completion):
        self.chat = SimpleNamespace(completions=FakeCompletions(completion))


def test_parse_success():
    client = FakeClient(make_completion(GOOD_PAYLOAD))
    reqs = parse_with_llm("招标文件全文", "sk-fake", client=client)
    assert len(reqs) == 3
    assert reqs[0]["category"] == "评分项"
    assert reqs[0]["status"] == "待响应"
    # 非法 category 映射为 其他，非法 confidence 映射为 中
    assert reqs[1]["category"] == "其他"
    assert reqs[2]["confidence"] == "中"
    # 调用参数符合契约
    kwargs = client.chat.completions.calls[0]
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 4096
    assert kwargs["model"] == "kimi-k2.6"


def test_api_error_raises():
    client = FakeClient(RuntimeError("429 throttled"))
    with pytest.raises(LLMParseError):
        parse_with_llm("text", "sk-fake", client=client)


def test_bad_json_raises():
    client = FakeClient(make_completion("这不是JSON"))
    with pytest.raises(LLMParseError):
        parse_with_llm("text", "sk-fake", client=client)


def test_missing_requirements_key_raises():
    client = FakeClient(make_completion('{"foo": []}'))
    with pytest.raises(LLMParseError):
        parse_with_llm("text", "sk-fake", client=client)


def test_truncated_raises():
    client = FakeClient(make_completion(GOOD_PAYLOAD, finish_reason="length"))
    with pytest.raises(LLMParseError):
        parse_with_llm("text", "sk-fake", client=client)


def test_empty_requirements_raises():
    client = FakeClient(make_completion('{"requirements": []}'))
    with pytest.raises(LLMParseError):
        parse_with_llm("text", "sk-fake", client=client)


def test_no_api_key_raises():
    with pytest.raises(LLMParseError):
        parse_with_llm("text", "")
