import os

app_cpp_path = "e:/videofon/downloader/src/ui/app.cpp"
with open(app_cpp_path, "r", encoding="utf-8") as f:
    code = f.read().replace("\r\n", "\n")

# 1. Redesign renderTabCatalog() completely and remove renderCategoriesView() body
# Find renderCategoriesView definition
idx_cat_view = code.find("void App::renderCategoriesView() {")
idx_video_icons = code.find("void App::renderTabVideoIcons() {")
assert idx_cat_view != -1 and idx_video_icons != -1, "Categories/VideoIcons not found"

# Replace renderCategoriesView with empty stub (since Catalog directly renders unified view)
empty_cat_view = """void App::renderCategoriesView() {
    // Legacy stub - Tab::Catalog now renders unified direct view with [L] Весь каталог and [R] Избранное
    renderTabCatalog();
}

"""
code = code[:idx_cat_view] + empty_cat_view + code[idx_video_icons:]
print("[+] Replaced renderCategoriesView with direct delegation")

# Now find renderTabCatalog()
idx_tab_cat = code.find("void App::renderTabCatalog() {")
idx_tab_dl = code.find("void App::renderTabDownloads() {")
assert idx_tab_cat != -1 and idx_tab_dl != -1, "renderTabCatalog/renderTabDownloads not found"

