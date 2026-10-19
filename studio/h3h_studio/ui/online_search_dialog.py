"""
Online Game, Homebrew & Artwork Search Dialog for H3H Studio.
Enables instant search across 7,200+ Switch games, homebrew ports, and live boxart loading.
"""

import tempfile
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QComboBox, QSplitter, QWidget, QFrame
)

from ..core.online_fetcher import OnlineFetcher


class ImageLoaderThread(QThread):
    loaded = Signal(str, bytes)

    def __init__(self, url: str, fallback_title: str):
        super().__init__()
        self.url = url
        self.fallback_title = fallback_title

    def run(self):
        temp_dir = Path(tempfile.gettempdir()) / "h3h_studio_thumbs"
        img_path = OnlineFetcher.download_image(self.url, temp_dir, "thumb_preview", fallback_title=self.fallback_title)
        if img_path and img_path.exists():
            try:
                with open(img_path, "rb") as f:
                    self.loaded.emit(self.url, f.read())
            except Exception:
                pass


class OnlineSearchDialog(QDialog):
    def __init__(
        self,
        on_select_artwork: Callable[[str, str, str], None],
        on_select_title_id: Callable[[str, str], None],
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Поиск игры в онлайн-базе Switch (Игры, Порты, Homebrew) — H3H Studio")
        self.resize(980, 620)
        self.setStyleSheet("""
            QDialog {
                background-color: #121418;
                color: #FFFFFF;
            }
            QLineEdit, QComboBox {
                background-color: #1B1F26;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #00E5FF;
            }
            QPushButton {
                background-color: #252B35;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 8px 16px;
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
                gridline-color: #242B35;
                color: #FFFFFF;
                selection-background-color: #0F4266;
            }
            QHeaderView::section {
                background-color: #252B35;
                color: #A0AEC0;
                padding: 8px;
                border: 1px solid #2D3540;
                font-weight: bold;
            }
        """)

        self.on_select_artwork = on_select_artwork
        self.on_select_title_id = on_select_title_id
        self.current_results = []
        self._thumb_thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        top_bar = QHBoxLayout()
        title_lbl = QLabel("🌐 База игр Nintendo Switch, портов и Homebrew (7 200+)", self)
        title_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        top_bar.addWidget(title_lbl)
        top_bar.addStretch()

        self.category_combo = QComboBox(self)
        self.category_combo.addItem("Все источники (игры + порты)", "all")
        self.category_combo.addItem("Только Homebrew и порты (NRO)", "homebrew")
        self.category_combo.addItem("Только официальные игры", "official")
        self.category_combo.currentIndexChanged.connect(self._trigger_search)
        top_bar.addWidget(self.category_combo)

        layout.addLayout(top_bar)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Введите название игры или Title ID (например: Zelda, Mario, Silent Hill, DOOM, 01007EF...)...")
        self.search_input.textChanged.connect(self._trigger_search)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton("Найти", self)
        search_btn.clicked.connect(self._trigger_search)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)

        # Main splitter (Table + Preview Panel)
        splitter = QSplitter(Qt.Horizontal, self)

        # Results table
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Название игры / порта", "Title ID (16 hex)", "Формат", "Издатель / Разработчик"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        # Right Preview Panel
        preview_panel = QFrame(self)
        preview_panel.setStyleSheet("background-color: #1B1F26; border-radius: 8px; padding: 10px;")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setAlignment(Qt.AlignTop)

        preview_header = QLabel("Превью обложки:", preview_panel)
        preview_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        preview_header.setStyleSheet("color: #00E5FF;")
        preview_layout.addWidget(preview_header)

        self.preview_image = QLabel(preview_panel)
        self.preview_image.setFixedSize(200, 280)
        self.preview_image.setStyleSheet("border: 1px dashed #2D3540; border-radius: 6px; background-color: #121418;")
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setText("Нет обложки")
        preview_layout.addWidget(self.preview_image)

        self.info_title = QLabel("", preview_panel)
        self.info_title.setWordWrap(True)
        self.info_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        preview_layout.addWidget(self.info_title)

        self.info_tid = QLabel("", preview_panel)
        self.info_tid.setFont(QFont("Consolas", 10))
        self.info_tid.setStyleSheet("color: #00E5FF;")
        preview_layout.addWidget(self.info_tid)

        self.info_format = QLabel("", preview_panel)
        self.info_format.setStyleSheet("color: #A0AEC0; font-size: 11px;")
        preview_layout.addWidget(self.info_format)

        preview_layout.addStretch()
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.status_lbl = QLabel("", self)
        self.status_lbl.setStyleSheet("color: #A0AEC0;")
        btn_layout.addWidget(self.status_lbl)
        btn_layout.addStretch()

        self.btn_load_art = QPushButton("📥 Загрузить арт в Режим A", self)
        self.btn_load_art.setStyleSheet("background-color: #00E5FF; color: #121418; font-weight: bold; padding: 10px 20px;")
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

        # Initial Search
        self._trigger_search()

    def _trigger_search(self):
        query = self.search_input.text()
        cat = self.category_combo.currentData()
        self.current_results = OnlineFetcher.search_switch_games(query, category=cat)
        self.table.setRowCount(len(self.current_results))

        for row, item in enumerate(self.current_results):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("title", "")))

            tid = item.get("titleId", "")
            tid_item = QTableWidgetItem(tid if tid else "— (NRO порт)")
            tid_item.setFont(QFont("Consolas", 10))
            if tid:
                tid_item.setForeground(Qt.cyan)
            else:
                tid_item.setForeground(Qt.gray)
            self.table.setItem(row, 1, tid_item)

            fmt = item.get("format", "Игра")
            fmt_item = QTableWidgetItem(fmt)
            fmt_item.setForeground(Qt.yellow if "NRO" in fmt else Qt.lightGray)
            self.table.setItem(row, 2, fmt_item)

            self.table.setItem(row, 3, QTableWidgetItem(item.get("publisher", "")))

        self.status_lbl.setText(f"Найдено: {len(self.current_results)} записей")

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

    def _on_row_selected(self):
        item = self._get_selected_item()
        if not item:
            self.preview_image.setText("Нет выбора")
            self.info_title.setText("")
            self.info_tid.setText("")
            self.info_format.setText("")
            return

        self.info_title.setText(item.get("title", "")[:60])
        tid = item.get("titleId", "")
        self.info_tid.setText(f"Title ID: {tid if tid else 'Не задан'}")
        self.info_format.setText(f"Формат: {item.get('format', '—')} | {item.get('genre', '')}")

        art_url = item.get("artUrl")
        if art_url:
            self.preview_image.setText("Загрузка...")
            if self._thumb_thread and self._thumb_thread.isRunning():
                self._thumb_thread.terminate()

            self._thumb_thread = ImageLoaderThread(art_url, item.get("title", ""))
            self._thumb_thread.loaded.connect(self._on_thumb_loaded)
            self._thumb_thread.start()
        else:
            self.preview_image.setText("Нет обложки")

    def _on_thumb_loaded(self, url: str, img_bytes: bytes):
        pixmap = QPixmap()
        if pixmap.loadFromData(img_bytes):
            scaled = pixmap.scaled(200, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview_image.setPixmap(scaled)
        else:
            self.preview_image.setText("Ошибка превью")

    def _load_selected_art(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "Внимание", "Выберите игру из списка!")
            return

        title = item.get("title", "")
        tid = item.get("titleId", "").strip().upper()
        if not tid:
            # If homebrew NRO without ID, ask or generate
            tid = "0100000000001000"

        temp_dir = Path(tempfile.gettempdir()) / "h3h_studio_cache"
        self.btn_load_art.setEnabled(False)
        self.btn_load_art.setText("Загрузка арта...")

        art_file = OnlineFetcher.download_image(
            item.get("artUrl"),
            temp_dir,
            tid,
            fallback_title=title
        )

        self.btn_load_art.setEnabled(True)
        self.btn_load_art.setText("📥 Загрузить арт в Режим A")

        if art_file and art_file.exists():
            self.on_select_artwork(str(art_file), tid, title)
            QMessageBox.information(
                self, "Успех",
                f"Арт игры '{title}' успешно загружен в Режим A!\nTitle ID: {tid}"
            )
            self.accept()
        else:
            QMessageBox.critical(
                self, "Ошибка",
                f"Не удалось скачать обложку для '{title}'.\nПопробуйте выбрать другой вариант или указать локальный файл."
            )

    def _apply_selected_id(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "Внимание", "Выберите игру из списка!")
            return
        tid = item.get("titleId", "").strip().upper()
        if not tid:
            QMessageBox.information(
                self, "Инфо",
                "У этого Homebrew NRO нет зарегистрированного Title ID. Вы можете задать Title ID вручную в основном окне."
            )
            return
        self.on_select_title_id(tid, item.get("title", ""))
        self.accept()
