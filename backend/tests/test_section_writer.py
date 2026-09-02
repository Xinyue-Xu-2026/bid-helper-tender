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


class FakeTruncatingClient:
    """前两次 finish_reason=length 截断，第三次正常结束；记录每次 create 的 messages。"""

    def __init__(self, rounds):
        self.rounds = rounds  # [([chunks], finish_reason), ...]
        self.calls = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        chunks, finish = self.rounds[min(len(self.calls) - 1, len(self.rounds) - 1)]

        def gen():
            for text in chunks:
                delta = type("D", (), {"content": text})()
                yield type("C", (), {"choices": [type("CC", (), {"delta": delta})()]})()
            delta = type("D", (), {"content": None})()
            yield type("C", (), {"choices": [type("CC", (),
                                              {"delta": delta, "finish_reason": finish})()]})()
        return gen()


def test_stream_section_continues_on_length_truncation():
    client = FakeTruncatingClient([
        (["前半段"], "length"),
        (["后半段"], "stop"),
    ])
    out = list(stream_section("p", "sk-test", "kimi-k3", client=client))
    assert out == ["前半段", "后半段"]
    assert len(client.calls) == 2
    # 续写请求携带已生成内容作为 assistant 消息
    msgs = client.calls[1]["messages"]
    assert msgs[-2] == {"role": "assistant", "content": "前半段"}
    assert msgs[-1]["role"] == "user"
    assert client.calls[0]["max_tokens"] == 16384


def test_stream_section_continuation_capped_at_two():
    client = FakeTruncatingClient([
        (["a"], "length"), (["b"], "length"), (["c"], "length"), (["d"], "stop"),
    ])
    out = list(stream_section("p", "sk-test", "kimi-k3", client=client))
    assert out == ["a", "b", "c"]  # 最多续 2 次，共 3 轮
    assert len(client.calls) == 3


def test_build_section_prompt_target_chars():
    p = build_section_prompt("1.1 项目背景", [], [], "", "", target_chars=1500)
    assert "本章不少于 1500 字，与参考模板篇幅相当" in p
    p2 = build_section_prompt("标题", [], [], "", "")
    assert "篇幅要求" not in p2
