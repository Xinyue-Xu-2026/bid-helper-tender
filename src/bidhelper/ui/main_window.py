from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QStackedWidget, QLabel

from bidhelper.ui.project_page import ProjectPage
from bidhelper.ui.tender_page import TenderPage
from bidhelper.ui.requirements_page import RequirementsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("投标助手 MVP v0.1")
        self.resize(1000, 700)

        self._current_project_id = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        self.nav = QListWidget()
        self.nav.addItems(["项目管理", "招标解析", "要求清单"])
        self.nav.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav, 1)

        self.stack = QStackedWidget()
        self.project_page = ProjectPage(self)
        self.tender_page = TenderPage(self)
        self.requirements_page = RequirementsPage(self)
        self.stack.addWidget(self.project_page)
        self.stack.addWidget(self.tender_page)
        self.stack.addWidget(self.requirements_page)
        layout.addWidget(self.stack, 4)

        self.status_bar = QLabel("就绪")
        self.setStatusBar(self.statusBar())
        self.statusBar().addWidget(self.status_bar)

        self.project_page.project_selected.connect(self._on_project_selected)

    def _on_nav_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.tender_page.load_project(self._current_project_id)
        elif index == 2:
            self.requirements_page.load_project(self._current_project_id)

    def _on_project_selected(self, project_id: int):
        self._current_project_id = project_id
        self.status_bar.setText(f"当前项目 ID: {project_id}")
        self.tender_page.load_project(project_id)
        self.requirements_page.load_project(project_id)
