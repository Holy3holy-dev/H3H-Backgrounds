import sys

with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Update sort label in renderTabCatalog
target_sort = """        case CatalogSortMode::VariantsCount: sortLabel += "По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: sortLabel += "Только со звуком"; break;
        case CatalogSortMode::InstalledOnly: sortLabel += "Установленные"; break;"""
repl_sort = """        case CatalogSortMode::VariantsCount: sortLabel += "По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: sortLabel += "Только со звуком"; break;
        case CatalogSortMode::IconsOnly: sortLabel += "Только с иконками"; break;
        case CatalogSortMode::InstalledOnly: sortLabel += "Установленные"; break;"""
assert target_sort in c, 'target_sort not found'
c = c.replace(target_sort, repl_sort, 1)

# 2. Update Catalog badges in renderTabCatalog
target_cat_badges = """        // Badges: Audio & Video Icon
        int cBadgeX = 570;
        if (hasAudioVariant) {
            drawRect(cBadgeX, y + 40, 65, 22, {0x18, 0x38, 0x24, 0xCC});
            drawRectOutline(cBadgeX, y + 40, 65, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", cBadgeX + 16, y + 44, Theme::COLOR_SUCCESS, 10);
            cBadgeX += 73;
        }
        if (hasIconVariant) {
            drawRect(cBadgeX, y + 40, 85, 22, {0x0E, 0x74, 0x90, 0x44});
            drawRectOutline(cBadgeX, y + 40, 85, 22, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("🔲 ИКОНКА", cBadgeX + 8, y + 44, Theme::COLOR_FOCUS_CYAN, 10);
            cBadgeX += 93;
        }"""

repl_cat_badges = """        // Badges: Audio & Video Icon
        int cBadgeX = 525;
        if (hasAudioVariant) {
            drawRect(cBadgeX, y + 40, 65, 22, {0x18, 0x38, 0x24, 0xCC});
            drawRectOutline(cBadgeX, y + 40, 65, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", cBadgeX + 16, y + 44, Theme::COLOR_SUCCESS, 10);
            cBadgeX += 73;
        }
        if (hasIconVariant) {
            drawRect(cBadgeX, y + 40, 80, 22, Theme::COLOR_ICON_BADGE_FILL);
            drawRectOutline(cBadgeX, y + 40, 80, 22, Theme::COLOR_ICON_BADGE, 1);
            drawText("ИКОНКА", cBadgeX + 14, y + 44, Theme::COLOR_ICON_BADGE, 10);
            cBadgeX += 88;
        }"""
assert target_cat_badges in c, 'target_cat_badges not found'
c = c.replace(target_cat_badges, repl_cat_badges, 1)

# 3. Update My Games variant badges in renderTabMyGames
target_mygames_badges = """                // Active installed background badge - EXACT MATCH ONLY
                bool isActiveOnConsole = (selGame.hasInstalledCover && v.id == selGame.installedVariantId);
                if (isActiveOnConsole) {
                    drawRect(785, vY + 38, 105, 22, {0x10, 0xB9, 0x81, 0x44});
                    drawRectOutline(785, vY + 38, 105, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("УСТАНОВЛЕН", 797, vY + 43, Theme::COLOR_SUCCESS, 10);
                }

                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(905, vY + 38, 70, 22, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(905, vY + 38, 70, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", 924, vY + 43, Theme::COLOR_SUCCESS, 10);
                } else {
                    drawRect(905, vY + 38, 85, 22, {0x28, 0x33, 0x47, 0x44});
                    drawRectOutline(905, vY + 38, 85, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", 916, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                }"""

repl_mygames_badges = """                // Badges row: Active on console, Audio, and Video Icon
                int vBadgeX = 720;
                bool isActiveOnConsole = (selGame.hasInstalledCover && v.id == selGame.installedVariantId);
                if (isActiveOnConsole) {
                    drawRect(vBadgeX, vY + 38, 92, 22, {0x10, 0xB9, 0x81, 0x44});
                    drawRectOutline(vBadgeX, vY + 38, 92, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("УСТАНОВЛЕН", vBadgeX + 8, vY + 43, Theme::COLOR_SUCCESS, 10);
                    vBadgeX += 98;
                }

                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(vBadgeX, vY + 38, 62, 22, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(vBadgeX, vY + 38, 62, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", vBadgeX + 15, vY + 43, Theme::COLOR_SUCCESS, 10);
                    vBadgeX += 68;
                } else {
                    drawRect(vBadgeX, vY + 38, 78, 22, Theme::COLOR_MUTED_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 78, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", vBadgeX + 9, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                    vBadgeX += 84;
                }

                // Video Icon Status Pill (prominent cyan when present, muted when absent)
                if (v.hasIcon) {
                    drawRect(vBadgeX, vY + 38, 72, 22, Theme::COLOR_ICON_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 72, 22, Theme::COLOR_ICON_BADGE, 1);
                    drawText("ИКОНКА", vBadgeX + 11, vY + 43, Theme::COLOR_ICON_BADGE, 10);
                } else {
                    drawRect(vBadgeX, vY + 38, 86, 22, Theme::COLOR_MUTED_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 86, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ИКОНКИ", vBadgeX + 9, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                }"""
assert target_mygames_badges in c, 'target_mygames_badges not found'
c = c.replace(target_mygames_badges, repl_mygames_badges, 1)

