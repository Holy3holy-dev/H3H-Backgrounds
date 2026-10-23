"""
H3H Studio Express Tab — Simplified 1-Click Publisher for Community Users:
- Search Nintendo Switch games by name, Russian alias, or Title ID
- Choose video source
- Select type: Video Cover (720p), Video Icon (256x256 HEVC), or Full Pack (Both)
- Interactive visual 1:1 square crop tool for video icons
- 1-Click Cloud Publishing to Google Drive & GitHub with embedded permanent credentials
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple

from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer, QStringListModel
from PySide6.QtGui import QFont, QPixmap, QImage, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QSlider, QDoubleSpinBox,
    QProgressBar, QMessageBox, QFileDialog, QFrame, QScrollArea,
    QCompleter, QGroupBox
)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.title_id_resolver import TitleIdResolver
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
                self.progress.emit(10.0, "1/3: Кодирование фонового видео 720p 30fps...")
                cover_mp4 = temp_dir / f"{self.title_id}_cover.mp4"
                cover_thumb = temp_dir / f"{self.title_id}_cover.jpg"
                ExpressProcessor.process_cover(
                    src_vid=self.src_video,
                    out_mp4=cover_mp4,
                    out_thumb=cover_thumb,
                    start_sec=self.start_sec,
                    dur_sec=self.dur_sec,
                    codec="h264",
                    keep_audio=True
                )

            # 2. Generate Icon if requested
            if self.mode in ("icon", "both"):
                self.progress.emit(35.0, "2/3: Кадрирование и сжатие видеоиконки 256x256 HEVC...")
                icon_mp4 = temp_dir / f"{self.title_id}_icon.mp4"
                icon_thumb = temp_dir / f"{self.title_id}_icon.jpg"
                ExpressProcessor.process_icon(
                    src_vid=self.src_video,
                    out_mp4=icon_mp4,
                    out_thumb=icon_thumb,
                    start_sec=self.start_sec,
                    dur_sec=min(12.0, self.dur_sec),
                    crop_pan_percent=self.crop_pan,
                    video_w=self.video_w,
                    video_h=self.video_h,
                    codec="hevc"
                )

            # 3. Publish to Cloud
            self.progress.emit(65.0, "3/3: Загрузка в облако Google Drive и регистрация...")
            res = ExpressProcessor.publish_community_asset(
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

        self.worker: Optional[PublishWorker] = None

        self._init_ui()

    def _init_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        # --- STEP 1: Game Selection ---
        step1_box = self._create_card("1. Выбор игры для Nintendo Switch", "#00E5FF")
        s1_layout = QVBoxLayout(step1_box)

        search_row = QHBoxLayout()
        self.game_search_edit = QLineEdit(self)
        self.game_search_edit.setPlaceholderText("🔍 Введите название игры, персонажа, сленг или 16-значный Title ID (например: Zelda, Mario, Witcher 3, Cyberpunk, 0100F2C0115B6000)...")
        self.game_search_edit.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.game_search_edit)

        s1_layout.addLayout(search_row)

        # Game Info Display Badge
        self.game_info_frame = QFrame(self)
        self.game_info_frame.setStyleSheet("""
            QFrame {
                background-color: #1A222D;
                border: 1px solid #2D3A4B;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        g_info_layout = QHBoxLayout(self.game_info_frame)
        self.game_badge_label = QLabel("🎮 <b>Игра не выбрана</b> — начните вводить название выше", self)
        self.game_badge_label.setStyleSheet("color: #9AA4B2; font-size: 13px;")
        g_info_layout.addWidget(self.game_badge_label)
        s1_layout.addWidget(self.game_info_frame)

        layout.addWidget(step1_box)

        # --- STEP 2: Video Selection ---
        step2_box = self._create_card("2. Выберите исходный видеоролик", "#3B82F6")
        s2_layout = QVBoxLayout(step2_box)

        file_row = QHBoxLayout()
        self.file_path_edit = QLineEdit(self)
        self.file_path_edit.setPlaceholderText("Перетащите видеофайл сюда (Drag & Drop) или нажмите Обзор... (MP4, WEBM, MOV, MKV)")
        self.file_path_edit.setReadOnly(True)
        browse_btn = QPushButton("📁 Обзор...", self)
        browse_btn.clicked.connect(self._browse_video)
        file_row.addWidget(self.file_path_edit)
        file_row.addWidget(browse_btn)
        s2_layout.addLayout(file_row)

        self.video_details_lbl = QLabel("", self)
        self.video_details_lbl.setStyleSheet("color: #00E5FF; font-size: 12px; margin-top: 4px;")
        s2_layout.addWidget(self.video_details_lbl)

        layout.addWidget(step2_box)

        # --- STEP 3: Content Mode Selection ---
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

        # --- STEP 4: Interactive Cropping & Preview ---
        self.crop_box = self._create_card("4. Настройка кадрирования и тайминга", "#EC4899")
        s4_layout = QVBoxLayout(self.crop_box)

        # Time range controls
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Начало (сек):", self))
        self.start_spin = QDoubleSpinBox(self)
        self.start_spin.setRange(0.0, 3600.0)
        self.start_spin.setValue(0.0)
        self.start_spin.setSingleStep(0.5)
        self.start_spin.valueChanged.connect(self._update_preview_frame)
        time_row.addWidget(self.start_spin)

        time_row.addWidget(QLabel("Длительность (сек):", self))
        self.dur_spin = QDoubleSpinBox(self)
        self.dur_spin.setRange(2.0, 30.0)
        self.dur_spin.setValue(8.0)
        self.dur_spin.setSingleStep(1.0)
        time_row.addWidget(self.dur_spin)
        time_row.addStretch()

        s4_layout.addLayout(time_row)

        # Preview Container (Wide Cover preview + 1:1 Icon preview)
        previews_row = QHBoxLayout()

        # Cover Preview Box
        cover_col = QVBoxLayout()
        cover_col.addWidget(QLabel("<b>Превью фонового кадра (16:9):</b>", self))
        self.cover_preview_lbl = QLabel(self)
        self.cover_preview_lbl.setFixedSize(384, 216)
        self.cover_preview_lbl.setStyleSheet("background-color: #0E1217; border: 1px solid #2D3A4B; border-radius: 6px;")
        self.cover_preview_lbl.setAlignment(Qt.AlignCenter)
        self.cover_preview_lbl.setText("Превью видео")
        cover_col.addWidget(self.cover_preview_lbl)
        previews_row.addLayout(cover_col)

        # Icon Preview Box (with 1:1 square preview)
        self.icon_col = QVBoxLayout()
        self.icon_col.addWidget(QLabel("<b>Превью видеоиконки 4IFIR (1:1):</b>", self))
        self.icon_preview_lbl = QLabel(self)
        self.icon_preview_lbl.setFixedSize(216, 216)
        self.icon_preview_lbl.setStyleSheet("background-color: #0E1217; border: 2px solid #00E5FF; border-radius: 8px;")
        self.icon_preview_lbl.setAlignment(Qt.AlignCenter)
        self.icon_preview_lbl.setText("Квадрат 1:1")
        self.icon_col.addWidget(self.icon_preview_lbl)
        previews_row.addLayout(self.icon_col)

        previews_row.addStretch()
        s4_layout.addLayout(previews_row)

        # Pan slider for square crop
        self.pan_control_widget = QWidget(self)
        pan_layout = QVBoxLayout(self.pan_control_widget)
        pan_layout.setContentsMargins(0, 8, 0, 0)

        pan_header = QHBoxLayout()
        pan_header.addWidget(QLabel("<b>Горизонтальное кадрирование иконки:</b>", self))
        self.pan_percent_lbl = QLabel("50% (По центру)", self)
        self.pan_percent_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        pan_header.addWidget(self.pan_percent_lbl)
        pan_header.addStretch()

        btn_left = QPushButton("◀ Влево (0%)", self)
        btn_left.clicked.connect(lambda: self.crop_slider.setValue(0))
        btn_center = QPushButton("• По центру (50%)", self)
        btn_center.clicked.connect(lambda: self.crop_slider.setValue(50))
        btn_right = QPushButton("▶ Вправо (100%)", self)
        btn_right.clicked.connect(lambda: self.crop_slider.setValue(100))

        pan_header.addWidget(btn_left)
        pan_header.addWidget(btn_center)
        pan_header.addWidget(btn_right)
        pan_layout.addLayout(pan_header)

        self.crop_slider = QSlider(Qt.Horizontal, self)
        self.crop_slider.setRange(0, 100)
        self.crop_slider.setValue(50)
        self.crop_slider.valueChanged.connect(self._on_crop_slider_changed)
        pan_layout.addWidget(self.crop_slider)

        s4_layout.addWidget(self.pan_control_widget)
        layout.addWidget(self.crop_box)

        # --- STEP 5: Metadata & Publish ---
        step5_box = self._create_card("5. Автор и Публикация в каталог", "#10B981")
        s5_layout = QVBoxLayout(step5_box)

        meta_grid = QHBoxLayout()

        # Variant Name
        v_col = QVBoxLayout()
        v_col.addWidget(QLabel("Название варианта темы:", self))
        self.var_name_edit = QLineEdit(self)
        self.var_name_edit.setPlaceholderText("Например: Dynamic Action, Title Screen, Neon Blade")
        self.var_name_edit.setText("Dynamic Theme")
        v_col.addWidget(self.var_name_edit)
        meta_grid.addLayout(v_col, 2)

        # Author Handle
        a_col = QVBoxLayout()
        a_col.addWidget(QLabel("Ваш ник / Автор (для титров):", self))
        self.author_edit = QLineEdit(self)
        saved_author = self.settings.value("author_name", "Community")
        self.author_edit.setText(saved_author)
        self.author_edit.setPlaceholderText("@username")
        a_col.addWidget(self.author_edit)
        meta_grid.addLayout(a_col, 1)

        # Category
        c_col = QVBoxLayout()
        c_col.addWidget(QLabel("Каталог назначения:", self))
        self.category_combo = QComboBox(self)
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

        main_vbox = QVBoxLayout(self)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.addWidget(scroll)

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

    # --- Search & Title Resolution ---

    def _on_search_text_changed(self, text: str):
        query = text.strip()
        if not query:
            self.selected_title_id = ""
            self.selected_game_name = ""
            self.game_badge_label.setText("🎮 <b>Игра не выбрана</b> — начните вводить название выше")
            return

        # Direct Title ID
        tid = TitleIdResolver.extract_title_id(query)
        if tid:
            resolved_name = self.resolver.resolve_by_title_id(tid) or f"Игра ({tid})"
            self.selected_title_id = tid
            self.selected_game_name = resolved_name
            self.game_badge_label.setText(f"🎯 <b>Определён Title ID:</b> <code>{tid}</code> — <b>{resolved_name}</b>")
            return

        # Fuzzy lookup
        matches = self.resolver.resolve_multiple(query, limit=1)
        if matches:
            top_tid, top_name, _ = matches[0]
            self.selected_title_id = top_tid
            self.selected_game_name = top_name
            self.game_badge_label.setText(f"🎯 <b>Найдено:</b> <b>{top_name}</b> (<code>{top_tid}</code>)")
        else:
            self.selected_title_id = ""
            self.selected_game_name = ""
            self.game_badge_label.setText("⚠️ Совпадений не найдено. Проверьте запрос или введите 16-значный Title ID напрямую.")

    # --- File Selection & Drag & Drop ---

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
            self.selected_title_id = detected_tid
            self.selected_game_name = resolved
            self.game_search_edit.setText(detected_tid)
            self.game_badge_label.setText(f"🎯 <b>Определён Title ID из имени файла:</b> <code>{detected_tid}</code> — <b>{resolved}</b>")

        # Auto-suggest variant name from filename
        stem = path.stem
        clean_name = stem.replace("_", " ").replace("-", " ").title()
        if len(clean_name) >= 3 and not self.var_name_edit.text() or self.var_name_edit.text() == "Dynamic Theme":
            self.var_name_edit.setText(clean_name)

        # Update preview
        self.start_spin.setRange(0.0, max(0.0, dur - 2.0))
        self.dur_spin.setRange(2.0, min(30.0, dur))
        self._update_preview_frame()

    # --- Mode & Cropping ---

    def _on_mode_changed(self):
        show_icon = not self.radio_cover.isChecked()
        self.pan_control_widget.setVisible(show_icon)
        self.icon_preview_lbl.setVisible(show_icon)
        if hasattr(self, "icon_col"):
            for i in range(self.icon_col.count()):
                w = self.icon_col.itemAt(i).widget()
                if w:
                    w.setVisible(show_icon)

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

    def _update_preview_frame(self):
        if not self.current_video_path or not self.current_video_path.exists():
            return

        ts = self.start_spin.value()
        ok = ExpressProcessor.extract_preview_frame(self.current_video_path, ts, self.temp_frame_path)
        if ok and self.temp_frame_path.exists():
            pix = QPixmap(str(self.temp_frame_path))
            if not pix.isNull():
                self.cover_preview_lbl.setPixmap(
                    pix.scaled(self.cover_preview_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                self._update_icon_crop_preview(pix)

    def _update_icon_crop_preview(self, source_pixmap: Optional[QPixmap] = None):
        if not self.temp_frame_path.exists():
            return
        pix = source_pixmap or QPixmap(str(self.temp_frame_path))
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
            cropped.scaled(216, 216, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        )

    # --- Publishing Pipeline ---

    def _start_publishing(self):
        if not self.current_video_path or not self.current_video_path.exists():
            QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите исходный видеоролик.")
            return

        if not self.selected_title_id:
            QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите игру из списка или укажите точный 16-значный Title ID.")
            return

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
