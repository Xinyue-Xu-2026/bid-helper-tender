"""可复用 UI 组件：StatCard 统计卡片、FilterBar 筛选栏、EditableTable 可编辑表格。"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
)

from bidhelper.ui import theme


class StatCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, color: str = theme.PRIMARY, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        self.value_label = QLabel("0")
        self.value_label.setObjectName("statValue")
        self.value_label.setStyleSheet(f"color: {color};")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("statTitle")
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)

    def set_value(self, value: int):
        self.value_label.setText(str(value))

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class FilterBar(QFrame):
    """搜索框 + 分类/状态下拉。filters() 返回 (text, category, status)，空串表示不过滤。"""

    filters_changed = pyqtSignal(str, str, str)

    ALL_CATEGORY = "全部分类"
    ALL_STATUS = "全部状态"

    def __init__(self, categories, statuses, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索要求内容…")
        self.search_edit.setClearButtonEnabled(True)
        self.category_combo = QComboBox()
        self.category_combo.addItems([self.ALL_CATEGORY] + list(categories))
        self.status_combo = QComboBox()
        self.status_combo.addItems([self.ALL_STATUS] + list(statuses))
        layout.addWidget(self.search_edit, 2)
        layout.addWidget(self.category_combo, 1)
        layout.addWidget(self.status_combo, 1)

        self.search_edit.textChanged.connect(self._emit)
        self.category_combo.currentTextChanged.connect(self._emit)
        self.status_combo.currentTextChanged.connect(self._emit)

    def filters(self):
        category = self.category_combo.currentText()
        status = self.status_combo.currentText()
        return (
            self.search_edit.text().strip(),
            "" if category == self.ALL_CATEGORY else category,
            "" if status == self.ALL_STATUS else status,
        )

    def set_status_filter(self, status: str):
        """供统计卡片快捷筛选调用；空串表示清除状态筛选。"""
        self.status_combo.setCurrentText(status if status else self.ALL_STATUS)

    def _emit(self, *args):
        self.filters_changed.emit(*self.filters())


class EditableTable(QTableWidget):
    """只读展示 + 指定列双击编辑。

    dropdown_columns: {列号: [选项]}，双击弹下拉选择；
    dialog_columns: 列号集合，双击弹多行编辑框；
    tag_colors: {单元格值: 颜色}，命中渲染为彩色加粗文字；
    每行 record_id 存于第 0 列 item 的 Qt.ItemDataRole.UserRole。
    """

    cell_edited = pyqtSignal(int, int, str)  # record_id, column, new_value

    def __init__(self, headers, dropdown_columns=None, dialog_columns=None,
                 tag_colors=None, parent=None):
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self._dropdown_columns = dropdown_columns or {}
        self._dialog_columns = dialog_columns or set()
        self._tag_colors = tag_colors or {}
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.cellDoubleClicked.connect(self._on_double_click)

    def set_rows(self, rows):
        """rows: list of (record_id, [col0_value, col1_value, ...])"""
        self.setSortingEnabled(False)
        self.setRowCount(0)
        self.setRowCount(len(rows))
        for r, (record_id, values) in enumerate(rows):
            for c, value in enumerate(values):
                text = str(value)
                item = QTableWidgetItem(text)
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record_id)
                self._apply_tag(item, text)
                self.setItem(r, c, item)
        self.setSortingEnabled(True)

    def _apply_tag(self, item, value):
        if value in self._tag_colors:
            item.setForeground(QBrush(QColor(self._tag_colors[value])))
            font = item.font()
            font.setBold(True)
            item.setFont(font)

    def _on_double_click(self, row, col):
        if col in self._dropdown_columns:
            self._edit_dropdown(row, col)
        elif col in self._dialog_columns:
            self._edit_dialog(row, col)

    def _edit_dropdown(self, row, col):
        item = self.item(row, col)
        if item is None:
            return
        options = self._dropdown_columns[col]
        current = options.index(item.text()) if item.text() in options else 0
        value, ok = QInputDialog.getItem(self, "编辑", "请选择：", options, current, False)
        if ok and value and value != item.text():
            item.setText(value)
            self._apply_tag(item, value)
            self.cell_edited.emit(self._record_id(row), col, value)

    def _edit_dialog(self, row, col):
        item = self.item(row, col)
        if item is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑内容")
        dialog.resize(480, 240)
        layout = QVBoxLayout(dialog)
        edit = QTextEdit(item.text())
        layout.addWidget(edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            value = edit.toPlainText().strip()
            if value and value != item.text():
                item.setText(value)
                self.cell_edited.emit(self._record_id(row), col, value)

    def _record_id(self, row):
        item = self.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None
