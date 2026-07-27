from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class ProjectPage(QWidget):
    project_selected = pyqtSignal(int)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("项目管理页占位"))

    def load_project(self, project_id: int):
        pass
