"""
Add Switch Home UI Overlay and 1280x720 Preview Dialog to ExpressTab.
"""
from pathlib import Path

def patch_express_tab():
    path = Path("studio/h3h_studio/ui/express_tab.py")
    content = path.read_text(encoding="utf-8")

    # 1. Add QCheckBox, QGraphicsOpacityEffect to imports
    old_imports = """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QSlider, QDoubleSpinBox,
    QProgressBar, QMessageBox, QFileDialog, QFrame, QScrollArea,
    QGroupBox, QSizePolicy
)"""

    new_imports = """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QSlider, QDoubleSpinBox,
    QProgressBar, QMessageBox, QFileDialog, QFrame, QScrollArea,
    QGroupBox, QSizePolicy, QCheckBox, QGraphicsOpacityEffect
)
from .switch_preview_dialog import SwitchHomePreviewDialog"""

    if old_imports in content:
        content = content.replace(old_imports, new_imports, 1)

    # 2. Add switch_mini_overlay inside video_viewport_frame
    old_viewport = """        self.video_placeholder_lbl = QLabel("Загрузите видео в Шаге 2\\nдля включения живого плеера", self.video_viewport_frame)
        self.video_placeholder_lbl.setAlignment(Qt.AlignCenter)
        self.video_placeholder_lbl.setStyleSheet("color: #6B7280; font-size: 13px; font-weight: bold; background: transparent;")
        viewport_layout.addWidget(self.video_placeholder_lbl)

        cover_col.addWidget(self.video_viewport_frame)"""

    new_viewport = """        self.video_placeholder_lbl = QLabel("Загрузите видео в Шаге 2\\nдля включения живого плеера", self.video_viewport_frame)
        self.video_placeholder_lbl.setAlignment(Qt.AlignCenter)
        self.video_placeholder_lbl.setStyleSheet("color: #6B7280; font-size: 13px; font-weight: bold; background: transparent;")
        viewport_layout.addWidget(self.video_placeholder_lbl)

        # Switch Home Menu UI overlay for checking occlusions
        self.switch_mini_overlay = QLabel(self.video_viewport_frame)
        self.switch_mini_overlay.setGeometry(0, 0, 392, 220)
        self.switch_mini_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.switch_mini_overlay.setStyleSheet("background: transparent;")
        tmpl_path = Path(__file__).parent.parent / "data" / "switch_home_template.png"
        if tmpl_path.exists():
            pix = QPixmap(str(tmpl_path)).scaled(392, 220, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.switch_mini_overlay.setPixmap(pix)
        self.switch_mini_opacity = QGraphicsOpacityEffect(self.switch_mini_overlay)
        self.switch_mini_opacity.setOpacity(0.85)
        self.switch_mini_overlay.setGraphicsEffect(self.switch_mini_opacity)
        self.switch_mini_overlay.setVisible(False)
        self.switch_mini_overlay.raise_()

        cover_col.addWidget(self.video_viewport_frame)"""

    if old_viewport in content:
        content = content.replace(old_viewport, new_viewport, 1)

    # 3. Add overlay toggle checkbox and 1280x720 Switch test button
    old_time_lbl = """        # Time readout
        self.time_display_lbl = QLabel("00:00.0 / 00:08.0 (Фрагмент Switch: 0.0с - 8.0с)", self)
        self.time_display_lbl.setStyleSheet("color: #9AA4B2; font-family: monospace; font-size: 11px;")
        cover_col.addWidget(self.time_display_lbl)

        # Timing controls row: Start & Duration"""

    new_time_lbl = """        # Time readout
        self.time_display_lbl = QLabel("00:00.0 / 00:08.0 (Фрагмент Switch: 0.0с - 8.0с)", self)
        self.time_display_lbl.setStyleSheet("color: #9AA4B2; font-family: monospace; font-size: 11px;")
        cover_col.addWidget(self.time_display_lbl)

        # Switch Home Interface Overlay & Fullscreen Test Controls
        overlay_bar = QHBoxLayout()
        overlay_bar.setSpacing(10)

        self.chk_switch_overlay = QCheckBox("🎮 Сетка Switch Home (проверка перекрытий)", self)
        self.chk_switch_overlay.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: bold;")
        self.chk_switch_overlay.toggled.connect(self._toggle_switch_mini_overlay)
        overlay_bar.addWidget(self.chk_switch_overlay)

        self.btn_switch_preview = QPushButton("🔍 Тест интерфейса Switch (1280×720)", self)
        self.btn_switch_preview.setFixedHeight(28)
        self.btn_switch_preview.setStyleSheet(\"\"\"
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #06B6D4);
                color: #FFFFFF;
                border: 1px solid #00E5FF;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                padding: 0 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #0891B2);
            }
        \"\"\")
        self.btn_switch_preview.clicked.connect(self._open_switch_preview_dialog)
        overlay_bar.addWidget(self.btn_switch_preview)
        overlay_bar.addStretch()
        cover_col.addLayout(overlay_bar)

        # Timing controls row: Start & Duration"""

    if old_time_lbl in content:
        content = content.replace(old_time_lbl, new_time_lbl, 1)

    # 4. Add handler methods _toggle_switch_mini_overlay and _open_switch_preview_dialog
    old_methods_anchor = """    def _toggle_playback(self):
        if not self.current_video_path or not self.current_video_path.exists():
            QMessageBox.information(self, "Внимание", "Сначала выберите видеофайл в Шаге 2.")
            return"""

    new_methods = """    def _toggle_switch_mini_overlay(self, checked: bool):
        self.switch_mini_overlay.setVisible(checked)
        if checked:
            self.switch_mini_overlay.raise_()

    def _open_switch_preview_dialog(self):
        vid = getattr(self, 'current_video_path', None) or getattr(self, 'src_video_path', None)
        if not vid or not vid.exists():
            QMessageBox.information(
                self,
                "Предпросмотр интерфейса Switch",
                "Сначала выберите или загрузите видеофайл в Шаге 2 для включения предпросмотра."
            )
            return

        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()

        vol = self.volume_slider.value() / 100.0 if hasattr(self, 'volume_slider') else 1.0
        dlg = SwitchHomePreviewDialog(
            parent=self,
            video_path=vid,
            start_sec=self.start_spin.value(),
            dur_sec=self.dur_spin.value(),
            volume=vol
        )
        dlg.exec()

    def _toggle_playback(self):
        if not self.current_video_path or not self.current_video_path.exists():
            QMessageBox.information(self, "Внимание", "Сначала выберите видеофайл в Шаге 2.")
            return"""

    assert old_methods_anchor in content, "old_methods_anchor not found"
    content = content.replace(old_methods_anchor, new_methods, 1)

    path.write_text(content, encoding="utf-8")
    print("SUCCESS: studio/h3h_studio/ui/express_tab.py patched with Switch Home Overlay & Preview!")

if __name__ == "__main__":
    patch_express_tab()
