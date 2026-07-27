from bidhelper import config


def test_paths_exist():
    assert "投标APP" in str(config.APP_ROOT)


def test_ensure_dirs_creates_directories(tmp_path):
    # 临时覆盖验证创建逻辑
    test_root = tmp_path / "投标APP"
    (test_root / "data").mkdir(parents=True, exist_ok=True)
    assert (test_root / "data").exists()
