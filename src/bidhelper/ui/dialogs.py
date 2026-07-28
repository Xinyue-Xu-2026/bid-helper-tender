from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
)


class ProjectDialog(QDialog):
    def __init__(self, parent=None, project=None):
        super().__init__(parent)
        self.project = project or {}
        self.setWindowTitle("编辑项目" if project else "新建项目")
        self.resize(400, 250)

        layout = QFormLayout(self)
        self.name_edit = QLineEdit(self.project.get("name", ""))
        self.client_edit = QLineEdit(self.project.get("client", ""))
        self.date_edit = QLineEdit(self.project.get("bid_date", ""))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["审计类", "造价咨询类", "其他"])
        self.type_combo.setCurrentText(self.project.get("project_type", "其他"))
        self.notes_edit = QTextEdit(self.project.get("notes", ""))

        layout.addRow("项目名称：", self.name_edit)
        layout.addRow("招标单位：", self.client_edit)
        layout.addRow("投标日期：", self.date_edit)
        layout.addRow("项目类型：", self.type_combo)
        layout.addRow("备注：", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "client": self.client_edit.text(),
            "bid_date": self.date_edit.text(),
            "project_type": self.type_combo.currentText(),
            "notes": self.notes_edit.toPlainText(),
        }


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(480, 200)

        from bidhelper.settings_store import load_settings
        settings = load_settings()

        layout = QFormLayout(self)

        self.key_edit = QLineEdit(settings.get("api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("sk-...（Moonshot API Key）")
        self.show_key_btn = QPushButton("显示")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visible)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(self.show_key_btn, 0)
        layout.addRow("API Key：", key_row)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["kimi-k2.6", "kimi-k3"])
        self.model_combo.setCurrentText(settings.get("model", "kimi-k2.6"))
        layout.addRow("解析模型：", self.model_combo)

        self.test_btn = QPushButton("测试连接")
        self.test_result_label = QLabel("")
        self.test_result_label.setObjectName("pageHint")
        test_row = QHBoxLayout()
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_result_label, 1)
        layout.addRow(test_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.test_btn.clicked.connect(self._test_connection)

    def _toggle_key_visible(self, checked):
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.show_key_btn.setText("隐藏" if checked else "显示")

    def _test_connection(self):
        api_key = self.key_edit.text().strip()
        if not api_key:
            self.test_result_label.setText("请先输入 API Key")
            return
        self.test_btn.setEnabled(False)
        self.test_result_label.setText("正在测试…")
        try:
            from bidhelper.llm_parser import _make_client
            client = _make_client(api_key, timeout=15.0)
            client.chat.completions.create(
                model=self.model_combo.currentText(),
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            self.test_result_label.setText("连接成功 ✓")
        except Exception as exc:
            self.test_result_label.setText(f"连接失败：{exc}")
        finally:
            self.test_btn.setEnabled(True)

    def get_data(self):
        return {
            "api_key": self.key_edit.text().strip(),
            "model": self.model_combo.currentText(),
        }
