"""单节正文生成测试（client 注入 mock，零网络）。"""
import pytest

from app.core.llm_parser import LLMParseError
from app.core.section_writer import build_section_prompt, stream_section


class FakeStreamClient:
    def __init__(self, chunks):
        self.chunks = chunks
        self.kwargs = None

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.kwargs = kwargs

        def gen():
            for text in self.chunks:
                delta = type("D", (), {"content": text})()
                choice = type("C", (), {"choices": [type("CC", (), {"delta": delta})()]})()
                yield choice
        return gen()


def test_build_section_prompt_contains_all_parts():
    p = build_section_prompt(
        "1.1 营业执照",
        ["第一章 资格审查资料", "　　1.1 营业执照"],
        [{"category": "资质门槛", "content": "提供营业执照副本", "source": "第三章"}],
        "【模板风格画像】\n语气正式",
        "【营业执照】编号: 9133XXXX",
    )
    assert "1.1 营业执照" in p
    assert "营业执照副本" in p
    assert "语气正式" in p
    assert "编号: 9133XXXX" in p
    assert "第一章 资格审查资料" in p


def test_build_section_prompt_optional_empty():
    p = build_section_prompt("标题", [], [], "", "")
    assert p == "当前撰写章节：标题"


def test_stream_section_yields_chunks():
    client = FakeStreamClient(["你好，", "世界"])
    out = list(stream_section("请撰写", "sk-test", "kimi-k3", client=client))
    assert out == ["你好，", "世界"]
    assert client.kwargs["stream"] is True


def test_stream_section_coding_key_model_fallback():
    client = FakeStreamClient(["x"])
    list(stream_section("p", "sk-kimi-abc", "kimi-k3", client=client))
    assert client.kwargs["model"] == "k3"
    assert "temperature" not in client.kwargs


def test_stream_section_platform_key_temperature():
    client = FakeStreamClient(["x"])
    list(stream_section("p", "sk-test", "kimi-k3", client=client))
    assert client.kwargs["temperature"] == 0.2


def test_stream_section_missing_key():
    with pytest.raises(LLMParseError, match="未配置 API Key"):
        list(stream_section("p", "", "kimi-k3", client=FakeStreamClient(["x"])))
