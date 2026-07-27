from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem

from bidhelper.service import BidService


class TenderPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.service = BidService()
        self.project_id = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("当前未选择项目")
        layout.addWidget(self.info_label)

        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("导入招标文件")
        self.parse_btn = QPushButton("开始解析")
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.parse_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.result_table = QTableWidget(0, 4)
        self.result_table.setHorizontalHeaderLabels(["分类", "内容", "来源章节", "置信度"])
        layout.addWidget(self.result_table)

        self.import_btn.clicked.connect(self._import_tender)
        self.parse_btn.clicked.connect(self._parse_tender)

    def load_project(self, project_id: int):
        self.project_id = project_id
        if project_id is None:
            self.info_label.setText("当前未选择项目")
            return
        project = self.service.db.get_project(project_id)
        self.info_label.setText(f"当前项目：{project['name']}")
        self._load_results()

    def _load_results(self):
        self.result_table.setRowCount(0)
        if self.project_id is None:
            return
        reqs = self.service.db.get_requirements(self.project_id)
        self.result_table.setRowCount(len(reqs))
        for i, r in enumerate(reqs):
            self.result_table.setItem(i, 0, QTableWidgetItem(r["category"]))
            self.result_table.setItem(i, 1, QTableWidgetItem(r["content"]))
            self.result_table.setItem(i, 2, QTableWidgetItem(r["source"]))
            self.result_table.setItem(i, 3, QTableWidgetItem(r["confidence"]))

    def _import_tender(self):
        if self.project_id is None:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入招标文件", "", "招标文件 (*.pdf *.docx)")
        if not path:
            return
        try:
            dest = self.service.import_tender(self.project_id, path)
            self.info_label.setText(f"已导入：{Path(dest).name}")
            QMessageBox.information(self, "成功", "招标文件已导入")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def _parse_tender(self):
        if self.project_id is None:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        try:
            self.service.parse_and_save_requirements(self.project_id)
            self._load_results()
            QMessageBox.information(self, "成功", "解析完成")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解析失败：{e}")
