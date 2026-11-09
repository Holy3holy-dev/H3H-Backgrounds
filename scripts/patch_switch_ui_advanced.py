from pathlib import Path

app_path = Path("downloader/src/ui/app.cpp")
c = app_path.read_text(encoding="utf-8")
is_crlf = "\r\n" in c
if is_crlf:
    c = c.replace("\r\n", "\n")

# 1. Add touch handling for Modals in handleInput()
target_touch_dialog = """            // If dialog is open, handle direct taps on dialog buttons
            if (m_activeDialog != DialogType::None) {
                // Confirm button: x in [440, 610], y in [400, 450]
                if (my >= 400 && my <= 450 && mx >= 440 && mx <= 610) {
                    m_dialogFocus = 0;
                    onButtonPress(0 /* A - Confirm */);
                }
                // Cancel button: x in [650, 820], y in [400, 450]
                else if (my >= 400 && my <= 450 && mx >= 650 && mx <= 820) {
                    m_dialogFocus = 1;
                    onButtonPress(1 /* B - Cancel */);
                }
                // Outside dialog: dismiss
                else if (mx < 315 || mx > 965 || my < 235 || my > 485) {
                    m_activeDialog = DialogType::None;
                }
                continue;
            }"""

replacement_touch_dialog = """            // If dialog is open, handle direct taps on dialog buttons
            if (m_activeDialog != DialogType::None) {
                if (my >= 400 && my <= 450 && mx >= 440 && mx <= 610) {
                    m_dialogFocus = 0;
                    onButtonPress(0 /* A - Confirm */);
                } else if (my >= 400 && my <= 450 && mx >= 650 && mx <= 820) {
                    m_dialogFocus = 1;
                    onButtonPress(1 /* B - Cancel */);
                } else if (mx < 315 || mx > 965 || my < 235 || my > 485) {
                    m_activeDialog = DialogType::None;
                }
                continue;
            }

            // If Fullscreen Preview is active, tap closes preview
            if (m_isFullscreenPreview) {
                closeFullscreenPreview();
                continue;
            }

            // If Game Picker Modal is open, handle touch navigation and selection
            if (m_isGamePickerOpen) {
                int bw = 1140, bh = 600;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeGamePicker();
                } else if (my >= by + 95 && my <= by + 95 + 5 * 88) {
                    int clickedIdx = m_gamePickerScrollOffset + (my - (by + 95)) / 88;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_installedGames.size())) {
                        m_gamePickerSelectedIndex = clickedIdx;
                        onButtonPress(0 /* A - Select Game */);
                    }
                }
                continue;
            }

            // If Recordings Browser Modal is open, handle touch
            if (m_isRecordingsBrowserOpen) {
                int bw = 1100, bh = 560;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeRecordingsBrowser();
                } else if (my >= by + 105 && my <= by + 105 + 5 * 74) {
                    int clickedIdx = m_recordingsScrollOffset + (my - (by + 105)) / 74;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_localRecordings.size())) {
                        m_recordingsSelectedIndex = clickedIdx;
                        onButtonPress(0 /* A - Install */);
                    }
                }
                continue;
            }

            // If Collection Browser Modal is open, handle touch
            if (m_isCollectionBrowserOpen) {
                int bw = 1220, bh = 660;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeCollectionBrowser();
                } else {
                    int lx = bx + 25, ly = by + 68, lw = 635;
                    // Left Column: tapping variant item
                    if (mx >= lx && mx <= lx + lw && my >= ly && my <= ly + 5 * 96) {
                        int clickedIdx = m_collectionScrollOffset + (my - ly) / 96;
                        if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_collectionVariants.size())) {
                            m_collectionSelectedIndex = clickedIdx;
                            loadCollectionThumbnail(m_collectionVariants[clickedIdx]);
                        }
                    } else {
                        int rx = bx + 675, ry = by + 68;
                        int px = rx + 20, py = ry + 20, pw = 480, ph = 270;
                        int b1y = py + ph + 80;
                        int b3y = py + ph + 130;

                        // Tap preview thumbnail -> open fullscreen live video
                        if (mx >= px && mx <= px + pw && my >= py && my <= py + ph) {
                            onButtonPress(2 /* X - Video */);
                        }
                        // Button [A] Назначить на игру
                        else if (mx >= px && mx <= px + 230 && my >= b1y && my <= b1y + 42) {
                            onButtonPress(0 /* A - Assign */);
                        }
                        // Button [X] Видео в полный экран
                        else if (mx >= px + 245 && mx <= px + 475 && my >= b1y && my <= b1y + 42) {
                            onButtonPress(2 /* X - Video */);
                        }
                        // Button [L] В избранное
                        else if (mx >= px && mx <= px + 230 && my >= b3y && my <= b3y + 36) {
                            onButtonPress(9 /* L - Favorite */);
                        }
                        // Button [B] Закрыть
                        else if (mx >= px + 245 && mx <= px + 475 && my >= b3y && my <= b3y + 36) {
                            closeCollectionBrowser();
                        }
                    }
                }
                continue;
            }"""

if target_touch_dialog in c:
    c = c.replace(target_touch_dialog, replacement_touch_dialog)
    print("[+] Patched modal touch handlers & leak prevention")
