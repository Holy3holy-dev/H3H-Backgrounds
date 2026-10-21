# scripts/patch_app_cpp_v121.py
from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
text = p.read_text(encoding="utf-8")

# 1. Insert Plus button handler at the top of Tab::MyGames in onButtonPress
old_mygames_start = """    } else if (m_activeTab == Tab::MyGames) {
        if (m_myGamesActivePane == MyGamesPane::GamesList) {"""

new_mygames_start = """    } else if (m_activeTab == Tab::MyGames) {
        // Feature 3: Plus (+) or L3 button opens 4IFIR SD Recordings browser immediately
        if (button == 6 /* SDL_CONTROLLER_BUTTON_START (Plus / +) */ ||
            button == 7 /* SDL_CONTROLLER_BUTTON_LEFTSTICK (L3) */) {
            if (!m_installedGames.empty() && m_myGamesSelectedIndex >= 0 &&
                m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                openRecordingsBrowser(g.titleId, g.name);
                return;
            }
        }

        if (m_myGamesActivePane == MyGamesPane::GamesList) {"""

if old_mygames_start in text:
    text = text.replace(old_mygames_start, new_mygames_start)
    print("[+] Added Plus / L3 button handler to MyGames")
else:
    print("[-] Could not find old_mygames_start")

# 2. Add [+] Записи 4IFIR button card in renderTabMyGames
old_btn_row = """            if (selGame.hasBackup) {
                drawRect(770, 202, 230, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_ACCENT, 1);
                drawText("[R] Восстановить (.bak)", 785, 210, Theme::COLOR_ACCENT, 13);
            }
        } else {"""

new_btn_row = """            if (selGame.hasBackup) {
                drawRect(770, 202, 230, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_ACCENT, 1);
                drawText("[R] Восстановить (.bak)", 785, 210, Theme::COLOR_ACCENT, 13);
            }

            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
        } else {
            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);"""

if old_btn_row in text:
    text = text.replace(old_btn_row, new_btn_row)
    print("[+] Added [ + Записи 4IFIR ] button to MyGames pane")
else:
    print("[-] Could not find old_btn_row")

# 3. Add touch click support for [ + Записи 4IFIR ]
old_touch_actions = """// MyGames Tab: "Установить все" button: x in [530, 780], y in [200, 235]
            else if (m_activeTab == Tab::MyGames && mx >= 530 && mx <= 780 && my >= 200 && my <= 235) {
                installAllMissing();
            }"""

new_touch_actions = """// MyGames Tab: "[+] Записи 4IFIR (SD)" button: x in [1010, 1230], y in [200, 235]
            else if (m_activeTab == Tab::MyGames && mx >= 1010 && mx <= 1230 && my >= 200 && my <= 235) {
                if (!m_installedGames.empty() && m_myGamesSelectedIndex >= 0 &&
                    m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    openRecordingsBrowser(g.titleId, g.name);
                }
            }
            // MyGames Tab: "Установить все" button: x in [530, 780], y in [200, 235]
            else if (m_activeTab == Tab::MyGames && mx >= 530 && mx <= 780 && my >= 200 && my <= 235) {
                installAllMissing();
            }"""

if old_touch_actions in text:
    text = text.replace(old_touch_actions, new_touch_actions)
    print("[+] Added touch support for [+] Записи 4IFIR button")
else:
    print("[-] Could not find old_touch_actions")

# 4. In loadPreviewTexture background thread: atomic download and validation of preview video
old_download_block = """        // Then download live video MP4
        if (!m_cancelPreview.load() && !videoUrl.empty() && !std::filesystem::exists(vidFile, ec2)) {
            std::string err;
            bool ok = m_platform->downloadFile(videoUrl, vidFile, nullptr, m_cancelPreview, err);
            m_videoDownloading = false;
            if (ok && m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                std::lock_guard<std::mutex> lock(m_previewMutex);
                m_pendingVideoToOpen = vidFile;
            }
        } else {
            m_videoDownloading = false;
        }"""

new_download_block = """        // Then download live video MP4 to temporary file first, validate before saving
        if (!m_cancelPreview.load() && !videoUrl.empty() && !std::filesystem::exists(vidFile, ec2)) {
            std::string err;
            std::string tmpVid = vidFile + ".tmp";
            bool ok = m_platform->downloadFile(videoUrl, tmpVid, nullptr, m_cancelPreview, err);
            m_videoDownloading = false;
            if (ok && std::filesystem::exists(tmpVid, ec2)) {
                std::string valErr;
                if (Installer::validateVideoFile(tmpVid, valErr)) {
                    std::filesystem::rename(tmpVid, vidFile, ec2);
                    if (m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                        std::lock_guard<std::mutex> lock(m_previewMutex);
                        m_pendingVideoToOpen = vidFile;
                    }
                } else {
                    // Corrupted or server error HTML -> purge so it does not poison cache
                    std::filesystem::remove(tmpVid, ec2);
                }
            } else {
                std::filesystem::remove(tmpVid, ec2);
            }
        } else {
            m_videoDownloading = false;
        }"""

if old_download_block in text:
    text = text.replace(old_download_block, new_download_block)
    print("[+] Patched loadPreviewTexture with atomic temp download and validation")
else:
    print("[-] Could not find old_download_block")

# 5. In update(), if videoPlayer.open fails, safely purge corrupted vidFile
old_open_vid = """    if (!vidPath.empty() && m_renderer && m_isFullscreenPreview) {
        m_videoPlayer.open(vidPath, m_renderer);
    }"""

new_open_vid = """    if (!vidPath.empty() && m_renderer && m_isFullscreenPreview) {
        if (!m_videoPlayer.open(vidPath, m_renderer)) {
            // Failed to open -> remove corrupted cache file so it won't hang on black screen
            std::error_code ec;
            std::filesystem::remove(vidPath, ec);
        }
    }"""

if old_open_vid in text:
    text = text.replace(old_open_vid, new_open_vid)
    print("[+] Patched App::update() with safe error cleanup for videoPlayer")
else:
    print("[-] Could not find old_open_vid")

p.write_text(text, encoding="utf-8")
print("[+] Finished patching app.cpp")
