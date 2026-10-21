import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

APP_CPP = Path("downloader/src/ui/app.cpp")

with open(APP_CPP, "r", encoding="utf-8") as f:
    code = f.read()

# Normalize line endings
code = code.replace("\r\n", "\n")

# 1. Update onButtonPress dialog handling
old_dialog_input = """    // If Dialog is active, route all input to dialog
    if (m_activeDialog != DialogType::None) {
        if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            m_dialogFocus = 1 - m_dialogFocus;
        } else if (button == 0 /* A - Confirm */) {
            if (m_dialogFocus == 0) { // Yes / Confirm
                if (m_activeDialog == DialogType::ConfirmInstall) {
                    for (const auto& g : m_installedGames) {
                        if (g.titleId == m_pendingActionTitleId) {
                            queueDownload(g, m_pendingActionVariant);
                            break;
                        }
                    }
                } else if (m_activeDialog == DialogType::ConfirmInstallAll) {
                    for (const auto& g : m_installedGames) {
                        if (!g.hasInstalledCover && g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                            bool alreadyInQueue = false;
                            for (const auto& task : m_downloadQueue) {
                                if (task.titleId == g.titleId && task.state != TaskState::Failed) {
                                    alreadyInQueue = true;
                                    break;
                                }
                            }
                            if (!alreadyInQueue) {
                                queueDownload(g, g.catalogEntry.variants[0]);
                            }
                        }
                    }
                    m_activeTab = Tab::Downloads;
                } else if (m_activeDialog == DialogType::ConfirmRestore) {
                    executeRestoreBackup(m_pendingActionTitleId);
                } else if (m_activeDialog == DialogType::ConfirmDelete) {
                    executeDeleteCover(m_pendingActionTitleId);
                }
            }
            m_activeDialog = DialogType::None;
        } else if (button == 1 /* B - Cancel */) {
            m_activeDialog = DialogType::None;
        }
        return;
    }"""

new_dialog_input = """    // If Dialog is active, route all input to dialog
    if (m_activeDialog != DialogType::None) {
        if (m_activeDialog == DialogType::UpdateProgress) {
            // While downloading, allow B to hide modal to background
            if (button == 1 /* B */) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::UpdateSuccess) {
            if (button == 0 /* A - Restart App */) {
                m_running = false; // Exit to hbmenu so user launches newly updated NRO
            } else if (button == 1 /* B - Continue */) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::MessageAlert) {
            if (button == 0 || button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }

        if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            m_dialogFocus = 1 - m_dialogFocus;
        } else if (button == 0 /* A - Confirm */) {
            if (m_dialogFocus == 0) { // Yes / Confirm
                if (m_activeDialog == DialogType::ConfirmInstall) {
                    for (const auto& g : m_installedGames) {
                        if (g.titleId == m_pendingActionTitleId) {
                            queueDownload(g, m_pendingActionVariant);
                            break;
                        }
                    }
                } else if (m_activeDialog == DialogType::ConfirmInstallAll) {
                    for (const auto& g : m_installedGames) {
                        if (!g.hasInstalledCover && g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                            bool alreadyInQueue = false;
                            for (const auto& task : m_downloadQueue) {
                                if (task.titleId == g.titleId && task.state != TaskState::Failed) {
                                    alreadyInQueue = true;
                                    break;
                                }
                            }
                            if (!alreadyInQueue) {
                                queueDownload(g, g.catalogEntry.variants[0]);
                            }
                        }
                    }
                    m_activeTab = Tab::Downloads;
                } else if (m_activeDialog == DialogType::ConfirmRestore) {
                    executeRestoreBackup(m_pendingActionTitleId);
                } else if (m_activeDialog == DialogType::ConfirmDelete) {
                    executeDeleteCover(m_pendingActionTitleId);
                }
            }
            m_activeDialog = DialogType::None;
        } else if (button == 1 /* B - Cancel */) {
            m_activeDialog = DialogType::None;
        }
        return;
    }"""

if old_dialog_input in code:
    code = code.replace(old_dialog_input, new_dialog_input, 1)
    print("[+] Patched dialog input handling")
else:
    print("[-] old_dialog_input not matched")

