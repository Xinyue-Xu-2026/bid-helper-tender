"""全局浅色扁平主题：颜色常量 + QSS 样式表。"""

BG = "#F5F6FA"
CARD = "#FFFFFF"
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_DISABLED = "#93C5FD"
TEXT = "#1F2937"
TEXT_MUTED = "#6B7280"
BORDER = "#E5E7EB"
PRIMARY_LIGHT = "#EFF6FF"
SELECT_BG = "#DBEAFE"

STATUS_COLORS = {"已响应": "#16A34A", "待响应": "#D97706", "需关注": "#DC2626"}
CONFIDENCE_COLORS = {"高": "#2563EB", "中": "#7C3AED", "低": "#6B7280"}

APP_QSS = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; font-size: 13px; color: {TEXT}; }}

/* 左侧导航与侧栏 */
QFrame#sidebar {{ background: {CARD}; border-right: 1px solid {BORDER}; }}
QListWidget#nav {{ background: {CARD}; border: none; outline: none; }}
QListWidget#nav::item {{ padding: 12px 16px; color: {TEXT_MUTED}; }}
QListWidget#nav::item:selected {{ background: {PRIMARY_LIGHT}; color: {PRIMARY}; border-left: 3px solid {PRIMARY}; font-weight: bold; }}
QListWidget#nav::item:hover:!selected {{ background: #F3F4F6; }}
QLabel#currentProject {{ padding: 10px 12px; color: {PRIMARY}; border-top: 1px solid {BORDER}; font-weight: bold; }}

/* 按钮 */
QPushButton {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 16px; }}
QPushButton:hover {{ background: #F3F4F6; }}
QPushButton:disabled {{ color: #9CA3AF; background: #F3F4F6; }}
QPushButton#primaryBtn {{ background: {PRIMARY}; color: #FFFFFF; border: none; font-weight: bold; }}
QPushButton#primaryBtn:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#primaryBtn:disabled {{ background: {PRIMARY_DISABLED}; }}

/* 表格 */
QTableWidget {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; gridline-color: #F3F4F6; alternate-background-color: #F9FAFB; selection-background-color: {SELECT_BG}; selection-color: {TEXT}; }}
QTableWidget::item {{ padding: 6px; border: none; }}
QHeaderView::section {{ background: {PRIMARY}; color: #FFFFFF; font-weight: bold; padding: 8px; border: none; }}

/* 输入控件 */
QLineEdit, QComboBox, QTextEdit {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px; }}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border: 1px solid {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}

/* 进度条 */
QProgressBar {{ background: {BORDER}; border: none; border-radius: 4px; max-height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 4px; }}

/* 统计卡片 */
QFrame#statCard {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; }}
QFrame#statCard:hover {{ border: 1px solid {PRIMARY}; }}
QLabel#statValue {{ font-size: 24px; font-weight: bold; }}
QLabel#statTitle {{ color: {TEXT_MUTED}; }}

/* 其他 */
QStatusBar {{ background: {CARD}; border-top: 1px solid {BORDER}; }}
QLabel#pageHint {{ color: {TEXT_MUTED}; }}
"""


def apply_theme(app) -> None:
    """对 QApplication 应用全局样式表。"""
    app.setStyleSheet(APP_QSS)
