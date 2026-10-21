"""
Complete 4IFIR Cyber-Glass redesign for all tabs and smart version-check updater.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

APP_CPP = Path("downloader/src/ui/app.cpp")
code = APP_CPP.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. Update updateApplicationNro with smart version-checking
target_update_nro = """void App::updateApplicationNro() {
    if (m_isUpdatingNro.load()) {
        return;
    }

    m_nroUpdateBytesDownloaded.store(0);
    m_nroUpdateTotalBytes.store(10549492); // ~10.5 MB default expected
    m_activeDialog = DialogType::UpdateProgress;
    m_dialogTitle = (m_language == Language::Russian) ? "Обновление системы H3H" : "H3H System Update";
    m_dialogMessage = (m_language == Language::Russian)
        ? "Загрузка новой версии H3H-Backgrounds.nro с GitHub..."
        : "Downloading new H3H-Backgrounds.nro from GitHub...";
    m_isUpdatingNro = true;

    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }

    m_nroUpdateThread = std::thread([this]() {
        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        
        std::vector<std::string> targetNros = {
            appDir + "/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds.nro"
        };
        if (!m_runningNroPath.empty()) {
            targetNros.insert(targetNros.begin(), m_runningNroPath);
        }

        std::atomic<bool> cancel{false};
        std::string err;
        auto progressCb = [this](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
            (void)speedBps;
            m_nroUpdateBytesDownloaded.store(bytesDownloaded);
            if (totalBytes > 0) m_nroUpdateTotalBytes.store(totalBytes);
        };

        bool ok = m_platform->downloadFile(nroUrl, tempNro, progressCb, cancel, err);
        bool success = false;
        if (ok) {
            // Release romfs handle so Horizon OS FAT32 unlocks the executing .nro file
            m_platform->releaseRomfs();

            for (const auto& targetNro : targetNros) {
                std::error_code ec;
                std::filesystem::create_directories(std::filesystem::path(targetNro).parent_path(), ec);

                // 1. Try atomic rename
                std::remove(targetNro.c_str());
                if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                    success = true;
                    break;
                }

                // 2. Binary stream copy fallback (overwrites existing open FAT32 files safely)
                std::ifstream src(tempNro, std::ios::binary);
                if (src.is_open()) {
                    std::ofstream dst(targetNro, std::ios::binary | std::ios::trunc);
                    if (dst.is_open()) {
                        dst << src.rdbuf();
                        dst.flush();
                        success = true;
                        break;
                    }
                }
            }

            std::remove(tempNro.c_str());
            m_platform->restoreRomfs();

            if (!success) {
                err = "Failed to replace H3H-Backgrounds.nro file";
            }
        }
        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            m_nroUpdateError = std::move(err);
            m_nroUpdateSuccess = success;
        }
        m_nroUpdateDone.store(true);
        m_isUpdatingNro.store(false);
    });
}"""

replacement_update_nro = """void App::updateApplicationNro() {
    if (m_isUpdatingNro.load()) {
        return;
    }

    m_nroUpdateBytesDownloaded.store(0);
    m_nroUpdateTotalBytes.store(10614212); // Expected release size
    m_activeDialog = DialogType::UpdateProgress;
    m_dialogTitle = (m_language == Language::Russian) ? "Проверка обновлений..." : "Checking for updates...";
    m_dialogMessage = (m_language == Language::Russian)
        ? "Связь с GitHub Releases и проверка версии..."
        : "Checking latest version on GitHub...";
    m_isUpdatingNro = true;

    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }

    m_nroUpdateThread = std::thread([this]() {
        // Step 1: Check remote version without downloading NRO
        std::string versionJsonStr;
        std::string checkErr;
        bool checkOk = m_platform->fetchCatalog(Config::VERSION_CHECK_URL, versionJsonStr, checkErr);

        std::string latestVer = Config::APP_VERSION;
        std::string releaseNotes = "Пакет улучшений 4IFIR Cyber-Glass";
        if (checkOk && !versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
                if (vJson.contains("latestVersion")) {
                    latestVer = vJson["latestVersion"].get<std::string>();
                }
                if (vJson.contains("releaseNotes")) {
                    releaseNotes = vJson["releaseNotes"].get<std::string>();
                }
            } catch (...) {
                // Ignore parse errors, fallback to direct download if needed
            }
        }

        // If current version is already up to date, skip download completely
        if (latestVer == Config::APP_VERSION) {
            {
                std::lock_guard<std::mutex> lock(m_nroMutex);
                m_nroUpdateError = "ALREADY_UP_TO_DATE";
                m_nroUpdateSuccess = false;
            }
            m_nroUpdateDone.store(true);
            m_isUpdatingNro.store(false);
            return;
        }

        // Step 2: New version found -> download and install
        m_dialogTitle = (m_language == Language::Russian)
            ? ("Загрузка обновления v" + latestVer)
            : ("Downloading update v" + latestVer);
        m_dialogMessage = (m_language == Language::Russian)
            ? ("Загрузка H3H-Backgrounds.nro с GitHub (" + releaseNotes + ")...")
            : ("Downloading new release from GitHub...");

        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        
        std::vector<std::string> targetNros = {
            appDir + "/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds.nro"
        };
        if (!m_runningNroPath.empty()) {
            targetNros.insert(targetNros.begin(), m_runningNroPath);
        }

        std::atomic<bool> cancel{false};
        std::string err;
        auto progressCb = [this](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
            (void)speedBps;
            m_nroUpdateBytesDownloaded.store(bytesDownloaded);
            if (totalBytes > 0) m_nroUpdateTotalBytes.store(totalBytes);
        };

        bool ok = m_platform->downloadFile(nroUrl, tempNro, progressCb, cancel, err);
        bool success = false;
        if (ok) {
            // Release romfs handle so Horizon OS FAT32 unlocks the executing .nro file
            m_platform->releaseRomfs();

            for (const auto& targetNro : targetNros) {
                std::error_code ec;
                std::filesystem::create_directories(std::filesystem::path(targetNro).parent_path(), ec);

                // 1. Try atomic rename
                std::remove(targetNro.c_str());
                if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                    success = true;
                    break;
                }

                // 2. Binary stream copy fallback (overwrites existing open FAT32 files safely)
                std::ifstream src(tempNro, std::ios::binary);
                if (src.is_open()) {
                    std::ofstream dst(targetNro, std::ios::binary | std::ios::trunc);
                    if (dst.is_open()) {
                        dst << src.rdbuf();
                        dst.flush();
                        success = true;
                        break;
                    }
                }
            }

            std::remove(tempNro.c_str());
            m_platform->restoreRomfs();

            if (!success) {
                err = "Failed to replace H3H-Backgrounds.nro file";
            }
        }
        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            m_nroUpdateError = std::move(err);
            m_nroUpdateSuccess = success;
        }
        m_nroUpdateDone.store(true);
        m_isUpdatingNro.store(false);
    });
}"""

if target_update_nro in code:
    code = code.replace(target_update_nro, replacement_update_nro, 1)
    print("[+] Patched updateApplicationNro with smart version-check")
else:
    print("[-] target_update_nro not found")

# 2. Update completion handler in update() for "ALREADY_UP_TO_DATE"
target_update_loop = """        if (ok) {
            m_activeDialog = DialogType::UpdateSuccess;
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление завершено!" : "Update Complete!";
            m_dialogMessage = (m_language == Language::Russian)
                ? "Приложение H3H-Backgrounds.nro успешно обновлено до актуальной версии!\\nНажмите [A], чтобы перезапустить сейчас, или [B] для продолжения."
                : "H3H-Backgrounds.nro updated successfully!\\nPress [A] to restart now, or [B] to continue.";
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Приложение обновлено!" : "Updated!";
        } else {
            m_activeDialog = DialogType::MessageAlert;
            m_dialogTitle = (m_language == Language::Russian) ? "Ошибка обновления" : "Update Error";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("Не удалось применить обновление: " + err)
                : ("Failed to apply update: " + err);
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? ("Ошибка: " + err) : ("Error: " + err);
        }
        m_notificationFramesRemaining = 240;"""

replacement_update_loop = """        if (ok) {
            m_activeDialog = DialogType::UpdateSuccess;
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление завершено!" : "Update Complete!";
            m_dialogMessage = (m_language == Language::Russian)
                ? "Приложение H3H-Backgrounds.nro успешно обновлено до актуальной версии!\\nНажмите [A], чтобы перезапустить сейчас, или [B] для продолжения."
                : "H3H-Backgrounds.nro updated successfully!\\nPress [A] to restart now, or [B] to continue.";
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Приложение обновлено!" : "Updated!";
        } else if (err == "ALREADY_UP_TO_DATE") {
            m_activeDialog = DialogType::MessageAlert;
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление не требуется" : "Up to date";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("У вас уже установлена актуальная версия:\\nH3H-Backgrounds v" + std::string(Config::APP_VERSION) + ".\\nНовых версий на сервере не найдено.")
                : ("You are already running the latest version:\\nv" + std::string(Config::APP_VERSION) + ".");
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Установлена последняя версия" : "Up to date";
        } else {
            m_activeDialog = DialogType::MessageAlert;
            m_dialogTitle = (m_language == Language::Russian) ? "Ошибка обновления" : "Update Error";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("Не удалось проверить или применить обновление: " + err)
                : ("Failed to apply update: " + err);
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? ("Ошибка: " + err) : ("Error: " + err);
        }
        m_notificationFramesRemaining = 240;"""

if target_update_loop in code:
    code = code.replace(target_update_loop, replacement_update_loop, 1)
    print("[+] Patched update() loop for ALREADY_UP_TO_DATE check")
else:
    print("[-] target_update_loop not found")

# 3. Complete 4IFIR Cyber-Glass redesign of renderHeader() and renderFooter()
target_header_footer = """void App::renderHeader() {
    const auto& s = getStrings(m_language);

    // Top Header bar
    drawRect(0, 0, Theme::SCREEN_WIDTH, 60, Theme::COLOR_BG_SURFACE);
    drawRect(0, 59, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // App Title
    drawText(s.appTitle, 30, 18, Theme::COLOR_TEXT_PRIMARY, 20);

    // Tab items
    const char* tabs[] = {s.tabHome, s.tabMyGames, s.tabCatalog, s.tabDownloads, s.tabSettings};
    int tabX = 350;
    for (int i = 0; i < 5; ++i) {
        bool isActive = (static_cast<int>(m_activeTab) == i);
        if (isActive) {
            drawRect(tabX - 10, 12, 110, 36, Theme::COLOR_BG_ELEVATED);
            drawRectOutline(tabX - 10, 12, 110, 36, Theme::COLOR_FOCUS_RING, 2);
        }
        drawText(tabs[i], tabX, 22, isActive ? Theme::COLOR_FOCUS_RING : Theme::COLOR_TEXT_MUTED, 15);
        tabX += 120;
    }

    // System info pills (Battery & 4IFIR)
    drawText(s.cfwActiveStatus, 960, 22, Theme::COLOR_SUCCESS, 13);
}

void App::renderFooter() {
    const auto& s = getStrings(m_language);

    // Bottom action bar
    drawRect(0, 670, Theme::SCREEN_WIDTH, 50, Theme::COLOR_BG_SURFACE);
    drawRect(0, 670, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    std::string hints;
    if (m_activeTab == Tab::Home) {
        hints = "[L/R] Вкладки   [A] Мои игры   [Y] Установить все недостающие   [X] Обновить   [-] GitHub";
    } else if (m_activeTab == Tab::MyGames) {
        bool hasCover = false;
        if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
            hasCover = m_installedGames[m_myGamesSelectedIndex].hasInstalledCover;
        }
        if (m_language == Language::Russian) {
            hints = hasCover ?
                "[L/R] Вкладки   [A] Сменить вариант   [Y] Удалить фон   [X] Восстановить   [B] Главная   [-] Каталог" :
                "[L/R] Вкладки   [A] Установить   [Y] Установить все   [B] Главная   [-] Каталог";
        } else {
            hints = hasCover ?
                "[L/R] Tabs   [A] Change variant   [Y] Delete background   [X] Restore   [B] Home   [-] Catalog" :
                "[L/R] Tabs   [A] Install   [Y] Install all   [B] Home   [-] Catalog";
        }
    } else if (m_activeTab == Tab::Catalog) {
        hints = "[L/R] Вкладки   [B] Назад   [-] / [X] Обновить каталог   [Y] Установить недостающие";
    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [B] Назад   [-] Обновить каталог";
    } else if (m_activeTab == Tab::Settings) {
        hints = "[L/R] Вкладки   [A] Язык   [B] Назад   [X] " + std::string(s.clearCacheBtn) + "   [-] / [Y] Обновить   [+] " + std::string(s.updateAppBtn);
    }

    drawText(hints, 30, 685, Theme::COLOR_TEXT_MUTED, 14);

    // Prominent "[-] Обновить" touch-button on the bottom right of footer
    drawRect(1070, 675, 180, 38, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(1070, 675, 180, 38, Theme::COLOR_ACCENT, 1);
    drawText("[-] " + std::string(s.actionRefresh), 1095, 686, Theme::COLOR_ACCENT, 14);
}"""

replacement_header_footer = """void App::renderHeader() {
    const auto& s = getStrings(m_language);

    // 4IFIR Cyber-Glass Top Bar
    drawRect(0, 0, Theme::SCREEN_WIDTH, 60, Theme::COLOR_BG_BASE);
    drawRect(0, 59, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // App Title with Cyber Accent
    drawText(s.appTitle, 30, 18, Theme::COLOR_TEXT_PRIMARY, 20);

    // Frosted Glass Tab Pills
    const char* tabs[] = {s.tabHome, s.tabMyGames, s.tabCatalog, s.tabDownloads, s.tabSettings};
    int tabX = 330;
    for (int i = 0; i < 5; ++i) {
        bool isActive = (static_cast<int>(m_activeTab) == i);
        if (isActive) {
            drawRect(tabX - 8, 12, 114, 36, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(tabX - 8, 12, 114, 36, 2);
        } else {
            drawRect(tabX - 8, 12, 114, 36, {0x13, 0x18, 0x24, 0x55});
            drawRectOutline(tabX - 8, 12, 114, 36, Theme::COLOR_BORDER, 1);
        }
        drawText(tabs[i], tabX + 8, 22, isActive ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 15);
        tabX += 122;
    }

    // 4IFIR Active Badge
    drawRect(960, 14, 130, 32, {0x10, 0xB9, 0x81, 0x22});
    drawRectOutline(960, 14, 130, 32, Theme::COLOR_SUCCESS, 1);
    drawText("4IFIR ACTIVE", 975, 23, Theme::COLOR_SUCCESS, 12);

    // Version Pill
    drawRect(1105, 14, 145, 32, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(1105, 14, 145, 32, Theme::COLOR_FOCUS_CYAN, 1);
    std::string verStr = "v" + std::string(Config::APP_VERSION) + " (" + std::to_string(m_sysInfo.batteryPercent) + "%)";
    drawText(verStr, 1120, 23, Theme::COLOR_FOCUS_CYAN, 13);
}

void App::renderFooter() {
    const auto& s = getStrings(m_language);

    // 4IFIR Translucent Bottom Control Bar
    drawRect(0, 670, Theme::SCREEN_WIDTH, 50, Theme::COLOR_BG_BASE);
    drawRect(0, 670, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    std::string hints;
    if (m_activeTab == Tab::Home) {
        hints = "[L/R] Вкладки   [A] Мои игры   [Y] Установить все недостающие   [X] Обновить   [-] GitHub";
    } else if (m_activeTab == Tab::MyGames) {
        bool hasCover = false;
        if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
            hasCover = m_installedGames[m_myGamesSelectedIndex].hasInstalledCover;
        }
        if (m_language == Language::Russian) {
            hints = hasCover ?
                "[L/R] Вкладки   [A] Сменить вариант   [Y] Удалить фон   [X] Восстановить   [B] Главная   [-] Каталог" :
                "[L/R] Вкладки   [A] Установить   [Y] Установить все   [B] Главная   [-] Каталог";
        } else {
            hints = hasCover ?
                "[L/R] Tabs   [A] Change variant   [Y] Delete background   [X] Restore   [B] Home   [-] Catalog" :
                "[L/R] Tabs   [A] Install   [Y] Install all   [B] Home   [-] Catalog";
        }
    } else if (m_activeTab == Tab::Catalog) {
        hints = "[L/R] Вкладки   [B] Назад   [-] / [X] Обновить каталог   [Y] Установить недостающие";
    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [B] Назад   [-] Обновить каталог";
    } else if (m_activeTab == Tab::Settings) {
        hints = "[L/R] Вкладки   [D-Pad Вверх/Вниз] Выбор   [A] Применить   [B] Назад   [X] Сброс кэша";
    }

    drawText(hints, 30, 685, Theme::COLOR_TEXT_MUTED, 14);

    // 4IFIR Cyber-Glass Touch Refresh Button
    drawGlassCard(1070, 675, 180, 38, true, false);
    drawText("[-] " + std::string(s.actionRefresh), 1095, 686, Theme::COLOR_FOCUS_CYAN, 14);
}"""

if target_header_footer in code:
    code = code.replace(target_header_footer, replacement_header_footer, 1)
    print("[+] Patched renderHeader and renderFooter to 4IFIR Cyber-Glass")
else:
    print("[-] target_header_footer not found")

# 4. Redesign renderTabHome to 4IFIR Cyber-Glass
target_tab_home = """void App::renderTabHome() {
    const auto& s = getStrings(m_language);

    size_t detected = m_installedGames.size();
    size_t installedCovers = 0;
    for (const auto& g : m_installedGames) {
        if (g.hasInstalledCover) installedCovers++;
    }
    size_t catalogCount = m_catalogManager.getGamesCount();
    int missing = getMissingCoversCount();

    // Metric Card 1: Detected Games
    drawRect(60, 95, 360, 145, Theme::COLOR_BG_SURFACE);
    drawRectOutline(60, 95, 360, 145, Theme::COLOR_BORDER, 1);
    drawText(s.statDetectedGames, 80, 115, Theme::COLOR_TEXT_MUTED, 16);
    drawText(std::to_string(detected), 80, 150, Theme::COLOR_TEXT_PRIMARY, 42);
    drawText("[A] Перейти в Мои игры", 80, 205, Theme::COLOR_FOCUS_RING, 13);

    // Metric Card 2: Installed Covers
    drawRect(460, 95, 360, 145, Theme::COLOR_BG_SURFACE);
    drawRectOutline(460, 95, 360, 145, Theme::COLOR_BORDER, 1);
    drawText(s.statInstalledCovers, 480, 115, Theme::COLOR_TEXT_MUTED, 16);
    drawText(std::to_string(installedCovers), 480, 150, Theme::COLOR_SUCCESS, 42);
    int missingInstalled = (detected > installedCovers) ? static_cast<int>(detected - installedCovers) : 0;
    drawText(std::to_string(missingInstalled) + " без видеофона", 480, 205, Theme::COLOR_TEXT_MUTED, 13);

    // Metric Card 3: Available in Catalog
    drawRect(860, 95, 360, 145, Theme::COLOR_BG_SURFACE);
    drawRectOutline(860, 95, 360, 145, Theme::COLOR_BORDER, 1);
    drawText(s.statAvailableCatalog, 880, 115, Theme::COLOR_TEXT_MUTED, 16);
    drawText(std::to_string(catalogCount), 880, 150, Theme::COLOR_ACCENT, 42);
    drawText("[-] " + std::string(s.actionRefreshCatalog), 880, 205, Theme::COLOR_FOCUS_RING, 13);

    // Prominent Action Card: Install All Missing Covers
    int cardY = 260;
    int cardH = 120;
    drawRect(60, cardY, 1160, cardH, Theme::COLOR_BG_SURFACE);
    if (missing > 0) {
        drawRectOutline(60, cardY, 1160, cardH, Theme::COLOR_ACCENT, 2);

        // Badge
        drawRect(80, cardY + 18, 175, 26, Theme::COLOR_FOCUS_FILL);
        drawRectOutline(80, cardY + 18, 175, 26, Theme::COLOR_ACCENT, 1);
        drawText("ТРЕБУЕТСЯ ДЕЙСТВИЕ", 90, cardY + 24, Theme::COLOR_FOCUS_RING, 12);

        std::string titleStr = "[Y]  Установить все недостающие видеофоны (" + std::to_string(missing) + " игр)";
        drawText(titleStr, 80, cardY + 54, Theme::COLOR_TEXT_PRIMARY, 20);

        std::string descStr = "Автоматически добавить все игры без видеофонов в очередь загрузки и установить в 4IFIR.";
        drawText(descStr, 80, cardY + 86, Theme::COLOR_TEXT_MUTED, 13);

        // Action button on the right
        drawRect(910, cardY + 35, 280, 50, Theme::COLOR_ACCENT);
        drawText("[Y] Установить все", 955, cardY + 50, Theme::COLOR_TEXT_PRIMARY, 16);
    } else {
        drawRectOutline(60, cardY, 1160, cardH, Theme::COLOR_SUCCESS, 1);
        drawText("✔ Все видеофоны установлены", 80, cardY + 35, Theme::COLOR_SUCCESS, 20);
        drawText("Все Ваши игры на консоли уже имеют установленные видеофоны 4IFIR.", 80, cardY + 70, Theme::COLOR_TEXT_MUTED, 14);
    }

    // Quick Action Cards
    int navY = 405;
    drawRect(60, navY, 560, 95, Theme::COLOR_BG_SURFACE);
    drawRectOutline(60, navY, 560, 95, Theme::COLOR_BORDER, 1);
    drawText("[A] Перейти к списку 'Мои игры'", 85, navY + 22, Theme::COLOR_TEXT_PRIMARY, 16);
    drawText("Просмотр установленных игр, выбор вариантов обложек и ручная установка", 85, navY + 55, Theme::COLOR_TEXT_MUTED, 13);

    drawRect(660, navY, 560, 95, Theme::COLOR_BG_SURFACE);
    drawRectOutline(660, navY, 560, 95, Theme::COLOR_BORDER, 1);
    drawText("[-] Обновить каталог видеофонов", 685, navY + 22, Theme::COLOR_ACCENT, 16);
    drawText("Загрузить новейшую базу видеофонов с официального репозитория GitHub", 685, navY + 55, Theme::COLOR_TEXT_MUTED, 13);

    // Applet Warning if applicable
    if (m_sysInfo.isAppletMode) {
        drawRect(60, 525, 1160, 50, Theme::COLOR_BG_ELEVATED);
        drawRectOutline(60, 525, 1160, 50, Theme::COLOR_WARNING, 2);
        drawText(s.appletWarning, 80, 542, Theme::COLOR_WARNING, 14);
    }
}"""

replacement_tab_home = """void App::renderTabHome() {
    const auto& s = getStrings(m_language);

    size_t detected = m_installedGames.size();
    size_t installedCovers = 0;
    for (const auto& g : m_installedGames) {
        if (g.hasInstalledCover) installedCovers++;
    }
    size_t catalogCount = m_catalogManager.getGamesCount();
    int missing = getMissingCoversCount();

    // 4IFIR Cyber-Glass Metric Cards
    // Metric Card 1: Detected Games
    drawGlassCard(60, 95, 360, 145, false, true);
    drawText(s.statDetectedGames, 85, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(detected), 85, 145, Theme::COLOR_TEXT_PRIMARY, 44);
    drawRect(85, 202, 190, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(85, 202, 190, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("[A] Мои игры", 95, 208, Theme::COLOR_FOCUS_CYAN, 12);

    // Metric Card 2: Installed Covers
    drawGlassCard(460, 95, 360, 145, false, true);
    drawText(s.statInstalledCovers, 485, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(installedCovers), 485, 145, Theme::COLOR_SUCCESS, 44);
    int missingInstalled = (detected > installedCovers) ? static_cast<int>(detected - installedCovers) : 0;
    drawRect(485, 202, 190, 26, {0x10, 0xB9, 0x81, 0x22});
    drawRectOutline(485, 202, 190, 26, Theme::COLOR_SUCCESS, 1);
    std::string missStr = (missingInstalled == 0) ? "Все установлены" : (std::to_string(missingInstalled) + " без видеофона");
    drawText(missStr, 495, 208, Theme::COLOR_SUCCESS, 12);

    // Metric Card 3: Available in Catalog
    drawGlassCard(860, 95, 360, 145, false, true);
    drawText(s.statAvailableCatalog, 885, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(catalogCount), 885, 145, Theme::COLOR_FOCUS_CYAN, 44);
    drawRect(885, 202, 190, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(885, 202, 190, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("[-] Обновить каталог", 895, 208, Theme::COLOR_FOCUS_CYAN, 12);

    // Signature Hero Action Card
    int cardY = 260;
    int cardH = 120;
    if (missing > 0) {
        drawGlassCard(60, cardY, 1160, cardH, true, true);

        // Required Action Badge
        drawRect(85, cardY + 16, 185, 26, Theme::COLOR_FOCUS_FILL);
        drawRectOutline(85, cardY + 16, 185, 26, Theme::COLOR_FOCUS_CYAN, 1);
        drawText("ТРЕБУЕТСЯ ДЕЙСТВИЕ", 95, cardY + 22, Theme::COLOR_FOCUS_CYAN, 12);

        std::string titleStr = "[Y]  Установить все недостающие видеофоны (" + std::to_string(missing) + " шт.)";
        drawText(titleStr, 85, cardY + 52, Theme::COLOR_TEXT_PRIMARY, 20);

        std::string descStr = "Автоматически добавить все игры без видеофонов в очередь и активировать в 4IFIR.";
        drawText(descStr, 85, cardY + 84, Theme::COLOR_TEXT_MUTED, 13);

        // Action button on the right
        drawGlassCard(910, cardY + 35, 280, 50, true, false);
        drawText("[Y] Установить все", 965, cardY + 50, Theme::COLOR_FOCUS_CYAN, 16);
    } else {
        drawGlassCard(60, cardY, 1160, cardH, false, false);
        drawText("✔ Все видеофоны 4IFIR установлены", 85, cardY + 35, Theme::COLOR_SUCCESS, 20);
        drawText("Все установленные на консоли игры имеют активные живые фоны.", 85, cardY + 70, Theme::COLOR_TEXT_MUTED, 14);
    }

    // 4IFIR Cyber-Glass Navigation Cards
    int navY = 405;
    drawGlassCard(60, navY, 560, 95, false, false);
    drawText("[A] Перейти в библиотеку 'Мои игры'", 85, navY + 20, Theme::COLOR_FOCUS_CYAN, 16);
    drawText("Просмотр установленных игр, выбор вариантов обложек и ручная установка", 85, navY + 52, Theme::COLOR_TEXT_MUTED, 13);

    drawGlassCard(660, navY, 560, 95, false, false);
    drawText("[-] Обновить онлайн-каталог фонов", 685, navY + 20, Theme::COLOR_FOCUS_CYAN, 16);
    drawText("Загрузить новейшую базу видеофонов с официального репозитория GitHub", 685, navY + 52, Theme::COLOR_TEXT_MUTED, 13);

    // Applet Warning if applicable
    if (m_sysInfo.isAppletMode) {
        drawGlassCard(60, 525, 1160, 50, false, true);
        drawText(s.appletWarning, 85, 542, Theme::COLOR_WARNING, 14);
    }
}"""

if target_tab_home in code:
    code = code.replace(target_tab_home, replacement_tab_home, 1)
    print("[+] Patched renderTabHome to 4IFIR Cyber-Glass")
else:
    print("[-] target_tab_home not found")

# 5. Redesign renderTabCatalog and renderTabDownloads
target_catalog = """void App::renderTabCatalog() {
    const auto& s = getStrings(m_language);

    drawRect(30, 80, 1220, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(30, 80, 1220, 570, Theme::COLOR_BORDER, 1);
    drawText("Онлайн-каталог видеофонов H3H", 60, 110, Theme::COLOR_TEXT_PRIMARY, 20);

    // Refresh button on top right of Catalog tab
    drawRect(980, 95, 240, 42, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(980, 95, 240, 42, Theme::COLOR_ACCENT, 1);
    drawText("[-] " + std::string(s.actionRefreshCatalog), 1000, 107, Theme::COLOR_ACCENT, 14);

    int missing = getMissingCoversCount();
    if (missing > 0) {
        drawRect(680, 95, 280, 42, Theme::COLOR_BG_ELEVATED);
        drawRectOutline(680, 95, 280, 42, Theme::COLOR_ACCENT, 1);
        drawText("[Y] Установить все (" + std::to_string(missing) + ")", 700, 107, Theme::COLOR_ACCENT, 14);
    }

    const auto& allGames = m_catalogManager.getAllGames();
    if (allGames.empty()) {
        drawText("Каталог пуст или ещё не загружен.", 60, 180, Theme::COLOR_TEXT_MUTED, 16);
        drawText("Нажмите кнопку [-] или [X], чтобы загрузить актуальный список видеофонов с GitHub.", 60, 215, Theme::COLOR_ACCENT, 15);
        return;
    }

    const int visibleCount = 5;
    int totalGames = static_cast<int>(allGames.size());

    if (m_catalogSelectedIndex < m_catalogScrollOffset) {
        m_catalogScrollOffset = m_catalogSelectedIndex;
    }
    if (m_catalogSelectedIndex >= m_catalogScrollOffset + visibleCount) {
        m_catalogScrollOffset = m_catalogSelectedIndex - visibleCount + 1;
    }

    std::string pageInfo = "Игр в каталоге: " + std::to_string(totalGames) +
                           "  (Выбрано: " + std::to_string(m_catalogSelectedIndex + 1) + " / " + std::to_string(totalGames) + ")";
    drawText(pageInfo, 60, 135, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalGames, m_catalogScrollOffset + visibleCount);
    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_catalogSelectedIndex);
        const auto& g = allGames[i];
        drawRect(60, y, 1160, 80, isSelected ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_BG_ELEVATED);
        drawRectOutline(60, y, 1160, 80, isSelected ? Theme::COLOR_FOCUS_RING : Theme::COLOR_BORDER, isSelected ? 2 : 1);

        drawText(g.title, 80, y + 15, Theme::COLOR_TEXT_PRIMARY, 16);
        drawText("Title ID: " + g.titleId + " | Вариантов: " + std::to_string(g.variants.size()),
                 80, y + 42, Theme::COLOR_TEXT_MUTED, 13);

        y += 95;
    }
}"""

replacement_catalog = """void App::renderTabCatalog() {
    const auto& s = getStrings(m_language);

    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    drawText("Онлайн-библиотека видеофонов 4IFIR", 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);

    // Action buttons on top right
    drawGlassCard(980, 95, 240, 42, true, false);
    drawText("[-] " + std::string(s.actionRefreshCatalog), 1000, 107, Theme::COLOR_FOCUS_CYAN, 14);

    int missing = getMissingCoversCount();
    if (missing > 0) {
        drawGlassCard(680, 95, 280, 42, true, false);
        drawText("[Y] Установить все (" + std::to_string(missing) + ")", 700, 107, Theme::COLOR_FOCUS_CYAN, 14);
    }

    const auto& allGames = m_catalogManager.getAllGames();
    if (allGames.empty()) {
        drawText("Каталог пуст или ещё не загружен.", 60, 180, Theme::COLOR_TEXT_MUTED, 16);
        drawText("Нажмите кнопку [-] или [X], чтобы загрузить актуальный список видеофонов с GitHub.", 60, 215, Theme::COLOR_FOCUS_CYAN, 15);
        return;
    }

    const int visibleCount = 5;
    int totalGames = static_cast<int>(allGames.size());

    if (m_catalogSelectedIndex < m_catalogScrollOffset) {
        m_catalogScrollOffset = m_catalogSelectedIndex;
    }
    if (m_catalogSelectedIndex >= m_catalogScrollOffset + visibleCount) {
        m_catalogScrollOffset = m_catalogSelectedIndex - visibleCount + 1;
    }

    std::string pageInfo = "Игр в каталоге: " + std::to_string(totalGames) +
                           "  (Выбрано: " + std::to_string(m_catalogSelectedIndex + 1) + " / " + std::to_string(totalGames) + ")";
    drawText(pageInfo, 60, 135, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalGames, m_catalogScrollOffset + visibleCount);
    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_catalogSelectedIndex);
        const auto& g = allGames[i];

        // 4IFIR Frosted Card for each catalog entry
        drawGlassCard(60, y, 1160, 80, isSelected, false);

        drawText(g.title, 85, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17);
        std::string meta = "Title ID: " + g.titleId + "   |   Доступных стилей: " + std::to_string(g.variants.size());
        drawText(meta, 85, y + 44, Theme::COLOR_TEXT_MUTED, 13);

        if (isSelected) {
            drawRect(1070, y + 22, 130, 36, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(1070, y + 22, 130, 36, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("В библиотеке", 1085, y + 31, Theme::COLOR_FOCUS_CYAN, 12);
        }

        y += 94;
    }
}"""

if target_catalog in code:
    code = code.replace(target_catalog, replacement_catalog, 1)
    print("[+] Patched renderTabCatalog to 4IFIR Cyber-Glass")
else:
    print("[-] target_catalog not found")

# 6. Redesign renderTabDownloads to 4IFIR Cyber-Glass
target_downloads = """void App::renderTabDownloads() {
    drawRect(30, 80, 1220, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(30, 80, 1220, 570, Theme::COLOR_BORDER, 1);
    drawText("Очередь загрузки видеофонов", 60, 110, Theme::COLOR_TEXT_PRIMARY, 20);

    std::vector<DownloadTask> tasksCopy;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        tasksCopy = m_downloadQueue;
    }

    if (tasksCopy.empty()) {
        drawText("Очередь пуста. Выберите видеофон в разделе 'Мои игры' или установите все недостающие.", 60, 160, Theme::COLOR_TEXT_MUTED, 15);
        drawText("Нажмите [Y] на главной вкладке, чтобы автоматически установить все недостающие видеофоны.", 60, 195, Theme::COLOR_ACCENT, 14);
        return;
    }

    const int visibleTasks = 5;
    int totalTasks = static_cast<int>(tasksCopy.size());
    if (m_downloadsScrollOffset < 0) m_downloadsScrollOffset = 0;
    if (m_downloadsScrollOffset + visibleTasks > totalTasks) {
        m_downloadsScrollOffset = std::max(0, totalTasks - visibleTasks);
    }

    std::string summary = "Задач в очереди: " + std::to_string(totalTasks) +
        "  (Показаны " + std::to_string(m_downloadsScrollOffset + 1) + " - " +
        std::to_string(std::min(totalTasks, m_downloadsScrollOffset + visibleTasks)) + ")";
    drawText(summary, 360, 114, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalTasks, m_downloadsScrollOffset + visibleTasks);
    for (int i = m_downloadsScrollOffset; i < endIdx; ++i) {
        const auto& task = tasksCopy[i];
        drawRect(60, y, 1160, 80, Theme::COLOR_BG_ELEVATED);
        drawRectOutline(60, y, 1160, 80, Theme::COLOR_BORDER, 1);

        // Title and variant
        drawText(task.gameTitle + "  [" + task.variant.name + "]", 80, y + 12, Theme::COLOR_TEXT_PRIMARY, 16);

        if (task.state == TaskState::Downloading) {
            // Progress bar
            int barW = 500;
            int barH = 10;
            drawRect(80, y + 44, barW, barH, Theme::COLOR_BG_SURFACE);
            int fillW = static_cast<int>(barW * std::clamp(task.progressPercent / 100.0, 0.0, 1.0));
            drawRect(80, y + 44, fillW, barH, Theme::COLOR_FOCUS_RING);

            std::string progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                std::to_string(task.bytesDownloaded / (1024 * 1024)) + " / " +
                std::to_string(task.totalBytes / (1024 * 1024)) + " MB)";
            drawText(progStr, 600, y + 42, Theme::COLOR_ACCENT, 13);

            double speedKb = task.downloadSpeedBps / 1024.0;
            std::string speedStr;
            if (speedKb >= 1024.0) {
                speedStr = std::to_string(static_cast<int>(speedKb / 1024.0)) + "." +
                    std::to_string(static_cast<int>((speedKb / 102.4)) % 10) + " MB/s";
            } else {
                speedStr = std::to_string(static_cast<int>(speedKb)) + " KB/s";
            }
            drawText(speedStr, 760, y + 42, Theme::COLOR_TEXT_MUTED, 13);

            drawRect(1010, y + 25, 180, 32, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_FOCUS_RING, 1);
            drawText("Загрузка...", 1055, y + 32, Theme::COLOR_FOCUS_RING, 13);
        } else if (task.state == TaskState::Verifying) {
            drawText("Проверка SHA-256 и установка в 4IFIR...", 80, y + 42, Theme::COLOR_WARNING, 14);
            drawRect(1010, y + 25, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_WARNING, 1);
            drawText("Установка...", 1050, y + 32, Theme::COLOR_WARNING, 13);
        } else if (task.state == TaskState::Completed) {
            drawText("Успешно установлен в sdmc:/recordings/covers/", 80, y + 42, Theme::COLOR_SUCCESS, 14);
            drawRect(1010, y + 25, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_SUCCESS, 1);
            drawText("✔ Установлен", 1045, y + 32, Theme::COLOR_SUCCESS, 13);
        } else if (task.state == TaskState::Failed) {
            drawText("Ошибка: " + task.errorMessage, 80, y + 42, Theme::COLOR_DANGER, 13);
            drawRect(1010, y + 25, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_DANGER, 1);
            drawText("✖ Ошибка", 1060, y + 32, Theme::COLOR_DANGER, 13);
        } else { // Pending
            drawText("В очереди ожидания...", 80, y + 42, Theme::COLOR_TEXT_MUTED, 14);
            drawRect(1010, y + 25, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_BORDER, 1);
            drawText("Ожидание", 1060, y + 32, Theme::COLOR_TEXT_MUTED, 13);
        }

        y += 92;
    }
}"""

replacement_downloads = """void App::renderTabDownloads() {
    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    drawText("Очередь загрузки видеофонов 4IFIR", 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);

    std::vector<DownloadTask> tasksCopy;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        tasksCopy = m_downloadQueue;
    }

    if (tasksCopy.empty()) {
        drawText("Очередь пуста. Выберите видеофон в разделе 'Мои игры' или установите все недостающие.", 60, 160, Theme::COLOR_TEXT_MUTED, 15);
        drawText("Нажмите [Y] на главной вкладке, чтобы автоматически добавить все игры в очередь.", 60, 195, Theme::COLOR_FOCUS_CYAN, 14);
        return;
    }

    const int visibleTasks = 5;
    int totalTasks = static_cast<int>(tasksCopy.size());
    if (m_downloadsScrollOffset < 0) m_downloadsScrollOffset = 0;
    if (m_downloadsScrollOffset + visibleTasks > totalTasks) {
        m_downloadsScrollOffset = std::max(0, totalTasks - visibleTasks);
    }

    std::string summary = "Задач в очереди: " + std::to_string(totalTasks) +
        "  (Показаны " + std::to_string(m_downloadsScrollOffset + 1) + " - " +
        std::to_string(std::min(totalTasks, m_downloadsScrollOffset + visibleTasks)) + ")";
    drawText(summary, 430, 110, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalTasks, m_downloadsScrollOffset + visibleTasks);
    for (int i = m_downloadsScrollOffset; i < endIdx; ++i) {
        const auto& task = tasksCopy[i];
        bool isDownloading = (task.state == TaskState::Downloading);

        // 4IFIR Frosted Card for each task
        drawGlassCard(60, y, 1160, 80, isDownloading, false);

        // Title and variant
        drawText(task.gameTitle + "  [" + task.variant.name + "]", 85, y + 14, isDownloading ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);

        if (task.state == TaskState::Downloading) {
            // Sleek Capsule Progress Bar
            drawCapsuleProgressBar(85, y + 44, 480, 16, task.progressPercent);

            std::string progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                std::to_string(task.bytesDownloaded / (1024 * 1024)) + " / " +
                std::to_string(task.totalBytes / (1024 * 1024)) + " MB)";
            drawText(progStr, 580, y + 44, Theme::COLOR_FOCUS_CYAN, 13);

            double speedKb = task.downloadSpeedBps / 1024.0;
            std::string speedStr;
            if (speedKb >= 1024.0) {
                speedStr = std::to_string(static_cast<int>(speedKb / 1024.0)) + "." +
                    std::to_string(static_cast<int>((speedKb / 102.4)) % 10) + " MB/s";
            } else {
                speedStr = std::to_string(static_cast<int>(speedKb)) + " KB/s";
            }
            drawText(speedStr, 760, y + 44, Theme::COLOR_TEXT_MUTED, 13);

            drawRect(1010, y + 24, 180, 32, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("Загрузка...", 1055, y + 31, Theme::COLOR_FOCUS_CYAN, 13);
        } else if (task.state == TaskState::Verifying) {
            drawText("Установка в 4IFIR (sdmc:/recordings/covers/)...", 85, y + 44, Theme::COLOR_WARNING, 14);
            drawRect(1010, y + 24, 180, 32, {0xF5, 0x9E, 0x0B, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_WARNING, 1);
            drawText("Установка...", 1050, y + 31, Theme::COLOR_WARNING, 13);
        } else if (task.state == TaskState::Completed) {
            drawText("✔ Успешно активирован в sdmc:/recordings/covers/", 85, y + 44, Theme::COLOR_SUCCESS, 14);
            drawRect(1010, y + 24, 180, 32, {0x10, 0xB9, 0x81, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_SUCCESS, 1);
            drawText("✔ Установлен", 1045, y + 31, Theme::COLOR_SUCCESS, 13);
        } else if (task.state == TaskState::Failed) {
            drawText("Ошибка: " + task.errorMessage, 85, y + 44, Theme::COLOR_DANGER, 13);
            drawRect(1010, y + 24, 180, 32, {0xF4, 0x3F, 0x5E, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_DANGER, 1);
            drawText("✖ Ошибка", 1060, y + 31, Theme::COLOR_DANGER, 13);
        } else { // Pending
            drawText("В очереди ожидания...", 85, y + 44, Theme::COLOR_TEXT_MUTED, 14);
            drawRect(1010, y + 24, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_BORDER, 1);
            drawText("Ожидание", 1060, y + 31, Theme::COLOR_TEXT_MUTED, 13);
        }

        y += 94;
    }
}"""

if target_downloads in code:
    code = code.replace(target_downloads, replacement_downloads, 1)
    print("[+] Patched renderTabDownloads to 4IFIR Cyber-Glass")
else:
    print("[-] target_downloads not found")

# 7. Redesign renderTabMyGames left panel to 4IFIR Cyber-Glass
target_my_games_left = """    // Left List Pane (450px wide)
    drawRect(30, 80, 450, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(30, 80, 450, 570, Theme::COLOR_BORDER, 1);

    const int visibleCount = 8;
    int totalCount = static_cast<int>(m_installedGames.size());

    if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex;
    }
    if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + visibleCount) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex - visibleCount + 1;
    }

    if (totalCount > 0) {
        std::string posStr = std::to_string(m_myGamesSelectedIndex + 1) + " / " + std::to_string(totalCount);
        drawText(posStr, 380, 84, Theme::COLOR_ACCENT, 12);
    }

    int startY = 105;
    int endIdx = std::min(totalCount, m_myGamesScrollOffset + visibleCount);
    for (int i = m_myGamesScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_myGamesSelectedIndex);
        const auto& game = m_installedGames[i];

        if (isSelected) {
            drawRect(35, startY, 440, 60, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(35, startY, 440, 60, Theme::COLOR_FOCUS_RING, 2);
        }

        drawText(game.name, 50, startY + 10, Theme::COLOR_TEXT_PRIMARY, 15);
        drawText(game.titleId, 50, startY + 34, Theme::COLOR_TEXT_MUTED, 12);

        // Status pill
        if (game.hasInstalledCover) {
            drawRect(380, startY + 18, 80, 24, Theme::COLOR_SUCCESS);
            drawText(s.statusInstalled, 390, startY + 22, Theme::COLOR_TEXT_PRIMARY, 11);
        } else {
            drawRect(380, startY + 18, 80, 24, Theme::COLOR_BG_ELEVATED);
            drawText(s.statusNoCover, 392, startY + 22, Theme::COLOR_TEXT_MUTED, 11);
        }

        startY += 66;
    }

    // Right Details Pane (750px wide)
    drawRect(500, 80, 750, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(500, 80, 750, 570, Theme::COLOR_BORDER, 1);"""

replacement_my_games_left = """    // Left List Pane (450px wide) - 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 450, 570, false, false);

    const int visibleCount = 8;
    int totalCount = static_cast<int>(m_installedGames.size());

    if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex;
    }
    if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + visibleCount) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex - visibleCount + 1;
    }

    if (totalCount > 0) {
        std::string posStr = std::to_string(m_myGamesSelectedIndex + 1) + " / " + std::to_string(totalCount);
        drawText(posStr, 380, 86, Theme::COLOR_FOCUS_CYAN, 12);
    }

    int startY = 105;
    int endIdx = std::min(totalCount, m_myGamesScrollOffset + visibleCount);
    for (int i = m_myGamesScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_myGamesSelectedIndex);
        const auto& game = m_installedGames[i];

        // 4IFIR Card with neon outline on focus
        drawGlassCard(35, startY, 440, 60, isSelected, isSelected);

        drawText(game.name, 48, startY + 10, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);
        drawText(game.titleId, 48, startY + 34, Theme::COLOR_TEXT_MUTED, 12);

        // Status pill
        if (game.hasInstalledCover) {
            drawRect(370, startY + 18, 95, 24, {0x10, 0xB9, 0x81, 0x22});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ФОН ЕСТЬ", 380, startY + 23, Theme::COLOR_SUCCESS, 11);
        } else {
            drawRect(370, startY + 18, 95, 24, {0x28, 0x33, 0x47, 0x55});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_BORDER, 1);
            drawText("НЕТ ФОНА", 384, startY + 23, Theme::COLOR_TEXT_MUTED, 11);
        }

        startY += 66;
    }

    // Right Details Pane (750px wide) - 4IFIR Cyber-Glass Container
    drawGlassCard(500, 80, 750, 570, false, false);"""

if target_my_games_left in code:
    code = code.replace(target_my_games_left, replacement_my_games_left, 1)
    print("[+] Patched renderTabMyGames left panel to 4IFIR Cyber-Glass")
else:
    print("[-] target_my_games_left not found")

APP_CPP.write_text(code, encoding="utf-8")
print("[+] All redesign patches saved.")
