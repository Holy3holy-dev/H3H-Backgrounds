import os
import re

app_cpp_path = r"downloader/src/ui/app.cpp"
with open(app_cpp_path, "r", encoding="utf-8") as f:
    code = f.read()

# ----------------------------------------------------
# 1. App::init() - loadFavorites() and refreshStorageStats()
# ----------------------------------------------------
init_target = """    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
    return true;"""

init_replacement = """    loadFavorites();
    refreshStorageStats();

    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
    return true;"""

if "loadFavorites();" not in code:
    assert init_target in code, "init_target not found"
    code = code.replace(init_target, init_replacement, 1)

# ----------------------------------------------------
# 2. App::shutdown() - saveFavorites()
# ----------------------------------------------------
shutdown_target = """void App::shutdown() {
    m_cancelQueue.store(true);"""

shutdown_replacement = """void App::shutdown() {
    saveFavorites();
    m_cancelQueue.store(true);"""

if "saveFavorites();" not in code:
    assert shutdown_target in code, "shutdown_target not found"
    code = code.replace(shutdown_target, shutdown_replacement, 1)

# ----------------------------------------------------
# 3. ZL / ZR Triggers in handleInput()
# ----------------------------------------------------
trigger_pat = r"\} else if \(event\.caxis\.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT\) \{.*?\}\s*\} else if \(event\.caxis\.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT\) \{.*?\}"
trigger_rep = """} else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT) {
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
code = re.sub(trigger_pat, trigger_rep, code, count=1, flags=re.DOTALL)

# ----------------------------------------------------
# 4. Touch support in Catalog (checkbox & banner) and Settings
# ----------------------------------------------------
touch_catalog_pat = r"// Catalog Tab: click directly on an item in the list\s*else if \(m_activeTab == Tab::Catalog && mx >= 60 && mx <= 1220 && my >= 160 && my <= 640\) \{.*?\}\s*// Settings Tab: buttons at y in \[300, 350\]\s*else if \(m_activeTab == Tab::Settings && my >= 300 && my <= 350\) \{.*?\}"
touch_catalog_rep = """// Catalog Tab: click directly on an item in the list or batch banner
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
code = re.sub(touch_catalog_pat, touch_catalog_rep, code, count=1, flags=re.DOTALL)

# ----------------------------------------------------
# 5. Collection Browser: R3 / L toggle favorite
# ----------------------------------------------------
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
if "toggleFavoriteVariant(m_collectionTitleId" not in code:
    assert coll_input_target in code, "coll_input_target not found"
    code = code.replace(coll_input_target, coll_input_replacement, 1)

# ----------------------------------------------------
# 6. Fullscreen Preview: R3 / L toggle favorite
# ----------------------------------------------------
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
if "toggleFavoriteVariant(m_previewTitleId" not in code:
    assert preview_input_target in code, "preview_input_target not found"
    code = code.replace(preview_input_target, preview_input_replacement, 1)

# ----------------------------------------------------
# 7. Tab Switching & ZL / ZR Handling
# ----------------------------------------------------
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
if "BUTTON_ZL" not in code:
    assert tab_switch_old in code, "tab_switch_old not found"
    code = code.replace(tab_switch_old, tab_switch_new, 1)

# ----------------------------------------------------
# 8. MyGames: B returns to Home, R3 toggles batch selection
# ----------------------------------------------------
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
if "toggleBatchSelection(m_installedGames" not in code:
    assert mygames_b_old in code, "mygames_b_old not found"
    code = code.replace(mygames_b_old, mygames_b_new, 1)

# ----------------------------------------------------
# 9. Catalog, Downloads, Settings in onButtonPress
# ----------------------------------------------------
cds_pat = r"\} else if \(m_activeTab == Tab::Catalog\) \{.*?\n    \}\n\}\n\nvoid App::render\(\)"
cds_rep = """} else if (m_activeTab == Tab::Catalog) {
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
                    m_catalogManager.loadFromJsonString("{\\"schemaVersion\\":1,\\"updatedAt\\":\\"\\",\\"games\\":[]}", m_statusNotification);
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
            m_catalogManager.loadFromJsonString("{\\"schemaVersion\\":1,\\"updatedAt\\":\\"\\",\\"games\\":[]}", m_statusNotification);
            refreshInstalledGames();
            m_statusNotification = getStrings(m_language).cacheClearedMsg;
            m_notificationFramesRemaining = 120;
        } else if (button == 3 /* Y - Refresh Catalog */) {
            fetchRemoteCatalog();
        } else if (button == 6 /* START / Plus - Update App NRO */) {
            updateApplicationNro();
        }
    }
}

void App::render()"""
code = re.sub(cds_pat, cds_rep, code, count=1, flags=re.DOTALL)