new_tab_catalog = """void App::renderTabCatalog() {
    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 74, 1220, 576, false, false);

    bool isFavTab = (m_catalogSortMode == CatalogSortMode::FavoritesOnly);
    size_t totalCatGames = m_catalogManager.getGamesCount();
    size_t totalFavorites = m_favoriteKeys.size();

    // 1. Top Bar: Segment Tabs, Search Bar, Sort Pill, Back Button (y=82, h=38)
    // Segment Tab 1: [L] Весь каталог
    std::string tab1Text = "[L] Весь каталог (" + std::to_string(totalCatGames) + ")";
    int t1W = measureTextWidth(tab1Text, 13) + 24;
    drawRoundedRect(50, 82, t1W, 38, 10, !isFavTab ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_PILL_BG);
    if (!isFavTab) {
        drawNeonRoundedOutline(50, 82, t1W, 38, 10, 2);
    } else {
        drawRoundedOutline(50, 82, t1W, 38, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }
    drawTextCentered(tab1Text, 50 + t1W / 2, 91, !isFavTab ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 13);

    // Segment Tab 2: [R] Избранное
    std::string tab2Text = "[R] Избранное (" + std::to_string(totalFavorites) + ")";
    int t2W = measureTextWidth(tab2Text, 13) + 24;
    int t2X = 50 + t1W + 10;
    drawRoundedRect(t2X, 82, t2W, 38, 10, isFavTab ? Color{0xEC, 0x48, 0x99, 0x24} : Theme::COLOR_PILL_BG);
    if (isFavTab) {
        drawRoundedOutline(t2X, 82, t2W, 38, 10, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 2);
    } else {
        drawRoundedOutline(t2X, 82, t2W, 38, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }
    drawTextCentered(tab2Text, t2X + t2W / 2, 91, isFavTab ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_MUTED, 13);

    // Interactive Search Bar (x=465, y=82, w=420, h=38)
    bool hasSearch = !m_catalogSearchQuery.empty();
    drawGlassCard(465, 82, 420, 38, hasSearch, false);
    drawSearchIcon(482, 101, hasSearch ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED);
    std::string searchLabel = hasSearch
        ? ("Поиск: " + m_catalogSearchQuery)
        : "Поиск по названию игры или TitleID...";
    drawText(searchLabel, 498, 92, hasSearch ? Theme::COLOR_TEXT_PRIMARY : Theme::COLOR_TEXT_MUTED, 13, 290);
    drawRoundedRect(805, 88, 72, 26, 6, Theme::COLOR_FOCUS_FILL);
    drawRoundedOutline(805, 88, 72, 26, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered("[Y] Поиск", 841, 93, Theme::COLOR_FOCUS_CYAN, 11);

    // Sort mode button (x=895, y=82, w=180, h=38)
    std::string sortStr = "[X] Сорт: ";
    switch (m_catalogSortMode) {
        case CatalogSortMode::Alphabetical: sortStr += "А-Я"; break;
        case CatalogSortMode::VariantsCount: sortStr += "Варианты"; break;
        case CatalogSortMode::AudioOnly: sortStr += "Звук"; break;
        case CatalogSortMode::IconsOnly: sortStr += "Иконки"; break;
        case CatalogSortMode::InstalledOnly: sortStr += "Установленные"; break;
        case CatalogSortMode::FavoritesOnly: sortStr += "Избранное"; break;
        default: sortStr += "По умолч."; break;
    }
    drawPillButton(895, 82, 180, 38, sortStr, false, Theme::COLOR_FOCUS_CYAN);

    // Back to Home button (x=1085, y=82, w=145, h=38)
    drawPillButton(1085, 82, 145, 38, "(B) На главную", false, Theme::COLOR_TEXT_MUTED);

    // 2. Games List Area
    int totalFiltered = static_cast<int>(m_filteredCatalogGames.size());
    if (totalFiltered == 0) {
        if (isFavTab) {
            // Elegant empty state for Favorites
            drawRoundedRect(490, 200, 300, 240, 24, {0x14, 0x1A, 0x28, 0xFF});
            drawRoundedOutline(490, 200, 300, 240, 24, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 2);
            drawTextCentered("★", 640, 245, Theme::COLOR_FOCUS_PINK, 36);
            drawTextCentered("Избранное пусто", 640, 295, Theme::COLOR_TEXT_PRIMARY, 18);
            drawTextCentered("Нажмите [-] на любой игре в каталоге,", 640, 330, Theme::COLOR_TEXT_MUTED, 13);
            drawTextCentered("чтобы добавить её в быстрый доступ", 640, 350, Theme::COLOR_TEXT_MUTED, 13);
            drawPillButton(540, 380, 200, 36, "[L] Открыть весь каталог", true, Theme::COLOR_FOCUS_CYAN);
        } else {
            drawTextCentered("Игры по вашему запросу не найдены", 640, 320, Theme::COLOR_TEXT_MUTED, 16);
            drawTextCentered("Нажмите [Y] для изменения поиска или [-] для сброса", 640, 355, Theme::COLOR_FOCUS_CYAN, 13);
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

    int y = 136;
    int endIdx = std::min(totalFiltered, m_catalogScrollOffset + visibleCount);
    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        const auto& game = m_filteredCatalogGames[i];
        bool isFocused = (i == m_catalogSelectedIndex);
        bool isFav = hasGameFavorites(game.titleId);

        drawGlassCard(50, y, 1180, 88, isFocused, isFocused);

        // Cartridge / Game Preview Box (x=64, y=y+9, w=70, h=70)
        int boxX = 64;
        int boxY = y + 9;
        drawRoundedRect(boxX, boxY, 70, 70, 12, {0x14, 0x1A, 0x28, 0xFF});
        drawRoundedOutline(boxX, boxY, 70, 70, 12, isFocused ? (isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN) : Theme::COLOR_BORDER, isFocused ? (isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN) : Theme::COLOR_BORDER, 1);

        // Draw mini cartridge symbol inside box
        drawRoundedRect(boxX + 22, boxY + 16, 26, 38, 4, {0x26, 0x32, 0x48, 0xFF});
        drawRoundedRect(boxX + 24, boxY + 18, 22, 10, 2, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN);
        drawRoundedRect(boxX + 24, boxY + 31, 22, 20, 2, {0x0E, 0x14, 0x22, 0xFF});

        // Info Column
        int infoX = boxX + 86;
        drawText(game.title, infoX, y + 14, isFocused ? (isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_FOCUS_CYAN) : Theme::COLOR_TEXT_PRIMARY, 16, 600);

        // Subline: TitleID + Publisher
        std::string pubText = game.publisher.empty() ? "Nintendo Switch" : game.publisher;
        drawText(game.titleId + "  |  " + pubText, infoX, y + 42, Theme::COLOR_TEXT_MUTED, 12);

        // Badges: Variants count & Video Icon
        int vCount = static_cast<int>(game.variants.size());
        std::string vStr = std::to_string(vCount) + " вар. фона";
        int vBadgeW = measureTextWidth(vStr, 11) + 16;
        int curBadgeX = infoX + 330;
        drawRoundedRect(curBadgeX, y + 42, vBadgeW, 22, 4, Theme::COLOR_FOCUS_FILL);
        drawRoundedOutline(curBadgeX, y + 42, vBadgeW, 22, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered(vStr, curBadgeX + vBadgeW / 2, y + 46, Theme::COLOR_FOCUS_CYAN, 11);

        bool hasIcon = false;
        for (const auto& v : game.variants) {
            if (v.hasIcon && !v.iconUrl.empty()) { hasIcon = true; break; }
        }
        if (hasIcon) {
            curBadgeX += vBadgeW + 8;
            drawRoundedRect(curBadgeX, y + 42, 85, 22, 4, Color{0xEC, 0x48, 0x99, 0x24});
            drawRoundedOutline(curBadgeX, y + 42, 85, 22, 4, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
            drawTextCentered("256x256", curBadgeX + 42, y + 46, Theme::COLOR_FOCUS_PINK, 11);
        }

        // Action Buttons on Right
        // 1. Favorite toggle button: [-] В избр. (x=805, y=y+25, w=115, h=38)
        drawRoundedRect(805, y + 25, 115, 38, 8, isFav ? Color{0xEC, 0x48, 0x99, 0x24} : Color{0x14, 0x1E, 0x30, 0xDD});
        drawRoundedOutline(805, y + 25, 115, 38, 8, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_BORDER, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_BORDER, 1);
        drawTextCentered(isFav ? "[-] В избр. ★" : "[-] В избр.", 805 + 57, y + 36, isFav ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_MUTED, 12);

        // 2. Quick Preview button: [ZL] Просмотр (x=930, y=y+25, w=135, h=38)
        drawRoundedRect(930, y + 25, 135, 38, 8, Color{0x14, 0x1E, 0x30, 0xDD});
        drawRoundedOutline(930, y + 25, 135, 38, 8, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
        drawTextCentered("[ZL] Просмотр", 930 + 67, y + 36, Theme::COLOR_TEXT_PRIMARY, 12);

        // 3. Select Themes button: [A] Выбрать (x=1075, y=y+25, w=140, h=38)
        drawRoundedRect(1075, y + 25, 140, 38, 8, isFocused ? Theme::COLOR_FOCUS_FILL : Color{0x18, 0x22, 0x34, 0xEE});
        drawNeonRoundedOutline(1075, y + 25, 140, 38, 8, isFocused ? 2 : 1);
        drawTextCentered("[A] Выбрать", 1075 + 70, y + 36, Theme::COLOR_FOCUS_CYAN, 13);

        y += 98;
    }
}
"""