# 2. Update onButtonPress for Tab::MyGames and Tab::Settings
old_nav_input = """    } else if (m_activeTab == Tab::MyGames) {
        if (button == 11 /* DPAD_UP */) {
            if (m_myGamesSelectedIndex > 0) {
                m_myGamesSelectedIndex--;
                m_selectedVariantIndex = 0;
            }
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_myGamesSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                m_myGamesSelectedIndex++;
                m_selectedVariantIndex = 0;
            }
        } else if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                    int vCount = static_cast<int>(g.catalogEntry.variants.size());
                    if (button == 14) m_selectedVariantIndex = (m_selectedVariantIndex + 1) % vCount;
                    else m_selectedVariantIndex = (m_selectedVariantIndex == 0) ? vCount - 1 : m_selectedVariantIndex - 1;
                }
            }
        }"""

new_nav_input = """    } else if (m_activeTab == Tab::MyGames) {
        if (button == 11 /* DPAD_UP */) {
            if (m_myGamesSelectedIndex > 0) {
                m_myGamesSelectedIndex--;
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
            }
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_myGamesSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                m_myGamesSelectedIndex++;
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
            }
        } else if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                    int vCount = static_cast<int>(g.catalogEntry.variants.size());
                    if (button == 14) m_selectedVariantIndex = (m_selectedVariantIndex + 1) % vCount;
                    else m_selectedVariantIndex = (m_selectedVariantIndex == 0) ? vCount - 1 : m_selectedVariantIndex - 1;

                    // Keep active variant visible inside the 4-variant window
                    if (m_selectedVariantIndex < m_variantScrollOffset) {
                        m_variantScrollOffset = m_selectedVariantIndex;
                    } else if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                        m_variantScrollOffset = m_selectedVariantIndex - 4 + 1;
                    }
                }
            }
        }"""

if old_nav_input in code:
    code = code.replace(old_nav_input, new_nav_input, 1)
    print("[+] Patched Tab::MyGames variant scroll navigation")
else:
    print("[-] old_nav_input not matched")

old_settings_input = """    } else if (m_activeTab == Tab::Settings) {
        if (button == 0 /* A */) {
            // Toggle language
            m_language = (m_language == Language::Russian) ? Language::English : Language::Russian;
            m_statusNotification = (m_language == Language::Russian) ? "Язык: Русский" : "Language: English";
            m_notificationFramesRemaining = 120;
        } else if (button == 2 /* X - Clear Cache */) {
            m_catalogManager.loadFromJsonString("{\\"schemaVersion\\":1,\\"updatedAt\\":\\"\\",\\"games\\":[]}", m_statusNotification);
            refreshInstalledGames();
            m_statusNotification = getStrings(m_language).cacheClearedMsg;
            m_notificationFramesRemaining = 120;
        } else if (button == 3 /* Y - Refresh Catalog */) {
            fetchRemoteCatalog();
        } else if (button == 6 /* START / Plus - Update App NRO */) {
            updateApplicationNro();
        }
    }"""

new_settings_input = """    } else if (m_activeTab == Tab::Settings) {
        if (button == 11 /* DPAD_UP */) {
            if (m_settingsSelectedIndex > 0) m_settingsSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_settingsSelectedIndex < 4) m_settingsSelectedIndex++;
        } else if (button == 0 /* A - Activate Selected Setting */) {
            switch (m_settingsSelectedIndex) {
                case 0: // Check & Update NRO
                    updateApplicationNro();
                    break;
                case 1: // Refresh Catalog
                    fetchRemoteCatalog();
                    break;
                case 2: // Toggle Language
                    m_language = (m_language == Language::Russian) ? Language::English : Language::Russian;
                    m_statusNotification = (m_language == Language::Russian) ? "Язык интерфейса: Русский" : "Interface language: English";
                    m_notificationFramesRemaining = 120;
                    break;
                case 3: // Clear Cache
                    m_catalogManager.loadFromJsonString("{\\"schemaVersion\\":1,\\"updatedAt\\":\\"\\",\\"games\\":[]}", m_statusNotification);
                    refreshInstalledGames();
                    m_statusNotification = getStrings(m_language).cacheClearedMsg;
                    m_notificationFramesRemaining = 120;
                    break;
                case 4: // Storage refresh
                    m_sysInfo = m_platform->getSystemInfo();
                    m_statusNotification = "Память MicroSD обновлена";
                    m_notificationFramesRemaining = 90;
                    break;
            }
        } else if (button == 2 /* X - Clear Cache */) {
            m_catalogManager.loadFromJsonString("{\\"schemaVersion\\":1,\\"updatedAt\\":\\"\\",\\"games\\":[]}", m_statusNotification);
            refreshInstalledGames();
            m_statusNotification = getStrings(m_language).cacheClearedMsg;
            m_notificationFramesRemaining = 120;
        } else if (button == 3 /* Y - Refresh Catalog */) {
            fetchRemoteCatalog();
        } else if (button == 6 /* START / Plus - Update App NRO */) {
            updateApplicationNro();
        }
    }"""