# ----------------------------------------------------
# 10. Footer Hints
# ----------------------------------------------------
footer_pat = r"void App::renderFooter\(\) \{.*?\n    drawText\(hints, 30, 685, Theme::COLOR_TEXT_MUTED, 14\);"
footer_rep = """void App::renderFooter() {
    const auto& s = getStrings(m_language);

    std::string hints;
    if (m_activeTab == Tab::Home) {
        hints = "[L/R] Вкладки   [A] Мои игры   [B] Выход в hbmenu   [Y] Установить все   [-] Обновить";
    } else if (m_activeTab == Tab::MyGames) {
        hints = "[L/R] Вкладки   [A] Выбрать   [R3] Чекбокс [✓]   [X] Видео   [Y] Удалить   [B] Назад в меню";
    } else if (m_activeTab == Tab::Catalog) {
        if (!m_batchSelectedTitleIds.empty()) {
            hints = "[▲/▼] Выбор   [R3/L3] Чекбокс [✓]   [ZL] Установить (" + std::to_string(m_batchSelectedTitleIds.size()) + ")   [X] Сорт   [Y] Поиск   [B] Назад";
        } else if (!m_catalogSearchQuery.empty()) {
            hints = "[▲/▼] Выбор   [◀/▶] ±5   [A] Фоны   [R3/L3] Чекбокс [✓]   [X] Сорт   [Y] Поиск   [-] Сброс   [B] Назад";
        } else {
            hints = "[▲/▼] Выбор   [◀/▶] ±5   [A] Фоны   [R3/L3] Чекбокс [✓]   [X] Сорт   [Y] Поиск   [-] Обновить   [B] Назад";
        }
    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [B] Назад в меню   [-] Обновить каталог";
    } else if (m_activeTab == Tab::Settings) {
        hints = "[L/R] Вкладки   [▲/▼] Выбор пункта   [A] Применить / Очистить   [B] Назад в меню";
    }

    drawText(hints, 30, 685, Theme::COLOR_TEXT_MUTED, 14);"""
code = re.sub(footer_pat, footer_rep, code, count=1, flags=re.DOTALL)

# ----------------------------------------------------
# 11. renderTabSettings()
# ----------------------------------------------------
settings_pat = r"void App::renderTabSettings\(\) \{.*?\n\}\n\nvoid App::renderDialog\(\)"
settings_rep = """void App::renderTabSettings() {
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
}

void App::renderDialog()"""
code = re.sub(settings_pat, settings_rep, code, count=1, flags=re.DOTALL)

