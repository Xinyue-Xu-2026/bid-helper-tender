from bidhelper.postprocess import dedupe_and_filter


def make(content, category="格式要求"):
    return {"category": category, "content": content, "source": "1.1", "confidence": "高", "status": "待响应"}


def test_dedupe_exact_and_normalized():
    reqs = [
        make("投标文件应签字盖章"),
        make(" 投标文件应签字盖章 "),   # 首尾空白
        make("投标文件应签字盖章　"),    # 全角空格
        make("另一条要求的内容文本"),
    ]
    result = dedupe_and_filter(reqs)
    assert [r["content"] for r in result] == ["投标文件应签字盖章", "另一条要求的内容文本"]


def test_filter_template_signature_lines():
    reqs = [
        make("法定代表人或授权代表：（签字或盖章）"),
        make("投标人名称：（盖章）"),
        make("日 期："),
        make("签字："),
        make("年   月   日"),
        make("投标文件应按照招标文件规定的顺序装订成册"),
    ]
    result = dedupe_and_filter(reqs)
    assert [r["content"] for r in result] == ["投标文件应按照招标文件规定的顺序装订成册"]


def test_filter_short_content():
    reqs = [make("盖章"), make("这条要求内容长度足够保留下来")]
    result = dedupe_and_filter(reqs)
    assert [r["content"] for r in result] == ["这条要求内容长度足够保留下来"]


def test_order_preserved():
    reqs = [make("第三条要求的内容文本"), make("第一条要求的内容文本"), make("第二条要求的内容文本")]
    result = dedupe_and_filter(reqs)
    assert [r["content"] for r in result] == ["第三条要求的内容文本", "第一条要求的内容文本", "第二条要求的内容文本"]


def test_empty_input():
    assert dedupe_and_filter([]) == []
