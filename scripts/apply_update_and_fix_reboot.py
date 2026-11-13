import re
from pathlib import Path

# 1. Patch main.cpp (Thread stack size on Switch)
main_path = Path("downloader/src/main.cpp")
main_text = main_path.read_text(encoding="utf-8")
if "__nx_threads_stack_size" not in main_text:
    main_text = main_text.replace(
        '#include <iostream>',
        '#include <iostream>\n\n#ifdef __SWITCH__\n#include <switch.h>\n// 2 MB thread stack size prevents mbedTLS / libcurl stack overflows\nsize_t __nx_threads_stack_size = 0x200000;\n#endif'
    )
    main_path.write_text(main_text, encoding="utf-8")
    print("[+] Patched main.cpp with 2MB thread stack size")
else:
    print("[*] main.cpp already has stack size patch")

# 2. Patch config.hpp (version bump to 1.4.6)
cfg_path = Path("downloader/include/core/config.hpp")
cfg_text = cfg_path.read_text(encoding="utf-8")
cfg_text = re.sub(r'APP_VERSION\s*=\s*"1\.4\.[0-9]+"', 'APP_VERSION = "1.4.6"', cfg_text)
cfg_path.write_text(cfg_text, encoding="utf-8")
print("[+] Bumped config.hpp to v1.4.6")

# 3. Patch app.cpp
app_path = Path("downloader/src/ui/app.cpp")
app_text = app_path.read_text(encoding="utf-8")

# 3a. Fix executeCycleNextCover
old_cycle = """void App::executeCycleNextCover(const std::string& titleId) {
    auto variants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), titleId);
    if (variants.size() <= 1) return;

    int targetIndex = 1;
    for (const auto& v : variants) {
        if (!v.isActive && v.index > 0) {
            targetIndex = v.index;
            break;
        }
    }

    bool switched = Installer::switchActiveCover(m_platform->getCoversDirectory(), titleId, targetIndex);
    if (switched) {
        m_statusNotification = (m_language == Language::Russian)
            ? ("Активным назначен видеофон #" + std::to_string(targetIndex))
            : ("Active video cover switched to #" + std::to_string(targetIndex));
    } else {
        m_statusNotification = "Не удалось сменить видеофон";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
}"""

new_cycle = """void App::executeCycleNextCover(const std::string& titleId) {
    // 1. Release any open file handle in video player before filesystem swap
    m_videoPlayer.close();
    std::this_thread::sleep_for(std::chrono::milliseconds(20));

    auto variants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), titleId);
    if (variants.size() <= 1) return;

    int targetIndex = 1;
    for (const auto& v : variants) {
        if (!v.isActive && v.index > 0) {
            targetIndex = v.index;
            break;
        }
    }

    bool switched = Installer::switchActiveCover(m_platform->getCoversDirectory(), titleId, targetIndex);
    if (switched) {
        m_statusNotification = (m_language == Language::Russian)
            ? ("Активным назначен видеофон #" + std::to_string(targetIndex))
            : ("Active video cover switched to #" + std::to_string(targetIndex));
    } else {
        m_statusNotification = "Не удалось сменить видеофон";
    }
    m_notificationFramesRemaining = 180;

    // Fast, safe local update: refresh variant state ONLY for this game without rescanning all SD games
    for (auto& g : m_installedGames) {
        if (g.titleId == titleId) {
            g.installedCoverVariants = Installer::findInstalledCoverVariants(m_platform->getCoversDirectory(), titleId);
            g.installedCoversCount = static_cast<int>(g.installedCoverVariants.size());
            for (const auto& var : g.installedCoverVariants) {
                if (var.isActive) {
                    g.installedCoverPath = var.filePath;
                    g.installedCoverSizeBytes = var.sizeBytes;
                    break;
                }
            }
            break;
        }
    }
}"""

if old_cycle in app_text:
    app_text = app_text.replace(old_cycle, new_cycle, 1)
    print("[+] Patched executeCycleNextCover (safe file close + local state update)")
else:
    print("[-] Old executeCycleNextCover not found directly, checking normalized...")
    norm_app = app_text.replace("\r\n", "\n")
    norm_old = old_cycle.replace("\r\n", "\n")
    norm_new = new_cycle.replace("\r\n", "\n")
    if norm_old in norm_app:
        app_text = norm_app.replace(norm_old, norm_new, 1)
        print("[+] Patched executeCycleNextCover (normalized)")

