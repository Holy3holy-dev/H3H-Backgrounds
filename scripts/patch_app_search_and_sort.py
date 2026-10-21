import sys
from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
content = app_cpp.read_text(encoding="utf-8")

# 1. In init(), call rebuildCatalogFilter() after refreshInstalledGames()
init_call = """    refreshInstalledGames();
    rebuildCatalogFilter();"""

if "rebuildCatalogFilter();" not in content:
    assert "refreshInstalledGames();" in content, "refreshInstalledGames() not found in init"
    # only replace the first occurrence (in init)
    content = content.replace("    refreshInstalledGames();", "    refreshInstalledGames();\n    rebuildCatalogFilter();", 1)
    print("[+] Added rebuildCatalogFilter() to init()")

# 2. In update(), when catalog is loaded from json string, call rebuildCatalogFilter()
old_cat_match = """                m_catalogManager.saveToCacheFile(m_platform->getAppDirectory() + "/cache.json");
                m_catalogManager.matchInstalledTitles(m_installedGames);"""

new_cat_match = """                m_catalogManager.saveToCacheFile(m_platform->getAppDirectory() + "/cache.json");
                m_catalogManager.matchInstalledTitles(m_installedGames);
                rebuildCatalogFilter();"""

if old_cat_match in content:
    content = content.replace(old_cat_match, new_cat_match)
    print("[+] Added rebuildCatalogFilter() to catalog fetch in update()")

# 3. Update handleInput() for Tab::Catalog touch clicks
old_touch_catalog = """            // Catalog Tab: top-right "[-] Обновить" button: x in [980, 1220], y in [95, 145]
            else if (m_activeTab == Tab::Catalog && mx >= 980 && mx <= 1220 && my >= 95 && my <= 145) {
                onButtonPress(4 /* Minus / Refresh */);
            }
            // Catalog Tab: top-right "Установить недостающие" button: x in [680, 960], y in [95, 145]
            else if (m_activeTab == Tab::Catalog && mx >= 680 && mx <= 960 && my >= 95 && my <= 145) {
                installAllMissing();
            }
            // Catalog Tab: click directly on an item in the list
            else if (m_activeTab == Tab::Catalog && mx >= 60 && mx <= 1220 && my >= 160 && my <= 640) {
                int clickedIndex = m_catalogScrollOffset + (my - 160) / 94;
                const auto& allGames = m_catalogManager.getAllGames();
                int totalGames = static_cast<int>(allGames.size());
                if (clickedIndex >= 0 && clickedIndex < totalGames) {
                    if (m_catalogSelectedIndex == clickedIndex || mx >= 950) {
                        m_catalogSelectedIndex = clickedIndex;
                        openFullscreenPreviewForCatalogGame(allGames[clickedIndex], 0);
                    } else {
                        m_catalogSelectedIndex = clickedIndex;
                    }
                }
            }"""

new_touch_catalog = """            // Catalog Tab: Search Bar click: x in [480, 780], y in [90, 140]
            else if (m_activeTab == Tab::Catalog && mx >= 480 && mx <= 780 && my >= 90 && my <= 140) {
                onButtonPress(3 /* Y - Open Keyboard / Search */);
            }
            // Catalog Tab: Sort Pill click: x in [795, 1060], y in [90, 140]
            else if (m_activeTab == Tab::Catalog && mx >= 795 && mx <= 1060 && my >= 90 && my <= 140) {
                onButtonPress(2 /* X - Cycle Sort Mode */);
            }
            // Catalog Tab: Reset/Refresh button: x in [1075, 1220], y in [90, 140]
            else if (m_activeTab == Tab::Catalog && mx >= 1075 && mx <= 1220 && my >= 90 && my <= 140) {
                onButtonPress(4 /* Minus / Reset or Refresh */);
            }
            // Catalog Tab: click directly on an item in the list
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
            }"""

assert old_touch_catalog in content, "old_touch_catalog not found"
content = content.replace(old_touch_catalog, new_touch_catalog)
print("[+] Updated touch controls in handleInput() for Search & Sort")

# 4. Update onButtonPress() for Tab::Catalog
old_btn_catalog = """    } else if (m_activeTab == Tab::Catalog) {
        const auto& allGames = m_catalogManager.getAllGames();
        int totalGames = static_cast<int>(allGames.size());
        if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) m_catalogSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) m_catalogSelectedIndex++;
        } else if (button == 0 /* A - Enter Collection Browser */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = allGames[m_catalogSelectedIndex];
                openCollectionBrowser(entry);
            }
        } else if (button == 2 /* X - Quick Video Preview */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = allGames[m_catalogSelectedIndex];
                openFullscreenPreviewForCatalogGame(entry, 0);
            }
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        } else if (button == 4 /* MINUS */) {
            fetchRemoteCatalog();
        }"""

new_btn_catalog = """    } else if (m_activeTab == Tab::Catalog) {
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
        }"""

assert old_btn_catalog in content, "old_btn_catalog not found"
content = content.replace(old_btn_catalog, new_btn_catalog)
print("[+] Updated onButtonPress() for Tab::Catalog")

# 5. Update footer hints for Tab::Catalog
old_footer_hints = """    } else if (m_activeTab == Tab::Catalog) {
        hints = "[L/R] Вкладки   [D-Pad Вверх/Вниз] Выбор игры   [X / A] Смотреть видео   [-] Обновить   [Y] Установить все";"""