# ----------------------------------------------------
# 12. renderTabCatalog()
# ----------------------------------------------------
cat_render_pat = r"void App::renderTabCatalog\(\) \{.*?\nvoid App::renderTabDownloads\(\)"
cat_render_rep = """void App::renderTabCatalog() {
    const auto& s = getStrings(m_language);
    (void)s;

    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    // Title & Info
    drawText("Онлайн-библиотека видеофонов 4IFIR", 60, 100, Theme::COLOR_TEXT_PRIMARY, 20);

    // 1. Search Bar Card [Y]: x in [480, 780], y in [92, 134]
    bool hasQuery = !m_catalogSearchQuery.empty();
    drawGlassCard(480, 92, 300, 42, hasQuery, false);
    if (!hasQuery) {
        drawText("🔍 [Y] Поиск по названию...", 495, 105, Theme::COLOR_TEXT_MUTED, 13, 270);
    } else {
        drawText("🔍 [Y] \\"" + m_catalogSearchQuery + "\\"", 495, 105, Theme::COLOR_FOCUS_CYAN, 13, 270);
    }

    // 2. Sort Pill [X]: x in [795, 1060], y in [92, 134]
    bool customSort = (m_catalogSortMode != CatalogSortMode::Default);
    drawGlassCard(795, 92, 265, 42, customSort, false);
    std::string sortLabel = "[X] Сорт: ";
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: sortLabel += "По умолчанию"; break;
        case CatalogSortMode::Alphabetical: sortLabel += "А-Я (по имени)"; break;
        case CatalogSortMode::VariantsCount: sortLabel += "По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: sortLabel += "Только со звуком"; break;
        case CatalogSortMode::InstalledOnly: sortLabel += "Установленные"; break;
        case CatalogSortMode::FavoritesOnly: sortLabel += "★ Только избранное"; break;
    }
    drawText(sortLabel, 808, 105, customSort ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 13, 245);

    // 3. Reset / Refresh button [-]: x in [1075, 1220], y in [92, 134]
    drawGlassCard(1075, 92, 145, 42, true, false);
    if (hasQuery) {
        drawText("[-] Сброс", 1105, 105, Theme::COLOR_FOCUS_PINK, 13);
    } else {
        drawText("[-] Обновить", 1095, 105, Theme::COLOR_FOCUS_CYAN, 13);
    }

    int totalFiltered = static_cast<int>(m_filteredCatalogGames.size());
    int totalAll = static_cast<int>(m_catalogManager.getAllGames().size());

    if (totalFiltered == 0) {
        if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
            drawText("В избранном пока нет видеофонов.", 60, 200, Theme::COLOR_FOCUS_PINK, 18);
            drawText("Откройте любую игру и нажмите [R3] или [L], чтобы добавить вариант в избранное ★", 60, 235, Theme::COLOR_TEXT_MUTED, 15);
        } else if (hasQuery) {
            drawText("По запросу \\"" + m_catalogSearchQuery + "\\" ничего не найдено.", 60, 200, Theme::COLOR_FOCUS_PINK, 18);
            drawText("Нажмите [Y], чтобы изменить запрос, или [-] для сброса фильтра.", 60, 235, Theme::COLOR_TEXT_MUTED, 15);
        } else {
            drawText("Каталог пуст или ещё не загружен.", 60, 180, Theme::COLOR_TEXT_MUTED, 16);
            drawText("Нажмите кнопку [-], чтобы загрузить актуальный список видеофонов с GitHub.", 60, 215, Theme::COLOR_FOCUS_CYAN, 15);
        }
        return;
    }

    const int visibleCount = 5;

    if (m_catalogSelectedIndex < m_catalogScrollOffset) {
        m_catalogScrollOffset = m_catalogSelectedIndex;
    }
    if (m_catalogSelectedIndex >= m_catalogScrollOffset + visibleCount) {
        m_catalogScrollOffset = m_catalogSelectedIndex - visibleCount + 1;
    }

    std::string pageInfo = "Игр: " + std::to_string(totalFiltered) + " из " + std::to_string(totalAll) +
                           "   (Выбрано: " + std::to_string(m_catalogSelectedIndex + 1) + " / " + std::to_string(totalFiltered) + ")" +
                           (hasQuery ? ("   Фильтр: \\"" + m_catalogSearchQuery + "\\"") : "");
    drawText(pageInfo, 60, 135, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalFiltered, m_catalogScrollOffset + visibleCount);
    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_catalogSelectedIndex);
        const auto& g = m_filteredCatalogGames[i];
        bool isBatchSel = (m_batchSelectedTitleIds.count(g.titleId) > 0);

        // 4IFIR Frosted Card for each catalog entry
        drawGlassCard(60, y, 1160, 80, isSelected, false);

        // Selection Checkbox [✓] or [ ]
        if (isBatchSel) {
            drawRect(78, y + 26, 28, 28, {0x00, 0xF0, 0xFF, 0x44});
            drawRectOutline(78, y + 26, 28, 28, Theme::COLOR_FOCUS_CYAN, 2);
            drawText("✓", 85, y + 30, Theme::COLOR_FOCUS_CYAN, 18);
        } else {
            drawRect(78, y + 26, 28, 28, {0x16, 0x20, 0x32, 0x88});
            drawRectOutline(78, y + 26, 28, 28, Theme::COLOR_BORDER, 1);
        }

        // Title (shifted to x = 118)
        drawText(g.title, 118, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17, 560);

        // Check if game is installed on console
        bool isInstalledOnSwitch = false;
        bool hasActiveCover = false;
        for (const auto& ig : m_installedGames) {
            if (ig.titleId == g.titleId) {
                isInstalledOnSwitch = true;
                hasActiveCover = ig.hasInstalledCover;
                break;
            }
        }

        // Check audio badge for game
        bool hasAudioVariant = false;
        for (const auto& v : g.variants) {
            if (v.hasAudio) { hasAudioVariant = true; break; }
        }

        // Check favorites badge
        bool hasFav = hasGameFavorites(g.titleId);

        std::string meta = "Title ID: " + g.titleId + "   |   Вариантов фона: " + std::to_string(g.variants.size());
        drawText(meta, 118, y + 44, Theme::COLOR_TEXT_MUTED, 13);

        if (hasFav) {
            drawText("★", 460, y + 42, {0xFF, 0xD7, 0x00, 0xFF}, 16);
        }

        // Audio badge
        if (hasAudioVariant) {
            drawRect(640, y + 40, 75, 22, {0x18, 0x38, 0x24, 0xCC});
            drawRectOutline(640, y + 40, 75, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", 658, y + 44, Theme::COLOR_SUCCESS, 10);
        }

        // Status badges on card
        if (isInstalledOnSwitch) {
            if (hasActiveCover) {
                drawRect(730, y + 40, 185, 22, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(730, y + 40, 185, 22, Theme::COLOR_SUCCESS, 1);
                drawText("НА SWITCH (ФОН ЕСТЬ)", 740, y + 44, Theme::COLOR_SUCCESS, 10);
            } else {
                drawRect(730, y + 40, 165, 22, {0x02, 0x84, 0xC7, 0x33});
                drawRectOutline(730, y + 40, 165, 22, Theme::COLOR_FOCUS_CYAN, 1);
                drawText("УСТАНОВЛЕНА НА SWITCH", 740, y + 44, Theme::COLOR_FOCUS_CYAN, 10);
            }
        } else {
            drawRect(730, y + 40, 140, 22, {0x28, 0x33, 0x47, 0x44});
            drawRectOutline(730, y + 40, 140, 22, Theme::COLOR_BORDER, 1);
            drawText("В ОНЛАЙН-КАТАЛОГЕ", 740, y + 44, Theme::COLOR_TEXT_MUTED, 10);
        }

        // Action button on right
        if (isSelected) {
            int vCount = static_cast<int>(g.variants.size());
            if (vCount > 1) {
                drawRect(915, y + 22, 285, 36, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(915, y + 22, 285, 36, 2);
                drawText("[A] Все фоны (" + std::to_string(vCount) + " шт.) ▶", 930, y + 31, Theme::COLOR_FOCUS_CYAN, 14);
            } else {
                drawRect(960, y + 22, 240, 36, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(960, y + 22, 240, 36, 2);
                drawText("[A] Смотреть фон ▶", 975, y + 31, Theme::COLOR_FOCUS_CYAN, 14);
            }
        }

        y += 80 + 14;
    }

    // Feature 7: Floating Batch Installation Action Banner
    if (!m_batchSelectedTitleIds.empty()) {
        int fbw = 880;
        int fbh = 46;
        int fbx = (Theme::SCREEN_WIDTH - fbw) / 2;
        int fby = 612;

        drawGlassCard(fbx, fby, fbw, fbh, true, true);
        drawNeonGradientOutline(fbx, fby, fbw, fbh, 2);

        std::string selText = "📥 Выбрано для установки: " + std::to_string(m_batchSelectedTitleIds.size()) + " игр";
        drawText(selText, fbx + 25, fby + 13, Theme::COLOR_FOCUS_CYAN, 16);

        // Action button [ZL]
        drawRect(fbx + 470, fby + 6, 240, 34, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(fbx + 470, fby + 6, 240, 34, 1);
        drawText("[ZL] Установить все ▶", fbx + 485, fby + 13, Theme::COLOR_FOCUS_CYAN, 14);

        // Clear button [-]
        drawRect(fbx + 725, fby + 6, 130, 34, {0x28, 0x33, 0x47, 0x88});
        drawRectOutline(fbx + 725, fby + 6, 130, 34, Theme::COLOR_BORDER, 1);
        drawText("[-] Сброс", fbx + 755, fby + 13, Theme::COLOR_TEXT_MUTED, 13);
    }
}

void App::renderTabDownloads()"""
code = re.sub(cat_render_pat, cat_render_rep, code, count=1, flags=re.DOTALL)