if old_settings_input in code:
    code = code.replace(old_settings_input, new_settings_input, 1)
    print("[+] Patched Tab::Settings row navigation")
else:
    print("[-] old_settings_input not matched")

# 3. Patch renderTabMyGames with 4-variant window and scroll indicators
old_render_variants = """        // Available variants from catalog
        drawText("Доступные варианты видеофона:", 530, 250, Theme::COLOR_TEXT_PRIMARY, 16);

        if (selGame.hasCatalogMatch && !selGame.catalogEntry.variants.empty()) {
            int vY = 285;
            for (size_t vIdx = 0; vIdx < selGame.catalogEntry.variants.size(); ++vIdx) {
                const auto& v = selGame.catalogEntry.variants[vIdx];
                bool isVarSelected = (static_cast<int>(vIdx) == m_selectedVariantIndex);

                drawRect(530, vY, 690, 70, isVarSelected ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_BG_ELEVATED);
                drawRectOutline(530, vY, 690, 70, isVarSelected ? Theme::COLOR_FOCUS_RING : Theme::COLOR_BORDER, isVarSelected ? 2 : 1);

                drawText(v.name + " (" + styleToString(v.style) + ")", 550, vY + 12, Theme::COLOR_TEXT_PRIMARY, 15);
                std::string meta = "Автор: " + v.author + " | " + std::to_string(v.width) + "x" +
                                   std::to_string(v.height) + " @" + std::to_string(static_cast<int>(v.fps)) + "fps | " +
                                   std::to_string(v.sizeBytes / (1024 * 1024)) + " MB";
                drawText(meta, 550, vY + 38, Theme::COLOR_TEXT_MUTED, 12);

                if (isVarSelected) {
                    drawText("[A] Установить", 1100, vY + 25, Theme::COLOR_FOCUS_RING, 14);
                }

                vY += 80;
            }
        } else {
            drawText("Для этой игры пока нет вариантов в онлайн-библиотеке.", 530, 290, Theme::COLOR_TEXT_MUTED, 14);
        }"""

new_render_variants = """        // Available variants from catalog
        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = "Доступные варианты видеофона (" + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 250, Theme::COLOR_TEXT_PRIMARY, 16);

        if (totalVariants > 0) {
            const int visibleVariants = 4;
            if (m_variantScrollOffset < 0) m_variantScrollOffset = 0;
            if (m_selectedVariantIndex < m_variantScrollOffset) {
                m_variantScrollOffset = m_selectedVariantIndex;
            } else if (m_selectedVariantIndex >= m_variantScrollOffset + visibleVariants) {
                m_variantScrollOffset = m_selectedVariantIndex - visibleVariants + 1;
            }

            // Scroll indicator ABOVE
            if (m_variantScrollOffset > 0) {
                drawText("▲ Еще варианты выше (используйте D-Pad Влево)", 780, 252, Theme::COLOR_FOCUS_CYAN, 12);
            }

            int vY = 280;
            int endVIdx = std::min(totalVariants, m_variantScrollOffset + visibleVariants);
            for (int vIdx = m_variantScrollOffset; vIdx < endVIdx; ++vIdx) {
                const auto& v = selGame.catalogEntry.variants[vIdx];
                bool isVarSelected = (vIdx == m_selectedVariantIndex);

                // 4IFIR Cyber-Glass variant card
                drawGlassCard(525, vY, 700, 72, isVarSelected, false);

                // Variant Title & Style
                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                drawText(vTitle, 545, vY + 12, isVarSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);

                // Tech Specs Line
                std::string meta = "Автор: " + v.author + "  |  " + std::to_string(v.width) + "x" +
                                   std::to_string(v.height) + " @" + std::to_string(static_cast<int>(v.fps)) + "fps  |  " +
                                   std::to_string(v.sizeBytes / (1024 * 1024)) + " MB";
                drawText(meta, 545, vY + 40, Theme::COLOR_TEXT_MUTED, 12);

                if (isVarSelected) {
                    drawRect(1070, vY + 18, 140, 36, Theme::COLOR_FOCUS_FILL);
                    drawRectOutline(1070, vY + 18, 140, 36, Theme::COLOR_FOCUS_CYAN, 1);
                    drawText("[A] Установить", 1085, vY + 27, Theme::COLOR_FOCUS_CYAN, 13);
                }

                vY += 80;
            }

            // Scroll indicator BELOW
            if (endVIdx < totalVariants) {
                std::string belowStr = "▼ Еще варианты ниже: " + std::to_string(totalVariants - endVIdx) + " шт. (используйте D-Pad Вправо)";
                drawText(belowStr, 720, vY + 6, Theme::COLOR_FOCUS_PINK, 12);
            }
        } else {
            drawText("Для этой игры пока нет вариантов в онлайн-библиотеке.", 530, 290, Theme::COLOR_TEXT_MUTED, 14);
        }"""

