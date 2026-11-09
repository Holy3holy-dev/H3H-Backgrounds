from pathlib import Path

file_path = Path("studio/h3h_studio/ui/express_tab.py")
code = file_path.read_text(encoding="utf-8")

# 1. Update _init_player
old_init_player = '''    def _init_player(self):
        """Initializes QtMultimedia QMediaPlayer & QAudioOutput."""
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.playbackStateChanged.connect(self._on_player_state_changed)'''

new_init_player = '''    def _init_player(self):
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
        self.icon_player.playbackStateChanged.connect(self._on_icon_player_state_changed)'''

assert old_init_player in code, "old_init_player not found"
code = code.replace(old_init_player, new_init_player, 1)

# 2. Replace Right Column UI
old_right_col = '''        # =========================================================
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
        icon_col.addLayout(icon_header)

        # 1:1 Preview center
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
        self.icon_preview_lbl.setText("Квадрат 1:1\\n(256x256 HEVC)")
        preview_center.addWidget(self.icon_preview_lbl)
        icon_col.addLayout(preview_center)

        self.icon_meta_lbl = QLabel("256x256 HEVC • 4.0 сек • Без звука • 24 FPS", self)
        self.icon_meta_lbl.setAlignment(Qt.AlignCenter)
        self.icon_meta_lbl.setStyleSheet("color: #00E5FF; font-size: 11px;")
        icon_col.addWidget(self.icon_meta_lbl)

        # Icon duration setting
        icon_dur_layout = QHBoxLayout()
        icon_dur_layout.addWidget(QLabel("<b>Длительность иконки:</b>", self))
        self.icon_dur_spin = QDoubleSpinBox(self)
        self.icon_dur_spin.setRange(1.0, 15.0)
        self.icon_dur_spin.setValue(4.0)
        self.icon_dur_spin.setSingleStep(0.5)
        self.icon_dur_spin.setDecimals(1)
        self.icon_dur_spin.setFixedHeight(28)
        self.icon_dur_spin.valueChanged.connect(self._on_icon_duration_changed)
        icon_dur_layout.addWidget(self.icon_dur_spin)

        for d in (2, 4, 6, 8):
            id_btn = QPushButton(f"{d}с", self)
            id_btn.setFixedSize(36, 28)
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
            id_btn.clicked.connect(lambda checked, val=d: self.icon_dur_spin.setValue(val))
            icon_dur_layout.addWidget(id_btn)

        icon_dur_layout.addStretch()
        icon_col.addLayout(icon_dur_layout)

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

        self.step4_cols_layout.addWidget(self.icon_card_frame, 1)'''

new_right_col = '''        # =========================================================
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
        self.icon_preview_lbl.setText("Квадрат 1:1\\n(256x256 HEVC)")
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

        self.step4_cols_layout.addWidget(self.icon_card_frame, 1)'''

assert old_right_col in code, "old_right_col not found"
code = code.replace(old_right_col, new_right_col, 1)

# Write updated code
file_path.write_text(code, encoding="utf-8")
print("[+] Successfully replaced Right Column UI in express_tab.py")
