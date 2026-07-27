from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
    QLineEdit,
)

from bidhelper.db import Database
from bidhelper.service import BidService
from bidhelper.ui import theme
from bidhelper.ui.widgets import EditableTable, FilterBar, StatCard

CATEGORIES = ["资质门槛", "评分项", "废标项", "格式要求", "时间节点", "其他"]
STATUSES = ["已响应", "待响应", "需关注"]
CONFIDENCES = ["高", "中", "低"]

HEADERS = ["分类", "内容", "来源章节", "置信度", "状态"]
COLUMN_FIELDS = ["category", "content", "source", "confidence", "status"]
TAG_COLORS = {**theme.STATUS_COLORS, **theme.CONFIDENCE_COLORS}


def matches_filter(req: dict, text: str, category: str, status: str) -> bool:
    """text 对内容列模糊匹配（大小写不敏感）；category/status 空串表示不过滤。"""
    if text and text.lower() not in (req.get("content") or "").lower():
        return False
    if category and req.get("category") != category:
        return False
    if status and req.get("status") != status:
        return False
    return True


def compute_stats(reqs) -> dict:
    return {
        "total": len(reqs),
        "待响应": sum(1 for r in reqs if r.get("status") == "待响应"),
        "需关注": sum(1 for r in reqs if r.get("status") == "需关注"),
        "已响应": sum(1 for r in reqs if r.get("status") == "已响应"),
    }


class RequirementDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.data = data or {}
        self.setWindowTitle("编辑要求" if data else "新增要求")
        self.resize(500, 300)

        layout = QFormLayout(self)
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        self.category_combo.setCurrentText(self.data.get("category", "其他"))

        self.content_edit = QTextEdit(self.data.get("content", ""))
        self.source_edit = QLineEdit(self.data.get("source", ""))

        self.confidence_combo = QComboBox()
        self.confidence_combo.addItems(CONFIDENCES)
        self.confidence_combo.setCurrentText(self.data.get("confidence", "中"))

        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUSES)
        self.status_combo.setCurrentText(self.data.get("status", "待响应"))

        layout.addRow("分类：", self.category_combo)
        layout.addRow("内容：", self.content_edit)
        layout.addRow("来源章节：", self.source_edit)
        layout.addRow("置信度：", self.confidence_combo)
        layout.addRow("状态：", self.status_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return {
            "category": self.category_combo.currentText(),
            "content": self.content_edit.toPlainText(),
            "source": self.source_edit.text(),
            "confidence": self.confidence_combo.currentText(),
            "status": self.status_combo.currentText(),
        }


class RequirementsPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.db = Database()
        self.service = BidService()
        self.project_id = None
        self._filters = ("", "", "")

        layout = QVBoxLayout(self)

        # 统计卡片
        cards_layout = QHBoxLayout()
        self.card_total = StatCard("要求总数", theme.PRIMARY)
        self.card_pending = StatCard("待响应", theme.STATUS_COLORS["待响应"])
        self.card_attention = StatCard("需关注", theme.STATUS_COLORS["需关注"])
        self.card_done = StatCard("已响应", theme.STATUS_COLORS["已响应"])
        for card in (self.card_total, self.card_pending, self.card_attention, self.card_done):
            cards_layout.addWidget(card)
        layout.addLayout(cards_layout)

        # 筛选栏
        self.filter_bar = FilterBar(CATEGORIES, STATUSES)
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        layout.addWidget(self.filter_bar)

        self.card_total.clicked.connect(lambda: self.filter_bar.set_status_filter(""))
        self.card_pending.clicked.connect(lambda: self.filter_bar.set_status_filter("待响应"))
        self.card_attention.clicked.connect(lambda: self.filter_bar.set_status_filter("需关注"))
        self.card_done.clicked.connect(lambda: self.filter_bar.set_status_filter("已响应"))

        # 工具栏
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("新增")
        self.add_btn.setObjectName("primaryBtn")
        self.delete_btn = QPushButton("删除")
        self.export_btn = QPushButton("导出 Excel")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

        # 表格
        self.table = EditableTable(
            HEADERS,
            dropdown_columns={0: CATEGORIES, 4: STATUSES},
            dialog_columns={1},
            tag_colors=TAG_COLORS,
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.cell_edited.connect(self._on_cell_edited)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self._add)
        self.delete_btn.clicked.connect(self._delete)
        self.export_btn.clicked.connect(self._export)

    def load_project(self, project_id: int):
        self.project_id = project_id
        self._reload()

    def _reload(self):
        if self.project_id is None:
            self.table.set_rows([])
            self._update_stats([])
            return
        reqs = self.db.get_requirements(self.project_id)
        self._update_stats(reqs)
        text, category, status = self._filters
        filtered = [r for r in reqs if matches_filter(r, text, category, status)]
        rows = [
            (r["id"], [r["category"], r["content"], r["source"] or "",
                       r["confidence"] or "", r["status"]])
            for r in filtered
        ]
        self.table.set_rows(rows)

    def _update_stats(self, reqs):
        stats = compute_stats(reqs)
        self.card_total.set_value(stats["total"])
        self.card_pending.set_value(stats["待响应"])
        self.card_attention.set_value(stats["需关注"])
        self.card_done.set_value(stats["已响应"])

    def _on_filters_changed(self, text, category, status):
        self._filters = (text, category, status)
        self._reload()

    def _on_cell_edited(self, record_id, col, value):
        if record_id is None:
            return
        field = COLUMN_FIELDS[col]
        try:
            self.db.update_requirement(record_id, **{field: value})
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"保存失败：{exc}")
        finally:
            self._reload()

    def _selected_record_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add(self):
        if self.project_id is None:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        dialog = RequirementDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.db.create_requirement(self.project_id, **dialog.get_data())
            self._reload()

    def _delete(self):
        record_id = self._selected_record_id()
        if record_id is None:
            QMessageBox.warning(self, "提示", "请先选择一条要求")
            return
        reply = QMessageBox.question(self, "确认", "确定删除该要求？")
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_requirement(record_id)
            self._reload()

    def _export(self):
        if self.project_id is None:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        project = self.db.get_project(self.project_id)
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project["name"])
        default_name = f"{safe_name}_要求清单_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "导出要求清单", default_name, "Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            dest = self.service.export_requirements_excel(self.project_id, path)
            QMessageBox.information(self, "成功", f"已导出：\n{dest}")
        except PermissionError:
            QMessageBox.critical(self, "错误", "导出失败：文件正被占用，请关闭已打开的 Excel 文件后重试。")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"导出失败：{exc}")