new_footer_hints = """    } else if (m_activeTab == Tab::Catalog) {
        if (!m_catalogSearchQuery.empty()) {
            hints = "[▲/▼] Выбор   [◀/▶] ±5   [A] Открыть   [Y] Поиск   [X] Сортировка   [-] Сбросить поиск   [B] Назад";
        } else {
            hints = "[▲/▼] Выбор   [◀/▶] ±5   [A] Открыть   [Y] Поиск   [X] Сортировка   [-] Обновить   [B] Назад";
        }"""

assert old_footer_hints in content, "old_footer_hints not found"
content = content.replace(old_footer_hints, new_footer_hints)
print("[+] Updated footer hints for Tab::Catalog")

# 6. Replace renderTabCatalog() with Search Bar, Sort pill and filtered items
old_render_catalog_start = "void App::renderTabCatalog() {"
old_render_catalog_end = "void App::renderTabDownloads() {"

start_cat = content.find(old_render_catalog_start)
end_cat = content.find(old_render_catalog_end)
assert start_cat != -1 and end_cat != -1, "renderTabCatalog bounds not found"

new_render_catalog = """void App::renderTabCatalog() {
    const auto& s = getStrings(m_language);

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
        if (hasQuery) {
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

        // 4IFIR Frosted Card for each catalog entry
        drawGlassCard(60, y, 1160, 80, isSelected, false);

        // Title
        drawText(g.title, 85, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17, 680);

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

        std::string meta = "Title ID: " + g.titleId + "   |   Вариантов фона: " + std::to_string(g.variants.size());
        drawText(meta, 85, y + 44, Theme::COLOR_TEXT_MUTED, 13);

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
}

"""

content = content[:start_cat] + new_render_catalog + content[end_cat:]
print("[+] Replaced renderTabCatalog() with Search & Sort visual interface")

# 7. Append implementation of rebuildCatalogFilter, openCatalogKeyboard, cycleCatalogSortMode
new_methods = """
// ----------------- Catalog Filtering, Sorting & Horizon OS Keyboard -----------------

void App::rebuildCatalogFilter() {
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

        m_filteredCatalogGames.push_back(g);
    }

    // 4. Sorting
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
    int nextMode = (static_cast<int>(m_catalogSortMode) + 1) % 5;
    m_catalogSortMode = static_cast<CatalogSortMode>(nextMode);
    rebuildCatalogFilter();

    std::string modeDesc;
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: modeDesc = "Сортировка: По умолчанию"; break;
        case CatalogSortMode::Alphabetical: modeDesc = "Сортировка: По алфавиту (А-Я)"; break;
        case CatalogSortMode::VariantsCount: modeDesc = "Сортировка: По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: modeDesc = "Фильтр: Только со звуком [ЗВУК]"; break;
        case CatalogSortMode::InstalledOnly: modeDesc = "Фильтр: Только установленные игры"; break;
    }
    m_statusNotification = modeDesc;
    m_notificationFramesRemaining = 120;
}

void App::openCatalogKeyboard() {
#ifdef __SWITCH__
    SwkbdConfig kbd;
    char textBuf[256] = {0};
    if (!m_catalogSearchQuery.empty()) {
        strncpy(textBuf, m_catalogSearchQuery.c_str(), sizeof(textBuf) - 1);
    }

    Result rc = swkbdCreate(&kbd, 0);
    if (R_SUCCEEDED(rc)) {
        swkbdConfigMakePresetDefault(&kbd);
        swkbdConfigSetHeaderText(&kbd, "Поиск по каталогу H3H Backgrounds");
        swkbdConfigSetGuideText(&kbd, "Введите название игры, Title ID или персонажа (напр. Mario, Zelda, NFS)");
        swkbdConfigSetOkButtonText(&kbd, "Найти");
        swkbdConfigSetInitialText(&kbd, textBuf);
        swkbdConfigSetStringLenMax(&kbd, 64);

        rc = swkbdShow(&kbd, textBuf, sizeof(textBuf));
        if (R_SUCCEEDED(rc)) {
            m_catalogSearchQuery = std::string(textBuf);
            // Trim whitespace
            while (!m_catalogSearchQuery.empty() && std::isspace(static_cast<unsigned char>(m_catalogSearchQuery.back()))) {
                m_catalogSearchQuery.pop_back();
            }
            while (!m_catalogSearchQuery.empty() && std::isspace(static_cast<unsigned char>(m_catalogSearchQuery.front()))) {
                m_catalogSearchQuery.erase(m_catalogSearchQuery.begin());
            }
            rebuildCatalogFilter();
            m_statusNotification = m_catalogSearchQuery.empty()
                ? "Поиск сброшен (показаны все игры)"
                : ("Результаты поиска для: \\"" + m_catalogSearchQuery + "\\" (" + std::to_string(m_filteredCatalogGames.size()) + " игр)");
            m_notificationFramesRemaining = 150;
        }
        swkbdClose(&kbd);
    }
#else
    // Desktop simulator
    if (m_catalogSearchQuery.empty()) {
        m_catalogSearchQuery = "Mario";
    } else {
        m_catalogSearchQuery.clear();
    }
    rebuildCatalogFilter();
    m_statusNotification = "Desktop test: " + m_catalogSearchQuery;
    m_notificationFramesRemaining = 120;
#endif
}
"""

# Insert new methods before closing namespaces
last_ns_idx = content.rfind("} // namespace ui")
assert last_ns_idx != -1, "closing namespace ui not found"
content = content[:last_ns_idx] + new_methods + "\n" + content[last_ns_idx:]
print("[+] Appended rebuildCatalogFilter, cycleCatalogSortMode, openCatalogKeyboard")

app_cpp.write_text(content, encoding="utf-8")
print("[SUCCESS] app.cpp fully patched with Search & Sort functionality!")