# 4. Update preview HUD badges in renderFullscreenPreview
target_preview_badges = """        if (v.hasIcon) {
            drawRect(badgeX, hudY + 66, 95, 24, {0x0E, 0x74, 0x90, 0x44});
            drawRectOutline(badgeX, hudY + 66, 95, 24, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("🔲 ИКОНКА", badgeX + 10, hudY + 71, Theme::COLOR_FOCUS_CYAN, 11);
            badgeX += 103;
        }"""

repl_preview_badges = """        if (v.hasIcon) {
            drawRect(badgeX, hudY + 66, 80, 24, Theme::COLOR_ICON_BADGE_FILL);
            drawRectOutline(badgeX, hudY + 66, 80, 24, Theme::COLOR_ICON_BADGE, 1);
            drawText("ИКОНКА", badgeX + 13, hudY + 71, Theme::COLOR_ICON_BADGE, 11);
            badgeX += 88;
        } else {
            drawRect(badgeX, hudY + 66, 92, 24, Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(badgeX, hudY + 66, 92, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ИКОНКИ", badgeX + 9, hudY + 71, Theme::COLOR_TEXT_MUTED, 11);
            badgeX += 100;
        }"""
assert target_preview_badges in c, 'target_preview_badges not found'
c = c.replace(target_preview_badges, repl_preview_badges, 1)

# 5. Update collection browser in renderCollectionBrowser
target_coll_audio = """        // Audio badge
        if (v.hasAudio) {
            drawRect(bxPos, cardY + 46, 65, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(bxPos, cardY + 46, 65, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", bxPos + 14, cardY + 51, Theme::COLOR_SUCCESS, 11);
            bxPos += 75;
        } else {
            drawRect(bxPos, cardY + 46, 85, 24, {0x28, 0x33, 0x47, 0x44});
            drawRectOutline(bxPos, cardY + 46, 85, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ЗВУКА", bxPos + 10, cardY + 51, Theme::COLOR_TEXT_MUTED, 10);
            bxPos += 95;
        }"""

repl_coll_audio = """        // Audio badge
        if (v.hasAudio) {
            drawRect(bxPos, cardY + 46, 65, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(bxPos, cardY + 46, 65, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", bxPos + 14, cardY + 51, Theme::COLOR_SUCCESS, 11);
            bxPos += 75;
        } else {
            drawRect(bxPos, cardY + 46, 82, 24, Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 82, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ЗВУКА", bxPos + 9, cardY + 51, Theme::COLOR_TEXT_MUTED, 10);
            bxPos += 90;
        }

        // Icon badge
        if (v.hasIcon) {
            drawRect(bxPos, cardY + 46, 75, 24, Theme::COLOR_ICON_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 75, 24, Theme::COLOR_ICON_BADGE, 1);
            drawText("ИКОНКА", bxPos + 11, cardY + 51, Theme::COLOR_ICON_BADGE, 11);
            bxPos += 83;
        } else {
            drawRect(bxPos, cardY + 46, 86, 24, Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 86, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ИКОНКИ", bxPos + 8, cardY + 51, Theme::COLOR_TEXT_MUTED, 10);
            bxPos += 94;
        }"""
assert target_coll_audio in c, 'target_coll_audio not found'
c = c.replace(target_coll_audio, repl_coll_audio, 1)

# 6. Update filter and cycle logic
target_filter = """        // 3. Audio Only filter
        if (m_catalogSortMode == CatalogSortMode::AudioOnly) {
            bool hasAud = false;
            for (const auto& v : g.variants) {
                if (v.hasAudio) {
                    hasAud = true;
                    break;
                }
            }
            if (!hasAud) continue;
        }"""

repl_filter = """        // 3. Audio Only filter
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

        // 3.1 Icons Only filter
        if (m_catalogSortMode == CatalogSortMode::IconsOnly) {
            bool hasIco = false;
            for (const auto& v : g.variants) {
                if (v.hasIcon) {
                    hasIco = true;
                    break;
                }
            }
            if (!hasIco) continue;
        }"""
assert target_filter in c, 'target_filter not found'
c = c.replace(target_filter, repl_filter, 1)

target_cycle = """void App::cycleCatalogSortMode() {
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
    }"""

repl_cycle = """void App::cycleCatalogSortMode() {
    int nextMode = (static_cast<int>(m_catalogSortMode) + 1) % 7;
    m_catalogSortMode = static_cast<CatalogSortMode>(nextMode);
    rebuildCatalogFilter();

    std::string modeDesc;
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: modeDesc = "Сортировка: По умолчанию"; break;
        case CatalogSortMode::Alphabetical: modeDesc = "Сортировка: По алфавиту (А-Я)"; break;
        case CatalogSortMode::VariantsCount: modeDesc = "Сортировка: По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: modeDesc = "Фильтр: Только со звуком [ЗВУК]"; break;
        case CatalogSortMode::IconsOnly: modeDesc = "Фильтр: Только с видеоиконками [ИКОНКА]"; break;
        case CatalogSortMode::InstalledOnly: modeDesc = "Фильтр: Только установленные игры"; break;
        case CatalogSortMode::FavoritesOnly: modeDesc = "Фильтр: ★ Только избранное"; break;
    }"""
assert target_cycle in c, 'target_cycle not found'
c = c.replace(target_cycle, repl_cycle, 1)

with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8', newline='\r\n') as f:
    f.write(c)

print('app.cpp successfully patched with prominent icon badges and sort mode!')
