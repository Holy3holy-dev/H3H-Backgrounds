import os
import re

app_cpp_path = r"downloader/src/ui/app.cpp"
with open(app_cpp_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. In App::init(): call loadFavorites() and refreshStorageStats()
init_target = """    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
    return true;"""

init_replacement = """    loadFavorites();
    refreshStorageStats();

    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
    return true;"""

assert init_target in code, "init_target not found"
code = code.replace(init_target, init_replacement, 1)

# 2. In App::shutdown(): call saveFavorites()
shutdown_target = """void App::shutdown() {
    m_cancelQueue.store(true);"""

shutdown_replacement = """void App::shutdown() {
    saveFavorites();
    m_cancelQueue.store(true);"""

assert shutdown_target in code, "shutdown_target not found"
code = code.replace(shutdown_target, shutdown_replacement, 1)

# 3. In handleInput(): ZL / ZR trigger event routing
# Currently:
#   } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT) {
#       uint32_t now = SDL_GetTicks();
#       if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
#           onButtonPress(9 /* LEFTSHOULDER / ZL */);
#           m_lastTriggerTime = now;
#       }
#   } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
#       uint32_t now = SDL_GetTicks();
#       if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
#           onButtonPress(10 /* RIGHTSHOULDER / ZR */);
#           m_lastTriggerTime = now;
#       }
#   }
trigger_old = """            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(9 /* LEFTSHOULDER / ZL */);
                    m_lastTriggerTime = now;
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(10 /* RIGHTSHOULDER / ZR */);
                    m_lastTriggerTime = now;
                }
            }"""

trigger_new = """            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(15 /* BUTTON_ZL */);
                    m_lastTriggerTime = now;
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(16 /* BUTTON_ZR */);
                    m_lastTriggerTime = now;
                }
            }"""

assert trigger_old in code, "trigger_old not found"
code = code.replace(trigger_old, trigger_new, 1)

# 4. In handleInput(): Touch support for catalog checkboxes & action banner, and Settings rows
touch_catalog_old = """            // Catalog Tab: click directly on an item in the list
            else if (m_activeTab == Tab::Catalog && mx >= 60 && mx <= 1220 && my >= 160 && my <= 640) {
                int clickedIndex = m_catalogScrollOffset + (my - 160) / 94;
                int totalGames = static_cast<int>(m_filteredCatalogGames.size());
                if (clickedIndex >= 0 && clickedIndex < totalGames) {
                    if (m_catalogSelectedIndex == clickedIndex || mx >= 950) {
                        m_catalogSelectedIndex = clickedIndex;
                        openCollectionBrowser(m_filteredCatalogGames[clickedIndex]);
                    } else {
                        m_catalogSelectedIndex = clickedIndex;
                    }
                }
            }
            // Settings Tab: buttons at y in [300, 350]
            else if (m_activeTab == Tab::Settings && my >= 300 && my <= 350) {
                if (mx >= 60 && mx <= 340) onButtonPress(2 /* Clear Cache */);
                else if (mx >= 370 && mx <= 690) onButtonPress(3 /* Refresh Catalog */);
                else if (mx >= 720 && mx <= 1060) onButtonPress(6 /* Update NRO */);
            }"""

touch_catalog_new = """            // Catalog Tab: click directly on an item in the list or batch banner
            else if (m_activeTab == Tab::Catalog && mx >= 60 && mx <= 1220 && my >= 160 && my <= 660) {
                // Check if clicked on floating action banner
                if (!m_batchSelectedTitleIds.empty() && my >= 610 && my <= 660 && mx >= 200 && mx <= 1080) {
                    if (mx >= 460 && mx <= 710) {
                        installBatchSelected();
                    } else if (mx >= 715 && mx <= 860) {
                        clearBatchSelection();
                    }
                } else {
                    int clickedIndex = m_catalogScrollOffset + (my - 160) / 94;
                    int totalGames = static_cast<int>(m_filteredCatalogGames.size());
                    if (clickedIndex >= 0 && clickedIndex < totalGames) {
                        // Tapping checkbox on left toggles batch selection
                        if (mx >= 60 && mx <= 120) {
                            toggleBatchSelection(m_filteredCatalogGames[clickedIndex].titleId);
                        } else if (m_catalogSelectedIndex == clickedIndex || mx >= 915) {
                            m_catalogSelectedIndex = clickedIndex;
                            openCollectionBrowser(m_filteredCatalogGames[clickedIndex]);
                        } else {
                            m_catalogSelectedIndex = clickedIndex;
                        }
                    }
                }
            }
            // Settings Tab: interactive setting rows at y in [230, 615]
            else if (m_activeTab == Tab::Settings && mx >= 50 && mx <= 1230 && my >= 230 && my <= 615) {
                int clickedRow = (my - 236) / 54;
                if (clickedRow >= 0 && clickedRow <= 6) {
                    m_settingsSelectedIndex = clickedRow;
                    onButtonPress(0 /* A - Activate Setting */);
                }
            }"""

assert touch_catalog_old in code, "touch_catalog_old not found"
code = code.replace(touch_catalog_old, touch_catalog_new, 1)

# 5. In Collection Browser onButtonPress: add L / R3 toggle favorite
coll_input_target = """        if (button == 2 /* X - Fullscreen live video */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                openFullscreenPreviewForCatalogGame(m_collectionEntry, m_collectionSelectedIndex);
            }
            return;
        }"""

coll_input_replacement = """        if (button == 8 /* R3 */ || button == 9 /* L - Toggle Favorite */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                toggleFavoriteVariant(m_collectionTitleId, m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 2 /* X - Fullscreen live video */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                openFullscreenPreviewForCatalogGame(m_collectionEntry, m_collectionSelectedIndex);
            }
            return;
        }"""

assert coll_input_target in code, "coll_input_target not found"
code = code.replace(coll_input_target, coll_input_replacement, 1)

# 6. In Fullscreen Preview onButtonPress: add L / R3 toggle favorite
preview_input_target = """        if (button == 1 /* B */ || button == 2 /* X */) {
            closeFullscreenPreview();
    closeCollectionBrowser();
            return;
        }"""

preview_input_replacement = """        if (button == 8 /* R3 */ || button == 9 /* L - Toggle Favorite */) {
            if (!m_previewVariants.empty() && m_previewVariantIndex >= 0 &&
                m_previewVariantIndex < static_cast<int>(m_previewVariants.size())) {
                toggleFavoriteVariant(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
            }
            return;
        }
        if (button == 1 /* B */ || button == 2 /* X */) {
            closeFullscreenPreview();
    closeCollectionBrowser();
            return;
        }"""

assert preview_input_target in code, "preview_input_target not found"
code = code.replace(preview_input_target, preview_input_replacement, 1)

# 7. In onButtonPress: ZL & ZR buttons handling before tab switching
tab_switch_old = """    if (button == 9 /* LEFTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 0) ? 4 : tabInt - 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }
    if (button == 10 /* RIGHTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 4) ? 0 : tabInt + 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }"""

tab_switch_new = """    // ZL / ZR Triggers
    if (button == 15 /* BUTTON_ZL */) {
        if (!m_batchSelectedTitleIds.empty()) {
            installBatchSelected();
            return;
        }
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 0) ? 4 : tabInt - 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }
    if (button == 16 /* BUTTON_ZR */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 4) ? 0 : tabInt + 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }
    if (button == 9 /* LEFTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 0) ? 4 : tabInt - 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }
    if (button == 10 /* RIGHTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 4) ? 0 : tabInt + 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }"""

assert tab_switch_old in code, "tab_switch_old not found"
code = code.replace(tab_switch_old, tab_switch_new, 1)

# 8. User requirement 3: Only B in Home exits app. In other tabs, B returns to Home!
# In MyGames:
mygames_b_old = """        if (m_myGamesActivePane == MyGamesPane::GamesList) {
            // LEFT COLUMN: Games List navigation
            if (button == 1 /* B - Exit to hbmenu */) {
                m_running = false;
                return;
            }"""

mygames_b_new = """        if (m_myGamesActivePane == MyGamesPane::GamesList) {
            // LEFT COLUMN: Games List navigation
            if (button == 1 /* B - Back to Home */) {
                m_activeTab = Tab::Home;
                return;
            }
            if (button == 8 /* R3 - Toggle Batch Selection */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    toggleBatchSelection(m_installedGames[m_myGamesSelectedIndex].titleId);
                }
                return;
            }"""

assert mygames_b_old in code, "mygames_b_old not found"
code = code.replace(mygames_b_old, mygames_b_new, 1)

# In Catalog onButtonPress: add B return to Home, R3/L3 toggle batch selection, ZL install batch
catalog_input_old = """    } else if (m_activeTab == Tab::Catalog) {
        int totalGames = static_cast<int>(m_filteredCatalogGames.size());
        if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) m_catalogSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) m_catalogSelectedIndex++;
        } else if (button == 13 /* DPAD_LEFT - Page Up 5 */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
        } else if (button == 14 /* DPAD_RIGHT - Page Down 5 */) {
            if (totalGames > 0) m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
        } else if (button == 0 /* A - Enter Collection Browser */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = m_filteredCatalogGames[m_catalogSelectedIndex];
                openCollectionBrowser(entry);
            }
        } else if (button == 2 /* X - Cycle Sort Mode */) {
            cycleCatalogSortMode();
        } else if (button == 3 /* Y - Open Horizon Software Keyboard (Search) */) {
            openCatalogKeyboard();
        } else if (button == 4 /* MINUS - Clear Search or Refresh */) {
            if (!m_catalogSearchQuery.empty()) {
                m_catalogSearchQuery.clear();
                rebuildCatalogFilter();
                m_statusNotification = (m_language == Language::Russian) ? "Поиск сброшен (показаны все игры)" : "Search cleared";
                m_notificationFramesRemaining = 90;
            } else {
                fetchRemoteCatalog();
            }
        }
    } else if (m_activeTab == Tab::Downloads) {
        if (button == 11 /* DPAD_UP */) {
            if (m_downloadsScrollOffset > 0) m_downloadsScrollOffset--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_downloadsScrollOffset + 5 < static_cast<int>(m_downloadQueue.size())) m_downloadsScrollOffset++;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        }
    } else if (m_activeTab == Tab::Settings) {
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
                    m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
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
            m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
            refreshInstalledGames();
            m_statusNotification = getStrings(m_language).cacheClearedMsg;
            m_notificationFramesRemaining = 120;
        } else if (button == 3 /* Y - Refresh Catalog */) {
            fetchRemoteCatalog();
        } else if (button == 6 /* START / Plus - Update App NRO */) {
            updateApplicationNro();
        }"""

catalog_input_new = """    } else if (m_activeTab == Tab::Catalog) {
        int totalGames = static_cast<int>(m_filteredCatalogGames.size());
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 7 /* L3 */ || button == 8 /* R3 - Toggle Batch Selection */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                toggleBatchSelection(m_filteredCatalogGames[m_catalogSelectedIndex].titleId);
            }
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) m_catalogSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) m_catalogSelectedIndex++;
        } else if (button == 13 /* DPAD_LEFT - Page Up 5 */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
        } else if (button == 14 /* DPAD_RIGHT - Page Down 5 */) {
            if (totalGames > 0) m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
        } else if (button == 0 /* A - Enter Collection Browser */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = m_filteredCatalogGames[m_catalogSelectedIndex];
                openCollectionBrowser(entry);
            }
        } else if (button == 2 /* X - Cycle Sort Mode */) {
            cycleCatalogSortMode();
        } else if (button == 3 /* Y - Open Horizon Software Keyboard (Search) */) {
            openCatalogKeyboard();
        } else if (button == 4 /* MINUS - Clear Selection or Search or Refresh */) {
            if (!m_batchSelectedTitleIds.empty()) {
                clearBatchSelection();
            } else if (!m_catalogSearchQuery.empty()) {
                m_catalogSearchQuery.clear();
                rebuildCatalogFilter();
                m_statusNotification = (m_language == Language::Russian) ? "Поиск сброшен (показаны все игры)" : "Search cleared";
                m_notificationFramesRemaining = 90;
            } else {
                fetchRemoteCatalog();
            }
        }
    } else if (m_activeTab == Tab::Downloads) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_downloadsScrollOffset > 0) m_downloadsScrollOffset--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_downloadsScrollOffset + 5 < static_cast<int>(m_downloadQueue.size())) m_downloadsScrollOffset++;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        }
    } else if (m_activeTab == Tab::Settings) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_settingsSelectedIndex > 0) m_settingsSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_settingsSelectedIndex < 6) m_settingsSelectedIndex++;
        } else if (button == 0 /* A - Activate Selected Setting */) {
            switch (m_settingsSelectedIndex) {
                case 0: // Check & Update NRO
                    updateApplicationNro();
                    break;
                case 1: // Refresh Catalog
                    fetchRemoteCatalog();
                    break;
                case 2: // Clear thumbnail previews cache
                    clearThumbnailCache();
                    break;
                case 3: // Clear video player cache
                    clearVideoPreviewCache();
                    break;
                case 4: // Clear Local Catalog Cache (cache.json)
                    m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
                    refreshInstalledGames();
                    m_statusNotification = getStrings(m_language).cacheClearedMsg;
                    m_notificationFramesRemaining = 120;
                    break;
                case 5: // Integrity check
                    runIntegrityCheck();
                    break;
                case 6: // Toggle Language
                    m_language = (m_language == Language::Russian) ? Language::English : Language::Russian;
                    m_statusNotification = (m_language == Language::Russian) ? "Язык интерфейса: Русский" : "Interface language: English";
                    m_notificationFramesRemaining = 120;
                    break;
            }
        } else if (button == 2 /* X - Clear Cache */) {
            m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
            refreshInstalledGames();
            m_statusNotification = getStrings(m_language).cacheClearedMsg;
            m_notificationFramesRemaining = 120;
        } else if (button == 3 /* Y - Refresh Catalog */) {
            fetchRemoteCatalog();
        } else if (button == 6 /* START / Plus - Update App NRO */) {
            updateApplicationNro();
        }"""

assert catalog_input_old in code, "catalog_input_old not found"
code = code.replace(catalog_input_old, catalog_input_new, 1)

# 9. Update renderTabSettings()
settings_render_old = """void App::renderTabSettings() {
    const auto& s = getStrings(m_language);
    (void)s;

    // Main 4IFIR Frosted Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    drawText(std::string("4IFIR System Settings  |  ") + Config::APP_NAME, 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);
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
        {"Обновление приложения (NRO)", "Проверить и установить новую версию H3H-Backgrounds.nro с GitHub", std::string("v") + Config::APP_VERSION + " [A - Проверить]", Theme::COLOR_FOCUS_CYAN},
        {"Обновление каталога видеофонов", "Загрузить новейший каталог игр и обложек без обновления NRO", "GitHub Releases [A]", Theme::COLOR_FOCUS_CYAN},
        {"Язык интерфейса / Language", "Выбор языка отображения меню и подсказок управления", (m_language == Language::Russian ? "Русский [A]" : "English [A]"), Theme::COLOR_TEXT_PRIMARY},
        {"Очистить локальный кэш каталога", "Сбросить локальный файл cache.json и пересканировать игры", "[A / X] Сброс", Theme::COLOR_WARNING},
        {"Память на карте MicroSD", "Доступное свободное пространство для загрузки видеофонов", freeGb, Theme::COLOR_SUCCESS},
        {"Проверка целостности фонов", "Сканирование установленных видеофонов на ошибки и битые файлы", "[A] Сканировать", Theme::COLOR_FOCUS_CYAN}
    };

    int rowY = 165;
    for (size_t i = 0; i < rows.size(); ++i) {
        bool isFocused = (static_cast<int>(i) == m_settingsSelectedIndex);

        // Row background
        if (isFocused) {
            drawRect(50, rowY, 1180, 62, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(50, rowY, 1180, 62, 2);
        } else {
            drawRect(50, rowY, 1180, 62, Theme::COLOR_BG_SURFACE);
            drawRectOutline(50, rowY, 1180, 62, Theme::COLOR_BORDER, 1);
        }

        // Title and description
        drawText(rows[i].title, 75, rowY + 11, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 850);
        drawText(rows[i].desc, 75, rowY + 36, Theme::COLOR_TEXT_MUTED, 12, 850);

        // Right value pill
        drawText(rows[i].value, 940, rowY + 20, rows[i].valColor, 15, 270);

        rowY += 70;
    }

    // Bottom Help Banner
    drawRect(50, 600, 1180, 36, Theme::COLOR_BG_BASE);
    drawRectOutline(50, 600, 1180, 36, Theme::COLOR_BORDER, 1);
    drawText("Навигация: [D-Pad Вверх/Вниз] - выбор пункта   |   [A] - применить / обновить   |   [B] - главная", 75, 610, Theme::COLOR_TEXT_MUTED, 13);
}"""

settings_render_new = """void App::renderTabSettings() {
    const auto& s = getStrings(m_language);
    (void)s;

    refreshStorageStats();

    // Main 4IFIR Frosted Glass Container
    drawGlassCard(30, 80, 1220, 580, false, false);

    drawText(std::string("4IFIR System & Storage Manager  |  ") + Config::APP_NAME, 60, 95, Theme::COLOR_TEXT_PRIMARY, 20);

    // MicroSD Visual Dashboard Card at y = 120
    drawRect(50, 122, 1180, 100, Theme::COLOR_BG_SURFACE);
    drawRectOutline(50, 122, 1180, 100, Theme::COLOR_BORDER, 1);

    double freeGb = static_cast<double>(m_storageStats.freeSdBytes) / (1024.0 * 1024.0 * 1024.0);
    double totalGb = static_cast<double>(m_storageStats.totalSdBytes) / (1024.0 * 1024.0 * 1024.0);
    double usedGb = std::max(0.0, totalGb - freeGb);
    double usedPct = (totalGb > 0.0) ? (usedGb / totalGb * 100.0) : 0.0;

    char sdInfoBuf[128];
    snprintf(sdInfoBuf, sizeof(sdInfoBuf), "MicroSD: %.1f GB свободно из %.1f GB (%.1f%% занято)", freeGb, totalGb, usedPct);
    drawText(sdInfoBuf, 70, 132, Theme::COLOR_FOCUS_CYAN, 14);

    drawCapsuleProgressBar(70, 154, 1140, 14, usedPct);

    // Three metric badges inside dashboard
    double coversMb = static_cast<double>(m_storageStats.coversBytes) / (1024.0 * 1024.0);
    double thumbsMb = static_cast<double>(m_storageStats.thumbsBytes) / (1024.0 * 1024.0);
    double vidCacheMb = static_cast<double>(m_storageStats.vidCacheBytes) / (1024.0 * 1024.0);

    char covBuf[64], thBuf[64], vcBuf[64];
    snprintf(covBuf, sizeof(covBuf), "📁 Видеофоны: %d шт. (%.1f MB)", m_storageStats.coversCount, coversMb);
    snprintf(thBuf, sizeof(thBuf), "🖼️ Кэш превью: %d шт. (%.1f MB)", m_storageStats.thumbsCount, thumbsMb);
    snprintf(vcBuf, sizeof(vcBuf), "🎬 Кэш видео: %d шт. (%.1f MB)", m_storageStats.vidCacheCount, vidCacheMb);

    drawText(covBuf, 70, 185, Theme::COLOR_SUCCESS, 13);
    drawText(thBuf, 460, 185, Theme::COLOR_FOCUS_CYAN, 13);
    drawText(vcBuf, 850, 185, Theme::COLOR_FOCUS_PINK, 13);

    // Settings list options (7 rows)
    struct SettingRow {
        std::string title;
        std::string desc;
        std::string value;
        Color valColor;
    };

    std::vector<SettingRow> rows = {
        {"Обновление приложения (NRO)", "Проверить и установить новую версию H3H-Backgrounds.nro с GitHub", std::string("v") + Config::APP_VERSION + " [A]", Theme::COLOR_FOCUS_CYAN},
        {"Обновление каталога видеофонов", "Загрузить новейший каталог игр и обложек без обновления NRO", "GitHub Releases [A]", Theme::COLOR_FOCUS_CYAN},
        {"Очистить кэш мини-превью (галерея)", "Удалить сохраненные миниатюры обложек (thumbs/) для освобождения места", "[A] Очистить", Theme::COLOR_FOCUS_PINK},
        {"Очистить кэш видеоплеера (видео)", "Удалить временные видеофайлы предпросмотра (mp4) на SD-карте", "[A] Очистить", Theme::COLOR_FOCUS_PINK},
        {"Очистить локальный кэш каталога", "Сбросить локальный файл cache.json и пересканировать игры", "[A / X] Сброс", Theme::COLOR_WARNING},
        {"Проверка целостности фонов", "Сканирование установленных видеофонов на ошибки и битые файлы", "[A] Сканировать", Theme::COLOR_FOCUS_CYAN},
        {"Язык интерфейса / Language", "Выбор языка отображения меню и подсказок управления", (m_language == Language::Russian ? "Русский [A]" : "English [A]"), Theme::COLOR_TEXT_PRIMARY}
    };

    int rowY = 236;
    for (size_t i = 0; i < rows.size(); ++i) {
        bool isFocused = (static_cast<int>(i) == m_settingsSelectedIndex);

        if (isFocused) {
            drawRect(50, rowY, 1180, 48, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(50, rowY, 1180, 48, 2);
        } else {
            drawRect(50, rowY, 1180, 48, Theme::COLOR_BG_SURFACE);
            drawRectOutline(50, rowY, 1180, 48, Theme::COLOR_BORDER, 1);
        }

        drawText(rows[i].title, 75, rowY + 7, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15, 850);
        drawText(rows[i].desc, 75, rowY + 28, Theme::COLOR_TEXT_MUTED, 11, 850);

        drawText(rows[i].value, 940, rowY + 14, rows[i].valColor, 14, 270);

        rowY += 54;
    }

    // Bottom Help Banner
    drawRect(50, 622, 1180, 32, Theme::COLOR_BG_BASE);
    drawRectOutline(50, 622, 1180, 32, Theme::COLOR_BORDER, 1);
    drawText("Навигация: [D-Pad Вверх/Вниз] Выбор   |   [A] Применить / Очистить   |   [B] Главная", 75, 629, Theme::COLOR_TEXT_MUTED, 13);
}"""

assert settings_render_old in code, "settings_render_old not found"
code = code.replace(settings_render_old, settings_render_new, 1)

with open(app_cpp_path, "w", encoding="utf-8") as f:
    f.write(code)

print("[OK] Part 1 of app.cpp patched successfully")
