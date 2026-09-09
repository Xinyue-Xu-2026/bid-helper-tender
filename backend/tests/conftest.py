import pytest


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture(autouse=True)
def _isolate_data_dirs(tmp_path, monkeypatch):
    """把 app.config 的所有数据目录/DB 路径重定向到 tmp_path，
    防止测试写真实 data/ 目录（config.json、files/ 等）。
    各模块均经 `from app import config` 属性访问这些常量（已全量排查，
    无按值导入），因此 patch app.config 模块属性即可全局生效。"""
    data = tmp_path / "data"
    monkeypatch.setattr("app.config.DATA_DIR", data)
    monkeypatch.setattr("app.config.UPLOADS_DIR", data / "uploads")
    monkeypatch.setattr("app.config.TEMPLATES_DIR", data / "templates")
    monkeypatch.setattr("app.config.MATERIALS_DIR", data / "materials")
    monkeypatch.setattr("app.config.FILES_DIR", data / "files")
    monkeypatch.setattr("app.config.BID_DRAFTS_DIR", data / "bid_drafts")
    monkeypatch.setattr("app.config.DB_PATH", data / "app.db")
    # 指向不存在的路径 → 页眉移植走降级分支；需要真实参考的用例自行 monkeypatch
    monkeypatch.setattr("app.config.BID_HEADER_SOURCE_PATH",
                        data / "商务标页眉参考.docx")

