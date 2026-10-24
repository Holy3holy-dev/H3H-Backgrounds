import os
import sys
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt, QUrl, QTimer, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QDoubleSpinBox, QSlider, QProgressBar,
    QFileDialog, QMessageBox, QGroupBox, QFrame, QScrollArea
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
STUDIO_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from ..core.online_fetcher import OnlineFetcher
from ..core.express_processor import ExpressProcessor
from .online_icons_dialog import OnlineIconsDialog


class IconWorkerThread(QThread):
    progress_changed = Signal(float, str)
    finished_success = Signal(dict)
    finished_error = Signal(str)

    def __init__(
        self,
        title_id: str,
        game_name: str,
        variant_name: str,
        author: str,
        category: str,
        src_video: Path,
        start_sec: float,
        dur_sec: float,
        crop_pan: float,
        codec: str,
        is_cloud_publish: bool,
        export_dir: Optional[Path] = None
    ):
        super().__init__()
        self.title_id = title_id
        self.game_name = game_name
        self.variant_name = variant_name
        self.author = author
        self.category = category
        self.src_video = src_video
        self.start_sec = start_sec
        self.dur_sec = dur_sec
        self.crop_pan = crop_pan
        self.codec = codec
        self.is_cloud_publish = is_cloud_publish
        self.export_dir = export_dir

    def run(self):
        try:
            tmp_dir = Path("tmp/icon_studio_export")
            tmp_dir.mkdir(parents=True, exist_ok=True)

            out_icon_mp4 = tmp_dir / f"{self.title_id}_icon.mp4"
            out_icon_thumb = tmp_dir / f"{self.title_id}_icon_thumb.jpg"

            # 1. Process Video Icon
            self.progress_changed.emit(10.0, "Анализ исходного видео...")
            probe = ExpressProcessor.probe_video(self.src_video)
            vw = probe.get("width", 1280)
            vh = probe.get("height", 720)

            self.progress_changed.emit(25.0, "Нарезка и кодирование видеоиконки 256x256...")
            ok = ExpressProcessor.process_icon(
                src_vid=self.src_video,
                out_mp4=out_icon_mp4,
                out_thumb=out_icon_thumb,
                start_sec=self.start_sec,
                dur_sec=self.dur_sec,
                crop_pan_percent=self.crop_pan,
                video_w=vw,
                video_h=vh,
                codec=self.codec,
                on_progress=lambda p, s: self.progress_changed.emit(25.0 + p * 0.4, s)
            )
            if not ok or not out_icon_mp4.exists():
                raise RuntimeError("Не удалось создать видеоиконку.")

            # 2. Local Export Mode
            if not self.is_cloud_publish and self.export_dir:
                self.progress_changed.emit(85.0, "Сохранение файла на Switch...")
                self.export_dir.mkdir(parents=True, exist_ok=True)

                target_icon = self.export_dir / f"{self.title_id}.mp4"
                shutil.copy2(out_icon_mp4, target_icon)

                self.progress_changed.emit(100.0, "Готово! Видеоиконка сохранена.")
                self.finished_success.emit({"mode": "local", "path": str(target_icon)})
                return

            # 3. Cloud Publishing Mode
            if self.is_cloud_publish:
                self.progress_changed.emit(70.0, "Публикация в каталог H3H на Google Диск...")
                res = ExpressProcessor.publish_community_asset(
                    title_id=self.title_id,
                    game_name=self.game_name,
                    variant_name=self.variant_name or "Видеоиконка 4IFIR",
                    author=self.author,
                    category=self.category,
                    cover_mp4=None,
                    cover_thumb=out_icon_thumb,
                    icon_mp4=out_icon_mp4,
                    on_progress=lambda p, s: self.progress_changed.emit(p, s)
                )
                self.finished_success.emit(res)

        except Exception as e:
            self.finished_error.emit(str(e))


