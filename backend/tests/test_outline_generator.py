"""目录大纲生成器测试（client 注入 mock，零网络）。"""
import json

import pytest

from app.core.llm_parser import LLMParseError
from app.core.outline_generator import generate_outline, parse_outline


def _client(content):
    choice = type("C", (), {"message": type("M", (), {"content": content})()})()
    result = type("R", (), {"choices": [choice]})()
    return type("FakeClient", (), {
        "chat": type("Chat", (), {
            "completions": type("Comp", (), {"create": lambda self, **kw: result})()})(),
    })()


VALID = json.dumps({"outline": [
    {"title": "第一章 资格审查资料", "children": [
        {"title": "1.1 营业执照", "children": []},
        {"title": "1.2 资质证书", "children": []},
    ]},
    {"title": "第二章 技术方案", "children": []},
]}, ensure_ascii=False)


def test_parse_outline_valid():
    outline = parse_outline(VALID)
    assert len(outline) == 2
    assert outline[0]["level"] == 1
    assert outline[0]["children"][0]["level"] == 2
    assert outline[0]["children"][0]["title"] == "1.1 营业执照"


def test_parse_outline_invalid_json():
    with pytest.raises(LLMParseError, match="不是合法 JSON"):
        parse_outline("not json")


def test_parse_outline_missing_array():
    with pytest.raises(LLMParseError, match="缺少 outline 数组"):
        parse_outline('{"foo": []}')


def test_parse_outline_level_capped_at_3():
    deep = json.dumps({"outline": [{"title": "A", "children": [
        {"title": "B", "children": [
            {"title": "C", "children": [
                {"title": "D", "children": []}]}]}]}]})
    outline = parse_outline(deep)
    level3 = outline[0]["children"][0]["children"][0]
    assert level3["level"] == 3
    assert level3["children"] == []  # 第 4 层被截断


def test_parse_outline_skips_empty_titles():
    outline = parse_outline('{"outline": [{"title": "", "children": []}, {"title": "有效"}]}')
    assert len(outline) == 1 and outline[0]["title"] == "有效"


def test_generate_outline_mock():
    reqs = [{"category": "格式要求", "content": "投标文件应包含...", "source": "第三章"}]
    outline = generate_outline(reqs, "sk-test", "kimi-k3", client=_client(VALID))
    assert outline[0]["title"] == "第一章 资格审查资料"


def test_generate_outline_empty_requirements():
    with pytest.raises(LLMParseError, match="暂无要求清单"):
        generate_outline([], "sk-test", "kimi-k3", client=_client(VALID))
