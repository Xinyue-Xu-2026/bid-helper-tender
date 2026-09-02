"""章节标题 AI 改写测试（client 注入 mock，零网络）。"""
import json

import pytest

from app.core.llm_parser import LLMParseError
from app.core.title_adapter import adapt_titles, parse_adapted_titles


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.kwargs = kwargs
        msg = type("M", (), {"content": self.payload})()
        return type("R", (), {"choices": [type("C", (), {"message": msg})()], })()


def test_adapt_titles_success():
    payload = json.dumps({"titles": ["第一章 GZ659项目概况", "1.1 GZ659工程简介"]},
                         ensure_ascii=False)
    client = FakeClient(payload)
    out = adapt_titles(["第一章 工程概况", "　　1.1 工程简介"],
                       "GZ659商业综合体项目", "要求摘要", "sk-test", "kimi-k3", client=client)
    assert out == ["第一章 GZ659项目概况", "1.1 GZ659工程简介"]
    user_msg = client.kwargs["messages"][1]["content"]
    assert "GZ659商业综合体项目" in user_msg
    assert "共 2 条" in user_msg
    assert client.kwargs["response_format"] == {"type": "json_object"}


def test_adapt_titles_count_mismatch():
    client = FakeClient(json.dumps({"titles": ["仅一条"]}, ensure_ascii=False))
    with pytest.raises(LLMParseError, match="不一致"):
        adapt_titles(["A", "B"], "项目", "", "sk-test", "kimi-k3", client=client)


def test_parse_adapted_titles_bad_json():
    with pytest.raises(LLMParseError, match="合法 JSON"):
        parse_adapted_titles("not json", 1)
    with pytest.raises(LLMParseError, match="缺少 titles"):
        parse_adapted_titles('{"x": []}', 1)
    with pytest.raises(LLMParseError, match="空标题"):
        parse_adapted_titles('{"titles": ["  "]}', 1)


def test_adapt_titles_empty_input():
    assert adapt_titles([], "项目", "", "sk-test", "kimi-k3") == []