class IconsTab(QWidget):
    """
    Dedicated 4IFIR Video Icons Studio:
    - Search & Select Switch Game (Auto-completes from switch_titles_db.json)
    - Load Gameplay / Clip and crop 1:1 Video Icon with live preview & presets
    - 1-Click Cloud Publish to Google Drive & GitHub Catalog
    - Local Export directly to Switch SD (sdmc:/recordings/icons/<TitleID>.mp4)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.src_video_path: Optional[Path] = None
        self.titles_db: List[Dict[str, Any]] = OnlineFetcher._load_db()
        self.worker: Optional[IconWorkerThread] = None

        self._init_ui()
        self._init_video_player()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(16)

        # ==========================================
        # LEFT COLUMN: Parameters & Controls (Scrollable)
        # ==========================================
        left_scroll = QScrollArea(self)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_widget = QWidget(left_scroll)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(14)

        # Group 1: Game Identification
        grp_game = QGroupBox("🎮 1. Выбор игры (Switch Title ID)", left_widget)
        g_lay = QVBoxLayout(grp_game)
        g_lay.setSpacing(8)

        search_hdr = QLabel("Быстрый поиск по базе игр:", grp_game)
        search_hdr.setStyleSheet("color: #94A3B8; font-size: 11px;")
        g_lay.addWidget(search_hdr)

        self.search_input = QLineEdit(grp_game)
        self.search_input.setPlaceholderText("Введите название игры (напр. Mario, Zelda, Witcher, NFS)...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        g_lay.addWidget(self.search_input)

        self.db_combo = QComboBox(grp_game)
        self.db_combo.currentIndexChanged.connect(self._on_game_selected)
        g_lay.addWidget(self.db_combo)

        row_tid = QHBoxLayout()
        row_tid.addWidget(QLabel("Title ID игры:", grp_game))
        self.title_id_edit = QLineEdit(grp_game)
        self.title_id_edit.setPlaceholderText("0100000000010000 (16 шестн. знаков)")
        self.title_id_edit.setMaxLength(16)
        row_tid.addWidget(self.title_id_edit, 1)
        g_lay.addLayout(row_tid)

        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Имя игры:", grp_game))
        self.game_name_edit = QLineEdit(grp_game)
        self.game_name_edit.setPlaceholderText("Название игры для каталога")
        row_name.addWidget(self.game_name_edit, 1)
        g_lay.addLayout(row_name)

        self.game_status_lbl = QLabel("Статус: Игра не выбрана", grp_game)
        self.game_status_lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        g_lay.addWidget(self.game_status_lbl)

        left_layout.addWidget(grp_game)

        # Group 2: 4IFIR Video Icon Settings
        grp_video = QGroupBox("🎬 2. Исходное видео и кадрирование 1:1 (HEVC 256x256)", left_widget)
        v_lay = QVBoxLayout(grp_video)
        v_lay.setSpacing(10)

        # Online Search Button
        self.btn_online_search = QPushButton("🌐 Найти анимированные иконки онлайн (SteamGrid / Steam / Tenor)...", grp_video)
        self.btn_online_search.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #7C3AED);
                color: #FFFFFF;
                font-weight: bold;
                padding: 11px 16px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #3B82F6;
            }
        """)
        self.btn_online_search.clicked.connect(self._on_open_online_search)
        v_lay.addWidget(self.btn_online_search)

        v_btn_row = QHBoxLayout()
        self.btn_select_video = QPushButton("📁 Выбрать видеофайл с ПК...", grp_video)
        self.btn_select_video.setStyleSheet("background-color: #1F2937; font-weight: bold; padding: 9px 14px;")
        self.btn_select_video.clicked.connect(self._on_choose_source_video)
        v_btn_row.addWidget(self.btn_select_video)

        self.video_info_lbl = QLabel("Видео не выбрано", grp_video)
        self.video_info_lbl.setStyleSheet("color: #94A3B8; font-size: 12px;")
        v_btn_row.addWidget(self.video_info_lbl, 1)
        v_lay.addLayout(v_btn_row)

        # Pan slider
        pan_box = QVBoxLayout()
        pan_hdr_row = QHBoxLayout()
        pan_hdr_row.addWidget(QLabel("Кадрирование (Панорама 1:1):", grp_video))
        self.pan_val_lbl = QLabel("50% (Центр)", grp_video)
        self.pan_val_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        pan_hdr_row.addWidget(self.pan_val_lbl, 0, Qt.AlignRight)
        pan_box.addLayout(pan_hdr_row)

        self.pan_slider = QSlider(Qt.Horizontal, grp_video)
        self.pan_slider.setRange(0, 100)
        self.pan_slider.setValue(50)
        self.pan_slider.valueChanged.connect(self._on_pan_changed)
        pan_box.addWidget(self.pan_slider)
        v_lay.addLayout(pan_box)

        # Timing controls
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Старт (сек):", grp_video))
        self.start_spin = QDoubleSpinBox(grp_video)
        self.start_spin.setRange(0.0, 3600.0)
        self.start_spin.setSingleStep(0.5)
        self.start_spin.setValue(0.0)
        self.start_spin.valueChanged.connect(self._on_timing_changed)
        time_row.addWidget(self.start_spin)

        time_row.addWidget(QLabel("Длина (сек):", grp_video))
        self.dur_spin = QDoubleSpinBox(grp_video)
        self.dur_spin.setRange(1.0, 30.0)
        self.dur_spin.setSingleStep(0.5)
        self.dur_spin.setValue(6.0)
        self.dur_spin.valueChanged.connect(self._on_timing_changed)
        time_row.addWidget(self.dur_spin)
        v_lay.addLayout(time_row)

        # Fast Presets
        presets_row = QHBoxLayout()
        presets_row.addWidget(QLabel("Быстрые пресеты длины:", grp_video))
        for sec in [2, 4, 6, 8, 10]:
            btn_p = QPushButton(f"{sec}с", grp_video)
            btn_p.setStyleSheet("padding: 5px 10px; font-size: 12px;")
            btn_p.clicked.connect(lambda _, s=sec: self.dur_spin.setValue(float(s)))
            presets_row.addWidget(btn_p)
        v_lay.addLayout(presets_row)

        # Codec choice
        codec_row = QHBoxLayout()
        codec_row.addWidget(QLabel("Кодек видеоиконки:", grp_video))
        self.codec_combo = QComboBox(grp_video)
        self.codec_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.codec_combo.setMinimumContentsLength(15)
        self.codec_combo.addItem("HEVC (H.265) — 24fps (Стандарт 4IFIR, рекомендуется)", "hevc")
        self.codec_combo.addItem("H.264 / AVC — 30fps (Совместимость)", "h264")
        codec_row.addWidget(self.codec_combo, 1)
        v_lay.addLayout(codec_row)

        left_layout.addWidget(grp_video)

        # Group 3: Publishing & Export
        grp_action = QGroupBox("🚀 3. Публикация и Сохранение", left_widget)
        a_lay = QVBoxLayout(grp_action)
        a_lay.setSpacing(10)

        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("Название варианта:", grp_action))
        self.var_name_edit = QLineEdit("Главная тема (Иконка)", grp_action)
        meta_row.addWidget(self.var_name_edit, 1)

        meta_row.addWidget(QLabel("Автор:", grp_action))
        self.author_edit = QLineEdit("@Community", grp_action)
        meta_row.addWidget(self.author_edit, 1)

        meta_row.addWidget(QLabel("Каталог:", grp_action))
        self.cat_combo = QComboBox(grp_action)
        self.cat_combo.addItem("Стандартный", "standard")
        self.cat_combo.addItem("After Dark (18+)", "after_dark")
        meta_row.addWidget(self.cat_combo)
        a_lay.addLayout(meta_row)

        self.btn_publish = QPushButton("🚀 Опубликовать в общее облако H3H (Google Диск + Каталог)", grp_action)
        self.btn_publish.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #00E5FF);
                color: #0E1217;
                font-weight: bold;
                font-size: 14px;
                padding: 12px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #00E5FF;
            }
        """)
        self.btn_publish.clicked.connect(self._on_publish_clicked)
        a_lay.addWidget(self.btn_publish)

        self.btn_export_local = QPushButton("💾 Сохранить прямо на Switch (sdmc:/recordings/icons/)", grp_action)
        self.btn_export_local.setStyleSheet("background-color: #3B82F6; font-weight: bold; font-size: 13px; padding: 10px 16px;")
        self.btn_export_local.clicked.connect(self._on_export_local_clicked)
        a_lay.addWidget(self.btn_export_local)

        self.progress_bar = QProgressBar(grp_action)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        a_lay.addWidget(self.progress_bar)

        self.status_log_lbl = QLabel("", grp_action)
        self.status_log_lbl.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 12px;")
        a_lay.addWidget(self.status_log_lbl)

        left_layout.addWidget(grp_action)
        left_layout.addStretch()

        left_scroll.setWidget(left_widget)
        main_layout.addWidget(left_scroll, 1)

        # ==========================================
        # RIGHT COLUMN: Live 1:1 Video Icon Preview
        # ==========================================
        right_panel = QFrame(self)
        right_panel.setFixedWidth(320)
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #141A23;
                border: 1px solid #232B36;
                border-radius: 8px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(12)

        lbl_vid_header = QLabel("🔲 Превью видеоиконки 4IFIR (1:1)", right_panel)
        lbl_vid_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lbl_vid_header.setStyleSheet("color: #00E5FF; border: none;")
        right_layout.addWidget(lbl_vid_header)

        self.video_widget = QVideoWidget(right_panel)
        self.video_widget.setFixedSize(280, 280)
        self.video_widget.setStyleSheet("""
            QVideoWidget {
                background-color: #000000;
                border: 2px solid #00E5FF;
                border-radius: 16px;
            }
        """)
        right_layout.addWidget(self.video_widget, 0, Qt.AlignCenter)

        # Player Controls
        ctrl_row = QHBoxLayout()
        self.btn_play = QPushButton("▶", right_panel)
        self.btn_play.setFixedWidth(40)
        self.btn_play.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹", right_panel)
        self.btn_stop.setFixedWidth(40)
        self.btn_stop.clicked.connect(self._stop_play)
        ctrl_row.addWidget(self.btn_stop)

        self.time_lbl = QLabel("00:00 / 00:00", right_panel)
        self.time_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; border: none;")
        ctrl_row.addWidget(self.time_lbl, 1, Qt.AlignRight)
        right_layout.addLayout(ctrl_row)

        self.player_slider = QSlider(Qt.Horizontal, right_panel)
        self.player_slider.setRange(0, 1000)
        self.player_slider.sliderMoved.connect(self._on_slider_seek)
        right_layout.addWidget(self.player_slider)

        info_card = QFrame(right_panel)
        info_card.setStyleSheet("""
            QFrame {
                background-color: #0E1217;
                border: 1px solid #1F2937;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        ic_lay = QVBoxLayout(info_card)
        ic_lay.setSpacing(4)
        ic_lay.setContentsMargins(6, 6, 6, 6)

        t1 = QLabel("📐 <b>Разрешение:</b> 256×256 (Квадрат 1:1)", info_card)
        t1.setStyleSheet("color: #E2E8F0; font-size: 11px; border: none;")
        ic_lay.addWidget(t1)

        t2 = QLabel("🎞️ <b>Кодек:</b> HEVC / H.265 (24 FPS)", info_card)
        t2.setStyleSheet("color: #E2E8F0; font-size: 11px; border: none;")
        ic_lay.addWidget(t2)

        t3 = QLabel("📁 <b>Путь на SD:</b><br><code style='color: #00E5FF;'>sdmc:/recordings/icons/&lt;TitleID&gt;.mp4</code>", info_card)
        t3.setStyleSheet("color: #94A3B8; font-size: 10px; border: none;")
        t3.setWordWrap(True)
        ic_lay.addWidget(t3)

        t4 = QLabel("💡 <i>Видеоиконка зацикливается в меню Switch автоматически без звука.</i>", info_card)
        t4.setStyleSheet("color: #64748B; font-size: 10px; border: none;")
        t4.setWordWrap(True)
        ic_lay.addWidget(t4)

        right_layout.addWidget(info_card)
        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        # Populate top games in combo
        self._populate_games_combo(self.titles_db[:50])

    def _init_video_player(self):
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setMuted(True)  # Video icons in 4IFIR are silent
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)

    # ==========================================
    # LOGIC & HANDLERS
    # ==========================================
    def _populate_games_combo(self, games: List[Dict[str, Any]]):
        self.db_combo.blockSignals(True)
        self.db_combo.clear()
        self.db_combo.addItem("-- Выберите найденную игру --", None)
        for g in games:
            name = g.get("name") or g.get("title") or "Unknown"
            tid = (g.get("id") or g.get("titleId") or "").upper()
            self.db_combo.addItem(f"{name} ({tid})", g)
        self.db_combo.blockSignals(False)

    def _on_search_text_changed(self, text: str):
        query = text.strip().lower()
        if not query:
            self._populate_games_combo(self.titles_db[:50])
            return

        matches = []
        for g in self.titles_db:
            name = (g.get("name") or g.get("title") or "").lower()
            tid = (g.get("id") or g.get("titleId") or "").lower()
            if query in name or query in tid:
                matches.append(g)
                if len(matches) >= 50:
                    break
        self._populate_games_combo(matches)
        if matches:
            self._on_game_selected(0)

    def _on_game_selected(self, index: int):
        if index < 0 or index >= self.db_combo.count():
            return
        g = self.db_combo.itemData(index)
        if not g:
            return

        tid = (g.get("id") or g.get("titleId") or "").upper()
        name = g.get("name") or g.get("title") or ""

        self.title_id_edit.setText(tid)
        self.game_name_edit.setText(name)
        self.game_status_lbl.setText(f"Выбрана игра: {name} [{tid}]")
        self.game_status_lbl.setStyleSheet("color: #34D399; font-size: 11px;")

    def _on_open_online_search(self):
        query = self.game_name_edit.text().strip() or self.search_input.text().strip()
        self._online_dlg = OnlineIconsDialog(self, initial_query=query)
        self._online_dlg.icon_chosen.connect(self._on_online_icon_loaded)
        self._online_dlg.exec()

    def _on_online_icon_loaded(self, mp4_path: Path, title: str):
        self.src_video_path = Path(mp4_path).resolve()
        self.video_info_lbl.setText(f"🌐 Онлайн: {self.src_video_path.name}")
        self.video_info_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        if title and (not self.var_name_edit.text() or self.var_name_edit.text() == "Главная тема (Иконка)"):
            self.var_name_edit.setText(title[:40])

        self.player.setSource(QUrl.fromLocalFile(str(self.src_video_path)))
        self.player.play()
        self.btn_play.setText("⏸")

    def _on_choose_source_video(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Выберите видео для создания видеоиконки", "", "Video files (*.mp4 *.mkv *.avi *.webm *.mov)"
        )
        if fn:
            self.src_video_path = Path(fn)
            self.video_info_lbl.setText(f"{self.src_video_path.name}")
            self.video_info_lbl.setStyleSheet("color: #10B981; font-weight: bold;")

            self.player.setSource(QUrl.fromLocalFile(str(self.src_video_path)))
            self.player.play()
            self.btn_play.setText("⏸")

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶")
        else:
            self.player.play()
            self.btn_play.setText("⏸")

    def _stop_play(self):
        self.player.stop()
        self.btn_play.setText("▶")

    def _on_player_position_changed(self, pos_ms: int):
        dur_ms = self.player.duration()
        if dur_ms > 0:
            self.player_slider.blockSignals(True)
            self.player_slider.setValue(int(pos_ms * 1000 / dur_ms))
            self.player_slider.blockSignals(False)

        cur_sec = pos_ms // 1000
        tot_sec = dur_ms // 1000 if dur_ms > 0 else 0
        self.time_lbl.setText(f"{cur_sec//60:02d}:{cur_sec%60:02d} / {tot_sec//60:02d}:{tot_sec%60:02d}")

    def _on_player_duration_changed(self, dur_ms: int):
        tot_sec = dur_ms // 1000
        cur_sec = self.player.position() // 1000
        self.time_lbl.setText(f"{cur_sec//60:02d}:{cur_sec%60:02d} / {tot_sec//60:02d}:{tot_sec%60:02d}")

    def _on_slider_seek(self, val: int):
        dur_ms = self.player.duration()
        if dur_ms > 0:
            seek_ms = int(val * dur_ms / 1000)
            self.player.setPosition(seek_ms)

    def _on_pan_changed(self, val: int):
        if val == 50:
            self.pan_val_lbl.setText("50% (Центр)")
        elif val < 50:
            self.pan_val_lbl.setText(f"{val}% (Слева)")
        else:
            self.pan_val_lbl.setText(f"{val}% (Справа)")

    def _on_timing_changed(self):
        start = self.start_spin.value()
        if self.player.duration() > 0:
            self.player.setPosition(int(start * 1000))

    def _validate_inputs(self) -> bool:
        tid = self.title_id_edit.text().strip().upper()
        if len(tid) != 16 or not all(c in "0123456789ABCDEF" for c in tid):
            QMessageBox.warning(self, "Ошибка", "Укажите корректный 16-значный Title ID (например: 0100000000010000).")
            return False
        if not self.src_video_path or not self.src_video_path.exists():
            QMessageBox.warning(self, "Ошибка", "Выберите исходный видеофайл для нарезки видеоиконки.")
            return False
        return True

    def _on_publish_clicked(self):
        if not self._validate_inputs():
            return

        self._start_worker(is_cloud_publish=True)

    def _on_export_local_clicked(self):
        if not self._validate_inputs():
            return

        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку для сохранения (напр. sdmc:/recordings/icons/)"
        )
        if not folder:
            return

        self._start_worker(is_cloud_publish=False, export_dir=Path(folder))

    def _start_worker(self, is_cloud_publish: bool, export_dir: Optional[Path] = None):
        self.btn_publish.setEnabled(False)
        self.btn_export_local.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_log_lbl.setText("Запуск обработки...")

        self.worker = IconWorkerThread(
            title_id=self.title_id_edit.text().strip().upper(),
            game_name=self.game_name_edit.text().strip() or "Unknown Game",
            variant_name=self.var_name_edit.text().strip() or "Видеоиконка 4IFIR",
            author=self.author_edit.text().strip() or "@Community",
            category=self.cat_combo.currentData(),
            src_video=self.src_video_path,
            start_sec=self.start_spin.value(),
            dur_sec=self.dur_spin.value(),
            crop_pan=float(self.pan_slider.value()),
            codec=self.codec_combo.currentData(),
            is_cloud_publish=is_cloud_publish,
            export_dir=export_dir
        )
        self.worker.progress_changed.connect(self._on_worker_progress)
        self.worker.finished_success.connect(self._on_worker_success)
        self.worker.finished_error.connect(self._on_worker_error)
        self.worker.start()

    def _on_worker_progress(self, pct: float, msg: str):
        self.progress_bar.setValue(int(pct))
        self.status_log_lbl.setText(msg)

    def _on_worker_success(self, res: dict):
        self.progress_bar.setValue(100)
        self.btn_publish.setEnabled(True)
        self.btn_export_local.setEnabled(True)

        if res.get("mode") == "local":
            self.status_log_lbl.setText("✔ Успешно сохранено для Switch!")
            QMessageBox.information(self, "Готово", f"Файл видеоиконки успешно сохранен:\n{res.get('path')}")
        else:
            self.status_log_lbl.setText("✔ Успешно опубликовано в облако!")
            QMessageBox.information(
                self, "Успешная публикация",
                f"Видеоиконка успешно опубликована в облако H3H!\n\nИгра: {self.game_name_edit.text()}\nTitle ID: {self.title_id_edit.text()}\nКаталог обновлен."
            )

    def _on_worker_error(self, err: str):
        self.progress_bar.setVisible(False)
        self.btn_publish.setEnabled(True)
        self.btn_export_local.setEnabled(True)
        self.status_log_lbl.setText(f"Ошибка: {err}")
        QMessageBox.critical(self, "Ошибка создания иконки", f"Произошла ошибка при обработке:\n\n{err}")
