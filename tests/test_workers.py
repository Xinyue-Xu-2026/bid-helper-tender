from pathlib import Path

from bidhelper.service import BidService
from bidhelper.ui.workers import ParseWorker

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_worker_success(qapp, tmp_path):
    service = BidService(str(tmp_path / "app.db"))
    pid = service.create_project("项目", "单位", "2026-08-15", "审计类", "")
    service.import_tender(pid, str(FIXTURES / "sample_tender.docx"))

    worker = ParseWorker(service, pid)
    ok, err = [], []
    worker.finished_ok.connect(ok.append)
    worker.failed.connect(err.append)
    worker.run()  # 直接同步调用，测试线程体逻辑
    assert len(ok) == 1 and ok[0] > 0
    assert err == []
    assert len(service.db.get_requirements(pid)) == ok[0]


def test_parse_worker_failure(qapp, tmp_path):
    service = BidService(str(tmp_path / "app.db"))
    pid = service.create_project("项目", "单位", "2026-08-15", "审计类", "")
    worker = ParseWorker(service, pid)  # 未导入招标文件
    ok, err = [], []
    worker.finished_ok.connect(ok.append)
    worker.failed.connect(err.append)
    worker.run()
    assert ok == []
    assert len(err) == 1
