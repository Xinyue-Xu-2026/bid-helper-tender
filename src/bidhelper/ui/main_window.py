from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QMainWindow,
    QStackedWidget, QVBoxLayout, QWidget,
)

from bidhelper.ui.project_page import ProjectPage
from bidhelper.ui.requirements_page import RequirementsPage
from bidhelper.ui.tender_page import TenderPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("投标助手 v0.2")
        self.resize(1200, 760)

        self._current_project_id = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 左侧：导航 + 当前项目指示
        side = QFrame()
        side.setObjectName("sidebar")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.addItems(["项目管理", "招标解析", "要求清单"])
        self.nav.currentRowChanged.connect(self._on_nav_changed)
        side_layout.addWidget(self.nav, 1)

        self.current_project_label = QLabel("未选择项目")
        self.current_project_label.setObjectName("currentProject")
        self.current_project_label.setWordWrap(True)
        side_layout.addWidget(self.current_project_label, 0)

        layout.addWidget(side, 1)

        self.stack = QStackedWidget()
        self.project_page = ProjectPage(self)
        self.tender_page = TenderPage(self)
        self.requirements_page = RequirementsPage(self)
        self.stack.addWidget(self.project_page)
        self.stack.addWidget(self.tender_page)
        self.stack.addWidget(self.requirements_page)
        layout.addWidget(self.stack, 5)

        self.statusBar().showMessage("就绪")

        self.nav.setCurrentRow(0)
        self.project_page.project_selected.connect(self._on_project_selected)

    def _on_nav_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.tender_page.load_project(self._current_project_id)
        elif index == 2:
            self.requirements_page.load_project(self._current_project_id)

    def _on_project_selected(self, project_id: int):
        self._current_project_id = project_id
        project = self.project_page.db.get_project(project_id)
        name = project["name"] if project else str(project_id)
        self.current_project_label.setText(f"当前项目：\n{name}")
        self.statusBar().showMessage(f"当前项目：{name}")
        self.tender_page.load_project(project_id)
        self.requirements_page.load_project(project_id)

    def show_requirements_page(self):
        """解析完成后自动跳转到要求清单页。"""
        self.nav.setCurrentRow(2)
