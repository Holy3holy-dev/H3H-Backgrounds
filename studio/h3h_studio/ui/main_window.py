import re
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QThread
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QFileDialog, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QProgressBar, QTextEdit,
    QMessageBox, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QInputDialog, QFrame, QSystemTrayIcon
)

from ..core.analyzer import VideoAnalyzer, VideoAnalysis
from ..core.encoder import Encoder, PROFILES, EncodingProfile
from ..core.ken_burns import KenBurnsGenerator
from ..core.pipeline import FFmpegPipeline
from ..core.project import StudioProject
from ..core.online_fetcher import OnlineFetcher
from ..core.github_publisher import GitHubPublisher
from .ffmpeg_log_dialog import FFmpegLogDialog
from .online_search_dialog import OnlineSearchDialog
from .github_publish_dialog import GitHubPublishDialog

TITLE_ID_PATTERN = re.compile(r"^[0-9A-Fa-f]{16}$")


class ProposalNotificationWorker(QThread):
    proposals_found = Signal(list)

    def __init__(self, token: Optional[str] = None, repo: str = GitHubPublisher.DEFAULT_REPO):
        super().__init__()
        self.token = token
        self.repo = repo

    def run(self):
        try:
            proposals = GitHubPublisher.fetch_catalog_proposals(self.token, self.repo)
            self.proposals_found.emit(proposals)
        except Exception:
            self.proposals_found.emit([])