if old_render_variants in code:
    code = code.replace(old_render_variants, new_render_variants, 1)
    print("[+] Patched renderTabMyGames with 4-variant window and scroll indicators")
else:
    print("[-] old_render_variants not matched")

# 4. Patch renderTabSettings to 4IFIR Cyber-Glass design matching screenshots
old_render_settings = """void App::renderTabSettings() {
    const auto& s = getStrings(m_language);

    drawRect(30, 80, 1220, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(30, 80, 1220, 570, Theme::COLOR_BORDER, 1);

    drawText("Настройки системы H3H", 60, 110, Theme::COLOR_TEXT_PRIMARY, 20);

    // Option 1: Language
    drawText("Язык интерфейса / Language: " + std::string(m_language == Language::Russian ? "Русский" : "English") + " [Нажмите A для переключения]",
             60, 160, Theme::COLOR_TEXT_PRIMARY, 15);

    // Option 2: Catalog URL
    drawText("Источник каталога: " + std::string(Config::DEFAULT_CATALOG_URL), 60, 205, Theme::COLOR_TEXT_MUTED, 13);

    // Option 3: Storage
    std::string storage = "Свободно на SD: " + std::to_string(m_sysInfo.freeStorageBytes / (1024 * 1024 * 1024)) + " GB";
    drawText(storage, 60, 245, Theme::COLOR_TEXT_MUTED, 14);

    // Option 4: Clear Cache button
    drawRect(60, 300, 280, 45, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(60, 300, 280, 45, Theme::COLOR_BORDER, 1);
    drawText("[X] " + std::string(s.clearCacheBtn), 75, 315, Theme::COLOR_TEXT_PRIMARY, 14);

    // Option 5: Refresh Catalog button
    drawRect(370, 300, 320, 45, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(370, 300, 320, 45, Theme::COLOR_ACCENT, 1);
    drawText("[-] / [Y] " + std::string(s.actionRefreshCatalog), 390, 315, Theme::COLOR_ACCENT, 14);

    // Option 6: Update Application NRO button
    drawRect(720, 300, 340, 45, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(720, 300, 340, 45, Theme::COLOR_SUCCESS, 1);
    drawText("[+] " + std::string(s.updateAppBtn), 740, 315, Theme::COLOR_SUCCESS, 14);
}"""

