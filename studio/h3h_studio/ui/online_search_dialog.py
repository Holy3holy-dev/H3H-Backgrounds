import tempfile
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

from ..core.online_fetcher import OnlineFetcher


class OnlineSearchDialog(QDialog):
    def __init__(self, on_select_artwork: Callable[[str, str, str], None], on_select_title_id: Callable[[str, str], None], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Поиск игры в онлайн-базе Switch — H3H Studio")
        self.resize(800, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #121418;
                color: #FFFFFF;
            }
            QLineEdit {
                background-color: #1B1F26;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 10px 14px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #00E5FF;
            }
            QPushButton {
                background-color: #252B35;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 8px 14px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #323B47;
            }
            QTableWidget {
                background-color: #1B1F26;
                border: 1px solid #2D3540;
                gridline-color: #2D3540;
                color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: #252B35;
                color: #9AA4B2;
                padding: 8px;
                border: 1px solid #2D3540;
                font-weight: bold;
            }
        """)

        self.on_select_artwork = on_select_artwork
        self.on_select_title_id = on_select_title_id
        self.current_results = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        title_lbl = QLabel("🌐 Онлайн-поиск игры и Title ID", self)
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(title_lbl)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Введите название игры (например: Zelda, Mario, Turtles, Metroid)...")
        self.search_input.textChanged.connect(self._do_search)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton("Поиск", self)
        search_btn.clicked.connect(lambda: self._do_search(self.search_input.text()))
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)

        # Results table
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Название игры", "Title ID (16 hex)", "Издатель"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

        # Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_load_art = QPushButton("📥 Загрузить арт в Режим A", self)
        self.btn_load_art.setStyleSheet("background-color: #00E5FF; color: #121418; font-weight: bold; padding: 10px 18px;")
        self.btn_load_art.clicked.connect(self._load_selected_art)
        btn_layout.addWidget(self.btn_load_art)

        self.btn_apply_id = QPushButton("✓ Применить Title ID", self)
        self.btn_apply_id.setStyleSheet("background-color: #3B82F6; color: #FFFFFF; font-weight: bold; padding: 10px 18px;")
        self.btn_apply_id.clicked.connect(self._apply_selected_id)
        btn_layout.addWidget(self.btn_apply_id)

        close_btn = QPushButton("Закрыть", self)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # Initial populate
        self._do_search("")

    def _do_search(self, query: str):
        self.current_results = OnlineFetcher.search_switch_games(query)
        self.table.setRowCount(len(self.current_results))

        for row, item in enumerate(self.current_results):
            self.table.setItem(row, 0, QTableWidgetItem(item["title"]))
            tid_item = QTableWidgetItem(item["titleId"])
            tid_item.setFont(QFont("JetBrains Mono, Consolas", 11))
            self.table.setItem(row, 1, tid_item)
            self.table.setItem(row, 2, QTableWidgetItem(item.get("publisher", "")))

        if len(self.current_results) > 0:
            self.table.selectRow(0)

    def _get_selected_item(self) -> Optional[dict]:
        sel = self.table.selectedIndexes()
        if not sel:
            return None
        row = sel[0].row()
        if 0 <= row < len(self.current_results):
            return self.current_results[row]
        return None

    def _load_selected_art(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "Внимание", "Выберите игру из списка!")
            return

        art_url = item.get("artUrl")
        if not art_url:
            QMessageBox.warning(self, "Внимание", "Для выбранной игры нет ссылки на обложку.")
            return

        temp_dir = Path(tempfile.gettempdir()) / "h3h_studio_cache"
        self.btn_load_art.setEnabled(False)
        self.btn_load_art.setText("Загрузка арта...")

        art_file = OnlineFetcher.download_image(art_url, temp_dir, item["titleId"])
        self.btn_load_art.setEnabled(True)
        self.btn_load_art.setText("📥 Загрузить арт в Режим A")

        if art_file and art_file.exists():
            self.on_select_artwork(str(art_file), item["titleId"], item["title"])
            QMessageBox.information(
                self, "Успех",
                f"Арт игры '{item['title']}' успешно скачан и загружен в Режим A!\nTitle ID установлен: {item['titleId']}"
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось скачать изображение.")

    def _apply_selected_id(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "Внимание", "Выберите игру из списка!")
            return
        self.on_select_title_id(item["titleId"], item["title"])
        self.accept()
