def test_main_window_layout(qapp):
    from bidhelper.ui.main_window import MainWindow
    window = MainWindow()
    assert window.windowTitle() == "投标助手 v0.2"
    assert window.nav.count() == 3
    assert window.current_project_label.text() == "未选择项目"
