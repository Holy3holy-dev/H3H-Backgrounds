from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt


class FFmpegLogDialog(QDialog):
    def __init__(self, logs: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Журнал команд FFmpeg — H3H Studio")
        self.resize(750, 480)
        self.setStyleSheet("background-color: #121418; color: #FFFFFF;")

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("JetBrains Mono, Consolas, Courier New", 10))
        self.text_edit.setStyleSheet(
            "background-color: #1B1F26; color: #9AA4B2; border: 1px solid #323B47; border-radius: 6px; padding: 10px;"
        )
        self.text_edit.setPlainText("\n".join(logs))
        layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Копировать журнал", self)
        copy_btn.setStyleSheet("background-color: #252B35; color: #FFFFFF; padding: 8px 16px; border-radius: 4px;")
        copy_btn.clicked.connect(self._copy_logs)
        btn_layout.addWidget(copy_btn)

        close_btn = QPushButton("Закрыть", self)
        close_btn.setStyleSheet("background-color: #3B82F6; color: #FFFFFF; padding: 8px 16px; border-radius: 4px;")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _copy_logs(self):
        self.text_edit.selectAll()
        self.text_edit.copy()
