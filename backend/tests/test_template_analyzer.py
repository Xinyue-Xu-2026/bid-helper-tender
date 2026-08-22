"""模板风格画像与模板策略测试（client 注入 mock，零网络）。"""
import pytest
from docx import Document

from app.core.llm_parser import LLMParseError
from app.core.template_analyzer import analyze_template
from app.core.template_strategy import ExampleReferenceStrategy


def _make_docx(path, text="第一章 项目概述\n我方郑重承诺……"):
    doc = Document()
    doc.add_paragraph(text)
    doc.save(str(path))
    return str(path)


class RecordClient:
    """记录 create 参数并返回固定内容的假 client（兼容流式/非流式测试）。"""

    def __init__(self, content="风格画像内容"):
        self.content = content
        self.kwargs = None

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.kwargs = kwargs
        choice = type("C", (), {
            "message": type("M", (), {"content": self.content})()})()
        return type("R", (), {"choices": [choice]})()


def test_analyze_template_returns_profile(tmp_path):
    path = _make_docx(tmp_path / "t.docx")
    profile = analyze_template(path, "sk-test", "kimi-k3", client=RecordClient("风格画像内容"))
    assert profile == "风格画像内容"


def test_analyze_template_coding_key_model_fallback(tmp_path):
    rec = RecordClient()
    analyze_template(_make_docx(tmp_path / "t.docx"), "sk-kimi-abc", "kimi-k3", client=rec)
    assert rec.kwargs["model"] == "k3"          # coding 网关强制回退
    assert "temperature" not in rec.kwargs      # coding 网关禁传 temperature


def test_analyze_template_platform_key_keeps_model(tmp_path):
    rec = RecordClient()
    analyze_template(_make_docx(tmp_path / "t.docx"), "sk-test", "kimi-k3", client=rec)
    assert rec.kwargs["model"] == "kimi-k3"
    assert rec.kwargs["temperature"] == 0.2


def test_analyze_template_api_error_friendly(tmp_path):
    class BadClient:
        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            raise Exception("401 Invalid Authentication")

    with pytest.raises(LLMParseError, match="无效或已过期"):
        analyze_template(_make_docx(tmp_path / "t.docx"), "sk-test", "kimi-k3",
                         client=BadClient())


def test_analyze_template_empty_file(tmp_path):
    with pytest.raises(LLMParseError, match="模板内容为空"):
        analyze_template(_make_docx(tmp_path / "empty.docx", ""), "sk-test", "kimi-k3",
                         client=RecordClient())


def test_strategy_with_profile():
    s = ExampleReferenceStrategy().build_prompt(
        {"style_profile": "画像文本", "file_path": "/nonexistent"})
    assert "画像文本" in s


def test_strategy_without_profile_reads_excerpt(tmp_path):
    path = _make_docx(tmp_path / "t.docx", "模板正文内容节选")
    s = ExampleReferenceStrategy().build_prompt({"style_profile": None, "file_path": path})
    assert "模板正文内容节选" in s


def test_strategy_no_template_returns_empty():
    assert ExampleReferenceStrategy().build_prompt(None) == ""
