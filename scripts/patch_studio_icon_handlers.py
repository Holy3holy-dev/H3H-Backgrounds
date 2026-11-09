from pathlib import Path

p = Path("studio/h3h_studio/ui/express_tab.py")
code = p.read_text(encoding="utf-8")

# 1. Update _load_video to initialize icon player & timing ranges
old_load_video_tail = '''        # Load video into media player
        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.media_player.setPosition(1)
        self.video_placeholder_lbl.setVisible(False)

        # Update initial frame & icon preview
        self._update_icon_crop_preview()
        self._update_time_label()'''

new_load_video_tail = '''        # Load video into cover media player
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
        self._update_icon_time_label()'''

assert old_load_video_tail in code, "old_load_video_tail not found"
code = code.replace(old_load_video_tail, new_load_video_tail, 1)

# 2. Update _start_publishing to pass icon_start_sec
old_worker_call = '''            start_sec=self.start_spin.value(),
            dur_sec=self.dur_spin.value(),
            icon_dur_sec=self.icon_dur_spin.value(),'''

new_worker_call = '''            start_sec=self.start_spin.value(),
            dur_sec=self.dur_spin.value(),
            icon_start_sec=self.icon_start_spin.value(),
            icon_dur_sec=self.icon_dur_spin.value(),'''

assert old_worker_call in code, "old_worker_call not found"
code = code.replace(old_worker_call, new_worker_call, 1)

# Also pause icon player on publishing start
old_pause_check = '''        # Pause playback during export
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()'''

new_pause_check = '''        # Pause playback during export
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        if self.icon_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.icon_player.pause()'''

assert old_pause_check in code, "old_pause_check not found"
code = code.replace(old_pause_check, new_pause_check, 1)

# 3. Add icon playback and timing handlers
old_icon_dur_changed = '''    def _on_icon_duration_changed(self, val: float):
        self.icon_meta_lbl.setText(f"256x256 HEVC • {val:.1f} сек • Без звука • 24 FPS")'''

new_icon_handlers = '''    # =========================================================================
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
        )'''

assert old_icon_dur_changed in code, "old_icon_dur_changed not found"
code = code.replace(old_icon_dur_changed, new_icon_handlers, 1)

# In _update_icon_crop_preview, use icon_start_spin.value()
old_crop_ts = '''        ts = self.start_spin.value()
        ok = ExpressProcessor.extract_preview_frame(self.current_video_path, ts, self.temp_frame_path)'''

new_crop_ts = '''        ts = self.icon_start_spin.value() if hasattr(self, "icon_start_spin") else self.start_spin.value()
        ok = ExpressProcessor.extract_preview_frame(self.current_video_path, ts, self.temp_frame_path)'''

assert old_crop_ts in code, "old_crop_ts not found"
code = code.replace(old_crop_ts, new_crop_ts, 1)

p.write_text(code, encoding="utf-8")
print("[+] Successfully patched icon handlers in express_tab.py")
