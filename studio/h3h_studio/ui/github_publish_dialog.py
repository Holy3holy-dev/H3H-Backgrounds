"""
GitHub Video Background Publisher Dialog for H3H Studio.
Supports single background publishing and batch publishing from ZIP archives or folders.
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QComboBox, QTextEdit, QProgressBar, QMessageBox,
    QFileDialog, QFrame, QGroupBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget
)

from ..core.github_publisher import GitHubPublisher
from ..core.compliance import ComplianceValidator
from ..core.google_drive import GoogleDriveHelper
from ..core.online_fetcher import OnlineFetcher


class PublishWorkerThread(QThread):
    progress_status = Signal(str)
    finished = Signal(bool, dict, str)

    def __init__(
        self,
        video_path: Path,
        title_id: str,
        game_title: str,
        variant_name: str,
        style: str,
        author: str,
        token: str,
        repo: str,
        release_tag: str,
        description: str
    ):
        super().__init__()
        self.video_path = video_path
        self.title_id = title_id
        self.game_title = game_title
        self.variant_name = variant_name
        self.style = style
        self.author = author
        self.token = token
        self.repo = repo
        self.release_tag = release_tag
        self.description = description

    def run(self):
        try:
            res = GitHubPublisher.upload_video(
                video_path=self.video_path,
                title_id=self.title_id,
                game_title=self.game_title,
                variant_name=self.variant_name,
                style=self.style,
                author=self.author,
                token=self.token,
                repo=self.repo,
                release_tag=self.release_tag,
                description=self.description,
                progress_cb=self.progress_status.emit
            )
            self.finished.emit(True, res, "")
        except Exception as e:
            self.finished.emit(False, {}, str(e))


class BatchPublishWorkerThread(QThread):
    progress_status = Signal(str)
    finished = Signal(bool, list, str)

    def __init__(
        self,
        items: List[Dict[str, Any]],
        token: str,
        repo: str,
        release_tag: str,
        author: str
    ):
        super().__init__()
        self.items = items
        self.token = token
        self.repo = repo
        self.release_tag = release_tag
        self.author = author

    def run(self):
        try:
            res = GitHubPublisher.upload_batch_videos(
                items=self.items,
                token=self.token,
                repo=self.repo,
                release_tag=self.release_tag,
                author=self.author,
                progress_cb=self.progress_status.emit
            )
            self.finished.emit(True, res, "")
        except Exception as e:
            self.finished.emit(False, [], str(e))


class DeleteWorkerThread(QThread):
    progress_status = Signal(str)
    finished = Signal(bool, str)

    def __init__(
        self,
        title_id: str,
        variant_id: str,
        token: str,
        repo: str,
        release_tag: str
    ):
        super().__init__()
        self.title_id = title_id
        self.variant_id = variant_id
        self.token = token
        self.repo = repo
        self.release_tag = release_tag

    def run(self):
        try:
            ok = GitHubPublisher.delete_published_variant(
                title_id=self.title_id,
                variant_id=self.variant_id,
                token=self.token,
                repo=self.repo,
                release_tag=self.release_tag,
                progress_cb=self.progress_status.emit
            )
            if ok:
                self.finished.emit(True, "")
            else:
                self.finished.emit(False, "Запись не найдена в каталоге")
        except Exception as e:
            self.finished.emit(False, str(e))


class BatchScanWorkerThread(QThread):
    progress_status = Signal(str)
    finished = Signal(list)

    def __init__(self, source_path: Path):
        super().__init__()
        self.source_path = source_path

    def run(self):
        try:
            items = GitHubPublisher.scan_archive_or_folder(
                self.source_path,
                progress_cb=self.progress_status.emit
            )
            self.finished.emit(items)
        except Exception as e:
            print(f"[-] Scan worker error: {e}")
            self.finished.emit([])


class GitHubPublishDialog(QDialog):
    def __init__(
        self,
        video_path: Optional[str] = None,
        title_id: str = "",
        game_title: str = "",
        style: str = "Animated Art",
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Публикация видеофонов на GitHub — H3H Studio")
        self.resize(880, 720)
        self.setStyleSheet("""
            QDialog {
                background-color: #121418;
                color: #FFFFFF;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #1B1F26;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: #00E5FF;
            }
            QPushButton {
                background-color: #252B35;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 9px 16px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #323B47;
            }
            QGroupBox {
                border: 1px solid #2D3540;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: bold;
                color: #00E5FF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QTabWidget::pane {
                border: 1px solid #2D3540;
                background-color: #161A20;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #1B1F26;
                color: #A0AEC0;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #252B35;
                color: #00E5FF;
                border-bottom: 2px solid #00E5FF;
            }
            QTableWidget {
                background-color: #121418;
                border: 1px solid #2D3540;
                gridline-color: #2D3540;
                color: #FFFFFF;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #1F242D;
                color: #00E5FF;
                padding: 6px;
                font-weight: bold;
                border: 1px solid #2D3540;
            }
        """)

        token, user = GitHubPublisher.get_stored_credentials()
        self.default_token = token or ""
        self.default_user = user or "Holy3holy-dev"
        self._worker: Optional[PublishWorkerThread] = None
        self._batch_worker: Optional[BatchPublishWorkerThread] = None
        self._delete_worker: Optional[DeleteWorkerThread] = None
        self._scan_worker: Optional[BatchScanWorkerThread] = None
        self.scanned_items: List[Dict[str, Any]] = []
        self.catalog_items: List[Dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header
        header = QLabel("🚀 Публикация и управление видеофонами на GitHub", self)
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(header)

        # Tabs: Single Video vs Batch / Archive vs Manage
        self.tabs = QTabWidget(self)

        # Tab 1: Single Video
        single_tab = self._create_single_tab(video_path, title_id, game_title, style)
        self.tabs.addTab(single_tab, "📄 Одиночное видео")

        # Tab 2: Batch / Archive
        batch_tab = self._create_batch_tab()
        self.tabs.addTab(batch_tab, "📦 Пакетная публикация (Архив / Папка)")

        # Tab 3: Manage & Delete
        manage_tab = self._create_manage_tab()
        self.tabs.addTab(manage_tab, "🗑 Управление каталогом и удаление")

        # Tab 4: Google Drive (5 TB)
        gdrive_tab = self._create_gdrive_tab(video_path, title_id, game_title, style)
        self.tabs.addTab(gdrive_tab, "📁 Google Диск (5 ТБ)")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.tabs)

        # Common GitHub Credentials Section
        git_box = QGroupBox("Параметры GitHub", self)
        git_layout = QVBoxLayout(git_box)

        git_row = QHBoxLayout()
        repo_layout = QVBoxLayout()
        repo_layout.addWidget(QLabel("Репозиторий GitHub:", git_box))
        self.repo_edit = QLineEdit(GitHubPublisher.DEFAULT_REPO, git_box)
        repo_layout.addWidget(self.repo_edit)
        git_row.addLayout(repo_layout)

        tag_layout = QVBoxLayout()
        tag_layout.addWidget(QLabel("Тег релиза:", git_box))
        self.tag_edit = QLineEdit(GitHubPublisher.DEFAULT_TAG, git_box)
        tag_layout.addWidget(self.tag_edit)
        git_row.addLayout(tag_layout)

        author_layout = QVBoxLayout()
        author_layout.addWidget(QLabel("Автор видеофона:", git_box))
        self.common_author_edit = QLineEdit(self.default_user, git_box)
        author_layout.addWidget(self.common_author_edit)
        git_row.addLayout(author_layout)

        git_layout.addLayout(git_row)

        tok_layout = QVBoxLayout()
        tok_layout.addWidget(QLabel("GitHub Personal Access Token (PAT):", git_box))
        self.token_edit = QLineEdit(self.default_token, git_box)
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
        tok_layout.addWidget(self.token_edit)

        if self.default_token:
            tok_hint = QLabel("✓ Токен авторизации автоматически подгружен из системы", git_box)
            tok_hint.setStyleSheet("color: #10B981; font-size: 11px;")
            tok_layout.addWidget(tok_hint)

        git_layout.addLayout(tok_layout)
        layout.addWidget(git_box)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("", self)
        self.status_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        layout.addWidget(self.status_lbl)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        close_btn = QPushButton("Закрыть", self)
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        if video_path:
            self._validate_selected_file(video_path)

    def _create_single_tab(self, video_path: Optional[str], title_id: str, game_title: str, style: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Video file selection
        file_box = QGroupBox("1. Выбор видеофайла (MP4)", widget)
        file_layout = QVBoxLayout(file_box)
        pick_layout = QHBoxLayout()
        self.file_edit = QLineEdit(video_path or "", file_box)
        self.file_edit.setPlaceholderText("Путь к готовому MP4 файлу...")
        self.file_edit.textChanged.connect(self._validate_selected_file)
        pick_layout.addWidget(self.file_edit)

        browse_btn = QPushButton("Обзор...", file_box)
        browse_btn.clicked.connect(self._browse_single_file)
        pick_layout.addWidget(browse_btn)
        file_layout.addLayout(pick_layout)

        self.compliance_lbl = QLabel("Статус соответствия: Не проверено", file_box)
        self.compliance_lbl.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        file_layout.addWidget(self.compliance_lbl)
        layout.addWidget(file_box)

        # 2. Game & Variant Metadata
        meta_box = QGroupBox("2. Метаданные игры и варианта", widget)
        meta_layout = QVBoxLayout(meta_box)

        row1 = QHBoxLayout()
        tid_layout = QVBoxLayout()
        tid_layout.addWidget(QLabel("Title ID игры (16 шестнадцатеричных символов):", meta_box))
        self.tid_edit = QLineEdit(title_id, meta_box)
        self.tid_edit.setPlaceholderText("01007EF00011E000")
        self.tid_edit.setFont(QFont("Consolas", 11))
        tid_layout.addWidget(self.tid_edit)
        row1.addLayout(tid_layout)

        game_layout = QVBoxLayout()
        game_layout.addWidget(QLabel("Название игры:", meta_box))
        self.game_edit = QLineEdit(game_title, meta_box)
        self.game_edit.setPlaceholderText("The Legend of Zelda...")
        game_layout.addWidget(self.game_edit)
        row1.addLayout(game_layout)
        meta_layout.addLayout(row1)

        row2 = QHBoxLayout()
        var_layout = QVBoxLayout()
        var_layout.addWidget(QLabel("Название варианта (например, Opening Loop):", meta_box))
        self.var_edit = QLineEdit(meta_box)
        self.var_edit.setPlaceholderText("Main Theme Animated Loop")
        var_layout.addWidget(self.var_edit)
        row2.addLayout(var_layout)

        style_layout = QVBoxLayout()
        style_layout.addWidget(QLabel("Категория / Стиль:", meta_box))
        self.style_combo = QComboBox(meta_box)
        self.style_combo.addItems(["Animated Art", "Cinematic", "Gameplay", "Minimal", "Dark", "Retro"])
        self.style_combo.setCurrentText(style)
        style_layout.addWidget(self.style_combo)
        row2.addLayout(style_layout)
        meta_layout.addLayout(row2)

        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Краткое описание / теги (необязательно):", meta_box))
        self.desc_edit = QLineEdit(meta_box)
        self.desc_edit.setPlaceholderText("Плавное зацикливание, 60fps, высокое качество")
        desc_layout.addWidget(self.desc_edit)
        meta_layout.addLayout(desc_layout)
        layout.addWidget(meta_box)

        # Single Publish Button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.single_publish_btn = QPushButton("🚀 Опубликовать видеофон на GitHub", widget)
        self.single_publish_btn.setStyleSheet("background-color: #00E5FF; color: #121418; font-weight: bold; padding: 11px 24px; font-size: 13px;")
        self.single_publish_btn.clicked.connect(self._start_single_publish)
        btn_box.addWidget(self.single_publish_btn)
        layout.addLayout(btn_box)

        return widget

    def _create_batch_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Archive / Folder picker buttons
        src_box = QGroupBox("1. Источник видеофайлов", widget)
        src_layout = QVBoxLayout(src_box)

        btn_row = QHBoxLayout()
        zip_btn = QPushButton("📦 Выбрать ZIP-архив с видео...", src_box)
        zip_btn.setStyleSheet("background-color: #3B82F6; color: #FFFFFF; font-weight: bold; padding: 9px 16px;")
        zip_btn.clicked.connect(self._browse_zip_archive)
        btn_row.addWidget(zip_btn)

        folder_btn = QPushButton("📁 Выбрать папку с видео...", src_box)
        folder_btn.setStyleSheet("background-color: #252B35; color: #FFFFFF; font-weight: bold; padding: 9px 16px;")
        folder_btn.clicked.connect(self._browse_folder)
        btn_row.addWidget(folder_btn)
        src_layout.addLayout(btn_row)

        self.batch_src_lbl = QLabel("Архив или папка не выбраны. Выберите архив или папку с видеофонами.", src_box)
        self.batch_src_lbl.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        src_layout.addWidget(self.batch_src_lbl)
        layout.addWidget(src_box)

        # Table of found videos
        table_box = QGroupBox("2. Обнаруженные видеофоны", widget)
        t_layout = QVBoxLayout(table_box)

        self.batch_table = QTableWidget(0, 6, table_box)
        self.batch_table.setHorizontalHeaderLabels([
            "Вкл", "Имя файла", "Title ID", "Название игры", "Размер", "Статус 4IFIR"
        ])
        self.batch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.batch_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.batch_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Interactive)
        t_layout.addWidget(self.batch_table)

        # Table buttons
        tbl_btn_row = QHBoxLayout()
        sel_all_btn = QPushButton("Выбрать все", table_box)
        sel_all_btn.clicked.connect(lambda: self._set_all_checks(True))
        tbl_btn_row.addWidget(sel_all_btn)

        desel_all_btn = QPushButton("Снять выбор", table_box)
        desel_all_btn.clicked.connect(lambda: self._set_all_checks(False))
        tbl_btn_row.addWidget(desel_all_btn)

        self.batch_stats_lbl = QLabel("Видео не загружены", table_box)
        self.batch_stats_lbl.setStyleSheet("color: #10B981; font-weight: bold;")
        tbl_btn_row.addWidget(self.batch_stats_lbl)
        tbl_btn_row.addStretch()

        self.batch_publish_btn = QPushButton("🚀 Опубликовать все выбранные видео на GitHub", table_box)
        self.batch_publish_btn.setEnabled(False)
        self.batch_publish_btn.setStyleSheet("background-color: #00E5FF; color: #121418; font-weight: bold; padding: 11px 24px; font-size: 13px;")
        self.batch_publish_btn.clicked.connect(self._start_batch_publish)
        tbl_btn_row.addWidget(self.batch_publish_btn)

        t_layout.addLayout(tbl_btn_row)
        layout.addWidget(table_box)

        return widget

    def _browse_single_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выберите готовый видеофон MP4", "", "MP4 Videos (*.mp4)")
        if f:
            self.file_edit.setText(f)
            # Try to infer Title ID from filename if empty
            fname = Path(f).name
            m = re.search(r"\b(0100[0-9A-Fa-f]{12})\b", fname, re.IGNORECASE) or re.search(r"\b([0-9A-Fa-f]{16})\b", fname)
            if m and not self.tid_edit.text():
                self.tid_edit.setText(m.group(1).upper())

    def _browse_zip_archive(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Выберите архив с видеофонами", "",
            "Архивы (*.zip *.7z *.rar *.tar);;Все файлы (*.*)"
        )
        if f:
            self._load_batch_source(Path(f))

    def _browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Выберите папку с видеофонами MP4")
        if d:
            self._load_batch_source(Path(d))

    def _load_batch_source(self, source_path: Path):
        self.batch_src_lbl.setText(f"Подготовка к сканированию: {source_path.name}...")
        self.batch_src_lbl.setStyleSheet("color: #00E5FF;")
        self.status_lbl.setText(f"Сканирование: {source_path.name}...")
        self.progress_bar.setVisible(True)
        self.batch_publish_btn.setEnabled(False)

        self._scan_worker = BatchScanWorkerThread(source_path)
        self._scan_worker.progress_status.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_progress(self, msg: str):
        self.batch_src_lbl.setText(msg)
        self.status_lbl.setText(msg)

    def _on_scan_finished(self, items: list):
        self.progress_bar.setVisible(False)
        self.scanned_items = items
        if not self.scanned_items:
            self.batch_src_lbl.setText("В выбранном источнике не найдено видеофайлов MP4.")
            self.batch_src_lbl.setStyleSheet("color: #EF4444;")
            self.batch_table.setRowCount(0)
            self.batch_publish_btn.setEnabled(False)
            return

        self.batch_src_lbl.setText(f"✓ Загружено {len(self.scanned_items)} видеофонов.")
        self.batch_src_lbl.setStyleSheet("color: #10B981; font-weight: bold;")
        self.status_lbl.setText(f"Найдено {len(self.scanned_items)} видеофонов, готовых к публикации.")
        self._populate_batch_table()

    def _populate_batch_table(self):
        self.batch_table.setRowCount(len(self.scanned_items))
        valid_count = 0

        for row, it in enumerate(self.scanned_items):
            # 0. Checkbox
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if it["titleId"] else Qt.Unchecked)
            self.batch_table.setItem(row, 0, chk)

            # 1. Filename
            self.batch_table.setItem(row, 1, QTableWidgetItem(it["filename"]))

            # 2. Title ID
            tid_item = QTableWidgetItem(it["titleId"] or "Не найден")
            tid_item.setFont(QFont("Consolas", 10))
            tid_item.setForeground(Qt.cyan if it["titleId"] else Qt.red)
            self.batch_table.setItem(row, 2, tid_item)

            # 3. Game Title
            self.batch_table.setItem(row, 3, QTableWidgetItem(it["gameTitle"]))

            # 4. Size
            sz_mb = it["sizeBytes"] / (1024 * 1024)
            self.batch_table.setItem(row, 4, QTableWidgetItem(f"{sz_mb:.2f} MB"))

            # 5. 4IFIR Status
            if it["isValid"]:
                valid_count += 1
                stat_item = QTableWidgetItem(f"✓ 4IFIR OK ({it['width']}x{it['height']} @{round(it['fps'])}fps)")
                stat_item.setForeground(QColor("#10B981"))
            else:
                err_str = "; ".join(it["errors"]) if it["errors"] else "Несовместимо"
                stat_item = QTableWidgetItem(f"⚠ {err_str}")
                stat_item.setForeground(QColor("#F59E0B"))
            self.batch_table.setItem(row, 5, stat_item)

        self.batch_stats_lbl.setText(f"Найдено: {len(self.scanned_items)} видео | Готово к 4IFIR: {valid_count}")
        self.batch_publish_btn.setEnabled(len(self.scanned_items) > 0)

    def _set_all_checks(self, checked: bool):
        st = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.batch_table.rowCount()):
            item = self.batch_table.item(row, 0)
            if item:
                item.setCheckState(st)

    def _validate_selected_file(self, path_str: str):
        p = Path(path_str.strip())
        if not p.exists() or not p.is_file():
            self.compliance_lbl.setText("Файл не найден")
            self.compliance_lbl.setStyleSheet("color: #EF4444;")
            return

        comp = ComplianceValidator.validate_mp4(p)
        if comp.is_valid:
            self.compliance_lbl.setText(
                f"✓ Соответствует 4IFIR: {comp.width}x{comp.height} @{round(comp.fps)}fps, кодек: {comp.codec}, размер: {p.stat().st_size / 1024 / 1024:.2f} MB"
            )
            self.compliance_lbl.setStyleSheet("color: #10B981; font-weight: bold;")
        else:
            err = "; ".join(comp.errors)
            self.compliance_lbl.setText(f"⚠ Предупреждение 4IFIR: {err}")
            self.compliance_lbl.setStyleSheet("color: #F59E0B;")

    def _start_single_publish(self):
        video_p = Path(self.file_edit.text().strip())
        if not video_p.exists():
            QMessageBox.warning(self, "Ошибка", "Выберите существующий MP4 файл для загрузки!")
            return

        tid = self.tid_edit.text().strip().upper()
        if not tid or len(tid) != 16 or not re.match(r"^[0-9A-Fa-f]{16}$", tid):
            QMessageBox.warning(self, "Ошибка", "Title ID должен состоять из 16 шестнадцатеричных символов!")
            return

        game = self.game_edit.text().strip()
        if not game:
            QMessageBox.warning(self, "Ошибка", "Укажите название игры!")
            return

        var_name = self.var_edit.text().strip() or "Default"
        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Ошибка", "Укажите GitHub Personal Access Token (PAT)!")
            return

        repo = self.repo_edit.text().strip()
        tag = self.tag_edit.text().strip()
        style = self.style_combo.currentText()
        author = self.common_author_edit.text().strip() or self.default_user
        desc = self.desc_edit.text().strip()

        self._set_ui_busy(True)
        self.status_lbl.setText("Подготовка к отправке...")

        self._worker = PublishWorkerThread(
            video_path=video_p,
            title_id=tid,
            game_title=game,
            variant_name=var_name,
            style=style,
            author=author,
            token=token,
            repo=repo,
            release_tag=tag,
            description=desc
        )
        self._worker.progress_status.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_single_worker_finished)
        self._worker.start()

    def _start_batch_publish(self):
        # Collect checked items
        selected_items = []
        for row in range(self.batch_table.rowCount()):
            chk_item = self.batch_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                it = self.scanned_items[row]
                # In case user edited table
                tid_cell = self.batch_table.item(row, 2)
                if tid_cell and tid_cell.text():
                    it["titleId"] = tid_cell.text().strip().upper()
                name_cell = self.batch_table.item(row, 3)
                if name_cell and name_cell.text():
                    it["gameTitle"] = name_cell.text().strip()

                if not it.get("titleId") or len(it["titleId"]) != 16:
                    QMessageBox.warning(
                        self, "Неверный Title ID",
                        f"Строка {row+1} ({it['filename']}): отсутствует корректный 16-значный Title ID!"
                    )
                    return
                selected_items.append(it)

        if not selected_items:
            QMessageBox.warning(self, "Внимание", "Не выбрано ни одного видео для публикации!")
            return

        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Ошибка", "Укажите GitHub Personal Access Token (PAT)!")
            return

        confirm = QMessageBox.question(
            self, "Подтверждение пакетной публикации",
            f"Вы собираетесь опубликовать {len(selected_items)} видеофонов в репозиторий {self.repo_edit.text()} (релиз {self.tag_edit.text()}).\nПродолжить?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self._set_ui_busy(True)
        self.status_lbl.setText(f"Запуск пакетной публикации ({len(selected_items)} видео)...")

        self._batch_worker = BatchPublishWorkerThread(
            items=selected_items,
            token=token,
            repo=self.repo_edit.text().strip(),
            release_tag=self.tag_edit.text().strip(),
            author=self.common_author_edit.text().strip() or self.default_user
        )
        self._batch_worker.progress_status.connect(self._on_worker_progress)
        self._batch_worker.finished.connect(self._on_batch_worker_finished)
        self._batch_worker.start()

    def _set_ui_busy(self, busy: bool):
        self.progress_bar.setVisible(busy)
        self.single_publish_btn.setEnabled(not busy)
        self.batch_publish_btn.setEnabled(not busy)
        self.tabs.setEnabled(not busy)

    def _on_worker_progress(self, msg: str):
        self.status_lbl.setText(msg)

    def _on_single_worker_finished(self, success: bool, res: dict, err: str):
        self._set_ui_busy(False)
        if success:
            self.status_lbl.setText("✓ Видеофон успешно опубликован на GitHub!")
            QMessageBox.information(
                self, "Успех публикации",
                f"Видеофон для игры '{res.get('titleId')}' успешно опубликован в GitHub Releases!\n\n"
                f"URL: {res.get('downloadUrl')}\n"
                f"Имя файла для 4IFIR: {res.get('targetCoverName')}\n"
                f"Путь на SD: {res.get('sdCardPath')}\n\n"
                f"Каталог catalog.json обновлён и доступен Switch Downloader'у!"
            )
            self.accept()
        else:
            self.status_lbl.setText("❌ Ошибка при публикации")
            QMessageBox.critical(self, "Ошибка публикации", f"Не удалось опубликовать видеофон:\n\n{err}")

    def _on_batch_worker_finished(self, success: bool, results: list, err: str):
        self._set_ui_busy(False)
        if success:
            self.status_lbl.setText(f"✓ Успешно опубликовано {len(results)} видеофонов!")
            QMessageBox.information(
                self, "Пакетная публикация завершена",
                f"Успешно опубликовано {len(results)} видеофонов на GitHub Releases!\n\n"
                f"Каталог catalog.json обновлён одной транзакцией и доступен в Homebrew-загрузчике на Switch."
            )
            self.accept()
        else:
            self.status_lbl.setText("❌ Ошибка при пакетной публикации")
            QMessageBox.critical(self, "Ошибка пакетной публикации", f"Произошла ошибка при пакетной публикации:\n\n{err}")

    def _create_manage_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        info_lbl = QLabel(
            "Список всех опубликованных видеофонов в онлайн-каталоге. "
            "Вы можете выбрать любой видеофон и удалить его из каталога и GitHub Releases.",
            widget
        )
        info_lbl.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        layout.addWidget(info_lbl)

        self.manage_table = QTableWidget(0, 6, widget)
        self.manage_table.setHorizontalHeaderLabels([
            "Title ID", "Название игры", "Вариант", "Стиль", "Размер", "Автор"
        ])
        self.manage_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.manage_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.manage_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.manage_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.manage_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.manage_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Interactive)
        self.manage_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.manage_table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.manage_table)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Обновить список из каталога", widget)
        refresh_btn.clicked.connect(self._refresh_catalog_table)
        btn_row.addWidget(refresh_btn)

        self.manage_stats_lbl = QLabel("Фоны не загружены", widget)
        self.manage_stats_lbl.setStyleSheet("color: #00E5FF;")
        btn_row.addWidget(self.manage_stats_lbl)

        btn_row.addStretch()

        self.delete_btn = QPushButton("🗑 Удалить выбранный видеофон с GitHub", widget)
        self.delete_btn.setStyleSheet("background-color: #EF4444; color: #FFFFFF; font-weight: bold; padding: 10px 20px;")
        self.delete_btn.clicked.connect(self._delete_selected_catalog_item)
        btn_row.addWidget(self.delete_btn)

        layout.addLayout(btn_row)
        return widget

    def _on_tab_changed(self, idx: int):
        if idx == 2 and not self.catalog_items:
            self._refresh_catalog_table()

    def _refresh_catalog_table(self):
        token = self.token_edit.text().strip()
        repo = self.repo_edit.text().strip()
        self.manage_stats_lbl.setText("Загрузка каталога с GitHub...")
        cat = GitHubPublisher.fetch_catalog(token, repo)

        self.catalog_items = []
        for g in cat.get("games", []):
            tid = g.get("titleId", "")
            title = g.get("title", "")
            for v in g.get("variants", []):
                self.catalog_items.append({
                    "titleId": tid,
                    "gameTitle": title,
                    "variantId": v.get("id", ""),
                    "variantName": v.get("name", ""),
                    "style": v.get("style", ""),
                    "sizeBytes": v.get("sizeBytes", 0),
                    "author": v.get("author", ""),
                    "url": v.get("url", "")
                })

        self.manage_table.setRowCount(len(self.catalog_items))
        for row, it in enumerate(self.catalog_items):
            tid_item = QTableWidgetItem(it["titleId"])
            tid_item.setFont(QFont("Consolas", 10))
            tid_item.setForeground(Qt.cyan)
            self.manage_table.setItem(row, 0, tid_item)

            self.manage_table.setItem(row, 1, QTableWidgetItem(it["gameTitle"]))
            self.manage_table.setItem(row, 2, QTableWidgetItem(f"{it['variantName']} ({it['variantId']})"))
            self.manage_table.setItem(row, 3, QTableWidgetItem(it["style"]))

            sz_mb = it["sizeBytes"] / (1024 * 1024)
            self.manage_table.setItem(row, 4, QTableWidgetItem(f"{sz_mb:.2f} MB"))
            self.manage_table.setItem(row, 5, QTableWidgetItem(it["author"]))

        self.manage_stats_lbl.setText(f"Всего в каталоге: {len(self.catalog_items)} видеофонов")
        if self.catalog_items:
            self.manage_table.selectRow(0)

    def _delete_selected_catalog_item(self):
        sel = self.manage_table.selectedIndexes()
        if not sel:
            QMessageBox.warning(self, "Внимание", "Выберите видеофон из таблицы для удаления!")
            return

        row = sel[0].row()
        if not (0 <= row < len(self.catalog_items)):
            return

        it = self.catalog_items[row]
        tid = it["titleId"]
        vid = it["variantId"]
        vname = it["variantName"]
        gtitle = it["gameTitle"]

        confirm = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы действительно хотите удалить видеофон '{vname}' для игры '{gtitle}' ({tid})?\n\n"
            f"• Видеофайл будет удалён из GitHub Releases.\n"
            f"• Запись будет удалена из онлайн-каталога catalog.json.\n\n"
            f"Это действие необратимо!",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Ошибка", "Не указан токен GitHub для выполнения операции!")
            return

        self._set_ui_busy(True)
        self.status_lbl.setText(f"Удаление фона '{vname}'...")

        self._delete_worker = DeleteWorkerThread(
            title_id=tid,
            variant_id=vid,
            token=token,
            repo=self.repo_edit.text().strip(),
            release_tag=self.tag_edit.text().strip()
        )
        self._delete_worker.progress_status.connect(self._on_worker_progress)
        self._delete_worker.finished.connect(self._on_delete_worker_finished)
        self._delete_worker.start()

    def _on_delete_worker_finished(self, success: bool, err: str):
        self._set_ui_busy(False)
        if success:
            self.status_lbl.setText("✓ Видеофон успешно удалён!")
            QMessageBox.information(
                self, "Успех",
                "Видеофон успешно удалён из GitHub Releases и онлайн-каталога!"
            )
            self._refresh_catalog_table()
        else:
            self.status_lbl.setText("❌ Ошибка при удалении")
            QMessageBox.critical(self, "Ошибка удаления", f"Не удалось удалить видеофон:\n\n{err}")

    def _create_gdrive_tab(self, video_path: Optional[str], title_id: str, game_title: str, style: str) -> QWidget:
        widget = QWidget()
        scroll_layout = QVBoxLayout(widget)
        scroll_layout.setContentsMargins(12, 12, 12, 12)
        scroll_layout.setSpacing(10)

        # Informational banner
        banner = QLabel(
            "📁 <b>Хранение видеофонов на Google Диске (до 5 ТБ)</b><br>"
            "<span style='color: #A0AEC0; font-size: 11px;'>"
            "Загрузите видео на ваш Google Диск и скопируйте ссылку «Поделиться». "
            "Студия автоматически сформирует прямую ссылку прямого скачивания для Switch без лимитов GitHub."
            "</span>",
            widget
        )
        banner.setStyleSheet("background-color: #1A2332; border: 1px solid #00E5FF; border-radius: 6px; padding: 10px;")
        scroll_layout.addWidget(banner)

        # Sub-sections in Tab
        sub_tabs = QTabWidget(widget)

        # Sub-tab 1: Single file link
        single_gdrive = QWidget()
        s_layout = QVBoxLayout(single_gdrive)
        s_layout.setSpacing(8)

        # Video file selector
        v_box = QHBoxLayout()
        self.gdrive_video_edit = QLineEdit(video_path or "", single_gdrive)
        self.gdrive_video_edit.setPlaceholderText("Путь к локальному .mp4 файлу (для расчёта SHA-256 и проверки 4IFIR)")
        v_browse = QPushButton("Обзор...", single_gdrive)
        v_browse.clicked.connect(self._browse_gdrive_video)
        v_box.addWidget(self.gdrive_video_edit)
        v_box.addWidget(v_browse)
        s_layout.addLayout(v_box)

        # Title ID and Game Title
        tid_row = QHBoxLayout()
        self.gdrive_tid_edit = QLineEdit(title_id or "", single_gdrive)
        self.gdrive_tid_edit.setPlaceholderText("Title ID (например, 01005CA01580E000)")
        self.gdrive_tid_edit.textChanged.connect(self._on_gdrive_tid_changed)
        tid_row.addWidget(QLabel("Title ID:", single_gdrive))
        tid_row.addWidget(self.gdrive_tid_edit)

        self.gdrive_title_edit = QLineEdit(game_title or "", single_gdrive)
        self.gdrive_title_edit.setPlaceholderText("Название игры")
        tid_row.addWidget(QLabel("Игра:", single_gdrive))
        tid_row.addWidget(self.gdrive_title_edit)
        s_layout.addLayout(tid_row)

        # Variant & Style
        var_row = QHBoxLayout()
        self.gdrive_var_edit = QLineEdit("Standard", single_gdrive)
        self.gdrive_var_edit.setPlaceholderText("Название варианта (например, Standard, 60fps, Loop)")
        var_row.addWidget(QLabel("Вариант:", single_gdrive))
        var_row.addWidget(self.gdrive_var_edit)

        self.gdrive_style_combo = QComboBox(single_gdrive)
        for st in ["Animated Art", "Cinematic", "Gameplay", "Minimal", "Dark", "Retro", "Music"]:
            self.gdrive_style_combo.addItem(st)
        var_row.addWidget(QLabel("Стиль:", single_gdrive))
        var_row.addWidget(self.gdrive_style_combo)
        s_layout.addLayout(var_row)

        # Google Drive Link input
        s_layout.addWidget(QLabel("<b>Ссылка на файл Google Диска:</b>", single_gdrive))
        self.gdrive_url_edit = QLineEdit(single_gdrive)
        self.gdrive_url_edit.setPlaceholderText("Вставьте ссылку на файл: https://drive.google.com/file/d/.../view?usp=sharing")
        self.gdrive_url_edit.textChanged.connect(self._on_gdrive_url_changed)
        s_layout.addWidget(self.gdrive_url_edit)

        self.gdrive_preview_lbl = QLabel("Прямая ссылка для консоли: (ожидание ввода ссылки)", single_gdrive)
        self.gdrive_preview_lbl.setStyleSheet("color: #10B981; font-size: 11px;")
        s_layout.addWidget(self.gdrive_preview_lbl)

        # Save button
        gdrive_save_btn = QPushButton("⚡ Сохранить в catalog.json", single_gdrive)
        gdrive_save_btn.setStyleSheet("background-color: #00E5FF; color: #000000; font-weight: bold; padding: 10px;")
        gdrive_save_btn.clicked.connect(self._save_single_gdrive_entry)
        s_layout.addWidget(gdrive_save_btn)
        s_layout.addStretch()

        sub_tabs.addTab(single_gdrive, "🔗 Одиночная ссылка")

        # Sub-tab 2: Batch Links Importer
        batch_gdrive = QWidget()
        b_layout = QVBoxLayout(batch_gdrive)
        b_layout.setSpacing(8)

        b_layout.addWidget(QLabel(
            "Вставьте список ссылок (формат: <code>01005CA01580E000 https://drive.google.com/file/d/...</code>):",
            batch_gdrive
        ))
        self.gdrive_batch_text = QTextEdit(batch_gdrive)
        self.gdrive_batch_text.setPlaceholderText(
            "01005CA01580E000 https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs/view\n"
            "0100000000010000 https://drive.google.com/open?id=2CyjNWt1YSB6oGNeLwCeCakhVVrqumct\n"
        )
        b_layout.addWidget(self.gdrive_batch_text)

        batch_btn = QPushButton("📦 Импортировать список ссылок в catalog.json", batch_gdrive)
        batch_btn.setStyleSheet("background-color: #3B82F6; color: #FFFFFF; font-weight: bold; padding: 10px;")
        batch_btn.clicked.connect(self._import_batch_gdrive_links)
        b_layout.addWidget(batch_btn)

        sub_tabs.addTab(batch_gdrive, "📋 Пакетный импорт ссылок")

        scroll_layout.addWidget(sub_tabs)

        # Sync catalog to GitHub button
        sync_box = QGroupBox("Синхронизация каталога с сервером", widget)
        sync_layout = QHBoxLayout(sync_box)
        sync_desc = QLabel("После добавления видео нажмите кнопку, чтобы Switch получил обновлённый список:", sync_box)
        sync_desc.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        sync_layout.addWidget(sync_desc)

        sync_btn = QPushButton("☁ Отправить catalog.json на GitHub", sync_box)
        sync_btn.setStyleSheet("background-color: #10B981; color: #FFFFFF; font-weight: bold; padding: 9px 16px;")
        sync_btn.clicked.connect(self._sync_catalog_to_github)
        sync_layout.addWidget(sync_btn)

        scroll_layout.addWidget(sync_box)
        return widget

    def _browse_gdrive_video(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Выберите видеофайл MP4", "", "Видео MP4 (*.mp4)")
        if fpath:
            self.gdrive_video_edit.setText(fpath)
            name = Path(fpath).stem
            tid_m = re.search(r"0100[0-9A-Fa-f]{12}", name)
            if tid_m and not self.gdrive_tid_edit.text().strip():
                self.gdrive_tid_edit.setText(tid_m.group(0).upper())

    def _on_gdrive_tid_changed(self, text: str):
        cleaned = text.strip().upper()
        if re.match(r"^0100[0-9A-Fa-f]{12}$", cleaned):
            title = OnlineFetcher.get_title_by_id(cleaned)
            if title and (not self.gdrive_title_edit.text().strip() or self.gdrive_title_edit.text().startswith("Game 0100")):
                self.gdrive_title_edit.setText(title)

    def _on_gdrive_url_changed(self, text: str):
        fid = GoogleDriveHelper.extract_file_id(text)
        if fid:
            direct_url = GoogleDriveHelper.to_direct_download_url(fid)
            self.gdrive_preview_lbl.setText(f"✓ ID: {fid} | Прямая ссылка: {direct_url}")
            self.gdrive_preview_lbl.setStyleSheet("color: #10B981; font-size: 11px;")
        else:
            if text.strip():
                self.gdrive_preview_lbl.setText("⚠ Не удалось распознать ссылку Google Диска")
                self.gdrive_preview_lbl.setStyleSheet("color: #EF4444; font-size: 11px;")
            else:
                self.gdrive_preview_lbl.setText("Прямая ссылка для консоли: (ожидание ввода ссылки)")
                self.gdrive_preview_lbl.setStyleSheet("color: #A0AEC0; font-size: 11px;")

    def _save_single_gdrive_entry(self):
        vpath_str = self.gdrive_video_edit.text().strip()
        tid = self.gdrive_tid_edit.text().strip().upper()
        url = self.gdrive_url_edit.text().strip()
        title = self.gdrive_title_edit.text().strip()
        vname = self.gdrive_var_edit.text().strip() or "Standard"
        style = self.gdrive_style_combo.currentText()
        author = self.common_author_edit.text().strip() or "Anonymous"

        if not vpath_str or not Path(vpath_str).exists():
            QMessageBox.warning(self, "Внимание", "Укажите существующий локальный .mp4 файл для расчёта SHA-256 и параметров видео!")
            return

        if not re.match(r"^0100[0-9A-Fa-f]{12}$", tid):
            QMessageBox.warning(self, "Внимание", "Введите корректный Title ID (16 hex-символов, начиная с 0100)!")
            return

        if not GoogleDriveHelper.extract_file_id(url):
            QMessageBox.warning(self, "Внимание", "Укажите корректную ссылку на файл Google Диска!")
            return

        catalog_path = Path("catalog/data/catalog.json")
        try:
            res = GoogleDriveHelper.register_drive_video(
                catalog_path=catalog_path,
                video_path=Path(vpath_str),
                drive_url_or_id=url,
                title_id=tid,
                game_title=title,
                variant_name=vname,
                style=style,
                author=author
            )
            QMessageBox.information(
                self,
                "Успех",
                f"Видеофон для {title or tid} успешно сохранён в catalog.json!\n\n"
                f"Прямой URL: {res['directUrl']}\n"
                f"SHA-256: {res['sha256'][:16]}...\n\n"
                f"Не забудьте нажать кнопку 'Отправить catalog.json на GitHub', чтобы обновить базу на сервере."
            )
            self._refresh_catalog_table()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось зарегистрировать видеофон:\n{e}")

    def _import_batch_gdrive_links(self):
        text = self.gdrive_batch_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Внимание", "Вставьте список ссылок Google Диска!")
            return

        items = GoogleDriveHelper.parse_batch_links(text)
        if not items:
            QMessageBox.warning(self, "Внимание", "Не найдено ни одной корректной ссылки Google Диска!")
            return

        catalog_path = Path("catalog/data/catalog.json")
        cat_data = {"schemaVersion": 1, "updatedAt": "", "games": []}
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as cf:
                    cat_data = json.load(cf)
            except Exception:
                pass

        added_count = 0
        for it in items:
            tid = it["titleId"]
            if not tid:
                continue
            game_title = OnlineFetcher.get_title_by_id(tid) or f"Game {tid}"

            # Check if game exists
            game_entry = None
            for g in cat_data.get("games", []):
                if g.get("titleId", "").upper() == tid:
                    game_entry = g
                    break

            if not game_entry:
                game_entry = {
                    "titleId": tid,
                    "title": game_title,
                    "publisher": "Unknown",
                    "variants": []
                }
                cat_data.setdefault("games", []).append(game_entry)

            new_var = {
                "id": "gdrive-standard",
                "name": "Standard (Google Drive)",
                "style": "Animated Art",
                "version": "1.0",
                "url": it["directUrl"],
                "previewUrl": it["previewUrl"],
                "sizeBytes": 15000000,
                "sha256": "",
                "durationSec": 20.0,
                "author": self.common_author_edit.text().strip() or "GoogleDrive",
                "codec": "h264",
                "width": 1280,
                "height": 720,
                "fps": 30.0,
                "notes": "Google Drive Cloud Host"
            }

            existing_idx = -1
            for v_idx, v in enumerate(game_entry.get("variants", [])):
                if v.get("id") == "gdrive-standard":
                    existing_idx = v_idx
                    break
            if existing_idx >= 0:
                game_entry["variants"][existing_idx] = new_var
            else:
                game_entry["variants"].append(new_var)
            added_count += 1

        cat_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        cat_data["totalGames"] = len(cat_data["games"])
        cat_data["totalVariants"] = sum(len(g.get("variants", [])) for g in cat_data["games"])

        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(catalog_path, "w", encoding="utf-8") as cf:
            json.dump(cat_data, cf, ensure_ascii=False, indent=2)

        QMessageBox.information(
            self,
            "Импорт завершён",
            f"Успешно обработано и добавлено {added_count} видеофонов в catalog.json!"
        )
        self._refresh_catalog_table()

    def _sync_catalog_to_github(self):
        token = self.token_edit.text().strip()
        repo = self.repo_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Внимание", "Укажите GitHub Token внизу окна для отправки на GitHub!")
            return

        catalog_path = Path("catalog/data/catalog.json")
        try:
            GoogleDriveHelper.sync_catalog_to_github(
                catalog_path=catalog_path,
                token=token,
                repo=repo,
                progress_cb=self.status_lbl.setText
            )
            QMessageBox.information(self, "Успех", "Обновлённый catalog.json успешно опубликован на GitHub!")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось отправить каталог на GitHub:\n{e}")

