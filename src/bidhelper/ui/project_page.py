from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from bidhelper.db import Database
from bidhelper.ui.dialogs import ProjectDialog


class ProjectPage(QWidget):
    project_selected = pyqtSignal(int)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.db = Database()
        self.db.init_schema()

        layout = QVBoxLayout(self)

        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("新建项目")
        self.new_btn.setObjectName("primaryBtn")
        self.edit_btn = QPushButton("编辑项目")
        self.delete_btn = QPushButton("删除项目")
        self.open_btn = QPushButton("打开项目")
        for btn in (self.new_btn, self.edit_btn, self.delete_btn, self.open_btn):
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "项目名称", "招标单位", "投标日期", "项目类型"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnHidden(0, True)  # ID 仅内部使用
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self._new_project)
        self.edit_btn.clicked.connect(self._edit_project)
        self.delete_btn.clicked.connect(self._delete_project)
        self.open_btn.clicked.connect(self._open_project)
        self.table.cellDoubleClicked.connect(lambda *args: self._open_project())

        self._load_projects()

    def _load_projects(self):
        projects = self.db.get_projects()
        self.table.setRowCount(len(projects))
        for i, p in enumerate(projects):
            self.table.setItem(i, 0, QTableWidgetItem(str(p["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(p["name"]))
            self.table.setItem(i, 2, QTableWidgetItem(p["client"]))
            self.table.setItem(i, 3, QTableWidgetItem(p["bid_date"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(p["project_type"]))

    def _selected_project_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def _new_project(self):
        dialog = ProjectDialog(self)
        if dialog.exec() == ProjectDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db.create_project(**data)
            self._load_projects()

    def _edit_project(self):
        pid = self._selected_project_id()
        if pid is None:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        project = self.db.get_project(pid)
        dialog = ProjectDialog(self, project)
        if dialog.exec() == ProjectDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db.update_project(pid, **data)
            self._load_projects()

    def _delete_project(self):
        pid = self._selected_project_id()
        if pid is None:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        reply = QMessageBox.question(self, "确认", "确定删除该项目？其要求清单一并删除。")
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_project(pid)
            self._load_projects()

    def _open_project(self):
        pid = self._selected_project_id()
        if pid is None:
            return  # 双击空白区域或无选中时静默忽略
        self.project_selected.emit(pid)
        self.main_window.nav.setCurrentRow(1)
