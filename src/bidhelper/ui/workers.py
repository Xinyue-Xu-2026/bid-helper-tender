"""后台工作线程。"""
from PyQt6.QtCore import QThread, pyqtSignal


class ParseWorker(QThread):
    """后台解析招标文件，避免阻塞界面。仅调用 service，不含业务逻辑。"""

    finished_ok = pyqtSignal(int)   # 解析出的要求条数
    failed = pyqtSignal(str)        # 错误信息

    def __init__(self, service, project_id: int, parent=None):
        super().__init__(parent)
        self._service = service
        self._project_id = project_id

    def run(self):
        try:
            reqs = self._service.parse_and_save_requirements(self._project_id)
            self.finished_ok.emit(len(reqs))
        except Exception as exc:  # 错误经信号回主线程展示
            self.failed.emit(str(exc))
