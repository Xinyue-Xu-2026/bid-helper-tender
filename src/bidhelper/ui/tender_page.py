from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from bidhelper.service import BidService
from bidhelper.ui.workers import ParseWorker


class TenderPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.service = BidService()
        self.project_id = None
        self._worker = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("当前未选择项目")
        layout.addWidget(self.info_label)

        self.file_label = QLabel("尚未导入招标文件")
        self.file_label.setObjectName("pageHint")
        layout.addWidget(self.file_label)

        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("导入招标文件")
        self.parse_btn = QPushButton("开始解析")
        self.parse_btn.setObjectName("primaryBtn")
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.parse_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # 忙碌模式（不确定进度）
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.result_table = QTableWidget(0, 4)
        self.result_table.setHorizontalHeaderLabels(["分类", "内容", "来源章节", "置信度"])
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.result_table)

        self.import_btn.clicked.connect(self._import_tender)
        self.parse_btn.clicked.connect(self._parse_tender)

    def load_project(self, project_id: int):
        self.project_id = project_id
        if project_id is None:
            self.info_label.setText("当前未选择项目")
            self.file_label.setText("尚未导入招标文件")
            self.result_table.setRowCount(0)
            return
        project = self.service.db.get_project(project_id)
        if project is None:
            self.info_label.setText("当前未选择项目")
            self.file_label.setText("尚未导入招标文件")
            self.result_table.setRowCount(0)
            return
        self.info_label.setText(f"当前项目：{project['name']}")
        notes = project.get("notes") or ""
        if "招标文件：" in notes:
            name = Path(notes.split("招标文件：")[-1].strip()).name
            self.file_label.setText(f"已导入：{name}（重新导入将覆盖）")
        else:
            self.file_label.setText("尚未导入招标文件")
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
            self.file_label.setText(f"已导入：{Path(dest).name}（重新导入将覆盖）")
            QMessageBox.information(self, "成功", "招标文件已导入，可点击“开始解析”。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{e}")

    def _parse_tender(self):
        if self.project_id is None:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_parsing(True)
        self._worker = ParseWorker(self.service, self.project_id)
        self._worker.finished_ok.connect(self._on_parse_ok)
        self._worker.failed.connect(self._on_parse_failed)
        self._worker.start()

    def _set_parsing(self, parsing: bool):
        self.progress.setVisible(parsing)
        self.parse_btn.setEnabled(not parsing)
        self.import_btn.setEnabled(not parsing)
        self.parse_btn.setText("解析中…" if parsing else "开始解析")

    def _on_parse_ok(self, count: int):
        self._set_parsing(False)
        self._load_results()
        QMessageBox.information(self, "解析完成", f"共解析出 {count} 条要求，已切换到要求清单页。")
        self.main_window.show_requirements_page()

    def _on_parse_failed(self, message: str):
        self._set_parsing(False)
        QMessageBox.critical(self, "解析失败", message)
