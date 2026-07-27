from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class RequirementsPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("要求清单页占位"))

    def load_project(self, project_id: int):
        pass
