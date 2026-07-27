from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from bidhelper.ui.widgets import EditableTable, FilterBar, StatCard


def test_statcard_displays_and_click(qapp):
    card = StatCard("待响应", "#D97706")
    card.set_value(5)
    assert card.value_label.text() == "5"
    hits = []
    card.clicked.connect(lambda: hits.append(1))
    QTest.mouseClick(card, Qt.MouseButton.LeftButton)
    assert hits == [1]


def test_filterbar_emits_filters(qapp):
    bar = FilterBar(["废标项", "评分项"], ["待响应", "已响应"])
    events = []
    bar.filters_changed.connect(lambda *a: events.append(a))
    bar.search_edit.setText("签字")
    bar.category_combo.setCurrentText("废标项")
    bar.status_combo.setCurrentText("待响应")
    assert ("签字", "废标项", "待响应") in events
    assert bar.filters() == ("签字", "废标项", "待响应")


def test_filterbar_set_status_filter(qapp):
    bar = FilterBar(["废标项"], ["待响应", "已响应"])
    bar.set_status_filter("已响应")
    assert bar.filters()[2] == "已响应"
    bar.set_status_filter("")
    assert bar.filters()[2] == ""


def test_editable_table_rows_and_tags(qapp):
    table = EditableTable(
        ["分类", "内容", "状态"],
        dropdown_columns={0: ["废标项", "评分项"]},
        dialog_columns={1},
        tag_colors={"待响应": "#D97706"},
    )
    table.set_rows([(7, ["废标项", "必须签字", "待响应"])])
    assert table.item(0, 1).text() == "必须签字"
    assert table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 7
    assert table.item(0, 2).foreground().color().name().lower() == "#d97706"
    assert table.item(0, 2).font().bold()