else:
    print("[-] target_touch_dialog not found")

# 2. GamePicker fast scrolling (Left/Right ±5, ZL/ZR ±10)
target_gp_nav = """        if (button == 12 /* DOWN */) {
            if (m_gamePickerSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                m_gamePickerSelectedIndex++;
            }
            return;
        }"""

replacement_gp_nav = """        if (button == 12 /* DOWN */) {
            if (m_gamePickerSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                m_gamePickerSelectedIndex++;
            }
            return;
        }
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_gamePickerSelectedIndex = std::max(0, m_gamePickerSelectedIndex - 5);
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            if (!m_installedGames.empty()) {
                m_gamePickerSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_gamePickerSelectedIndex + 5);
            }
            return;
        }
        if (button == 15 /* ZL - Fast Page Up 10 */) {
            m_gamePickerSelectedIndex = std::max(0, m_gamePickerSelectedIndex - 10);
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 10 */) {
            if (!m_installedGames.empty()) {
                m_gamePickerSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_gamePickerSelectedIndex + 10);
            }
            return;
        }"""

if target_gp_nav in c:
    c = c.replace(target_gp_nav, replacement_gp_nav)
    print("[+] Patched GamePicker fast navigation")
else:
    print("[-] target_gp_nav not found")

# 3. RecordingsBrowser fast scrolling (Left/Right ±5, ZL/ZR ±10)
target_rec_nav = """        if (button == 12 /* DOWN */) {
            if (m_recordingsSelectedIndex + 1 < static_cast<int>(m_localRecordings.size())) {
                m_recordingsSelectedIndex++;
            }
            return;
        }"""

replacement_rec_nav = """        if (button == 12 /* DOWN */) {
            if (m_recordingsSelectedIndex + 1 < static_cast<int>(m_localRecordings.size())) {
                m_recordingsSelectedIndex++;
            }
            return;
        }
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_recordingsSelectedIndex = std::max(0, m_recordingsSelectedIndex - 5);
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            if (!m_localRecordings.empty()) {
                m_recordingsSelectedIndex = std::min(static_cast<int>(m_localRecordings.size()) - 1, m_recordingsSelectedIndex + 5);
            }
            return;
        }
        if (button == 15 /* ZL - Fast Page Up 10 */) {
            m_recordingsSelectedIndex = std::max(0, m_recordingsSelectedIndex - 10);
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 10 */) {
            if (!m_localRecordings.empty()) {
                m_recordingsSelectedIndex = std::min(static_cast<int>(m_localRecordings.size()) - 1, m_recordingsSelectedIndex + 10);
            }
            return;
        }"""

if target_rec_nav in c:
    c = c.replace(target_rec_nav, replacement_rec_nav)
    print("[+] Patched RecordingsBrowser fast navigation")
else:
    print("[-] target_rec_nav not found")

# 4. Downloads Tab: [X] clears finished/failed tasks
target_dl_btn = """    } else if (m_activeTab == Tab::Downloads) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;"""

replacement_dl_btn = """    } else if (m_activeTab == Tab::Downloads) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 2 /* X - Clear finished/failed tasks */) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            m_downloadQueue.erase(
                std::remove_if(m_downloadQueue.begin(), m_downloadQueue.end(),
                    [](const DownloadTask& t) {
                        return t.state == TaskState::Completed || t.state == TaskState::Failed;
                    }),
                m_downloadQueue.end()
            );
            m_statusNotification = (m_language == Language::Russian) ? "Завершённые задачи очищены" : "Finished tasks cleared";
            m_notificationFramesRemaining = 90;
            return;"""

if target_dl_btn in c:
    c = c.replace(target_dl_btn, replacement_dl_btn)
    print("[+] Patched Downloads tab X-button clear")
else:
    print("[-] target_dl_btn not found")

# 5. Footer for Downloads tab
target_dl_footer = """    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [B] Назад в меню   [-] Обновить каталог";"""

replacement_dl_footer = """    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [X] Очистить завершённые   [Y] Добавить все недостающие   [B] Назад";"""

if target_dl_footer in c:
    c = c.replace(target_dl_footer, replacement_dl_footer)
    print("[+] Patched Downloads footer hints")
else:
    print("[-] target_dl_footer not found")

# 6. Settings row 0 app name
target_set_app = """        {"Обновление приложения (NRO)", "Проверить и установить новую версию H3H-Backgrounds.nro с GitHub", std::string("v") + Config::APP_VERSION + " [A]", Theme::COLOR_FOCUS_CYAN},"""
replacement_set_app = """        {"Обновление приложения (NRO)", std::string("Проверить и установить новую версию ") + Config::APP_NAME + " с GitHub", std::string("v") + Config::APP_VERSION + " [A]", Theme::COLOR_FOCUS_CYAN},"""

if target_set_app in c:
    c = c.replace(target_set_app, replacement_set_app)
    print("[+] Patched Settings app name string")
else:
    print("[-] target_set_app not found")

if is_crlf:
    c = c.replace("\n", "\r\n")

app_path.write_text(c, encoding="utf-8")
print("[+] Successfully updated downloader/src/ui/app.cpp with advanced improvements!")