new_render_settings = """void App::renderTabSettings() {
    const auto& s = getStrings(m_language);

    // Main 4IFIR Frosted Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    drawText("4IFIR System Settings  |  H3H Backgrounds", 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);
    drawText("Настройки системы, прямое обновление NRO и управление локальным хранилищем", 60, 135, Theme::COLOR_TEXT_MUTED, 13);

    // Settings list options
    struct SettingRow {
        std::string title;
        std::string desc;
        std::string value;
        Color valColor;
    };

    std::string freeGb = std::to_string(m_sysInfo.freeStorageBytes / (1024 * 1024 * 1024)) + " GB свободно";
    std::vector<SettingRow> rows = {
        {"Обновление приложения (NRO)", "Проверить и установить новую версию H3H-Backgrounds.nro с GitHub", "v1.0.3 [A - Обновить]", Theme::COLOR_FOCUS_CYAN},
        {"Обновление каталога видеофонов", "Загрузить новейший каталог игр и обложек без обновления NRO", "GitHub Releases [A]", Theme::COLOR_FOCUS_CYAN},
        {"Язык интерфейса / Language", "Выбор языка отображения меню и подсказок управления", (m_language == Language::Russian ? "Русский [A]" : "English [A]"), Theme::COLOR_TEXT_PRIMARY},
        {"Очистить локальный кэш каталога", "Сбросить локальный файл cache.json и пересканировать игры", "[A / X] Сброс", Theme::COLOR_WARNING},
        {"Память на карте MicroSD", "Доступное свободное пространство для загрузки видеофонов", freeGb, Theme::COLOR_SUCCESS}
    };

    int rowY = 175;
    for (size_t i = 0; i < rows.size(); ++i) {
        bool isFocused = (static_cast<int>(i) == m_settingsSelectedIndex);

        // Row background
        if (isFocused) {
            drawRect(50, rowY, 1180, 72, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(50, rowY, 1180, 72, 2);
        } else {
            drawRect(50, rowY, 1180, 72, Theme::COLOR_BG_SURFACE);
            drawRectOutline(50, rowY, 1180, 72, Theme::COLOR_BORDER, 1);
        }

        // Title and description
        drawText(rows[i].title, 75, rowY + 14, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17);
        drawText(rows[i].desc, 75, rowY + 42, Theme::COLOR_TEXT_MUTED, 13);

        // Right value pill
        drawText(rows[i].value, 950, rowY + 26, rows[i].valColor, 15);

        rowY += 84;
    }

    // Bottom Help Banner
    drawRect(50, 600, 1180, 36, Theme::COLOR_BG_BASE);
    drawRectOutline(50, 600, 1180, 36, Theme::COLOR_BORDER, 1);
    drawText("Навигация: [D-Pad Вверх/Вниз] - выбор пункта   |   [A] - применить / обновить   |   [B] - главная", 75, 610, Theme::COLOR_TEXT_MUTED, 13);
}"""

if old_render_settings in code:
    code = code.replace(old_render_settings, new_render_settings, 1)
    print("[+] Patched renderTabSettings to 4IFIR Cyber-Glass design")
else:
    print("[-] old_render_settings not matched")

# 5. Patch renderDialog to 4IFIR Cyber-Glass modal
old_render_dialog = """void App::renderDialog() {
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x00, 0x00, 0x00, 0xBB});

    // Dialog Box
    int dw = 650;
    int dh = 250;
    int dx = (Theme::SCREEN_WIDTH - dw) / 2;
    int dy = (Theme::SCREEN_HEIGHT - dh) / 2;

    drawRect(dx, dy, dw, dh, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(dx, dy, dw, dh, Theme::COLOR_FOCUS_RING, 2);

    drawText(m_dialogTitle, dx + 30, dy + 25, Theme::COLOR_TEXT_PRIMARY, 20);

    // Render multi-line message
    std::stringstream ss(m_dialogMessage);
    std::string line;
    int msgY = dy + 75;
    while (std::getline(ss, line, '\\n')) {
        drawText(line, dx + 30, msgY, Theme::COLOR_TEXT_MUTED, 14);
        msgY += 24;
    }

    // Action buttons
    int btnW = 160;
    int btnH = 40;
    int btnY = dy + 170;

    // Confirm button
    bool focusConfirm = (m_dialogFocus == 0);
    drawRect(dx + 130, btnY, btnW, btnH, focusConfirm ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_BG_SURFACE);
    drawRectOutline(dx + 130, btnY, btnW, btnH, focusConfirm ? Theme::COLOR_FOCUS_RING : Theme::COLOR_BORDER, focusConfirm ? 2 : 1);
    drawText("[A] Подтвердить", dx + 145, btnY + 12, Theme::COLOR_TEXT_PRIMARY, 14);

    // Cancel button
    bool focusCancel = (m_dialogFocus == 1);
    drawRect(dx + 340, btnY, btnW, btnH, focusCancel ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_BG_SURFACE);
    drawRectOutline(dx + 340, btnY, btnW, btnH, focusCancel ? Theme::COLOR_FOCUS_RING : Theme::COLOR_BORDER, focusCancel ? 2 : 1);
    drawText("[B] Отмена", dx + 375, btnY + 12, Theme::COLOR_TEXT_PRIMARY, 14);
}"""