code = code[:idx_tab_cat] + new_tab_catalog + code[idx_tab_dl:]
print("[+] Replaced renderTabCatalog with high-grade unified view")

# 2. Update onButtonPress for Tab::Catalog
idx_btn_cat = code.find("} else if (m_activeTab == Tab::Catalog) {")
idx_btn_cat_end = code.find("} else if (m_activeTab == Tab::VideoIcons) {")
assert idx_btn_cat != -1 and idx_btn_cat_end != -1, "Button press Tab::Catalog not found"

new_btn_cat = """} else if (m_activeTab == Tab::Catalog) {
        int totalGames = static_cast<int>(m_filteredCatalogGames.size());

        // [B] - Back to Home dashboard
        if (button == 1 /* B */) {
            m_activeTab = Tab::Home;
            return;
        }

        // [L] - Switch to "Весь каталог" tab
        if (button == 7 /* L */) {
            if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
                m_catalogSortMode = CatalogSortMode::Default;
                m_activeCategoryName = "Весь каталог";
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                m_statusNotification = "Каталог: Весь каталог";
                m_notificationFramesRemaining = 90;
            }
            return;
        }

        // [R] - Switch to "Избранное" tab
        if (button == 8 /* R */) {
            if (m_catalogSortMode != CatalogSortMode::FavoritesOnly) {
                m_catalogSortMode = CatalogSortMode::FavoritesOnly;
                m_activeCategoryName = "Избранное";
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                m_statusNotification = "Каталог: Избранное";
                m_notificationFramesRemaining = 90;
            }
            return;
        }

        // [X] - Cycle Sort Mode
        if (button == 2 /* X */) {
            cycleCatalogSortMode();
            return;
        }

        // [Y] - Open Horizon Software Keyboard for Search
        if (button == 3 /* Y */) {
            openCatalogKeyboard();
            return;
        }

        // [-] (Minus) - Toggle Favorite for selected game
        if (button == 4 /* MINUS */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
                if (!curGame.variants.empty()) {
                    bool wasFav = hasGameFavorites(curGame.titleId);
                    if (wasFav) {
                        for (const auto& v : curGame.variants) {
                            m_favoriteKeys.erase(curGame.titleId + ":" + v.id);
                            m_favoriteKeys.erase(v.id);
                        }
                        m_statusNotification = "Удалено из избранного: " + curGame.title;
                    } else {
                        m_favoriteKeys.insert(curGame.titleId + ":" + curGame.variants[0].id);
                        m_statusNotification = "Добавлено в избранное ★: " + curGame.title;
                    }
                    m_notificationFramesRemaining = 90;
                    saveFavorites();
                    rebuildCatalogFilter();
                }
            } else {
                fetchRemoteCatalog();
            }
            return;
        }

        // Navigation
        if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) m_catalogSelectedIndex--;
            return;
        }
        if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) m_catalogSelectedIndex++;
            return;
        }
        if (button == 13 /* DPAD_LEFT - Page Up 5 */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
            return;
        }
        if (button == 14 /* DPAD_RIGHT - Page Down 5 */) {
            if (totalGames > 0) m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
            return;
        }

        // [ZL] - Quick Fullscreen Preview with audio
        if (button == 15 /* ZL */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& curGame = m_filteredCatalogGames[m_catalogSelectedIndex];
                if (!curGame.variants.empty()) {
                    openFullscreenPreview(curGame.titleId, curGame.variants, 0);
                }
            }
            return;
        }

        // [A] - Open Collection Browser modal
        if (button == 0 /* A */) {
            if (totalGames > 0 && m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                openCollectionBrowser(m_filteredCatalogGames[m_catalogSelectedIndex]);
            }
            return;
        }
        return;
    """