# ----------------------------------------------------
# 13. renderFullscreenPreview() - Favorites badge & hint
# ----------------------------------------------------
fs_pat = r"drawText\(\"\[Y\] Привязать к другой игре\", hudX \+ 680, hudY \+ 68, Theme::COLOR_FOCUS_CYAN, 12\);"
fs_rep = """bool isFav = isVariantFavorite(m_previewTitleId, v.id);
        if (isFav) {
            drawRect(hudX + 690, hudY + 14, 195, 38, {0xFF, 0xD7, 0x00, 0x33});
            drawRectOutline(hudX + 690, hudY + 14, 195, 38, {0xFF, 0xD7, 0x00, 0xFF}, 1);
            drawText("★ В ИЗБРАННОМ", hudX + 710, hudY + 24, {0xFF, 0xD7, 0x00, 0xFF}, 14);
        }

        drawText("[R3/L] ★ В избранное   |   [Y] Привязать к игре", hudX + 540, hudY + 68, Theme::COLOR_FOCUS_CYAN, 12);"""
if "isVariantFavorite(m_previewTitleId" not in code:
    code = re.sub(fs_pat, fs_rep, code, count=1)

# ----------------------------------------------------
# 14. renderCollectionBrowser() - Star badge, Fav Button, and Hints
# ----------------------------------------------------
coll_card_pat = r"std::string titleStr = std::to_string\(i \+ 1\) \+ \"\. \" \+ v\.name;\s*drawText\(titleStr, lx \+ 16, cardY \+ 14, isSelected \? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, lw - 70\);"
coll_card_rep = """bool isFav = isVariantFavorite(m_collectionTitleId, v.id);
        std::string titleStr = (isFav ? "★ " : "") + std::to_string(i + 1) + ". " + v.name;
        drawText(titleStr, lx + 16, cardY + 14, isFav ? Color{0xFF, 0xD7, 0x00, 0xFF} : (isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY), 16, lw - 70);"""