new_render_dialog = """void App::renderDialog() {
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x00, 0x00, 0x00, 0xCC});

    // 4IFIR Obsidian Glass Modal
    int dw = 700;
    int dh = 270;
    int dx = (Theme::SCREEN_WIDTH - dw) / 2;
    int dy = (Theme::SCREEN_HEIGHT - dh) / 2;

    drawRect(dx, dy, dw, dh, Theme::COLOR_BG_MODAL);
    drawNeonGradientOutline(dx, dy, dw, dh, 2);

    drawText(m_dialogTitle, dx + 35, dy + 25, Theme::COLOR_FOCUS_CYAN, 20);

    // Specialized dialog: Update Progress with Capsule Bar
    if (m_activeDialog == DialogType::UpdateProgress) {
        drawText(m_dialogMessage, dx + 35, dy + 70, Theme::COLOR_TEXT_PRIMARY, 15);

        uint64_t bytes = m_nroUpdateBytesDownloaded.load();
        uint64_t total = m_nroUpdateTotalBytes.load();
        double pct = (total > 0) ? (static_cast<double>(bytes) / total * 100.0) : 0.0;

        // Sleek Capsule Progress Bar
        drawCapsuleProgressBar(dx + 35, dy + 115, dw - 70, 22, pct);

        std::string progStr = std::to_string(bytes / (1024 * 1024)) + "." +
                              std::to_string((bytes / (1024 * 102)) % 10) + " MB / " +
                              std::to_string(total / (1024 * 1024)) + "." +
                              std::to_string((total / (1024 * 102)) % 10) + " MB  (" +
                              std::to_string(static_cast<int>(pct)) + "%)";
        drawText(progStr, dx + 35, dy + 150, Theme::COLOR_FOCUS_CYAN, 14);
        drawText("Обновление безопасно заменяет файл на SD карте без перезаписи в Horizon OS", dx + 35, dy + 185, Theme::COLOR_TEXT_MUTED, 12);
        drawText("[B] Скрыть окно в фон", dx + 490, dy + 225, Theme::COLOR_TEXT_MUTED, 13);
        return;
    }

    // Specialized dialog: Update Success
    if (m_activeDialog == DialogType::UpdateSuccess) {
        std::stringstream ss(m_dialogMessage);
        std::string line;
        int msgY = dy + 70;
        while (std::getline(ss, line, '\\n')) {
            drawText(line, dx + 35, msgY, Theme::COLOR_TEXT_PRIMARY, 15);
            msgY += 26;
        }

        int btnW = 200;
        int btnH = 44;
        int btnY = dy + 195;
        drawRect(dx + 250, btnY, btnW, btnH, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(dx + 250, btnY, btnW, btnH, 2);
        drawText("[A] Перезапустить", dx + 275, btnY + 13, Theme::COLOR_FOCUS_CYAN, 15);
        return;
    }

    // Specialized dialog: Alert
    if (m_activeDialog == DialogType::MessageAlert) {
        std::stringstream ss(m_dialogMessage);
        std::string line;
        int msgY = dy + 70;
        while (std::getline(ss, line, '\\n')) {
            drawText(line, dx + 35, msgY, Theme::COLOR_WARNING, 15);
            msgY += 26;
        }

        int btnW = 160;
        int btnH = 40;
        int btnY = dy + 195;
        drawRect(dx + 270, btnY, btnW, btnH, Theme::COLOR_BG_SURFACE);
        drawRectOutline(dx + 270, btnY, btnW, btnH, Theme::COLOR_BORDER, 1);
        drawText("[A] Закрыть", dx + 310, btnY + 12, Theme::COLOR_TEXT_PRIMARY, 14);
        return;
    }

    // Standard Confirmation Dialogs
    std::stringstream ss(m_dialogMessage);
    std::string line;
    int msgY = dy + 70;
    while (std::getline(ss, line, '\\n')) {
        drawText(line, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14);
        msgY += 24;
    }

    int btnW = 180;
    int btnH = 42;
    int btnY = dy + 190;

    // Confirm button
    bool focusConfirm = (m_dialogFocus == 0);
    drawGlassCard(dx + 130, btnY, btnW, btnH, focusConfirm, false);
    drawText("[A] Подтвердить", dx + 155, btnY + 12, focusConfirm ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14);

    // Cancel button
    bool focusCancel = (m_dialogFocus == 1);
    drawGlassCard(dx + 390, btnY, btnW, btnH, focusCancel, false);
    drawText("[B] Отмена", dx + 435, btnY + 12, focusCancel ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14);
}"""

if old_render_dialog in code:
    code = code.replace(old_render_dialog, new_render_dialog, 1)
    print("[+] Patched renderDialog to 4IFIR Cyber-Glass modal")
else:
    print("[-] old_render_dialog not matched")

# Save file
with open(APP_CPP, "w", encoding="utf-8") as f:
    f.write(code)

print("[+] Script patch step 2 finished.")