code = code[:idx_btn_cat] + new_btn_cat + code[idx_btn_cat_end:]
print("[+] Replaced button handling for Tab::Catalog")

# 3. Update footer prompts for Tab::Catalog
idx_foot_cat = code.find("} else if (m_activeTab == Tab::Catalog) {")
idx_foot_mygames = code.find("} else if (m_activeTab == Tab::MyGames) {")
assert idx_foot_cat != -1 and idx_foot_mygames != -1, "Footer Tab::Catalog not found"

new_foot_cat = """} else if (m_activeTab == Tab::Catalog) {
        drawPrompt("A", "Выбрать", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", "Назад", Theme::COLOR_TEXT_MUTED);
        drawPrompt("ZL", "Просмотр", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("-", "В избр. ★", Theme::COLOR_FOCUS_PINK);
        drawPrompt("L/R", "Разделы", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("Y", "Поиск", Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("X", "Сортировка", Theme::COLOR_TEXT_PRIMARY);
    """

code = code[:idx_foot_cat] + new_foot_cat + code[idx_foot_mygames:]
print("[+] Updated footer prompts for Tab::Catalog")

# 4. Update touch zone for Tab::Catalog
old_touch_cat_start = code.find("else if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::Categories && mx >= 340")
if old_touch_cat_start == -1:
    old_touch_cat_start = code.find("else if (m_activeTab == Tab::Catalog && mx >= 340")