code = re.sub(coll_card_pat, coll_card_rep, code, count=1)

coll_btn_pat = r"drawText\(\"Совет: Нажмите \[A\], чтобы выбрать игру на Switch для этого фона\", px, b1y \+ 54, Theme::COLOR_TEXT_MUTED, 12, pw\);"
coll_btn_rep = """// [R3 / L] Favorite Button
        bool isSelFav = isVariantFavorite(m_collectionTitleId, selVar.id);
        int b3w = 480;
        int b3h = 36;
        int b3x = px;
        int b3y = b1y + 48;
        if (isSelFav) {
            drawRect(b3x, b3y, b3w, b3h, {0xFF, 0xD7, 0x00, 0x33});
            drawRectOutline(b3x, b3y, b3w, b3h, {0xFF, 0xD7, 0x00, 0xFF}, 1);
            drawText("★ [R3 / L] В ИЗБРАННОМ (Нажмите, чтобы убрать)", b3x + 65, b3y + 10, {0xFF, 0xD7, 0x00, 0xFF}, 13);
        } else {
            drawRect(b3x, b3y, b3w, b3h, {0x16, 0x20, 0x32, 0xAA});
            drawRectOutline(b3x, b3y, b3w, b3h, Theme::COLOR_BORDER, 1);
            drawText("☆ [R3 / L] Добавить вариант в избранное", b3x + 85, b3y + 10, Theme::COLOR_TEXT_MUTED, 13);
        }

        drawText("Совет: Нажмите [A], чтобы выбрать игру на Switch для этого фона", px, b3y + 42, Theme::COLOR_TEXT_MUTED, 12, pw);"""
code = re.sub(coll_btn_pat, coll_btn_rep, code, count=1)

coll_hint_pat = r"drawText\(\"\[▲/▼\] Список   \|   \[◀/▶\] Страница \(±5\)   \|   \[A\] Назначить на игру Switch   \|   \[X\] Видео   \|   \[B\] Назад\",\s*bx \+ 60, footY \+ 8, Theme::COLOR_TEXT_MUTED, 12\);"
coll_hint_rep = """drawText("[▲/▼] Список   |   [◀/▶] ±5   |   [A] Назначить   |   [X] Видео   |   [R3/L] ★ В избранное   |   [B] Назад",
                 bx + 40, footY + 8, Theme::COLOR_TEXT_MUTED, 12);"""
code = re.sub(coll_hint_pat, coll_hint_rep, code, count=1)

