"""
Online Animated Icons & Loops Search Dialog for H3H Studio.
Uses QNetworkAccessManager for 100% thread-safe async image loading without segfaults.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QScrollArea,
    QProgressBar, QFrame, QMessageBox
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from ..core.animated_icons_fetcher import AnimatedIconsFetcher


class SearchWorker(QThread):
    results_ready = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, query: str, source: str):
        super().__init__()
        self.query = query
        self.source = source

    def run(self):
        try:
            items = AnimatedIconsFetcher.search_all(self.query, self.source)
            self.results_ready.emit(items)
        except Exception as e:
            self.error_occurred.emit(str(e))


class DownloadWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(Path, str)
    error = Signal(str)

    def __init__(self, item: Dict[str, Any]):
        super().__init__()
        self.item = item

    def run(self):
        try:
            dest_dir = Path("tmp/online_icons_cache")
            out_path = AnimatedIconsFetcher.download_and_convert_to_mp4(
                self.item,
                dest_dir,
                on_progress=lambda p, s: self.progress.emit(p, s)
            )
            if out_path and out_path.exists():
                self.finished.emit(out_path, self.item.get("title", ""))
            else:
                self.error.emit("Не удалось загрузить или сконвертировать анимацию.")
        except Exception as e:
            self.error.emit(str(e))


class OnlineIconsDialog(QDialog):
    icon_chosen = Signal(Path, str)  # Emits (converted_mp4_path, item_title)

    def __init__(self, parent=None, initial_query: str = ""):
        super().__init__(parent)
        self.setWindowTitle("🌐 Поиск анимированных иконок и гифок онлайн (SteamGridDB / Steam / Tenor)")
        self.resize(920, 680)
        self.setMinimumSize(800, 550)
        self.initial_query = initial_query

        self.search_worker: Optional[SearchWorker] = None
        self.download_worker: Optional[DownloadWorker] = None
        
        # Native Qt network manager for asynchronous thumbnail downloading on GUI loop
        self.net_manager = QNetworkAccessManager(self)
        self.active_replies: List[QNetworkReply] = []

        self._apply_style()
        self._init_ui()

        if self.initial_query:
            self.search_edit.setText(self.initial_query)
            self._start_search()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0E1217;
                color: #FFFFFF;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLineEdit {
                background-color: #1A222D;
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                padding: 10px 14px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #00E5FF;
            }
            QComboBox {
                background-color: #1A222D;
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 9px 16px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2D3748;
            }
            QScrollArea {
                border: 1px solid #232B36;
                border-radius: 8px;
                background-color: #141A23;
            }
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Info
        hdr_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_lbl = QLabel("🌐 Онлайн-галерея анимированных иконок", self)
        title_lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title_lbl.setStyleSheet("color: #FFFFFF;")
        sub_lbl = QLabel("Поиск живых аватаров и анимаций по базам SteamGridDB, Магазина Steam и Tenor", self)
        sub_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        hdr_row.addLayout(title_box)
        hdr_row.addStretch()
        main_layout.addLayout(hdr_row)

        # Search Controls Bar
        ctrl_card = QFrame(self)
        ctrl_card.setStyleSheet("background-color: #141A23; border: 1px solid #232B36; border-radius: 8px; padding: 6px;")
        c_lay = QHBoxLayout(ctrl_card)
        c_lay.setContentsMargins(10, 8, 10, 8)
        c_lay.setSpacing(10)

        self.search_edit = QLineEdit(ctrl_card)
        self.search_edit.setPlaceholderText("Введите название игры (напр. Witcher 3, Cyberpunk, Hades, Celeste)...")
        self.search_edit.returnPressed.connect(self._start_search)
        c_lay.addWidget(self.search_edit, 1)

        self.source_combo = QComboBox(ctrl_card)
        self.source_combo.addItem("🌐 Все источники", "all")
        self.source_combo.addItem("🎮 Магазин Steam (Аватары)", "steam_points")
        self.source_combo.addItem("🎨 SteamGridDB (Сетки и иконки)", "steamgriddb")
        self.source_combo.addItem("✨ MoeWalls (Живые обои 1080p)", "moewalls")
        self.source_combo.addItem("🌀 Tenor (Гифки)", "tenor")
        self.source_combo.currentIndexChanged.connect(self._start_search)
        c_lay.addWidget(self.source_combo)

        self.btn_search = QPushButton("🔍 Найти", ctrl_card)
        self.btn_search.setStyleSheet("background-color: #0284C7; font-weight: bold; padding: 10px 20px;")
        self.btn_search.clicked.connect(self._start_search)
        c_lay.addWidget(self.btn_search)

        main_layout.addWidget(ctrl_card)

        # Progress & Status
        self.status_lbl = QLabel("Введите название игры и нажмите «Найти»", self)
        self.status_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        main_layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #2D3A4B;
                border-radius: 4px;
                text-align: center;
                background-color: #141A23;
                color: #FFFFFF;
                height: 16px;
            }
            QProgressBar::chunk {
                background: #00E5FF;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        # Scrollable Cards Area
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(12, 12, 12, 12)
        self.cards_layout.setSpacing(12)
        self.scroll.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll, 1)

        # Footer Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_close = QPushButton("Закрыть", self)
        self.btn_close.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_close)
        main_layout.addLayout(btn_box)

    def _cancel_active_replies(self):
        for reply in self.active_replies:
            try:
                reply.abort()
                reply.deleteLater()
            except Exception:
                pass
        self.active_replies.clear()

    def _start_search(self):
        query = self.search_edit.text().strip()
        if not query:
            return

        self._cancel_active_replies()

        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.terminate()
            self.search_worker.wait(500)

        self.btn_search.setEnabled(False)
        self.status_lbl.setText(f"Поиск анимаций для «{query}» во всех онлайн-базах...")
        self.status_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate

        # Clear existing cards
        for i in reversed(range(self.cards_layout.count())):
            w = self.cards_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        self.search_worker = SearchWorker(query, self.source_combo.currentData())
        self.search_worker.results_ready.connect(self._on_results_ready)
        self.search_worker.error_occurred.connect(self._on_search_error)
        self.search_worker.start()

    def _on_results_ready(self, items: List[Dict[str, Any]]):
        self.btn_search.setEnabled(True)
        self.progress_bar.setVisible(False)

        if not items:
            self.status_lbl.setText("Ничего не найдено. Попробуйте ввести название игры на английском (напр. Witcher, Cyberpunk).")
            self.status_lbl.setStyleSheet("color: #EF4444;")
            return

        self.status_lbl.setText(f"Найдено {len(items)} анимаций. Нажмите «Выбрать», чтобы применить как видеоиконку:")
        self.status_lbl.setStyleSheet("color: #10B981; font-weight: bold;")

        cols = 3
        for idx, item in enumerate(items):
            card = self._create_item_card(item)
            r = idx // cols
            c = idx % cols
            self.cards_layout.addWidget(card, r, c)

    def _create_item_card(self, item: Dict[str, Any]) -> QWidget:
        card = QFrame(self.cards_container)
        card.setStyleSheet("""
            QFrame {
                background-color: #1A222D;
                border: 1px solid #2D3A4B;
                border-radius: 8px;
                padding: 6px;
            }
            QFrame:hover {
                border: 1px solid #00E5FF;
            }
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # Top Badge Row (Source & Format)
        b_row = QHBoxLayout()
        src = item.get("source", "")
        bg_col = "#0284C7" if src == "steam_points" else ("#7C3AED" if src == "steamgriddb" else "#059669")
        badge = QLabel(f" {item.get('source_label', 'Online')} ", card)
        badge.setStyleSheet(f"background-color: {bg_col}; color: #FFFFFF; font-weight: bold; font-size: 10px; border-radius: 4px; padding: 2px 6px;")
        b_row.addWidget(badge)

        b_row.addStretch()
        fmt_lbl = QLabel(item.get("format", "mp4").upper(), card)
        fmt_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; font-weight: bold;")
        b_row.addWidget(fmt_lbl)
        lay.addLayout(b_row)

        # Thumbnail
        thumb_lbl = QLabel(card)
        thumb_lbl.setFixedSize(140, 140)
        thumb_lbl.setAlignment(Qt.AlignCenter)
        thumb_lbl.setStyleSheet("background-color: #0E1217; border-radius: 6px; border: 1px solid #232B36; color: #64748B; font-size: 10px;")
        thumb_lbl.setText("Загрузка...")
        lay.addWidget(thumb_lbl, 0, Qt.AlignCenter)

        # Load thumbnail asynchronously via QNetworkAccessManager (100% thread-safe on GUI loop)
        t_url = item.get("thumb_url") or item.get("url")
        if t_url:
            req = QNetworkRequest(QUrl(t_url))
            req.setRawHeader(b"User-Agent", b"Mozilla/5.0")
            reply = self.net_manager.get(req)
            self.active_replies.append(reply)
            reply.finished.connect(lambda r=reply, lbl=thumb_lbl: self._on_thumb_received(r, lbl))

        # Title
        title_lbl = QLabel(item.get("title", ""), card)
        title_lbl.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 11px;")
        title_lbl.setWordWrap(True)
        title_lbl.setFixedHeight(34)
        lay.addWidget(title_lbl)

        # Select Button
        btn_select = QPushButton("⚡️ Выбрать анимацию", card)
        btn_select.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #00E5FF);
                color: #0E1217;
                font-weight: bold;
                font-size: 12px;
                padding: 7px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #00E5FF;
            }
        """)
        btn_select.clicked.connect(lambda _, it=item: self._select_item(it))
        lay.addWidget(btn_select)

        return card

    def _on_thumb_received(self, reply: QNetworkReply, label: QLabel):
        try:
            if reply in self.active_replies:
                self.active_replies.remove(reply)
            if reply.error() == QNetworkReply.NoError:
                data = reply.readAll().data()
                pix = QPixmap()
                if pix.loadFromData(data):
                    scaled = pix.scaled(136, 136, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    label.setPixmap(scaled)
        except Exception:
            pass
        finally:
            reply.deleteLater()

    def _select_item(self, item: Dict[str, Any]):
        self._cancel_active_replies()
        self.btn_search.setEnabled(False)
        self.status_lbl.setText(f"Загрузка и подготовка «{item.get('title')}»...")
        self.status_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(20)

        self.download_worker = DownloadWorker(item)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.error.connect(self._on_download_error)
        self.download_worker.start()

    def _on_download_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.status_lbl.setText(msg)

    def _on_download_finished(self, mp4_path: Path, title: str):
        self.progress_bar.setValue(100)
        self.status_lbl.setText("✔ Успешно загружено!")
        self.icon_chosen.emit(mp4_path, title)
        self.accept()

    def _on_download_error(self, err: str):
        self.btn_search.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setText(f"Ошибка: {err}")
        self.status_lbl.setStyleSheet("color: #EF4444;")
        QMessageBox.warning(self, "Ошибка загрузки", f"Не удалось загрузить анимацию:\n{err}")

    def _on_search_error(self, err: str):
        self.btn_search.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_lbl.setText(f"Ошибка поиска: {err}")
        self.status_lbl.setStyleSheet("color: #EF4444;")

    def closeEvent(self, event):
        self._cancel_active_replies()
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.terminate()
            self.search_worker.wait(500)
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.terminate()
            self.download_worker.wait(500)
        super().closeEvent(event)
