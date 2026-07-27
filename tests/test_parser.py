from bidhelper.parser import parse_tender


SAMPLE = """
第四章 投标报价、投标文件编制和投标保证金
2.5 投标文件应按照招标文件规定的顺序，统一用A4规格幅面打印、装订成册并编制目录。
8.1 投标人应提交一式三份投标文件（一份正本，二份副本）。
9.1 投标人应将投标文件正本和所有副本密封包装。
10.1 未按要求密封的投标文件将被视为无效投标。
投标截止时间：2026年8月13日9时00分。
开标时间：2026年8月13日9时30分。
"""


def test_parse_tender_finds_format_and_deadline():
    results = parse_tender(SAMPLE)
    categories = {r["category"] for r in results}
    assert "格式要求" in categories
    assert "时间节点" in categories
    assert "废标项" in categories
