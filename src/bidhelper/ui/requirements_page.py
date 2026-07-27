from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QLineEdit, QTextEdit, QDialog, QFormLayout, QDialogButtonBox

from bidhelper.db import Database


CATEGORIES = ["资质门槛", "评分项", "废标项", "格式要求", "时间节点", "其他"]
STATUSES = ["已响应", "待响应", "需关注"]
CONFIDENCES = ["高", "中", "低"]


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
        self.project_id = None

        layout = QVBoxLayout(self)
        self.info_label = QLabel("当前未选择项目")
        layout.addWidget(self.info_label)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("新增")
        self.edit_btn = QPushButton("编辑")
        self.delete_btn = QPushButton("删除")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["分类", "内容", "来源章节", "置信度", "状态"])
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.delete_btn.clicked.connect(self._delete)

    def load_project(self, project_id: int):
        self.project_id = project_id
        if project_id is None:
            self.info_label.setText("当前未选择项目")
            self.table.setRowCount(0)
            return
        project = self.db.get_project(project_id)
        self.info_label.setText(f"当前项目：{project['name']}")
        self._load_table()

    def _load_table(self):
        self.table.setRowCount(0)
        reqs = self.db.get_requirements(self.project_id)
        self.table.setRowCount(len(reqs))
        for i, r in enumerate(reqs):
            self.table.setItem(i, 0, QTableWidgetItem(r["category"]))
            self.table.setItem(i, 1, QTableWidgetItem(r["content"]))
            self.table.setItem(i, 2, QTableWidgetItem(r["source"]))
            self.table.setItem(i, 3, QTableWidgetItem(r["confidence"]))
            self.table.setItem(i, 4, QTableWidgetItem(r["status"]))

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        reqs = self.db.get_requirements(self.project_id)
        return reqs[row]["id"]

    def _add(self):
        if self.project_id is None:
            return
        dialog = RequirementDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db.create_requirement(self.project_id, **data)
            self._load_table()

    def _edit(self):
        rid = self._selected_id()
        if rid is None:
            return
        req = next(r for r in self.db.get_requirements(self.project_id) if r["id"] == rid)
        dialog = RequirementDialog(self, req)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db.update_requirement(rid, **data)
            self._load_table()

    def _delete(self):
        rid = self._selected_id()
        if rid is None:
            return
        reply = QMessageBox.question(self, "确认", "确定删除该要求？")
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_requirement(rid)
            self._load_table()
