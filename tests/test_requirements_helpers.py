from bidhelper.ui.requirements_page import compute_stats, matches_filter

REQS = [
    {"id": 1, "category": "废标项", "content": "投标文件必须签字盖章", "source": "第四章", "confidence": "高", "status": "需关注"},
    {"id": 2, "category": "格式要求", "content": "统一用A4规格幅面打印", "source": "2.5", "confidence": "中", "status": "待响应"},
    {"id": 3, "category": "时间节点", "content": "2026年8月13日9时00分", "source": "投标截止时间", "confidence": "高", "status": "已响应"},
    {"id": 4, "category": "废标项", "content": "未密封的投标文件将被拒收", "source": "9.1", "confidence": "中", "status": "待响应"},
]


def test_matches_filter_no_filter():
    assert all(matches_filter(r, "", "", "") for r in REQS)


def test_matches_filter_text():
    hits = [r for r in REQS if matches_filter(r, "签字", "", "")]
    assert [r["id"] for r in hits] == [1]


def test_matches_filter_category_and_status():
    hits = [r for r in REQS if matches_filter(r, "", "废标项", "待响应")]
    assert [r["id"] for r in hits] == [4]


def test_compute_stats():
    stats = compute_stats(REQS)
    assert stats == {"total": 4, "待响应": 2, "需关注": 1, "已响应": 1}


def test_compute_stats_empty():
    assert compute_stats([]) == {"total": 0, "待响应": 0, "需关注": 0, "已响应": 0}
