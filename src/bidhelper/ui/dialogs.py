from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QComboBox, QTextEdit, QDialogButtonBox


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
