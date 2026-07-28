import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from bidhelper import settings_store


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _isolate_llm_config(tmp_path, monkeypatch):
    """隔离真实 LLM 配置：测试中不得读取真实 API Key 或真实 config.json。"""
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", tmp_path / "config.json")
    yield