# 3b. Modal Dialog Handler in onButtonPress (Add DialogType::UpdateAvailable)
old_dialog_head = """        if (m_activeDialog == DialogType::UpdateProgress) {"""
new_dialog_head = """        if (m_activeDialog == DialogType::UpdateAvailable) {
            if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
                m_dialogFocus = 1 - m_dialogFocus;
            } else if (button == 0 /* A */) {
                if (m_dialogFocus == 0) {
                    m_activeDialog = DialogType::None;
                    updateApplicationNro();
                } else {
                    m_activeDialog = DialogType::None;
                }
            } else if (button == 1 /* B */) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::UpdateProgress) {"""

if old_dialog_head in app_text:
    app_text = app_text.replace(old_dialog_head, new_dialog_head, 1)
    print("[+] Added DialogType::UpdateAvailable handler to onButtonPress")

# 3c. Remove fetchRemoteCatalog from Tab::Home (button 4)
old_home_btn4 = """        if (button == 4 /* MINUS (-) - Refresh Catalog */) {
            fetchRemoteCatalog();
            return;
        }"""
new_home_btn4 = """        if (button == 4 /* MINUS (-) */) {
            checkForUpdates(true);
            return;
        }"""

if old_home_btn4 in app_text:
    app_text = app_text.replace(old_home_btn4, new_home_btn4, 1)
    print("[+] Replaced Tab::Home button 4 fetchRemoteCatalog with safe checkForUpdates")

# 3d. Tab::MyGames button 4 ensure return;
old_mygames_btn4 = """                } else if (g.hasBackup) {
                    m_pendingActionTitleId = g.titleId;
                    m_activeDialog = DialogType::ConfirmRestore;
                    m_dialogOpenedAt = SDL_GetTicks();
                    m_dialogTitle = "Восстановление резервной копии (.bak)";
                    m_dialogMessage = "Восстановить предыдущий видеофон из резервной копии для игры " + g.name + "?";
                    m_dialogFocus = 0;
                    return;
                }
            }
        }"""

new_mygames_btn4 = """                } else if (g.hasBackup) {
                    m_pendingActionTitleId = g.titleId;
                    m_activeDialog = DialogType::ConfirmRestore;
                    m_dialogOpenedAt = SDL_GetTicks();
                    m_dialogTitle = "Восстановление резервной копии (.bak)";
                    m_dialogMessage = "Восстановить предыдущий видеофон из резервной копии для игры " + g.name + "?";
                    m_dialogFocus = 0;
                    return;
                }
            }
            return;
        }"""

if old_mygames_btn4 in app_text:
    app_text = app_text.replace(old_mygames_btn4, new_mygames_btn4, 1)
    print("[+] Fixed Tab::MyGames button 4 fallthrough")

# 3e. Remove dangerous fetchRemoteCatalog from Tab::Catalog button 4 else branch
old_cat_btn4 = """            } else {
                fetchRemoteCatalog();
            }
            return;"""
new_cat_btn4 = """            }
            return;"""

if old_cat_btn4 in app_text:
    app_text = app_text.replace(old_cat_btn4, new_cat_btn4, 1)
    print("[+] Removed dangerous fetchRemoteCatalog from Tab::Catalog button 4 else branch")

# 3f. Startup update check & Prompt dialog (Yes/No)
old_startup_check = """                if (checkOk && !versionJsonStr.empty()) {
                    try {
                        auto vJson = nlohmann::json::parse(versionJsonStr);
                        if (vJson.contains("latestVersion")) {
                            std::string latestVer = vJson["latestVersion"].get<std::string>();
                            if (latestVer != Config::APP_VERSION) {
                                std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
                                m_startupUpdateLatestVer = latestVer;
                            }
                        }
                    } catch (...) {}
                }
                m_startupUpdateDone.store(true);
                m_isCheckingUpdateStartup.store(false);
            });
        }
    }

    if (m_startupUpdateDone.exchange(false)) {
        if (m_startupUpdateThread.joinable()) {
            m_startupUpdateThread.join();
        }
        std::string newVer;
        {
            std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
            newVer = std::move(m_startupUpdateLatestVer);
        }
        if (!newVer.empty()) {
            m_statusNotification = (m_language == Language::Russian)
                ? ("Обнаружено обновление v" + newVer + "! Нажмите [-] в Настройках")
                : ("New update v" + newVer + " detected! Press [-] in Settings");
            m_notificationFramesRemaining = 240;
        }
    }"""

