"""
H3H Studio Express Tab — Simplified 1-Click Publisher for Community Users:
- Search Nintendo Switch games by name, Russian alias, or Title ID with rich metadata & multi-match selection
- Choose video source (Drag & Drop or File Dialog)
- Select type: Full Pack (720p Cover + 256x256 HEVC Icon), Only Cover, or Only Icon
- Interactive live video player preview with Play/Pause, scrubber, and exact Switch loop playback
- Interactive visual 1:1 square crop tool for 4IFIR video icons
- 1-Click Cloud Publishing to Google Drive & GitHub with embedded permanent credentials
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer, QUrl
from PySide6.QtGui import QFont, QPixmap, QImage, QColor, QPainter, QPen, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QSlider, QDoubleSpinBox,
    QProgressBar, QMessageBox, QFileDialog, QFrame, QScrollArea,
    QGroupBox, QSizePolicy
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink, QVideoFrame
from PySide6.QtMultimediaWidgets import QVideoWidget

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ..core.title_id_resolver import TitleIdResolver
from ..core.express_processor import ExpressProcessor


class PublishWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(bool, str, dict)

    def __init__(
        self,
        src_video: Path,
        title_id: str,
        game_name: str,
        variant_name: str,
        author: str,
        category: str,
        mode: str,  # 'cover', 'icon', 'both'
        start_sec: float,
        dur_sec: float,
        icon_start_sec: float,
        icon_dur_sec: float,
        volume_percent: int,
        crop_pan: float,
        video_w: int,
        video_h: int
    ):
        super().__init__()
        self.src_video = src_video
        self.title_id = title_id
        self.game_name = game_name
        self.variant_name = variant_name
        self.author = author
        self.category = category
        self.mode = mode
        self.start_sec = start_sec
        self.dur_sec = dur_sec
        self.icon_start_sec = icon_start_sec
        self.icon_dur_sec = icon_dur_sec
        self.volume_percent = volume_percent
        self.crop_pan = crop_pan
        self.video_w = video_w
        self.video_h = video_h

    def run(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="h3h_express_"))
        cover_mp4 = None
        cover_thumb = None
        icon_mp4 = None

        try:
            # 1. Generate Cover if requested
            if self.mode in ("cover", "both"):
                vol_msg = f"со звуком {self.volume_percent}%" if self.volume_percent > 0 else "без звука"
                self.progress.emit(10.0, f"1/3: Кодирование фонового видео 720p 30fps ({vol_msg})...")
                cover_mp4 = temp_dir / f"{self.title_id}_cover.mp4"
                cover_thumb = temp_dir / f"{self.title_id}_cover.jpg"
                ExpressProcessor.process_cover(
                    src_vid=self.src_video,
                    out_mp4=cover_mp4,
                    out_thumb=cover_thumb,
                    start_sec=self.start_sec,
                    dur_sec=self.dur_sec,
                    codec="h264",
                    keep_audio=(self.volume_percent > 0),
                    volume_percent=self.volume_percent
                )

            # 2. Generate Icon if requested
            if self.mode in ("icon", "both"):
                self.progress.emit(35.0, f"2/3: Кадрирование и сжатие видеоиконки 256x256 HEVC ({self.icon_dur_sec:.1f}с)...")
                icon_mp4 = temp_dir / f"{self.title_id}_icon.mp4"
                icon_thumb = temp_dir / f"{self.title_id}_icon.jpg"
                ExpressProcessor.process_icon(
                    src_vid=self.src_video,
                    out_mp4=icon_mp4,
                    out_thumb=icon_thumb,
                    start_sec=self.icon_start_sec,
                    dur_sec=self.icon_dur_sec,
                    crop_pan_percent=self.crop_pan,
                    video_w=self.video_w,
                    video_h=self.video_h
                )

            # 3. Publish to Cloud
            self.progress.emit(65.0, "3/3: Загрузка на Google Диск и публикация в каталог...")
            res = ExpressProcessor.publish_to_cloud(
                title_id=self.title_id,
                game_name=self.game_name,
                variant_name=self.variant_name,
                author=self.author,
                category=self.category,
                cover_mp4=cover_mp4,
                cover_thumb=cover_thumb,
                icon_mp4=icon_mp4,
                on_progress=lambda p, msg: self.progress.emit(p, msg)
            )

            self.finished.emit(True, "Успешно опубликовано!", res)

        except Exception as e:
            self.finished.emit(False, str(e), {})


class ExpressTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

        self.resolver = TitleIdResolver()
        self.settings = QSettings("H3H", "StudioExpress")

        self.current_video_path: Optional[Path] = None
        self.video_meta: dict = {}
        self.temp_frame_path = Path(tempfile.gettempdir()) / "h3h_express_preview.jpg"

        self.selected_title_id: str = ""
        self.selected_game_name: str = ""
        self.selected_publisher: str = ""
        self.selected_genre: str = ""
        self.selected_is_homebrew: bool = False

        self.worker: Optional[PublishWorker] = None

        # Search debounce timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(220)
        self.search_timer.timeout.connect(self._do_search)

        self._init_ui()
        self._init_player()

    def _init_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        # =========================================================================
        # --- STEP 1: Game Selection with Rich Search & Multi-Option Cards ---
        # =========================================================================
        step1_box = self._create_card("1. Выбор игры для Nintendo Switch", "#00E5FF")
        s1_layout = QVBoxLayout(step1_box)

        # Search row
        search_row = QHBoxLayout()
        self.game_search_edit = QLineEdit(self)
        self.game_search_edit.setPlaceholderText(
            "🔍 Введите название игры, персонажа, сленг или Title ID (например: GTA 5, GTA 4, DBI, Half-Life, Witcher, Zelda)..."
        )
        self.game_search_edit.setFixedHeight(38)
        self.game_search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #111720;
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                padding: 6px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #00E5FF;
            }
        """)
        self.game_search_edit.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.game_search_edit)

        self.btn_clear_search = QPushButton("✕", self)
        self.btn_clear_search.setFixedSize(38, 38)
        self.btn_clear_search.setStyleSheet("""
            QPushButton {
                background-color: #1E2734;
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                color: #9AA4B2;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EF4444;
                color: #FFFFFF;
            }
        """)
        self.btn_clear_search.clicked.connect(self._clear_game_selection)
        search_row.addWidget(self.btn_clear_search)

        s1_layout.addLayout(search_row)

        # --- Confirmed Active Game Banner (Initially Hidden) ---
        self.active_game_frame = QFrame(self)
        self.active_game_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0B241E, stop:1 #111A24);
                border: 2px solid #10B981;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        active_layout = QHBoxLayout(self.active_game_frame)
        active_layout.setContentsMargins(12, 10, 12, 10)

        active_info_col = QVBoxLayout()
        self.active_game_title_lbl = QLabel("🎮 <b>Название игры</b>", self)
        self.active_game_title_lbl.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
        active_info_col.addWidget(self.active_game_title_lbl)

        active_meta_row = QHBoxLayout()
        self.active_tid_badge = QLabel("[ 0100000000000000 ]", self)
        self.active_tid_badge.setStyleSheet("""
            background-color: #00E5FF;
            color: #000000;
            font-family: monospace;
            font-size: 12px;
            font-weight: bold;
            border-radius: 4px;
            padding: 3px 7px;
        """)
        active_meta_row.addWidget(self.active_tid_badge)

        self.active_meta_lbl = QLabel("🏢 Издатель: —  •  🏷 Жанр: —", self)
        self.active_meta_lbl.setStyleSheet("color: #A7F3D0; font-size: 12px;")
        active_meta_row.addWidget(self.active_meta_lbl)
        active_meta_row.addStretch()
        active_info_col.addLayout(active_meta_row)

        active_layout.addLayout(active_info_col, 1)

        self.btn_change_game = QPushButton("🔄 Сменить игру", self)
        self.btn_change_game.setFixedHeight(34)
        self.btn_change_game.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #4B5563;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: bold;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #374151;
                border-color: #00E5FF;
            }
        """)
        self.btn_change_game.clicked.connect(self._change_game_clicked)
        active_layout.addWidget(self.btn_change_game)

        self.active_game_frame.setVisible(False)
        s1_layout.addWidget(self.active_game_frame)

        # --- Dynamic Search Candidates Container ---
        self.candidates_container = QWidget(self)
        self.candidates_layout = QVBoxLayout(self.candidates_container)
        self.candidates_layout.setContentsMargins(0, 4, 0, 0)
        self.candidates_layout.setSpacing(6)

        # Hint/Status label when no search or no results
        self.search_status_lbl = QLabel(
            "🎮 <b>Игра не выбрана</b> — начните вводить название (например GTA 5, DBI, Mario) или вставьте 16-значный Title ID",
            self
        )
        self.search_status_lbl.setStyleSheet("color: #9AA4B2; font-size: 12px; padding: 4px;")
        self.candidates_layout.addWidget(self.search_status_lbl)

        s1_layout.addWidget(self.candidates_container)
        layout.addWidget(step1_box)

        # =========================================================================
        # --- STEP 2: Video Selection ---
        # =========================================================================
        step2_box = self._create_card("2. Выберите исходный видеоролик", "#3B82F6")
        s2_layout = QVBoxLayout(step2_box)

        file_row = QHBoxLayout()
        self.file_path_edit = QLineEdit(self)
        self.file_path_edit.setPlaceholderText("Перетащите видеофайл сюда (Drag & Drop) или нажмите Обзор... (MP4, WEBM, MOV, MKV)")
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setFixedHeight(36)
        self.file_path_edit.setStyleSheet("""
            QLineEdit {
                background-color: #111720;
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                padding: 6px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
        """)
        browse_btn = QPushButton("📁 Обзор...", self)
        browse_btn.setFixedHeight(36)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        browse_btn.clicked.connect(self._browse_video)
        file_row.addWidget(self.file_path_edit)
        file_row.addWidget(browse_btn)
        s2_layout.addLayout(file_row)

        self.video_details_lbl = QLabel("", self)
        self.video_details_lbl.setStyleSheet("color: #00E5FF; font-size: 12px; margin-top: 4px;")
        s2_layout.addWidget(self.video_details_lbl)

        layout.addWidget(step2_box)

        # =========================================================================
        # --- STEP 3: Content Mode Selection ---
        # =========================================================================
        step3_box = self._create_card("3. Что создаём?", "#A855F7")
        s3_layout = QHBoxLayout(step3_box)

        self.mode_group = QButtonGroup(self)
        self.radio_pack = QRadioButton("✨ Полный пак (Фон 720p + Иконка 256x256)", self)
        self.radio_pack.setChecked(True)
        self.radio_cover = QRadioButton("🎬 Только видеофон (1280x720)", self)
        self.radio_icon = QRadioButton("🔲 Только видеоиконка (256x256 HEVC)", self)

        for btn in (self.radio_pack, self.radio_cover, self.radio_icon):
            btn.setStyleSheet("QRadioButton { font-size: 13px; font-weight: bold; color: #FFFFFF; }")
            self.mode_group.addButton(btn)
            s3_layout.addWidget(btn)

        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        layout.addWidget(step3_box)

        # =========================================================================
        # --- STEP 4: Interactive Video Player Preview, Volume & Icon Tuning ---
        # =========================================================================
        self.crop_box = self._create_card("4. Интерактивный предпросмотр, звук и кадрирование", "#EC4899")
        s4_layout = QVBoxLayout(self.crop_box)
        s4_layout.setSpacing(14)

        # Previews Container: Side-by-side columns
        self.step4_cols_layout = QHBoxLayout()
        self.step4_cols_layout.setSpacing(16)

        # =========================================================
        # --- LEFT COLUMN: 🎬 Видеофон (16:9 720p) ---
        # =========================================================
        self.cover_card_frame = QFrame(self)
        self.cover_card_frame.setStyleSheet("""
            QFrame {
                background-color: #121822;
                border: 1px solid #2D3A4B;
                border-radius: 8px;
            }
        """)
        cover_col = QVBoxLayout(self.cover_card_frame)
        cover_col.setContentsMargins(12, 12, 12, 12)
        cover_col.setSpacing(10)

        # Header
        cover_header = QHBoxLayout()
        self.cover_title_lbl = QLabel("<b>🎬 Фоновое видео (1280x720 30fps)</b>", self)
        self.cover_title_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px;")
        cover_header.addWidget(self.cover_title_lbl)
        cover_header.addStretch()
        cover_col.addLayout(cover_header)

        # Video viewport
        self.video_viewport_frame = QFrame(self)
        self.video_viewport_frame.setFixedSize(392, 220)
        self.video_viewport_frame.setStyleSheet("""
            QFrame {
                background-color: #05080C;
                border: 2px solid #2D3A4B;
                border-radius: 6px;
            }
        """)
        viewport_layout = QVBoxLayout(self.video_viewport_frame)
        viewport_layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QVideoWidget(self.video_viewport_frame)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        viewport_layout.addWidget(self.video_widget)

        self.video_placeholder_lbl = QLabel("Загрузите видео в Шаге 2\nдля включения живого плеера", self.video_viewport_frame)
        self.video_placeholder_lbl.setAlignment(Qt.AlignCenter)
        self.video_placeholder_lbl.setStyleSheet("color: #6B7280; font-size: 13px; font-weight: bold; background: transparent;")
        viewport_layout.addWidget(self.video_placeholder_lbl)

        cover_col.addWidget(self.video_viewport_frame)

        # Controls row (Play/Pause, Stop, Scrubber)
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.btn_play_pause = QPushButton("▶ Воспроизвести", self)
        self.btn_play_pause.setFixedHeight(34)
        self.btn_play_pause.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #EC4899);
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #DB2777);
            }
        """)
        self.btn_play_pause.clicked.connect(self._toggle_playback)
        controls_row.addWidget(self.btn_play_pause)

        self.btn_stop = QPushButton("⏹", self)
        self.btn_stop.setFixedSize(34, 34)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #374151; }
        """)
        self.btn_stop.clicked.connect(self._stop_playback)
        controls_row.addWidget(self.btn_stop)

        self.scrubber_slider = QSlider(Qt.Horizontal, self)
        self.scrubber_slider.setRange(0, 1000)
        self.scrubber_slider.setValue(0)
        self.scrubber_slider.sliderMoved.connect(self._on_scrubber_dragged)
        controls_row.addWidget(self.scrubber_slider)

        cover_col.addLayout(controls_row)

        # Time readout
        self.time_display_lbl = QLabel("00:00.0 / 00:08.0 (Фрагмент Switch: 0.0с - 8.0с)", self)
        self.time_display_lbl.setStyleSheet("color: #9AA4B2; font-family: monospace; font-size: 11px;")
        cover_col.addWidget(self.time_display_lbl)

        # Timing controls row: Start & Duration
        timing_row = QHBoxLayout()
        timing_row.setSpacing(8)

        timing_row.addWidget(QLabel("Начало:", self))
        self.start_spin = QDoubleSpinBox(self)
        self.start_spin.setRange(0.0, 3600.0)
        self.start_spin.setValue(0.0)
        self.start_spin.setSingleStep(0.5)
        self.start_spin.setDecimals(1)
        self.start_spin.setFixedHeight(28)
        self.start_spin.valueChanged.connect(self._on_timing_changed)
        timing_row.addWidget(self.start_spin)

        timing_row.addSpacing(6)
        timing_row.addWidget(QLabel("Длительность:", self))
        self.dur_spin = QDoubleSpinBox(self)
        self.dur_spin.setRange(2.0, 30.0)
        self.dur_spin.setValue(8.0)
        self.dur_spin.setSingleStep(1.0)
        self.dur_spin.setDecimals(1)
        self.dur_spin.setFixedHeight(28)
        self.dur_spin.valueChanged.connect(self._on_timing_changed)
        timing_row.addWidget(self.dur_spin)

        for d in (5, 8, 12, 15, 20):
            p_btn = QPushButton(f"{d}с", self)
            p_btn.setFixedSize(36, 28)
            p_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1F2937;
                    border: 1px solid #374151;
                    border-radius: 4px;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #EC4899; color: #FFFFFF; }
            """)
            p_btn.clicked.connect(lambda checked, val=d: self.dur_spin.setValue(val))
            timing_row.addWidget(p_btn)

        timing_row.addStretch()
        cover_col.addLayout(timing_row)

        # Volume controls row
        vol_box = QVBoxLayout()
        vol_box.setSpacing(4)
        vol_header = QHBoxLayout()
        vol_header.addWidget(QLabel("<b>🔊 Громкость видеофона:</b>", self))
        self.volume_lbl = QLabel("100% (Оригинал)", self)
        self.volume_lbl.setStyleSheet("color: #10B981; font-weight: bold; font-size: 12px;")
        vol_header.addWidget(self.volume_lbl)
        vol_header.addStretch()

        self.btn_mute = QPushButton("🔊", self)
        self.btn_mute.setFixedSize(30, 26)
        self.btn_mute.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 4px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #374151; }
        """)
        self.btn_mute.clicked.connect(self._toggle_mute)
        vol_header.addWidget(self.btn_mute)

        for v, label in [(0, "Без звука"), (50, "50%"), (100, "100%"), (150, "150%")]:
            v_btn = QPushButton(label, self)
            v_btn.setFixedHeight(26)
            v_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1F2937;
                    border: 1px solid #374151;
                    border-radius: 4px;
                    color: #D1D5DB;
                    font-size: 11px;
                    padding: 0 6px;
                }
                QPushButton:hover { background-color: #10B981; color: #FFFFFF; }
            """)
            v_btn.clicked.connect(lambda checked, val=v: self.volume_slider.setValue(val))
            vol_header.addWidget(v_btn)

        vol_box.addLayout(vol_header)

        self.volume_slider = QSlider(Qt.Horizontal, self)
        self.volume_slider.setRange(0, 150)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        vol_box.addWidget(self.volume_slider)

        cover_col.addLayout(vol_box)

        self.step4_cols_layout.addWidget(self.cover_card_frame, 1)

        # =========================================================
        # --- RIGHT COLUMN: 🔲 Видеоиконка 4IFIR (1:1 256x256) ---
        # =========================================================
        self.icon_card_frame = QFrame(self)
        self.icon_card_frame.setStyleSheet("""
            QFrame {
                background-color: #121822;
                border: 1px solid #2D3A4B;
                border-radius: 8px;
            }
        """)
        icon_col = QVBoxLayout(self.icon_card_frame)
        icon_col.setContentsMargins(12, 12, 12, 12)
        icon_col.setSpacing(10)

        icon_header = QHBoxLayout()
        self.icon_title_lbl = QLabel("<b>🔲 Видеоиконка 4IFIR (256x256 HEVC)</b>", self)
        self.icon_title_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px;")
        icon_header.addWidget(self.icon_title_lbl)
        icon_header.addStretch()
        
        self.icon_badge_lbl = QLabel("24 FPS • Без звука", self)
        self.icon_badge_lbl.setStyleSheet("""
            background-color: #0E7490;
            color: #FFFFFF;
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        icon_header.addWidget(self.icon_badge_lbl)
        icon_col.addLayout(icon_header)

        # 1:1 Preview center container
        preview_center = QHBoxLayout()
        self.icon_preview_lbl = QLabel(self)
        self.icon_preview_lbl.setFixedSize(196, 196)
        self.icon_preview_lbl.setStyleSheet("""
            QLabel {
                background-color: #05080C;
                border: 2px solid #00E5FF;
                border-radius: 10px;
            }
        """)
        self.icon_preview_lbl.setAlignment(Qt.AlignCenter)
        self.icon_preview_lbl.setText("Квадрат 1:1\n(256x256 HEVC)")
        preview_center.addWidget(self.icon_preview_lbl)
        icon_col.addLayout(preview_center)

        # Icon Playback Controls (Play/Pause, Stop, Scrubber)
        icon_controls_row = QHBoxLayout()
        icon_controls_row.setSpacing(8)

        self.btn_play_icon = QPushButton("▶ Играть иконку", self)
        self.btn_play_icon.setFixedHeight(34)
        self.btn_play_icon.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06B6D4, stop:1 #3B82F6);
                color: #FFFFFF;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0891B2, stop:1 #2563EB);
            }
        """)
        self.btn_play_icon.clicked.connect(self._toggle_icon_playback)
        icon_controls_row.addWidget(self.btn_play_icon)

        self.btn_stop_icon = QPushButton("⏹", self)
        self.btn_stop_icon.setFixedSize(34, 34)
        self.btn_stop_icon.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #374151; }
        """)
        self.btn_stop_icon.clicked.connect(self._stop_icon_playback)
        icon_controls_row.addWidget(self.btn_stop_icon)

        self.icon_scrubber_slider = QSlider(Qt.Horizontal, self)
        self.icon_scrubber_slider.setRange(0, 1000)
        self.icon_scrubber_slider.setValue(0)
        self.icon_scrubber_slider.sliderMoved.connect(self._on_icon_scrubber_dragged)
        icon_controls_row.addWidget(self.icon_scrubber_slider)

        icon_col.addLayout(icon_controls_row)

        # Icon Time readout
        self.icon_time_display_lbl = QLabel("00:00.0 / 04.0с  (Иконка Switch: 0.0с - 4.0с)", self)
        self.icon_time_display_lbl.setStyleSheet("color: #00E5FF; font-family: monospace; font-size: 11px;")
        icon_col.addWidget(self.icon_time_display_lbl)

        # Independent Timing controls: Start, End, Duration
        icon_timing_row = QHBoxLayout()
        icon_timing_row.setSpacing(6)

        icon_timing_row.addWidget(QLabel("Начало:", self))
        self.icon_start_spin = QDoubleSpinBox(self)
        self.icon_start_spin.setRange(0.0, 3600.0)
        self.icon_start_spin.setValue(0.0)
        self.icon_start_spin.setSingleStep(0.5)
        self.icon_start_spin.setDecimals(1)
        self.icon_start_spin.setFixedHeight(28)
        self.icon_start_spin.valueChanged.connect(self._on_icon_start_changed)
        icon_timing_row.addWidget(self.icon_start_spin)

        icon_timing_row.addWidget(QLabel("Конец:", self))
        self.icon_end_spin = QDoubleSpinBox(self)
        self.icon_end_spin.setRange(0.5, 3600.0)
        self.icon_end_spin.setValue(4.0)
        self.icon_end_spin.setSingleStep(0.5)
        self.icon_end_spin.setDecimals(1)
        self.icon_end_spin.setFixedHeight(28)
        self.icon_end_spin.valueChanged.connect(self._on_icon_end_changed)
        icon_timing_row.addWidget(self.icon_end_spin)

        icon_timing_row.addWidget(QLabel("Длит.:", self))
        self.icon_dur_spin = QDoubleSpinBox(self)
        self.icon_dur_spin.setRange(1.0, 15.0)
        self.icon_dur_spin.setValue(4.0)
        self.icon_dur_spin.setSingleStep(0.5)
        self.icon_dur_spin.setDecimals(1)
        self.icon_dur_spin.setFixedHeight(28)
        self.icon_dur_spin.valueChanged.connect(self._on_icon_duration_changed)
        icon_timing_row.addWidget(self.icon_dur_spin)

        icon_timing_row.addStretch()
        icon_col.addLayout(icon_timing_row)

        # Preset buttons & Sync with cover button
        presets_row = QHBoxLayout()
        presets_row.setSpacing(6)

        for d in (2, 4, 6, 8):
            id_btn = QPushButton(f"{d}с", self)
            id_btn.setFixedSize(36, 26)
            id_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1F2937;
                    border: 1px solid #374151;
                    border-radius: 4px;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #00E5FF; color: #000000; }
            """)
            id_btn.clicked.connect(lambda checked, val=d: self._set_icon_duration_val(val))
            presets_row.addWidget(id_btn)

        self.btn_sync_cover = QPushButton("📋 Как у фона", self)
        self.btn_sync_cover.setFixedHeight(26)
        self.btn_sync_cover.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 4px;
                color: #A7F3D0;
                font-size: 11px;
                font-weight: bold;
                padding: 0 8px;
            }
            QPushButton:hover { background-color: #059669; color: #FFFFFF; }
        """)
        self.btn_sync_cover.clicked.connect(self._sync_icon_with_cover)
        presets_row.addWidget(self.btn_sync_cover)
        presets_row.addStretch()

        icon_col.addLayout(presets_row)

        # Crop pan controls
        pan_layout = QVBoxLayout()
        pan_layout.setSpacing(4)
        pan_header = QHBoxLayout()
        pan_header.addWidget(QLabel("<b>Горизонтальное кадрирование:</b>", self))
        self.pan_percent_lbl = QLabel("50% (По центру)", self)
        self.pan_percent_lbl.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 12px;")
        pan_header.addWidget(self.pan_percent_lbl)
        pan_header.addStretch()

        btn_left = QPushButton("◀ 0%", self)
        btn_left.setFixedSize(50, 26)
        btn_left.clicked.connect(lambda: self.crop_slider.setValue(0))
        btn_center = QPushButton("• 50%", self)
        btn_center.setFixedSize(50, 26)
        btn_center.clicked.connect(lambda: self.crop_slider.setValue(50))
        btn_right = QPushButton("▶ 100%", self)
        btn_right.setFixedSize(56, 26)
        btn_right.clicked.connect(lambda: self.crop_slider.setValue(100))

        for b in (btn_left, btn_center, btn_right):
            b.setStyleSheet("""
                QPushButton {
                    background-color: #1F2937;
                    border: 1px solid #374151;
                    border-radius: 4px;
                    color: #FFFFFF;
                    font-size: 11px;
                    padding: 3px 8px;
                }
                QPushButton:hover { background-color: #374151; border-color: #00E5FF; }
            """)
            pan_header.addWidget(b)

        pan_layout.addLayout(pan_header)

        self.crop_slider = QSlider(Qt.Horizontal, self)
        self.crop_slider.setRange(0, 100)
        self.crop_slider.setValue(50)
        self.crop_slider.valueChanged.connect(self._on_crop_slider_changed)
        pan_layout.addWidget(self.crop_slider)

        icon_col.addLayout(pan_layout)
        icon_col.addStretch()

        self.step4_cols_layout.addWidget(self.icon_card_frame, 1)

        s4_layout.addLayout(self.step4_cols_layout)
        layout.addWidget(self.crop_box)

        # =========================================================================
        # --- STEP 5: Metadata & 1-Click Publish ---
        # =========================================================================
        step5_box = self._create_card("5. Автор и Публикация в каталог", "#10B981")
        s5_layout = QVBoxLayout(step5_box)

        meta_grid = QHBoxLayout()

        # Variant Name
        v_col = QVBoxLayout()
        v_col.addWidget(QLabel("Название варианта темы:", self))
        self.var_name_edit = QLineEdit(self)
        self.var_name_edit.setFixedHeight(34)
        self.var_name_edit.setPlaceholderText("Например: Dynamic Action, Title Screen, Neon Blade")
        self.var_name_edit.setText("Dynamic Theme")
        v_col.addWidget(self.var_name_edit)
        meta_grid.addLayout(v_col, 2)

        # Author Handle
        a_col = QVBoxLayout()
        a_col.addWidget(QLabel("Ваш ник / Автор (для титров):", self))
        self.author_edit = QLineEdit(self)
        self.author_edit.setFixedHeight(34)
        saved_author = self.settings.value("author_name", "Community")
        self.author_edit.setText(saved_author)
        self.author_edit.setPlaceholderText("@username")
        a_col.addWidget(self.author_edit)
        meta_grid.addLayout(a_col, 1)

        # Category
        c_col = QVBoxLayout()
        c_col.addWidget(QLabel("Каталог назначения:", self))
        self.category_combo = QComboBox(self)
        self.category_combo.setFixedHeight(34)
        self.category_combo.addItem("🎮 Обычный каталог H3H (Семейный)", "standard")
        self.category_combo.addItem("🌸 After Dark (18+ / Эччи)", "after_dark")
        c_col.addWidget(self.category_combo)
        meta_grid.addLayout(c_col, 1)

        s5_layout.addLayout(meta_grid)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(26)
        self.progress_bar.setVisible(False)
        s5_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("", self)
        self.status_lbl.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 13px;")
        s5_layout.addWidget(self.status_lbl)

        # Big Publish Button
        self.publish_btn = QPushButton("🚀 СКОНВЕРТИРОВАТЬ И ОПУБЛИКОВАТЬ НА GOOGLE ДИСК", self)
        self.publish_btn.setFixedHeight(54)
        self.publish_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                color: #FFFFFF;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6B7280;
            }
        """)
        self.publish_btn.clicked.connect(self._start_publishing)
        s5_layout.addWidget(self.publish_btn)

        layout.addWidget(step5_box)
        layout.addStretch()

        scroll.setWidget(container)

        main_vbox = QVBoxLayout(self)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.addWidget(scroll)

    def _init_player(self):
        """Initializes QtMultimedia QMediaPlayer & QAudioOutput for Cover & Icon."""
        # 1. Main Cover Player
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.playbackStateChanged.connect(self._on_player_state_changed)

        # 2. Dedicated 4IFIR Video Icon Player
        self.icon_player = QMediaPlayer(self)
        self.icon_audio_output = QAudioOutput(self)
        self.icon_audio_output.setMuted(True)
        self.icon_player.setAudioOutput(self.icon_audio_output)
        self.icon_video_sink = QVideoSink(self)
        self.icon_player.setVideoSink(self.icon_video_sink)
        self.icon_video_sink.videoFrameChanged.connect(self._on_icon_frame_received)
        self.icon_player.positionChanged.connect(self._on_icon_player_position_changed)
        self.icon_player.playbackStateChanged.connect(self._on_icon_player_state_changed)

    def _create_card(self, title: str, accent_color: str) -> QGroupBox:
        box = QGroupBox(title, self)
        box.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid #2D3A4B;
                border-radius: 8px;
                background-color: #161C24;
                margin-top: 14px;
                font-weight: bold;
                font-size: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                color: {accent_color};
            }}
        """)
        return box

    # =========================================================================
    # --- Step 1: Game Search & Multi-Match Selection ---
    # =========================================================================

    def _on_search_text_changed(self, text: str):
        # Restart debounce timer
        self.search_timer.start()

    def _do_search(self):
        query = self.game_search_edit.text().strip()

        # If user cleared search text
        if not query:
            if not self.selected_title_id:
                self._clear_candidate_cards()
                self.search_status_lbl.setText("🎮 <b>Игра не выбрана</b> — начните вводить название выше")
                self.search_status_lbl.setVisible(True)
            return

        # Direct 16-hex Title ID match
        tid_match = TitleIdResolver.extract_title_id(query)
        if tid_match:
            tid_upper = tid_match.upper()
            resolved = self.resolver.resolve_by_title_id(tid_upper) or f"Игра ({tid_upper})"
            self._select_game({
                "titleId": tid_upper,
                "title": resolved,
                "publisher": "Nintendo Switch",
                "genre": "Game",
                "isHomebrew": False
            })
            return

        # Search rich candidates
        matches = self.resolver.search_games_rich(query, limit=5)
        self._clear_candidate_cards()

        if not matches:
            self.search_status_lbl.setText(
                f"⚠️ По запросу <b>«{query}»</b> ничего не найдено. Проверьте опечатку или введите 16-значный Title ID напрямую."
            )
            self.search_status_lbl.setVisible(True)
            return

        # If only 1 result with exact or high confidence, show it prominently
        self.search_status_lbl.setText(f"🔎 <b>Найдено вариантов ({len(matches)}):</b> нажмите на игру или Title ID для выбора:")
        self.search_status_lbl.setVisible(True)

        for match in matches:
            card = self._create_candidate_card(match)
            self.candidates_layout.addWidget(card)
            card.show()

    def _create_candidate_card(self, game_info: Dict[str, Any]) -> QFrame:
        card = QFrame(self.candidates_container)
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setStyleSheet("""
            QFrame {
                background-color: #1A222D;
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QFrame:hover {
                background-color: #242E3D;
                border: 1px solid #00E5FF;
            }
        """)

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)

        # Title and details
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_row = QHBoxLayout()
        title_lbl = QLabel(f"<b>{game_info.get('title')}</b>", card)
        title_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px;")
        title_row.addWidget(title_lbl)

        if game_info.get("isHomebrew"):
            hb_badge = QLabel("Homebrew / Порт", card)
            hb_badge.setStyleSheet("""
                background-color: #F59E0B;
                color: #000000;
                font-size: 10px;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px 5px;
            """)
            title_row.addWidget(hb_badge)

        title_row.addStretch()
        text_col.addLayout(title_row)

        pub = game_info.get("publisher", "Unknown")
        genre = game_info.get("genre", "Nintendo Switch")
        meta_lbl = QLabel(f"🏢 {pub}  •  🏷 {genre}", card)
        meta_lbl.setStyleSheet("color: #9AA4B2; font-size: 11px;")
        text_col.addWidget(meta_lbl)

        card_layout.addLayout(text_col, 1)

        # Clickable Title ID Badge
        tid = game_info.get("titleId", "")
        tid_btn = QPushButton(f"🆔 {tid}", card)
        tid_btn.setCursor(QCursor(Qt.PointingHandCursor))
        tid_btn.setStyleSheet("""
            QPushButton {
                background-color: #0E7490;
                color: #FFFFFF;
                font-family: monospace;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #00E5FF;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #00E5FF;
                color: #000000;
            }
        """)
        tid_btn.clicked.connect(lambda checked=False, g=game_info: self._select_game(g))
        card_layout.addWidget(tid_btn)

        # Clicking the entire card also selects the game
        card.mousePressEvent = lambda event, g=game_info: self._select_game(g)

        return card

    def _select_game(self, game_info: Dict[str, Any]):
        tid = game_info.get("titleId", "").upper()
        name = game_info.get("title", "")
        pub = game_info.get("publisher", "Official")
        genre = game_info.get("genre", "Game")
        is_hb = game_info.get("isHomebrew", False)

        self.selected_title_id = tid
        self.selected_game_name = name
        self.selected_publisher = pub
        self.selected_genre = genre
        self.selected_is_homebrew = is_hb

        # Update confirmed banner
        hb_suffix = "  <span style='background:#F59E0B; color:#000; border-radius:3px; padding:2px 5px; font-size:11px;'>Homebrew / Порт</span>" if is_hb else ""
        self.active_game_title_lbl.setText(f"🎮 <b>{name}</b>{hb_suffix}")
        self.active_tid_badge.setText(f"[ {tid} ]")
        self.active_meta_lbl.setText(f"🏢 Издатель: {pub}  •  🏷 Жанр: {genre}")

        self.active_game_frame.setVisible(True)
        self._clear_candidate_cards()
        self.search_status_lbl.setVisible(False)

        # Sync search edit without retriggering search loop
        self.game_search_edit.blockSignals(True)
        self.game_search_edit.setText(name)
        self.game_search_edit.blockSignals(False)

    def _change_game_clicked(self):
        self.active_game_frame.setVisible(False)
        self.game_search_edit.setFocus()
        self.game_search_edit.selectAll()
        self._do_search()

    def _clear_game_selection(self):
        self.game_search_edit.clear()
        self.selected_title_id = ""
        self.selected_game_name = ""
        self.active_game_frame.setVisible(False)
        self._clear_candidate_cards()
        self.search_status_lbl.setText("🎮 <b>Игра не выбрана</b> — начните вводить название выше")
        self.search_status_lbl.setVisible(True)

    def _clear_candidate_cards(self):
        # Remove candidate cards, keeping only the search_status_lbl
        for i in reversed(range(self.candidates_layout.count())):
            item = self.candidates_layout.itemAt(i)
            widget = item.widget()
            if widget and widget != self.search_status_lbl:
                widget.setParent(None)
                widget.deleteLater()

    # =========================================================================
    # --- Step 2: Video Loading & Drag and Drop ---
    # =========================================================================

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = Path(urls[0].toLocalFile())
                if path.suffix.lower() in (".mp4", ".webm", ".mov", ".mkv", ".gif"):
                    event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            self._load_video(path)

    def _browse_video(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите исходное видео",
            "",
            "Видеофайлы (*.mp4 *.webm *.mov *.mkv *.gif);;Все файлы (*.*)"
        )
        if fpath:
            self._load_video(Path(fpath))

    def _load_video(self, path: Path):
        self.current_video_path = path
        self.file_path_edit.setText(str(path))

        # Probe video
        meta = ExpressProcessor.probe_video(path)
        if not meta.get("ok"):
            QMessageBox.warning(self, "Ошибка видео", f"Не удалось прочитать видео:\n{meta.get('error')}")
            return

        self.video_meta = meta
        w = meta.get("width", 0)
        h = meta.get("height", 0)
        dur = meta.get("duration", 0.0)
        fps = meta.get("fps", 30.0)
        mb = meta.get("file_size", 0) / (1024 * 1024)

        self.video_details_lbl.setText(
            f"⚡ Разрешение: {w}x{h} | Длительность: {dur:.1f}с | FPS: {fps} | Вес: {mb:.1f} МБ"
        )

        # Auto-detect Title ID from filename if not yet set
        detected_tid = TitleIdResolver.extract_title_id(path.name)
        if detected_tid and not self.selected_title_id:
            resolved = self.resolver.resolve_by_title_id(detected_tid) or f"Игра ({detected_tid})"
            self._select_game({
                "titleId": detected_tid,
                "title": resolved,
                "publisher": "Auto-detected",
                "genre": "Game",
                "isHomebrew": False
            })

        # Auto-suggest variant name from filename
        stem = path.stem
        clean_name = stem.replace("_", " ").replace("-", " ").title()
        if len(clean_name) >= 3 and (not self.var_name_edit.text() or self.var_name_edit.text() == "Dynamic Theme"):
            self.var_name_edit.setText(clean_name)

        # Set ranges for timing controls
        self.start_spin.blockSignals(True)
        self.dur_spin.blockSignals(True)
        self.start_spin.setRange(0.0, max(0.0, dur - 1.0))
        self.dur_spin.setRange(2.0, min(30.0, dur))
        self.start_spin.blockSignals(False)
        self.dur_spin.blockSignals(False)

        # Load video into cover media player
        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.media_player.setPosition(1)
        self.video_placeholder_lbl.setVisible(False)

        # Load video into icon media player
        self.icon_player.stop()
        self.icon_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.icon_player.setPosition(1)

        # Configure icon timing ranges
        self.icon_start_spin.blockSignals(True)
        self.icon_end_spin.blockSignals(True)
        self.icon_dur_spin.blockSignals(True)
        self.icon_start_spin.setRange(0.0, max(0.0, dur - 1.0))
        self.icon_end_spin.setRange(0.5, dur)
        self.icon_start_spin.setValue(0.0)
        self.icon_dur_spin.setValue(min(4.0, dur))
        self.icon_end_spin.setValue(min(4.0, dur))
        self.icon_start_spin.blockSignals(False)
        self.icon_end_spin.blockSignals(False)
        self.icon_dur_spin.blockSignals(False)

        # Update initial frame & icon preview
        self._update_icon_crop_preview()
        self._update_time_label()
        self._update_icon_time_label()

    # =========================================================================
    # --- Step 4: Interactive Video Playback & Loop Preview ---
    # =========================================================================

    def _toggle_playback(self):
        if not self.current_video_path or not self.current_video_path.exists():
            QMessageBox.information(self, "Внимание", "Сначала выберите видеофайл в Шаге 2.")
            return

        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            start_ms = int(self.start_spin.value() * 1000)
            end_ms = int((self.start_spin.value() + self.dur_spin.value()) * 1000)
            cur_ms = self.media_player.position()
            if cur_ms < start_ms or cur_ms >= end_ms:
                self.media_player.setPosition(start_ms)
            self.media_player.play()

    def _stop_playback(self):
        self.media_player.stop()
        start_ms = int(self.start_spin.value() * 1000)
        self.media_player.setPosition(start_ms)
        self.scrubber_slider.setValue(0)
        self._update_time_label()

    def _toggle_mute(self):
        is_muted = self.audio_output.isMuted()
        self.audio_output.setMuted(not is_muted)
        self.btn_mute.setText("🔇" if not is_muted else "🔊")

    def _on_player_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play_pause.setText("⏸ Пауза")
            self.btn_play_pause.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 13px;
                    border-radius: 6px;
                    padding: 0 14px;
                }
            """)
        else:
            self.btn_play_pause.setText("▶ Воспроизвести")
            self.btn_play_pause.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #EC4899);
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 13px;
                    border-radius: 6px;
                    padding: 0 14px;
                }
            """)

    def _on_player_position_changed(self, pos_ms: int):
        start_ms = int(self.start_spin.value() * 1000)
        end_ms = int((self.start_spin.value() + self.dur_spin.value()) * 1000)
        dur_ms = max(1, end_ms - start_ms)

        # Exact Switch loop playback: wrap around to start_ms
        if pos_ms >= end_ms or pos_ms < start_ms:
            self.media_player.setPosition(start_ms)
            pos_ms = start_ms

        rel_ms = max(0, min(pos_ms - start_ms, dur_ms))
        pct = int((rel_ms / dur_ms) * 1000)

        self.scrubber_slider.blockSignals(True)
        self.scrubber_slider.setValue(pct)
        self.scrubber_slider.blockSignals(False)

        curr_sec = rel_ms / 1000.0
        tot_sec = dur_ms / 1000.0
        start_sec = self.start_spin.value()
        end_sec = start_sec + self.dur_spin.value()
        self.time_display_lbl.setText(
            f"{curr_sec:04.1f}с / {tot_sec:04.1f}с  (Фрагмент Switch: {start_sec:.1f}с - {end_sec:.1f}с)"
        )

    def _on_scrubber_dragged(self, val: int):
        start_ms = int(self.start_spin.value() * 1000)
        end_ms = int((self.start_spin.value() + self.dur_spin.value()) * 1000)
        dur_ms = max(1, end_ms - start_ms)
        target_ms = start_ms + int((val / 1000.0) * dur_ms)
        self.media_player.setPosition(target_ms)
        self._update_time_label()

    def _on_timing_changed(self):
        start_ms = int(self.start_spin.value() * 1000)
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.setPosition(start_ms)
        self._update_time_label()
        self._update_icon_crop_preview()

    def _update_time_label(self):
        start_sec = self.start_spin.value()
        dur_sec = self.dur_spin.value()
        end_sec = start_sec + dur_sec
        self.time_display_lbl.setText(
            f"00:00.0 / {dur_sec:04.1f}с  (Фрагмент Switch: {start_sec:.1f}с - {end_sec:.1f}с)"
        )

    # =========================================================================
    # --- Mode & Cropping ---
    # =========================================================================

    def _on_volume_changed(self, val: int):
        if val == 0:
            txt = "0% (Без звука)"
            self.btn_mute.setText("🔇")
        elif val == 100:
            txt = "100% (Оригинал)"
            self.btn_mute.setText("🔊")
        elif val > 100:
            txt = f"{val}% (Усиление)"
            self.btn_mute.setText("🔊")
        else:
            txt = f"{val}%"
            self.btn_mute.setText("🔊")
        self.volume_lbl.setText(txt)
        self.audio_output.setVolume(val / 100.0)

    def _toggle_mute(self):
        if self.volume_slider.value() > 0:
            self._prev_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
        else:
            self.volume_slider.setValue(getattr(self, "_prev_volume", 100))

    # =========================================================================
    # --- Step 4: 🔲 Video Icon Playback & Independent Timing Handlers ---
    # =========================================================================

    def _toggle_icon_playback(self):
        if not self.current_video_path or not self.current_video_path.exists():
            QMessageBox.information(self, "Внимание", "Сначала выберите видеофайл в Шаге 2.")
            return

        if self.icon_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.icon_player.pause()
        else:
            # Pause cover player so only one preview plays at a time
            if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.media_player.pause()

            start_ms = int(self.icon_start_spin.value() * 1000)
            end_ms = int(self.icon_end_spin.value() * 1000)
            cur_ms = self.icon_player.position()
            if cur_ms < start_ms or cur_ms >= end_ms:
                self.icon_player.setPosition(start_ms)
            self.icon_player.play()

    def _stop_icon_playback(self):
        self.icon_player.stop()
        start_ms = int(self.icon_start_spin.value() * 1000)
        self.icon_player.setPosition(start_ms)
        self.icon_scrubber_slider.setValue(0)
        self._update_icon_time_label()
        self._update_icon_crop_preview()

    def _on_icon_player_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play_icon.setText("⏸ Пауза")
            self.btn_play_icon.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 6px;
                    padding: 0 12px;
                }
            """)
        else:
            self.btn_play_icon.setText("▶ Играть иконку")
            self.btn_play_icon.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06B6D4, stop:1 #3B82F6);
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 6px;
                    padding: 0 12px;
                }
            """)

    def _on_icon_player_position_changed(self, pos_ms: int):
        start_ms = int(self.icon_start_spin.value() * 1000)
        end_ms = int(self.icon_end_spin.value() * 1000)
        dur_ms = max(1, end_ms - start_ms)

        # Loop within icon interval [icon_start, icon_end]
        if pos_ms >= end_ms or pos_ms < start_ms:
            self.icon_player.setPosition(start_ms)
            pos_ms = start_ms

        rel_ms = max(0, min(pos_ms - start_ms, dur_ms))
        pct = int((rel_ms / dur_ms) * 1000)

        self.icon_scrubber_slider.blockSignals(True)
        self.icon_scrubber_slider.setValue(pct)
        self.icon_scrubber_slider.blockSignals(False)

        curr_sec = rel_ms / 1000.0
        tot_sec = dur_ms / 1000.0
        start_sec = self.icon_start_spin.value()
        end_sec = self.icon_end_spin.value()
        self.icon_time_display_lbl.setText(
            f"{curr_sec:04.1f}с / {tot_sec:04.1f}с  (Иконка Switch: {start_sec:.1f}с - {end_sec:.1f}с)"
        )

    def _on_icon_scrubber_dragged(self, val: int):
        start_ms = int(self.icon_start_spin.value() * 1000)
        end_ms = int(self.icon_end_spin.value() * 1000)
        dur_ms = max(1, end_ms - start_ms)
        target_ms = start_ms + int((val / 1000.0) * dur_ms)
        self.icon_player.setPosition(target_ms)

    def _on_icon_frame_received(self, vf: QVideoFrame):
        """Renders live cropped 1:1 frame into icon preview during playback."""
        img = vf.toImage()
        if img.isNull():
            return

        w = img.width()
        h = img.height()
        pan = self.crop_slider.value() / 100.0

        if w > h:
            sq = h
            offset_x = int((w - h) * pan)
            cropped = img.copy(offset_x, 0, sq, sq)
        elif h > w:
            sq = w
            offset_y = int((h - w) * pan)
            cropped = img.copy(0, offset_y, sq, sq)
        else:
            cropped = img

        pix = QPixmap.fromImage(cropped).scaled(196, 196, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.icon_preview_lbl.setPixmap(pix)

    def _on_icon_start_changed(self, val: float):
        dur = self.icon_dur_spin.value()
        new_end = val + dur
        self.icon_end_spin.blockSignals(True)
        self.icon_end_spin.setValue(new_end)
        self.icon_end_spin.blockSignals(False)

        if self.icon_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.icon_player.setPosition(int(val * 1000))
        self._update_icon_time_label()
        self._update_icon_crop_preview()

    def _on_icon_end_changed(self, val: float):
        start = self.icon_start_spin.value()
        if val <= start:
            val = start + 1.0
            self.icon_end_spin.blockSignals(True)
            self.icon_end_spin.setValue(val)
            self.icon_end_spin.blockSignals(False)
        dur = max(1.0, val - start)
        self.icon_dur_spin.blockSignals(True)
        self.icon_dur_spin.setValue(dur)
        self.icon_dur_spin.blockSignals(False)

        self._update_icon_time_label()

    def _on_icon_duration_changed(self, val: float):
        start = self.icon_start_spin.value()
        new_end = start + val
        self.icon_end_spin.blockSignals(True)
        self.icon_end_spin.setValue(new_end)
        self.icon_end_spin.blockSignals(False)

        self._update_icon_time_label()

    def _set_icon_duration_val(self, dur_val: float):
        self.icon_dur_spin.setValue(dur_val)

    def _sync_icon_with_cover(self):
        """Copies start time and duration from video cover to icon."""
        c_start = self.start_spin.value()
        c_dur = min(15.0, self.dur_spin.value())
        self.icon_start_spin.setValue(c_start)
        self.icon_dur_spin.setValue(c_dur)
        self.icon_end_spin.setValue(c_start + c_dur)
        self._update_icon_time_label()
        self._update_icon_crop_preview()

    def _update_icon_time_label(self):
        start_sec = self.icon_start_spin.value()
        dur_sec = self.icon_dur_spin.value()
        end_sec = self.icon_end_spin.value()
        self.icon_time_display_lbl.setText(
            f"00:00.0 / {dur_sec:04.1f}с  (Иконка Switch: {start_sec:.1f}с - {end_sec:.1f}с)"
        )

    def _on_mode_changed(self):
        is_pack = self.radio_pack.isChecked()
        is_cover = self.radio_cover.isChecked()
        is_icon = self.radio_icon.isChecked()

        self.cover_card_frame.setVisible(is_pack or is_cover)
        self.icon_card_frame.setVisible(is_pack or is_icon)

    def _on_crop_slider_changed(self, val: int):
        if val == 0:
            label_text = "0% (Левый край)"
        elif val == 50:
            label_text = "50% (По центру)"
        elif val == 100:
            label_text = "100% (Правый край)"
        else:
            label_text = f"{val}%"
        self.pan_percent_lbl.setText(label_text)
        self._update_icon_crop_preview()

    def _update_icon_crop_preview(self):
        if not self.current_video_path or not self.current_video_path.exists():
            return

        ts = self.icon_start_spin.value() if hasattr(self, "icon_start_spin") else self.start_spin.value()
        ok = ExpressProcessor.extract_preview_frame(self.current_video_path, ts, self.temp_frame_path)
        if not ok or not self.temp_frame_path.exists():
            return

        pix = QPixmap(str(self.temp_frame_path))
        if pix.isNull():
            return

        w = pix.width()
        h = pix.height()
        pan = self.crop_slider.value() / 100.0

        if w > h:
            sq = h
            offset_x = int((w - h) * pan)
            cropped = pix.copy(offset_x, 0, sq, sq)
        elif h > w:
            sq = w
            offset_y = int((h - w) * pan)
            cropped = pix.copy(0, offset_y, sq, sq)
        else:
            cropped = pix

        self.icon_preview_lbl.setPixmap(
            cropped.scaled(196, 196, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        )

    # =========================================================================
    # --- Step 5: Publishing Pipeline ---
    # =========================================================================

    def _start_publishing(self):
        if not self.current_video_path or not self.current_video_path.exists():
            QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите исходный видеоролик в Шаге 2.")
            return

        if not self.selected_title_id:
            QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите игру из списка в Шаге 1 или укажите 16-значный Title ID.")
            return

        # Pause playback during export
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        if self.icon_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.icon_player.pause()

        author = self.author_edit.text().strip() or "Community"
        self.settings.setValue("author_name", author)

        variant_name = self.var_name_edit.text().strip() or "Dynamic Theme"
        category = self.category_combo.currentData()

        if self.radio_pack.isChecked():
            mode = "both"
        elif self.radio_cover.isChecked():
            mode = "cover"
        else:
            mode = "icon"

        self.publish_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(5)
        self.status_lbl.setText("Подготовка процесса публикации...")

        self.worker = PublishWorker(
            src_video=self.current_video_path,
            title_id=self.selected_title_id,
            game_name=self.selected_game_name,
            variant_name=variant_name,
            author=author,
            category=category,
            mode=mode,
            start_sec=self.start_spin.value(),
            dur_sec=self.dur_spin.value(),
            icon_start_sec=self.icon_start_spin.value(),
            icon_dur_sec=self.icon_dur_spin.value(),
            volume_percent=self.volume_slider.value(),
            crop_pan=float(self.crop_slider.value()),
            video_w=self.video_meta.get("width", 1280),
            video_h=self.video_meta.get("height", 720)
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, val: float, msg: str):
        self.progress_bar.setValue(int(val))
        self.status_lbl.setText(msg)

    def _on_worker_finished(self, success: bool, message: str, result: dict):
        self.publish_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self.status_lbl.setText("✅ Успешно опубликовано в каталог!")
            cat_name = "Обычный каталог" if self.category_combo.currentData() == "standard" else "🌸 After Dark"
            QMessageBox.information(
                self,
                "Успешная публикация!",
                f"🎉 <b>ВИДЕО ТЕМА УСПЕШНО ОПУБЛИКОВАНА!</b>\n\n"
                f"🎮 <b>Игра:</b> {result.get('game_name')}\n"
                f"🆔 <b>Title ID:</b> <code>{result.get('title_id')}</code>\n"
                f"🎬 <b>Название:</b> {result.get('variant_name')}\n"
                f"📁 <b>Каталог:</b> {cat_name}\n\n"
                "Файлы уже на Google Диске, а каталог на GitHub обновлён.\n"
                "Тема сразу доступна всем пользователям в приложении на Nintendo Switch!"
            )
        else:
            self.status_lbl.setText("❌ Ошибка при публикации")
            QMessageBox.critical(self, "Ошибка публикации", f"Не удалось опубликовать:\n\n{message}")