assert old_touch_cat_start != -1, "Old touch catalog start not found"
old_touch_cat_end = code.find("else if (m_activeTab == Tab::MyGames)", old_touch_cat_start)
assert old_touch_cat_end != -1, "Touch Tab::MyGames not found"

new_touch_cat = """else if (m_activeTab == Tab::Catalog) {
                // Top Tab 1: [L] Весь каталог (x in [50, 270], y in [74, 122])
                if (mx >= 50 && mx <= 270 && my >= 74 && my <= 122) {
                    onButtonPress(7 /* L - Весь каталог */);
                }
                // Top Tab 2: [R] Избранное (x in [280, 460], y in [74, 122])
                else if (mx >= 280 && mx <= 460 && my >= 74 && my <= 122) {
                    onButtonPress(8 /* R - Избранное */);
                }
                // Search Bar (x in [465, 885], y in [74, 122])
                else if (mx >= 465 && mx <= 885 && my >= 74 && my <= 122) {
                    onButtonPress(3 /* Y - Open Search Keyboard */);
                }
                // Sort Mode Button (x in [895, 1075], y in [74, 122])
                else if (mx >= 895 && mx <= 1075 && my >= 74 && my <= 122) {
                    onButtonPress(2 /* X - Cycle Sort */);
                }
                // Back to Home Button (x in [1085, 1235], y in [74, 122])
                else if (mx >= 1085 && mx <= 1235 && my >= 74 && my <= 122) {
                    onButtonPress(1 /* B - Back to Home */);
                }
                // Click on Game row items (y in [136, 630])
                else if (mx >= 50 && mx <= 1230 && my >= 136 && my <= 630) {
                    int clickedIdx = m_catalogScrollOffset + (my - 136) / 98;
                    int totalGames = static_cast<int>(m_filteredCatalogGames.size());
                    if (clickedIdx >= 0 && clickedIdx < totalGames) {
                        m_catalogSelectedIndex = clickedIdx;
                        // Click on Favorite button [-] (x in [805, 920])
                        if (mx >= 805 && mx <= 920) {
                            onButtonPress(4 /* Minus - Toggle Favorite */);
                        }
                        // Click on Preview button [ZL] (x in [930, 1065])
                        else if (mx >= 930 && mx <= 1065) {
                            onButtonPress(15 /* ZL - Preview */);
                        }
                        // Click on Select button [A] (x in [1075, 1220])
                        else if (mx >= 1075 && mx <= 1220) {
                            onButtonPress(0 /* A - Open Collection Browser */);
                        }
                    }
                }
            }
            """

code = code[:old_touch_cat_start] + new_touch_cat + code[old_touch_cat_end:]
print("[+] Replaced touch handling for Tab::Catalog")

# 5. Update drawTileIconVector to render icons with size 92 for bolder presence
idx_icon_size = code.find("int iconSize = isFocused ? 76 : 70;")
if idx_icon_size != -1:
    code = code.replace("int iconSize = isFocused ? 76 : 70;", "int iconSize = isFocused ? 94 : 86;", 1)
    print("[+] Enlarged tab icon rendering size to 94px/86px for crisp 3D presence")

with open(app_cpp_path, "w", encoding="utf-8") as f:
    f.write(code)

print("\nSUCCESS! Successfully completed entire redesign of Tab::Catalog!")
