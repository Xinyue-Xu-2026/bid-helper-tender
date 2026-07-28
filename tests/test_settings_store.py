import json

import pytest

from bidhelper import settings_store


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(settings_store, "SETTINGS_FILE", path)
    return path


def test_load_settings_missing_file(settings_file):
    assert settings_store.load_settings() == {}


def test_save_and_load_settings(settings_file):
    settings_store.save_settings({"api_key": "sk-test", "model": "kimi-k3"})
    assert json.loads(settings_file.read_text(encoding="utf-8"))["api_key"] == "sk-test"
    assert settings_store.load_settings() == {"api_key": "sk-test", "model": "kimi-k3"}


def test_get_api_key_env_priority(settings_file, monkeypatch):
    settings_file.write_text(json.dumps({"api_key": "sk-file"}), encoding="utf-8")
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-env")
    assert settings_store.get_api_key() == "sk-env"


def test_get_api_key_from_file(settings_file, monkeypatch):
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    settings_file.write_text(json.dumps({"api_key": "sk-file"}), encoding="utf-8")
    assert settings_store.get_api_key() == "sk-file"


def test_get_api_key_empty(settings_file, monkeypatch):
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    assert settings_store.get_api_key() == ""


def test_get_model_default(settings_file):
    assert settings_store.get_model() == "kimi-k2.6"