new_startup_check = """                if (checkOk && !versionJsonStr.empty()) {
                    try {
                        auto vJson = nlohmann::json::parse(versionJsonStr);
                        if (vJson.contains("latestVersion")) {
                            std::string latestVer = vJson["latestVersion"].get<std::string>();
                            if (latestVer != Config::APP_VERSION) {
                                std::string relNotes = "Вышла новая версия приложения с улучшениями и исправлениями.";
                                if (vJson.contains("releaseNotes")) {
                                    relNotes = vJson["releaseNotes"].get<std::string>();
                                }
                                std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
                                m_startupUpdateLatestVer = latestVer;
                                m_startupUpdateReleaseNotes = relNotes;
                            }
                        }
                    } catch (...) {}
                }
                m_startupUpdateDone.store(true);
                m_isCheckingUpdateStartup.store(false);
            });
        }
    }

    if (m_startupUpdateDone.exchange(false)) {
        if (m_startupUpdateThread.joinable()) {
            m_startupUpdateThread.join();
        }
        std::string newVer;
        std::string notes;
        {
            std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
            newVer = std::move(m_startupUpdateLatestVer);
            notes = std::move(m_startupUpdateReleaseNotes);
        }
        if (!newVer.empty()) {
            m_activeDialog = DialogType::UpdateAvailable;
            m_dialogOpenedAt = SDL_GetTicks();
            m_dialogTitle = (m_language == Language::Russian)
                ? ("Доступно обновление v" + newVer)
                : ("Update Available v" + newVer);
            m_dialogMessage = (m_language == Language::Russian)
                ? ("Вышла новая версия H3H-Backgrounds v" + newVer + ":\\n\\n" + (notes.empty() ? "Рекомендуется обновить приложение." : notes) + "\\n\\nОбновить приложение сейчас?")
                : ("New version H3H-Backgrounds v" + newVer + " is available:\\n\\n" + notes + "\\n\\nDo you want to update now?");
            m_dialogFocus = 0; // Default focus on 'Да, обновить'
        }
    }"""

if old_startup_check in app_text:
    app_text = app_text.replace(old_startup_check, new_startup_check, 1)
    print("[+] Upgraded startup update check to display interactive Yes/No modal dialog")
else:
    norm_app = app_text.replace("\r\n", "\n")
    norm_old = old_startup_check.replace("\r\n", "\n")
    norm_new = new_startup_check.replace("\r\n", "\n")
    if norm_old in norm_app:
        app_text = norm_app.replace(norm_old, norm_new, 1)
        print("[+] Upgraded startup update check (normalized)")

# 3g. renderDialog UpdateAvailable UI
old_render_dialog = """    drawText(m_dialogTitle, dx + 35, dy + 25, Theme::COLOR_FOCUS_CYAN, 20);

    // Specialized dialog: Update Success"""

new_render_dialog = """    drawText(m_dialogTitle, dx + 35, dy + 25, Theme::COLOR_FOCUS_CYAN, 20);

    // Specialized dialog: Update Available (Interactive Yes/No Prompt)
    if (m_activeDialog == DialogType::UpdateAvailable) {
        std::stringstream ss(m_dialogMessage);
        std::string rawLine;
        int msgY = dy + 68;
        while (std::getline(ss, rawLine, '\\n')) {
            std::stringstream wordStream(rawLine);
            std::string word;
            std::string currentLine;
            while (wordStream >> word) {
                if (currentLine.empty()) {
                    currentLine = word;
                } else if (currentLine.length() + 1 + word.length() <= 54) {
                    currentLine += " " + word;
                } else {
                    drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_PRIMARY, 14, dw - 70);
                    msgY += 24;
                    currentLine = word;
                }
            }
            if (!currentLine.empty()) {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_PRIMARY, 14, dw - 70);
                msgY += 24;
            }
        }

        int btnW = 200;
        int btnH = 44;
        int btnY = dy + 200;

        // Button 0: [A] Да, обновить
        bool fYes = (m_dialogFocus == 0);
        drawGlassCard(dx + 120, btnY, btnW, btnH, fYes, false);
        drawText(tr("[A] Да, обновить", "[A] Yes, update"), dx + 145, btnY + 13, fYes ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);

        // Button 1: [B] Нет, позже
        bool fNo = (m_dialogFocus == 1);
        drawGlassCard(dx + 380, btnY, btnW, btnH, fNo, false);
        drawText(tr("[B] Нет, позже", "[B] No, later"), dx + 420, btnY + 13, fNo ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);
        return;
    }

    // Specialized dialog: Update Success"""

if old_render_dialog in app_text:
    app_text = app_text.replace(old_render_dialog, new_render_dialog, 1)
    print("[+] Added UpdateAvailable renderer with Yes/No glass cards")
else:
    norm_app = app_text.replace("\r\n", "\n")
    norm_old = old_render_dialog.replace("\r\n", "\n")
    norm_new = new_render_dialog.replace("\r\n", "\n")
    if norm_old in norm_app:
        app_text = norm_app.replace(norm_old, norm_new, 1)
        print("[+] Added UpdateAvailable renderer (normalized)")

app_path.write_text(app_text, encoding="utf-8")
print("[+] App.cpp successfully updated!")
