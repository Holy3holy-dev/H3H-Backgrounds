"""
Switch Home UI Preview Dialog for H3H Studio.
Displays video background in native 1280x720 resolution with the official
Nintendo Switch Home Menu UI overlay (switch_home_template.png) to verify
that characters, action, and text are not occluded by game tiles or system icons.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QFrame, QCheckBox, QGraphicsOpacityEffect,
    QApplication
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


class SwitchHomePreviewDialog(QDialog):
    """
    Dedicated 1280x720 Switch Home Preview with semi-transparent UI template overlay.
    Allows adjusting overlay opacity, seeking through video, and toggling UI elements.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        video_path: Optional[Path] = None,
        start_sec: float = 0.0,
        dur_sec: float = 8.0,
        volume: float = 1.0
    ):
        super().__init__(parent)
        self.video_path = video_path
        self.start_ms = int(start_sec * 1000)
        self.end_ms = int((start_sec + dur_sec) * 1000)
        self.dur_ms = max(1000, self.end_ms - self.start_ms)
        self.initial_volume = volume

        self.setWindowTitle("🎮 Предпросмотр видеофона в интерфейсе Nintendo Switch")
        self.setStyleSheet("""
            QDialog {
                background-color: #0A0D12;
                color: #FFFFFF;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QPushButton {
                background-color: #1F2937;
                border: 1px solid #374151;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 13px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #374151;
                border-color: #4B5563;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1F2937;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00E5FF;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                background: #FFFFFF;
                border: 2px solid #00E5FF;
                border-radius: 7px;
            }
            QCheckBox {
                color: #E2E8F0;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #4B5563;
                background: #1F2937;
            }
            QCheckBox::indicator:checked {
                background: #00E5FF;
                border-color: #00E5FF;
            }
        """)

        # Determine optimal viewport size based on screen
        self.viewport_w = 1280
        self.viewport_h = 720
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            max_w = avail.width() - 60
            max_h = avail.height() - 120
            if self.viewport_w > max_w or self.viewport_h > max_h:
                scale = min(max_w / self.viewport_w, max_h / self.viewport_h)
                scale = max(0.55, min(1.0, scale))
                self.viewport_w = int(1280 * scale)
                self.viewport_h = int(720 * scale)

        self._init_ui()
        self._init_player()

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle_playback)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # Header info
        hdr_row = QHBoxLayout()
        hdr_title = QLabel("🎮 Тест перекрытий интерфейсом Switch Home", self)
        hdr_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        hdr_title.setStyleSheet("color: #00E5FF;")
        hdr_row.addWidget(hdr_title)

        hdr_hint = QLabel("Проверьте, не перекрываются ли персонажи и логотипы плитками игр или нижней панелью", self)
        hdr_hint.setStyleSheet("color: #94A3B8; font-size: 12px;")
        hdr_row.addWidget(hdr_hint, 1, Qt.AlignLeft | Qt.AlignVCenter)

        hdr_res = QLabel(f"Разрешение: {self.viewport_w}×{self.viewport_h} (16:9)", self)
        hdr_res.setStyleSheet("color: #64748B; font-size: 11px;")
        hdr_row.addWidget(hdr_res)
        main_layout.addLayout(hdr_row)

        # Video viewport container
        self.viewport_frame = QFrame(self)
        self.viewport_frame.setFixedSize(self.viewport_w, self.viewport_h)
        self.viewport_frame.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: 2px solid #232B36;
                border-radius: 8px;
            }
        """)

        # Video Widget inside container
        self.video_widget = QVideoWidget(self.viewport_frame)
        self.video_widget.setGeometry(0, 0, self.viewport_w, self.viewport_h)

        # Overlay Label
        self.overlay_lbl = QLabel(self.viewport_frame)
        self.overlay_lbl.setGeometry(0, 0, self.viewport_w, self.viewport_h)
        self.overlay_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay_lbl.setStyleSheet("background: transparent;")

        # Load Template
        tmpl_path = Path(__file__).parent.parent / "data" / "switch_home_template.png"
        if tmpl_path.exists():
            pix = QPixmap(str(tmpl_path)).scaled(
                self.viewport_w, self.viewport_h,
                Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
            self.overlay_lbl.setPixmap(pix)

        self.opacity_effect = QGraphicsOpacityEffect(self.overlay_lbl)
        self.opacity_effect.setOpacity(0.85)
        self.overlay_lbl.setGraphicsEffect(self.opacity_effect)
        self.overlay_lbl.raise_()

        main_layout.addWidget(self.viewport_frame, 0, Qt.AlignCenter)

        # Scrubber bar
        scrubber_row = QHBoxLayout()
        scrubber_row.setSpacing(10)

        self.btn_play_pause = QPushButton("⏸ Пауза", self)
        self.btn_play_pause.setFixedWidth(90)
        self.btn_play_pause.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #EC4899);
                font-weight: bold;
                border: none;
            }
        """)
        self.btn_play_pause.clicked.connect(self._toggle_playback)
        scrubber_row.addWidget(self.btn_play_pause)

        self.scrubber = QSlider(Qt.Horizontal, self)
        self.scrubber.setRange(0, 1000)
        self.scrubber.sliderMoved.connect(self._on_scrubber_dragged)
        scrubber_row.addWidget(self.scrubber, 1)

        self.time_lbl = QLabel("0.0с / 8.0с", self)
        self.time_lbl.setStyleSheet("color: #94A3B8; font-family: monospace; font-size: 12px;")
        scrubber_row.addWidget(self.time_lbl)
        main_layout.addLayout(scrubber_row)

        # Bottom Tools & Settings Row
        tools_row = QHBoxLayout()
        tools_row.setSpacing(16)

        # Checkbox overlay visibility
        self.chk_overlay = QCheckBox("🎮 Показывать интерфейс Switch Home", self)
        self.chk_overlay.setChecked(True)
        self.chk_overlay.toggled.connect(self._on_toggle_overlay)
        tools_row.addWidget(self.chk_overlay)

        # Opacity slider
        lbl_op = QLabel("Прозрачность сетки:", self)
        lbl_op.setStyleSheet("color: #94A3B8; font-size: 12px;")
        tools_row.addWidget(lbl_op)

        self.opacity_slider = QSlider(Qt.Horizontal, self)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(85)
        self.opacity_slider.setFixedWidth(140)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        tools_row.addWidget(self.opacity_slider)

        self.opacity_val_lbl = QLabel("85%", self)
        self.opacity_val_lbl.setStyleSheet("color: #00E5FF; font-size: 12px; font-weight: bold;")
        tools_row.addWidget(self.opacity_val_lbl)

        tools_row.addStretch()

        # Close button
        btn_close = QPushButton("Закрыть [Esc]", self)
        btn_close.clicked.connect(self.close)
        tools_row.addWidget(btn_close)

        main_layout.addLayout(tools_row)

    def _init_player(self):
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(self.initial_volume)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

        if self.video_path and self.video_path.exists():
            self.player.setSource(QUrl.fromLocalFile(str(self.video_path.resolve())))
            self.player.setPosition(self.start_ms)
            self.player.play()

    def _toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            cur = self.player.position()
            if cur < self.start_ms or cur >= self.end_ms:
                self.player.setPosition(self.start_ms)
            self.player.play()

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play_pause.setText("⏸ Пауза")
        else:
            self.btn_play_pause.setText("▶ Пуск")

    def _on_position_changed(self, pos: int):
        if pos >= self.end_ms or pos < self.start_ms:
            self.player.setPosition(self.start_ms)
            pos = self.start_ms

        rel_ms = max(0, pos - self.start_ms)
        percent = (rel_ms / float(self.dur_ms)) * 1000.0 if self.dur_ms > 0 else 0
        if not self.scrubber.isSliderDown():
            self.scrubber.setValue(int(percent))

        cur_sec = rel_ms / 1000.0
        tot_sec = self.dur_ms / 1000.0
        self.time_lbl.setText(f"{cur_sec:.1f}с / {tot_sec:.1f}с")

    def _on_scrubber_dragged(self, val: int):
        target_ms = self.start_ms + int((val / 1000.0) * self.dur_ms)
        self.player.setPosition(target_ms)

    def _on_toggle_overlay(self, checked: bool):
        self.overlay_lbl.setVisible(checked)

    def _on_opacity_changed(self, val: int):
        self.opacity_effect.setOpacity(val / 100.0)
        self.opacity_val_lbl.setText(f"{val}%")

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
