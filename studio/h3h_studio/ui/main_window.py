"""
H3H Studio — Streamlined & Elegant 4IFIR Dynamic Theme & Video Icon Publisher.
Zero clutter. 1-Click workflow for community creators.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QMessageBox
)

from .express_tab import ExpressTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("H3H Studio — Видеофоны и Видеоиконки для 4IFIR")
        self.resize(1140, 880)
        self.setMinimumSize(960, 720)

        self._apply_theme()
        self._init_ui()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0E1217;
                color: #FFFFFF;
            }
            QWidget {
                background-color: #0E1217;
                color: #FFFFFF;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QGroupBox {
                border: 1px solid #232B36;
                border-radius: 8px;
                background-color: #141A23;
                margin-top: 14px;
                padding: 14px;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #1A222D;
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #00E5FF;
            }
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px 16px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #374151;
                border-color: #4B5563;
            }
            QProgressBar {
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                text-align: center;
                background-color: #141A23;
                color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #00E5FF);
                border-radius: 5px;
            }
            QScrollBar:vertical {
                border: none;
                background: #0E1217;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #2D3A4B;
                min-height: 24px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00E5FF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(12)

        # Header Bar
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 4)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_lbl = QLabel("H3H Studio", self)
        title_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_lbl.setStyleSheet("color: #FFFFFF;")

        subtitle_lbl = QLabel("Создание и публикация живых видеофонов и видеоиконок для Nintendo Switch (4IFIR)", self)
        subtitle_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(subtitle_lbl)

        header.addLayout(title_vbox)
        header.addStretch()

        # Cloud Status Badge (Permanent Access indicator)
        cloud_badge = QFrame(self)
        cloud_badge.setStyleSheet("""
            QFrame {
                background-color: #13271F;
                border: 1px solid #10B981;
                border-radius: 6px;
                padding: 4px 12px;
            }
        """)
        cb_layout = QHBoxLayout(cloud_badge)
        cb_layout.setContentsMargins(6, 4, 6, 4)
        cb_layout.setSpacing(6)
        cloud_icon_lbl = QLabel("☁️ <b>Google Диск:</b> Подключен (Вечный доступ)", cloud_badge)
        cloud_icon_lbl.setStyleSheet("color: #34D399; font-size: 12px;")
        cb_layout.addWidget(cloud_icon_lbl)
        header.addWidget(cloud_badge)

        main_layout.addLayout(header)

        # Main Express Publisher View (Clean, all-in-one workflow)
        self.express_view = ExpressTab(self)
        main_layout.addWidget(self.express_view, 1)


def main():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("H3H Studio")
    app.setOrganizationName("H3H")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
