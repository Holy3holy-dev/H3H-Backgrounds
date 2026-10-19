import re
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QFileDialog, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QProgressBar, QTextEdit,
    QMessageBox, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView
)

from ..core.analyzer import VideoAnalyzer, VideoAnalysis
from ..core.encoder import Encoder, PROFILES, EncodingProfile
from ..core.ken_burns import KenBurnsGenerator
from ..core.pipeline import FFmpegPipeline
from ..core.project import StudioProject
from .ffmpeg_log_dialog import FFmpegLogDialog

TITLE_ID_PATTERN = re.compile(r"^0100[0-9A-Fa-f]{12}$")


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

        self._apply_theme()
        self._init_ui()

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

        log_btn = QPushButton("Журнал FFmpeg", self)
        log_btn.clicked.connect(self._show_ffmpeg_logs)
        header_layout.addWidget(log_btn)

        main_layout.addLayout(header_layout)

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
        file_layout.addWidget(self.gameplay_file_edit)
        file_layout.addWidget(browse_btn)
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
            self.tid_badge.setText("✗ Ошибка (16 hex, начинается с 0100)")
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
            self.status_label.setText(f"✓ Успешно экспортировано: {msg}")
            QMessageBox.information(
                self, "Успех",
                f"Видеофон успешно сохранён:\n{msg}\n\nМетаданные каталога также экспортированы рядом."
            )
        else:
            self.status_label.setText("✗ Ошибка экспорта")
            QMessageBox.critical(self, "Ошибка", msg)

    def _show_ffmpeg_logs(self):
        dlg = FFmpegLogDialog(self.pipeline.logs, self)
        dlg.exec()
