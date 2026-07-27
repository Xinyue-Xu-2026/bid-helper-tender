import sys
from PyQt6.QtWidgets import QApplication
from bidhelper.ui import theme
from bidhelper.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    theme.apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
