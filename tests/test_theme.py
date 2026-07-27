from bidhelper.ui import theme


def test_color_constants():
    assert theme.PRIMARY == "#2563EB"
    assert theme.BG == "#F5F6FA"
    assert set(theme.STATUS_COLORS) == {"已响应", "待响应", "需关注"}
    assert theme.STATUS_COLORS["已响应"] == "#16A34A"
    assert theme.STATUS_COLORS["待响应"] == "#D97706"
    assert theme.STATUS_COLORS["需关注"] == "#DC2626"


def test_qss_contains_key_selectors():
    qss = theme.APP_QSS
    for selector in (
        "QListWidget#nav",
        "QPushButton#primaryBtn",
        "QTableWidget",
        "QHeaderView::section",
        "QFrame#statCard",
        "QProgressBar",
        "QFrame#sidebar",
        "QLabel#currentProject",
    ):
        assert selector in qss, selector
    assert "#2563EB" in qss