# ----------------------------------------------------
# 15. rebuildCatalogFilter() & cycleCatalogSortMode()
# ----------------------------------------------------
rebuild_pat = r"void App::rebuildCatalogFilter\(\) \{.*?\nvoid App::openCatalogKeyboard\(\)"
rebuild_rep = """void App::rebuildCatalogFilter() {
    const auto& allGames = m_catalogManager.getAllGames();
    m_filteredCatalogGames.clear();

    std::string qLower = m_catalogSearchQuery;
    std::transform(qLower.begin(), qLower.end(), qLower.begin(), [](unsigned char c) {
        return std::tolower(c);
    });

    for (const auto& g : allGames) {
        // 1. Search Query filter
        if (!qLower.empty()) {
            std::string titleLower = g.title;
            std::transform(titleLower.begin(), titleLower.end(), titleLower.begin(), [](unsigned char c) {
                return std::tolower(c);
            });
            std::string tidLower = g.titleId;
            std::transform(tidLower.begin(), tidLower.end(), tidLower.begin(), [](unsigned char c) {
                return std::tolower(c);
            });

            bool match = (titleLower.find(qLower) != std::string::npos) ||
                         (tidLower.find(qLower) != std::string::npos);
            if (!match) {
                for (const auto& v : g.variants) {
                    std::string vname = v.name;
                    std::transform(vname.begin(), vname.end(), vname.begin(), [](unsigned char c) {
                        return std::tolower(c);
                    });
                    if (vname.find(qLower) != std::string::npos) {
                        match = true;
                        break;
                    }
                }
            }
            if (!match) continue;
        }

        // 2. Installed Only filter
        if (m_catalogSortMode == CatalogSortMode::InstalledOnly) {
            bool isInst = false;
            for (const auto& ig : m_installedGames) {
                if (ig.titleId == g.titleId) {
                    isInst = true;
                    break;
                }
            }
            if (!isInst) continue;
        }

        // 3. Audio Only filter
        if (m_catalogSortMode == CatalogSortMode::AudioOnly) {
            bool hasAud = false;
            for (const auto& v : g.variants) {
                if (v.hasAudio) {
                    hasAud = true;
                    break;
                }
            }
            if (!hasAud) continue;
        }

        // 4. Favorites Only filter
        if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
            if (!hasGameFavorites(g.titleId)) {
                continue;
            }
        }

        m_filteredCatalogGames.push_back(g);
    }

    // 5. Sorting
    if (m_catalogSortMode == CatalogSortMode::Alphabetical) {
        std::sort(m_filteredCatalogGames.begin(), m_filteredCatalogGames.end(), [](const GameCatalogEntry& a, const GameCatalogEntry& b) {
            return a.title < b.title;
        });
    } else if (m_catalogSortMode == CatalogSortMode::VariantsCount) {
        std::sort(m_filteredCatalogGames.begin(), m_filteredCatalogGames.end(), [](const GameCatalogEntry& a, const GameCatalogEntry& b) {
            return a.variants.size() > b.variants.size();
        });
    }

    // Safe bounds clamp
    if (m_catalogSelectedIndex >= static_cast<int>(m_filteredCatalogGames.size())) {
        m_catalogSelectedIndex = std::max(0, static_cast<int>(m_filteredCatalogGames.size()) - 1);
    }
    m_catalogScrollOffset = 0;
}

void App::cycleCatalogSortMode() {
    int nextMode = (static_cast<int>(m_catalogSortMode) + 1) % 6;
    m_catalogSortMode = static_cast<CatalogSortMode>(nextMode);
    rebuildCatalogFilter();

    std::string modeDesc;
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: modeDesc = "Сортировка: По умолчанию"; break;
        case CatalogSortMode::Alphabetical: modeDesc = "Сортировка: По алфавиту (А-Я)"; break;
        case CatalogSortMode::VariantsCount: modeDesc = "Сортировка: По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: modeDesc = "Фильтр: Только со звуком [ЗВУК]"; break;
        case CatalogSortMode::InstalledOnly: modeDesc = "Фильтр: Только установленные игры"; break;
        case CatalogSortMode::FavoritesOnly: modeDesc = "Фильтр: ★ Только избранное"; break;
    }
    m_statusNotification = modeDesc;
    m_notificationFramesRemaining = 120;
}

void App::openCatalogKeyboard()"""
code = re.sub(rebuild_pat, rebuild_rep, code, count=1, flags=re.DOTALL)