class WorkerSignals(QObject):
    progress = Signal(float)
    log_line = Signal(str)
    finished = Signal(bool, str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("H3H Background Studio — Подготовка видеофонов для 4IFIR")
        self.resize(1100, 780)
        self.setMinimumSize(900, 680)

        self.pipeline = FFmpegPipeline()
        self.worker_thread: Optional[threading.Thread] = None
        self.signals = WorkerSignals()
        self.signals.progress.connect(self._on_progress)
        self.signals.finished.connect(self._on_finished)

        self.current_analysis: Optional[VideoAnalysis] = None
        self.current_project = StudioProject()

        self._proposal_worker: Optional[ProposalNotificationWorker] = None
        self._proposals_timer = QTimer(self)
        self._proposals_timer.setInterval(120000)  # check every 2 minutes
        self._proposals_timer.timeout.connect(self._check_proposals)
        self._proposals_timer.start()

        self._apply_theme()
        self._init_ui()

        # Initial background check after 2 seconds
        QTimer.singleShot(2000, self._check_proposals)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121418;
                color: #FFFFFF;
            }
            QWidget {
                background-color: #121418;
                color: #FFFFFF;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #2D3540;
                background-color: #1B1F26;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #1B1F26;
                color: #9AA4B2;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: #252B35;
                color: #00E5FF;
                border-bottom: 2px solid #00E5FF;
            }
            QGroupBox {
                border: 1px solid #2D3540;
                border-radius: 8px;
                margin-top: 16px;
                padding: 16px;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #00E5FF;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #1B1F26;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #00E5FF;
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
                border-color: #3E4856;
            }
            QPushButton#primaryBtn {
                background-color: #3B82F6;
                border: none;
            }
            QPushButton#primaryBtn:hover {
                background-color: #2563EB;
            }
            QProgressBar {
                border: 1px solid #2D3540;
                border-radius: 6px;
                text-align: center;
                background-color: #1B1F26;
                color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #00E5FF;
                border-radius: 5px;
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
                padding: 6px;
                border: 1px solid #2D3540;
                font-weight: bold;
            }
        """)

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("H3H Background Studio", self)
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))

        cfw_badge = QLabel("4IFIR Compliant Engine", self)
        cfw_badge.setStyleSheet("color: #00E5FF; border: 1px solid #00E5FF; border-radius: 4px; padding: 2px 8px; font-weight: bold;")

        header_layout.addWidget(title_label)
        header_layout.addWidget(cfw_badge)
        header_layout.addStretch()

        online_search_btn = QPushButton("🌐 Найти игру в интернете", self)
        online_search_btn.setStyleSheet("background-color: #00E5FF; color: #121418; font-weight: bold; padding: 6px 14px; border: none; border-radius: 4px;")
        online_search_btn.clicked.connect(self._open_online_search)
        header_layout.addWidget(online_search_btn)

        gdrive_publish_btn = QPushButton("📁 Google Диск", self)
        gdrive_publish_btn.setStyleSheet("background-color: #10B981; color: #FFFFFF; font-weight: bold; padding: 6px 14px; border: none; border-radius: 4px;")
        gdrive_publish_btn.clicked.connect(lambda: self._open_github_publish(initial_tab=3))
        header_layout.addWidget(gdrive_publish_btn)

        github_publish_btn = QPushButton("🚀 Опубликовать на GitHub", self)
        github_publish_btn.setStyleSheet("background-color: #3B82F6; color: #FFFFFF; font-weight: bold; padding: 6px 14px; border: none; border-radius: 4px;")
        github_publish_btn.clicked.connect(self._open_github_publish)
        header_layout.addWidget(github_publish_btn)

        log_btn = QPushButton("Журнал FFmpeg", self)
        log_btn.clicked.connect(self._show_ffmpeg_logs)
        header_layout.addWidget(log_btn)

        main_layout.addLayout(header_layout)

        # Proposals Notification Banner
        self.proposals_banner = QFrame(self)
        self.proposals_banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E293B, stop:1 #0F172A);
                border: 1px solid #00E5FF;
                border-radius: 6px;
                padding: 4px 10px;
            }
        """)
        banner_layout = QHBoxLayout(self.proposals_banner)
        banner_layout.setContentsMargins(10, 6, 10, 6)
        banner_layout.setSpacing(12)

        self.proposals_banner_lbl = QLabel("🔔 <b>Новые заявки от авторов сообщества:</b> Ожидают вашего подтверждения!", self.proposals_banner)
        self.proposals_banner_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px;")
        banner_layout.addWidget(self.proposals_banner_lbl, 1)

        self.proposals_approve_btn = QPushButton("⚡ Одобрить в 1 клик", self.proposals_banner)
        self.proposals_approve_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.proposals_approve_btn.clicked.connect(self._open_proposals_moderation)
        banner_layout.addWidget(self.proposals_approve_btn)

        dismiss_btn = QPushButton("✕", self.proposals_banner)
        dismiss_btn.setStyleSheet("background: transparent; color: #94A3B8; font-size: 14px; font-weight: bold; border: none; padding: 4px 8px;")
        dismiss_btn.clicked.connect(lambda: self.proposals_banner.setVisible(False))
        banner_layout.addWidget(dismiss_btn)

        self.proposals_banner.setVisible(False)
        main_layout.addWidget(self.proposals_banner)

        # Modes Tab Widget
        self.tabs = QTabWidget(self)
        self.tab_artwork = self._create_artwork_tab()
        self.tab_gameplay = self._create_gameplay_tab()
        self.tab_custom = self._create_custom_tab()

        self.tabs.addTab(self.tab_artwork, "Режим A: Animated Artwork (Изображение)")
        self.tabs.addTab(self.tab_gameplay, "Режим B: Gameplay & Trailer (Видеофрагмент)")
        self.tabs.addTab(self.tab_custom, "Режим C: Custom Video & Transcode (Анализ MP4)")
        main_layout.addWidget(self.tabs, stretch=2)

        # Export & Catalog Metadata Section
        export_group = self._create_export_section()
        main_layout.addWidget(export_group, stretch=1)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(24)
        main_layout.addWidget(self.progress_bar)

        # Status footer
        self.status_label = QLabel("Готов к работе. Выберите файл для подготовки видеофона.", self)
        self.status_label.setStyleSheet("color: #9AA4B2; font-size: 13px;")
        main_layout.addWidget(self.status_label)

    def _create_artwork_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # File picker
        file_layout = QHBoxLayout()
        self.art_file_edit = QLineEdit(widget)
        self.art_file_edit.setPlaceholderText("Выберите изображение игры (.png, .jpg, .webp)...")
        browse_btn = QPushButton("Обзор...", widget)
        browse_btn.clicked.connect(self._browse_artwork)
        file_layout.addWidget(self.art_file_edit)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Animation Settings
        form_layout = QHBoxLayout()

        # Effect selector
        effect_layout = QVBoxLayout()
        effect_layout.addWidget(QLabel("Тип циклического движения (Ken Burns):", widget))
        self.art_effect_combo = QComboBox(widget)
        self.art_effect_combo.addItem("Плавное циклическое приближение (Sine Zoom)", "sine_zoom")
        self.art_effect_combo.addItem("Горизонтальный дрейф камеры (Horizontal Drift)", "horizontal_drift")
        self.art_effect_combo.addItem("Диагональное парение (Diagonal Float)", "diagonal_float")
        effect_layout.addWidget(self.art_effect_combo)
        form_layout.addLayout(effect_layout)

        # Duration
        dur_layout = QVBoxLayout()
        dur_layout.addWidget(QLabel("Продолжительность цикла (сек):", widget))
        self.art_dur_spin = QDoubleSpinBox(widget)
        self.art_dur_spin.setRange(5.0, 60.0)
        self.art_dur_spin.setValue(15.0)
        self.art_dur_spin.setSingleStep(1.0)
        dur_layout.addWidget(self.art_dur_spin)
        form_layout.addLayout(dur_layout)

        # Vignette toggle
        vignette_layout = QVBoxLayout()
        vignette_layout.addWidget(QLabel("Эффекты освещения:", widget))
        self.art_vignette_check = QCheckBox("Мягкое виньетирование (Vignette)", widget)
        self.art_vignette_check.setChecked(True)
        vignette_layout.addWidget(self.art_vignette_check)
        form_layout.addLayout(vignette_layout)

        layout.addLayout(form_layout)

        # Artwork Preview
        self.art_preview_lbl = QLabel(widget)
        self.art_preview_lbl.setAlignment(Qt.AlignCenter)
        self.art_preview_lbl.setFixedHeight(150)
        self.art_preview_lbl.setStyleSheet("background-color: #121418; border: 1px dashed #2A303C; border-radius: 6px; color: #718096; font-size: 12px;")
        self.art_preview_lbl.setText("Превью выбранного арта появится здесь")
        self.art_file_edit.textChanged.connect(self._update_art_preview)
        layout.addWidget(self.art_preview_lbl)

        info_lbl = QLabel(
            "★ Математическое циклическое сглаживание: начальный и конечный кадры совпадают с точностью до пикселя, "
            "обеспечивая бесшовное бесконечное воспроизведение в меню 4IFIR.",
            widget
        )
        info_lbl.setStyleSheet("color: #10B981; font-size: 12px;")
        layout.addWidget(info_lbl)
        layout.addStretch()
        return widget

    def _create_gameplay_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Video picker
        file_layout = QHBoxLayout()
        self.gameplay_file_edit = QLineEdit(widget)
        self.gameplay_file_edit.setPlaceholderText("Выберите исходный видеофайл (.mp4, .mkv, .mov)...")
        browse_btn = QPushButton("Обзор...", widget)
        browse_btn.clicked.connect(self._browse_gameplay)
        online_dl_btn = QPushButton("🎬 Скачать видео по URL...", widget)
        online_dl_btn.setStyleSheet("background-color: #3B82F6; color: #FFFFFF;")
        online_dl_btn.clicked.connect(self._download_online_video)
        file_layout.addWidget(self.gameplay_file_edit)
        file_layout.addWidget(browse_btn)
        file_layout.addWidget(online_dl_btn)
        layout.addLayout(file_layout)

        # Trim and loop settings
        grid_layout = QHBoxLayout()

        # Start Time
        start_layout = QVBoxLayout()
        start_layout.addWidget(QLabel("Начало фрагмента (сек):", widget))
        self.gp_start_spin = QDoubleSpinBox(widget)
        self.gp_start_spin.setRange(0.0, 3600.0)
        self.gp_start_spin.setValue(0.0)
        start_layout.addWidget(self.gp_start_spin)
        grid_layout.addLayout(start_layout)

        # Duration
        dur_layout = QVBoxLayout()
        dur_layout.addWidget(QLabel("Длительность фрагмента (сек):", widget))
        self.gp_dur_spin = QDoubleSpinBox(widget)
        self.gp_dur_spin.setRange(3.0, 120.0)
        self.gp_dur_spin.setValue(18.0)
        dur_layout.addWidget(self.gp_dur_spin)
        grid_layout.addLayout(dur_layout)

        # Loop Crossfade
        fade_layout = QVBoxLayout()
        fade_layout.addWidget(QLabel("Бесшовный переход петли (сек):", widget))
        self.gp_fade_spin = QDoubleSpinBox(widget)
        self.gp_fade_spin.setRange(0.0, 3.0)
        self.gp_fade_spin.setValue(1.5)
        self.gp_fade_spin.setSingleStep(0.25)
        fade_layout.addWidget(self.gp_fade_spin)
        grid_layout.addLayout(fade_layout)

        layout.addLayout(grid_layout)

        # Audio settings
        self.gp_mute_check = QCheckBox("Отключить звук (рекомендуется для фонового видео меню)", widget)
        self.gp_mute_check.setChecked(True)
        layout.addWidget(self.gp_mute_check)

        layout.addStretch()
        return widget

    def _create_custom_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        file_layout = QHBoxLayout()
        self.custom_file_edit = QLineEdit(widget)
        self.custom_file_edit.setPlaceholderText("Выберите существующее MP4 видео для анализа...")
        browse_btn = QPushButton("Обзор и FFprobe...", widget)
        browse_btn.clicked.connect(self._browse_custom)
        file_layout.addWidget(self.custom_file_edit)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Diagnostic Table
        self.diag_table = QTableWidget(6, 3, widget)
        self.diag_table.setHorizontalHeaderLabels(["Параметр", "Фактическое значение", "Требование 4IFIR"])
        self.diag_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.diag_table.setFixedHeight(180)
        layout.addWidget(self.diag_table)

        self.compliance_status_label = QLabel("Статус совместимости: Выберите файл для проверки", widget)
        self.compliance_status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.compliance_status_label)

        return widget

    def _create_export_section(self) -> QGroupBox:
        box = QGroupBox("Параметры видеофона и экспорт в 4IFIR", self)
        layout = QVBoxLayout(box)

        row1 = QHBoxLayout()

        # Title ID with live validation
        tid_vbox = QVBoxLayout()
        tid_header = QHBoxLayout()
        tid_header.addWidget(QLabel("Title ID игры (16 hex):", box))
        self.tid_badge = QLabel("Ожидание", box)
        self.tid_badge.setStyleSheet("font-size: 11px; font-weight: bold; color: #9AA4B2;")
        tid_header.addWidget(self.tid_badge)
        tid_header.addStretch()
        tid_vbox.addLayout(tid_header)

        self.tid_input = QLineEdit(box)
        self.tid_input.setPlaceholderText("01005CA01580E000")
        self.tid_input.setFont(QFont("JetBrains Mono, Consolas", 11))
        self.tid_input.textChanged.connect(self._validate_title_id)
        tid_vbox.addWidget(self.tid_input)
        row1.addLayout(tid_vbox)

        # Game Title
        title_vbox = QVBoxLayout()
        title_vbox.addWidget(QLabel("Название игры:", box))
        self.game_title_input = QLineEdit(box)
        self.game_title_input.setPlaceholderText("Teenage Mutant Ninja Turtles: Shredder's Revenge")
        title_vbox.addWidget(self.game_title_input)
        row1.addLayout(title_vbox)

        layout.addLayout(row1)

        row2 = QHBoxLayout()

        # Variant Name
        vname_vbox = QVBoxLayout()
        vname_vbox.addWidget(QLabel("Название варианта:", box))
        self.vname_input = QLineEdit(box)
        self.vname_input.setText("Opening Intro Loop")
        vname_vbox.addWidget(self.vname_input)
        row2.addLayout(vname_vbox)

        # Style
        style_vbox = QVBoxLayout()
        style_vbox.addWidget(QLabel("Категория (стиль):", box))
        self.style_combo = QComboBox(box)
        for s in ["Cinematic", "Gameplay", "Animated Art", "Minimal", "Dark", "Retro", "Music"]:
            self.style_combo.addItem(s)
        style_vbox.addWidget(self.style_combo)
        row2.addLayout(style_vbox)

        # Encoding Profile
        prof_vbox = QVBoxLayout()
        prof_vbox.addWidget(QLabel("Профиль кодирования:", box))
        self.prof_combo = QComboBox(box)
        for key, p in PROFILES.items():
            self.prof_combo.addItem(p.name, key)
        prof_vbox.addWidget(self.prof_combo)
        row2.addLayout(prof_vbox)

        layout.addLayout(row2)

        # Export row
        export_row = QHBoxLayout()
        export_row.addStretch()

        self.publish_btn = QPushButton("🚀 Опубликовать на GitHub", box)
        self.publish_btn.setStyleSheet("background-color: #3B82F6; color: #FFFFFF; font-weight: bold; padding: 10px 18px; border-radius: 6px; font-size: 13px;")
        self.publish_btn.setFixedHeight(40)
        self.publish_btn.clicked.connect(self._open_github_publish)
        export_row.addWidget(self.publish_btn)

        self.export_btn = QPushButton("Экспортировать видеофон (<TITLEID>.mp4)", box)
        self.export_btn.setObjectName("primaryBtn")
        self.export_btn.setFixedHeight(40)
        self.export_btn.clicked.connect(self._start_export)
        export_row.addWidget(self.export_btn)

        layout.addLayout(export_row)
        return box

    def _browse_artwork(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if file:
            self.art_file_edit.setText(file)
            self.style_combo.setCurrentText("Animated Art")

    def _browse_gameplay(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Выберите видеофайл", "", "Videos (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if file:
            self.gameplay_file_edit.setText(file)
            self.style_combo.setCurrentText("Gameplay")

    def _browse_custom(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Выберите видео для анализа", "", "Videos (*.mp4 *.mkv *.mov *.avi *.webm)"
        )
        if file:
            self.custom_file_edit.setText(file)
            self._analyze_file(Path(file))

    def _analyze_file(self, file_path: Path):
        self.current_analysis = VideoAnalyzer.analyze_file(file_path)
        a = self.current_analysis

        rows = [
            ("Видеокодек", a.codec.upper(), "H.264 (AVC)"),
            ("Профиль / Уровень", f"{a.profile} L{a.level}", "High Profile 4.1"),
            ("Разрешение", f"{a.width}x{a.height}", "1280x720 (макс 1080p)"),
            ("Формат пикселей", a.pixel_format, "yuv420p (8-bit)"),
            ("Частота кадров", f"{a.fps} fps", "30.0 или 60.0 fps"),
            ("Заголовок faststart (moov)", "Да" if a.is_faststart else "Нет", "Требуется (+faststart)")
        ]

        for idx, (param, val, req) in enumerate(rows):
            self.diag_table.setItem(idx, 0, QTableWidgetItem(param))
            item_val = QTableWidgetItem(val)
            self.diag_table.setItem(idx, 1, item_val)
            self.diag_table.setItem(idx, 2, QTableWidgetItem(req))

        if a.is_compliant:
            self.compliance_status_label.setText("✓ Файл полностью совместим с аппаратным декодером 4IFIR!")
            self.compliance_status_label.setStyleSheet("color: #10B981; font-size: 14px; font-weight: bold;")
        else:
            issue_text = " • ".join(a.issues)
            self.compliance_status_label.setText(f"⚠ Требуется перекодирование: {issue_text}")
            self.compliance_status_label.setStyleSheet("color: #F59E0B; font-size: 13px; font-weight: bold;")

    def _validate_title_id(self, text: str):
        cleaned = text.strip().upper()
        if TITLE_ID_PATTERN.match(cleaned):
            self.tid_badge.setText("✓ Корректный Title ID")
            self.tid_badge.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        elif len(cleaned) == 0:
            self.tid_badge.setText("Ожидание ввода")
            self.tid_badge.setStyleSheet("color: #9AA4B2; font-size: 11px;")
        else:
            self.tid_badge.setText("✗ Ошибка (16 hex-символов)")
            self.tid_badge.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px;")

    def _start_export(self):
        title_id = self.tid_input.text().strip().upper()
        if not TITLE_ID_PATTERN.match(title_id):
            QMessageBox.critical(self, "Ошибка", "Укажите корректный 16-значный Title ID (например: 01005CA01580E000)!")
            return

        game_title = self.game_title_input.text().strip() or "Untitled Game"
        variant_name = self.vname_input.text().strip() or "Standard Loop"
        style = self.style_combo.currentText()
        profile_key = self.prof_combo.currentData()
        profile = PROFILES.get(profile_key, PROFILES["720p_30fps"])

        output_dir = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения (<TITLEID>.mp4)")
        if not output_dir:
            return

        output_path = Path(output_dir) / f"{title_id}.mp4"
        tab_idx = self.tabs.currentIndex()

        cmd = []
        total_dur = 15.0

        if tab_idx == 0:  # Mode A: Artwork
            inp = self.art_file_edit.text().strip()
            if not inp or not Path(inp).exists():
                QMessageBox.critical(self, "Ошибка", "Выберите существующее изображение!")
                return
            dur = self.art_dur_spin.value()
            effect = self.art_effect_combo.currentData()
            vignette = self.art_vignette_check.isChecked()
            cmd = KenBurnsGenerator.build_artwork_command(
                Path(inp), output_path, duration_sec=dur, effect_type=effect,
                profile=profile, add_vignette=vignette
            )
            total_dur = dur

        elif tab_idx == 1:  # Mode B: Gameplay
            inp = self.gameplay_file_edit.text().strip()
            if not inp or not Path(inp).exists():
                QMessageBox.critical(self, "Ошибка", "Выберите видеофайл!")
                return
            start = self.gp_start_spin.value()
            dur = self.gp_dur_spin.value()
            fade = self.gp_fade_spin.value()
            mute = self.gp_mute_check.isChecked()
            cmd = Encoder.build_transcode_command(
                Path(inp), output_path, profile=profile, mute_audio=mute,
                start_sec=start, duration_sec=dur, loop_crossfade_sec=fade
            )
            total_dur = dur

        else:  # Mode C: Custom
            inp = self.custom_file_edit.text().strip()
            if not inp or not Path(inp).exists():
                QMessageBox.critical(self, "Ошибка", "Выберите видеофайл!")
                return
            dur = self.current_analysis.duration_sec if self.current_analysis else 15.0
            cmd = Encoder.build_transcode_command(
                Path(inp), output_path, profile=profile, mute_audio=True
            )
            total_dur = dur

        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Кодирование {output_path.name} по профилю 4IFIR...")

        def run_thread():
            ok = self.pipeline.run(cmd, total_dur, on_progress=self.signals.progress.emit)
            if ok:
                # Generate catalog snippet
                metadata = Encoder.generate_catalog_entry(
                    title_id=title_id,
                    game_title=game_title,
                    variant_name=variant_name,
                    variant_id=variant_name.lower().replace(" ", "-"),
                    style=style,
                    author="Studio_User",
                    output_file=output_path,
                    profile=profile,
                    duration_sec=total_dur,
                    has_audio=False
                )
                meta_path = Path(output_dir) / f"{title_id}_catalog_entry.json"
                with open(meta_path, "w", encoding="utf-8") as f:
                    import json
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                self.signals.finished.emit(True, str(output_path))
            else:
                self.signals.finished.emit(False, "FFmpeg вернул ошибку при кодировании.")

        self.worker_thread = threading.Thread(target=run_thread, daemon=True)
        self.worker_thread.start()

    def _on_progress(self, val: float):
        self.progress_bar.setValue(int(val * 100))

    def _on_finished(self, success: bool, msg: str):
        self.export_btn.setEnabled(True)
        if success:
            self.last_exported_video = Path(msg)
            self.status_label.setText(f"✓ Успешно экспортировано: {msg}")

            box = QMessageBox(self)
            box.setWindowTitle("Видеофон готов")
            box.setText(
                f"Видеофон успешно сохранён:\n{msg}\n\n"
                f"Куда вы хотите опубликовать видеофон?"
            )
            gdrive_btn = box.addButton("📁 Google Диск", QMessageBox.ActionRole)
            pub_btn = box.addButton("🚀 GitHub", QMessageBox.ActionRole)
            open_btn = box.addButton("Открыть папку", QMessageBox.ActionRole)
            box.addButton("Закрыть", QMessageBox.RejectRole)
            box.exec()

            if box.clickedButton() == gdrive_btn:
                self._open_github_publish(initial_tab=3)
            elif box.clickedButton() == pub_btn:
                self._open_github_publish(initial_tab=0)
            elif box.clickedButton() == open_btn:
                import os
                try:
                    os.startfile(Path(msg).parent)
                except Exception:
                    pass
        else:
            self.status_label.setText("✗ Ошибка экспорта")
            QMessageBox.critical(self, "Ошибка", msg)

    def _show_ffmpeg_logs(self):
        dlg = FFmpegLogDialog(self.pipeline.logs, self)
        dlg.exec()

    def _open_online_search(self):
        dlg = OnlineSearchDialog(
            on_select_artwork=self._on_online_artwork_selected,
            on_select_title_id=self._on_online_title_id_selected,
            parent=self
        )
        dlg.exec()

    def _check_proposals(self):
        if self._proposal_worker and self._proposal_worker.isRunning():
            return
        token, _ = GitHubPublisher.get_stored_credentials()
        self._proposal_worker = ProposalNotificationWorker(token=token)
        self._proposal_worker.proposals_found.connect(self._on_proposals_found)
        self._proposal_worker.start()

    def _on_proposals_found(self, proposals: list):
        if not proposals:
            self.proposals_banner.setVisible(False)
            return

        count = len(proposals)
        if count == 1:
            txt = "🔔 <b>Новая заявка от сообщества:</b> 1 видеофон ожидает вашего одобрения!"
        elif 2 <= count <= 4:
            txt = f"🔔 <b>Новые заявки от сообщества:</b> {count} видеофона ожидают вашего одобрения!"
        else:
            txt = f"🔔 <b>Новые заявки от сообщества:</b> {count} видеофонов ожидают вашего одобрения!"

        self.proposals_banner_lbl.setText(txt)
        self.proposals_banner.setVisible(True)

    def _open_proposals_moderation(self):
        self._open_github_publish(initial_tab=4)
        self._check_proposals()

    def _open_github_publish(self, initial_tab: int = 0):
        try:
            video_path_str = ""
            if hasattr(self, "last_exported_video") and self.last_exported_video and self.last_exported_video.exists():
                video_path_str = str(self.last_exported_video)
            else:
                tid = self.tid_input.text().strip().upper()
                if tid:
                    for candidate_dir in [Path.cwd(), Path.home() / "Downloads"]:
                        cand = candidate_dir / f"{tid}.mp4"
                        if cand.exists():
                            video_path_str = str(cand)
                            break

            dlg = GitHubPublishDialog(
                video_path=video_path_str,
                title_id=self.tid_input.text().strip().upper(),
                game_title=self.game_title_input.text().strip(),
                style=self.style_combo.currentText(),
                initial_tab=initial_tab,
                parent=self
            )
            dlg.proposals_updated.connect(self._check_proposals)
            dlg.exec()
            self._check_proposals()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка открытия публикации", f"Не удалось открыть окно публикации:\n{e}")

    def _update_art_preview(self, path_str: str):
        p = Path(path_str.strip())
        if p.exists() and p.is_file():
            pm = QPixmap(str(p))
            if not pm.isNull():
                self.art_preview_lbl.setPixmap(pm.scaled(300, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                self.art_preview_lbl.setStyleSheet("background-color: #121418; border: 1px solid #10B981; border-radius: 6px;")
                return
        self.art_preview_lbl.setPixmap(QPixmap())
        self.art_preview_lbl.setText("Превью выбранного арта появится здесь")
        self.art_preview_lbl.setStyleSheet("background-color: #121418; border: 1px dashed #2A303C; border-radius: 6px; color: #718096; font-size: 12px;")

    def _on_online_artwork_selected(self, image_path: str, title_id: str, game_title: str):
        self.art_file_edit.setText(image_path)
        self.tid_input.setText(title_id)
        self.game_title_input.setText(game_title)
        self.style_combo.setCurrentText("Animated Art")
        self.tabs.setCurrentIndex(0)  # Switch to Mode A

    def _on_online_title_id_selected(self, title_id: str, game_title: str):
        self.tid_input.setText(title_id)
        self.game_title_input.setText(game_title)

    def _download_online_video(self):
        url, ok = QInputDialog.getText(
            self, "Скачивание онлайн-видео",
            "Вставьте прямую ссылку на MP4 или ссылку на видео/трейлер в YouTube:"
        )
        if not ok or not url.strip():
            return

        url = url.strip()
        title_id = self.tid_input.text().strip().upper() or "ONLINE_VIDEO"
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "h3h_studio_videos"

        self.status_label.setText(f"Загрузка видео с {url}...")
        self.export_btn.setEnabled(False)

        def dl_thread():
            video_file = OnlineFetcher.download_video_stream(url, temp_dir, title_id)
            if video_file and video_file.exists():
                QTimer.singleShot(0, lambda: self._on_video_downloaded(str(video_file)))
            else:
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Ошибка", "Не удалось скачать видео по указанной ссылке."))
            QTimer.singleShot(0, lambda: self.export_btn.setEnabled(True))

        threading.Thread(target=dl_thread, daemon=True).start()

    def _on_video_downloaded(self, video_path: str):
        self.gameplay_file_edit.setText(video_path)
        self.status_label.setText(f"✓ Онлайн-видео успешно загружено: {Path(video_path).name}")
        self.tabs.setCurrentIndex(1)  # Switch to Mode B