# ----------------------------------------------------
# 16. Append new methods to the end of app.cpp
# ----------------------------------------------------
methods_to_append = """

// ----------------- Feature 1: Favorites System -----------------

void App::loadFavorites() {
    m_favoriteKeys.clear();
    std::string favFile = m_platform->getAppDirectory() + "/favorites.json";
    std::error_code ec;
    if (!std::filesystem::exists(favFile, ec)) return;

    std::ifstream ifs(favFile);
    if (!ifs.is_open()) return;

    try {
        nlohmann::json j;
        ifs >> j;
        if (j.contains("keys") && j["keys"].is_array()) {
            for (const auto& k : j["keys"]) {
                if (k.is_string()) {
                    m_favoriteKeys.insert(k.get<std::string>());
                }
            }
        }
    } catch (...) {}
}

void App::saveFavorites() {
    nlohmann::json j;
    j["version"] = 1;
    j["keys"] = nlohmann::json::array();
    for (const auto& k : m_favoriteKeys) {
        j["keys"].push_back(k);
    }

    std::string appDir = m_platform->getAppDirectory();
    std::string targetFile = appDir + "/favorites.json";
    std::string tmpFile = targetFile + ".tmp";

    std::error_code ec;
    std::filesystem::create_directories(appDir, ec);

    std::ofstream ofs(tmpFile);
    if (ofs.is_open()) {
        ofs << j.dump(2);
        ofs.flush();
        ofs.close();
        std::filesystem::rename(tmpFile, targetFile, ec);
    }
}

bool App::isVariantFavorite(const std::string& titleId, const std::string& variantId) const {
    if (variantId.empty()) return false;
    if (!titleId.empty() && m_favoriteKeys.count(titleId + ":" + variantId) > 0) return true;
    if (m_favoriteKeys.count(variantId) > 0) return true;
    return false;
}

void App::toggleFavoriteVariant(const std::string& titleId, const Variant& variant) {
    if (variant.id.empty()) return;
    std::string key = (!titleId.empty() ? (titleId + ":" + variant.id) : variant.id);
    bool currentlyFav = isVariantFavorite(titleId, variant.id);

    if (currentlyFav) {
        m_favoriteKeys.erase(key);
        m_favoriteKeys.erase(variant.id);
        if (!titleId.empty()) m_favoriteKeys.erase(titleId + ":" + variant.id);
        m_statusNotification = "Удалено из избранного: " + variant.name;
    } else {
        m_favoriteKeys.insert(key);
        m_statusNotification = "★ Добавлено в избранное: " + variant.name;
    }
    m_notificationFramesRemaining = 90;
    saveFavorites();

    if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
        rebuildCatalogFilter();
    }
}

bool App::hasGameFavorites(const std::string& titleId) const {
    const auto* entry = m_catalogManager.findByTitleId(titleId);
    if (!entry && m_catalogManager.getGame(titleId)) {
        entry = m_catalogManager.getGame(titleId);
    }
    if (entry) {
        for (const auto& v : entry->variants) {
            if (isVariantFavorite(titleId, v.id)) return true;
        }
    }
    for (const auto& ig : m_installedGames) {
        if (ig.titleId == titleId) {
            for (const auto& v : ig.catalogEntry.variants) {
                if (isVariantFavorite(titleId, v.id)) return true;
            }
            break;
        }
    }
    return false;
}

// ----------------- Feature 6: Storage & Cache Manager -----------------

void App::refreshStorageStats() {
    m_sysInfo = m_platform->getSystemInfo();
    m_storageStats.totalSdBytes = m_sysInfo.totalStorageBytes;
    m_storageStats.freeSdBytes = m_sysInfo.freeStorageBytes;

    // Installed covers (*.mp4 in coversDir)
    std::string covDir = m_platform->getCoversDirectory();
    m_storageStats.coversCount = 0;
    m_storageStats.coversBytes = 0;
    std::error_code ec;
    if (std::filesystem::exists(covDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(covDir, ec)) {
            if (entry.is_regular_file(ec) && entry.path().extension() == ".mp4") {
                m_storageStats.coversCount++;
                m_storageStats.coversBytes += entry.file_size(ec);
            }
        }
    }

    // Cache folder (thumbs/*.jpg and thumbs/*.mp4)
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    m_storageStats.thumbsCount = 0;
    m_storageStats.thumbsBytes = 0;
    m_storageStats.vidCacheCount = 0;
    m_storageStats.vidCacheBytes = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".jpg" || ext == ".png") {
                    m_storageStats.thumbsCount++;
                    m_storageStats.thumbsBytes += entry.file_size(ec);
                } else if (ext == ".mp4" || ext == ".tmp") {
                    m_storageStats.vidCacheCount++;
                    m_storageStats.vidCacheBytes += entry.file_size(ec);
                }
            }
        }
    }
}

void App::clearThumbnailCache() {
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    int deleted = 0;
    uint64_t freed = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".jpg" || ext == ".png") {
                    freed += entry.file_size(ec);
                    std::filesystem::remove(entry.path(), ec);
                    deleted++;
                }
            }
        }
    }
    refreshStorageStats();
    double freedMb = static_cast<double>(freed) / (1024.0 * 1024.0);
    char buf[128];
    snprintf(buf, sizeof(buf), "Очищен кэш превью: %d файлов (%.1f MB)", deleted, freedMb);
    m_statusNotification = buf;
    m_notificationFramesRemaining = 120;
}

void App::clearVideoPreviewCache() {
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    int deleted = 0;
    uint64_t freed = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".mp4" || ext == ".tmp") {
                    freed += entry.file_size(ec);
                    std::filesystem::remove(entry.path(), ec);
                    deleted++;
                }
            }
        }
    }
    refreshStorageStats();
    double freedMb = static_cast<double>(freed) / (1024.0 * 1024.0);
    char buf[128];
    snprintf(buf, sizeof(buf), "Очищен кэш видео: %d файлов (%.1f MB)", deleted, freedMb);
    m_statusNotification = buf;
    m_notificationFramesRemaining = 120;
}

// ----------------- Feature 7: Batch Multi-Select Checklist -----------------

void App::toggleBatchSelection(const std::string& titleId) {
    if (titleId.empty()) return;
    if (m_batchSelectedTitleIds.count(titleId) > 0) {
        m_batchSelectedTitleIds.erase(titleId);
        m_statusNotification = "Снято выделение с игры";
    } else {
        m_batchSelectedTitleIds.insert(titleId);
        m_statusNotification = "✓ Игра выбрана (Всего: " + std::to_string(m_batchSelectedTitleIds.size()) + " шт.)";
    }
    m_notificationFramesRemaining = 90;
}

void App::clearBatchSelection() {
    m_batchSelectedTitleIds.clear();
    m_statusNotification = "Пакетный выбор очищен";
    m_notificationFramesRemaining = 90;
}

void App::installBatchSelected() {
    if (m_batchSelectedTitleIds.empty()) return;
    int queuedCount = 0;

    for (const auto& tid : m_batchSelectedTitleIds) {
        const auto* entry = m_catalogManager.findByTitleId(tid);
        if (!entry && m_catalogManager.getGame(tid)) {
            entry = m_catalogManager.getGame(tid);
        }
        if (!entry || entry->variants.empty()) continue;

        const Variant* chosenVariant = &entry->variants[0];
        for (const auto& v : entry->variants) {
            if (isVariantFavorite(tid, v.id)) {
                chosenVariant = &v;
                break;
            }
        }

        InstalledTitle targetTitle;
        bool found = false;
        for (const auto& ig : m_installedGames) {
            if (ig.titleId == tid) {
                targetTitle = ig;
                found = true;
                break;
            }
        }
        if (!found) {
            targetTitle.titleId = tid;
            targetTitle.name = entry->title;
            targetTitle.hasCatalogMatch = true;
            targetTitle.catalogEntry = *entry;
        }

        bool alreadyInQueue = false;
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            for (const auto& t : m_downloadQueue) {
                if (t.titleId == tid && t.state != TaskState::Failed && t.state != TaskState::Completed) {
                    alreadyInQueue = true;
                    break;
                }
            }
        }

        if (!alreadyInQueue) {
            queueDownload(targetTitle, *chosenVariant);
            queuedCount++;
        }
    }

    m_batchSelectedTitleIds.clear();
    m_activeTab = Tab::Downloads;
    m_statusNotification = "Добавлено в очередь загрузки: " + std::to_string(queuedCount) + " игр";
    m_notificationFramesRemaining = 150;
}
"""

end_pat = r"\}\s*// namespace ui\s*\}\s*// namespace h3h"
end_rep = methods_to_append + "\n} // namespace ui\n} // namespace h3h"
code = re.sub(end_pat, end_rep, code, count=1)

with open(app_cpp_path, "w", encoding="utf-8") as f:
    f.write(code)

print("[OK] app.cpp patched successfully for v1.2.9")
