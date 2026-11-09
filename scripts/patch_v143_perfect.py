import os

app_cpp = "downloader/src/ui/app.cpp"
with open(app_cpp, "r", encoding="utf-8") as f:
    code = f.read().replace("\r\n", "\n")

# 1. Add loadTabIcons and freeTabIcons implementations before App::~App()
tab_icon_funcs = """void App::loadTabIcons() {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    const char* names[5] = {
        "tab_catalog.png",
        "tab_video_icons.png",
        "tab_my_games.png",
        "tab_downloads.png",
        "tab_settings.png"
    };

    const char* prefixes[] = {
        "romfs:/icons/",
        "downloader/romfs/icons/",
        "sdmc:/switch/H3H-Backgrounds/icons/",
        "sdmc:/switch/H3H-AfterDark/icons/"
    };

    for (int i = 0; i < 5; ++i) {
        if (m_tabIconTextures[i]) continue;
        for (const char* pfx : prefixes) {
            std::string fullPath = std::string(pfx) + names[i];
            SDL_Texture* tex = loadTextureFromFile(m_renderer, fullPath);
            if (tex) {
                m_tabIconTextures[i] = tex;
                break;
            }
        }
    }
#endif
}

void App::freeTabIcons() {
#ifdef HAS_SDL2
    for (int i = 0; i < 5; ++i) {
        if (m_tabIconTextures[i]) {
            SDL_DestroyTexture(m_tabIconTextures[i]);
            m_tabIconTextures[i] = nullptr;
        }
    }
#endif
}
"""

if "void App::loadTabIcons()" not in code:
    idx_dtor = code.find("App::~App()")
    assert idx_dtor != -1, "App::~App() not found"
    code = code[:idx_dtor] + tab_icon_funcs + "\n" + code[idx_dtor:]
    print("[1] Added loadTabIcons and freeTabIcons")

# 2. Call loadTabIcons() in init()
old_init = """    m_renderer = SDL_CreateRenderer(
        m_window,
        -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
    );

    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }"""
new_init = old_init + "\n\n    loadTabIcons();"
if "loadTabIcons();" not in code:
    assert old_init in code, "old_init not found"
    code = code.replace(old_init, new_init, 1)
    print("[2] Added loadTabIcons() in init()")

# 3. Call freeTabIcons() in shutdown()
old_shut = """#ifdef HAS_SDL2
    if (m_collectionThumbTexture) {"""
new_shut = """#ifdef HAS_SDL2
    freeTabIcons();
    if (m_collectionThumbTexture) {"""
if "freeTabIcons();" not in code:
    assert old_shut in code, "old_shut not found"
    code = code.replace(old_shut, new_shut, 1)
    print("[3] Added freeTabIcons() in shutdown()")

# 4. Add animation updates to App::update()
if "m_tileAnimScale[i] += (targetScale - m_tileAnimScale[i])" not in code:
    old_upd = """void App::update() {
#ifdef HAS_SDL2"""
    new_upd = """void App::update() {
#ifdef HAS_SDL2
    uint32_t currentTicks = SDL_GetTicks();
    float timeMs = static_cast<float>(currentTicks);

    // 1. Smooth 60 FPS spring-lerp tile scale for Home Dashboard
    for (int i = 0; i < 5; ++i) {
        float targetScale = (m_homeFocusedTile == i) ? 1.055f : 1.0f;
        m_tileAnimScale[i] += (targetScale - m_tileAnimScale[i]) * 0.22f;
    }

    // 2. Continuous idle animation parameters
    m_gearAngle += 0.025f;
    if (m_gearAngle > 6.2831853f) m_gearAngle -= 6.2831853f;

    m_downloadArrowBob = std::sin(timeMs * 0.006f) * 3.5f;

    // 3. Header Equalizer bars animation (smooth audio wave visualizer)
    m_equalizerHeights[0] = 16.0f + 6.0f * std::sin(timeMs * 0.005f);
    m_equalizerHeights[1] = 22.0f + 8.0f * std::sin(timeMs * 0.007f + 1.2f);
    m_equalizerHeights[2] = 14.0f + 5.0f * std::sin(timeMs * 0.006f + 2.4f);

    // 4. Subtle cyber-glow breathing pulse
    m_glowPulse = 0.82f + 0.18f * std::sin(timeMs * 0.005f);

    // 5. Button click bounce decay
    if (m_buttonPressAnim > 0.01f) {
        m_buttonPressAnim *= 0.78f;
    } else {
        m_buttonPressAnim = 0.0f;
    }

    // 6. Smooth tab transition alpha fade-in
    if (m_tabTransitionAlpha < 255.0f) {
        m_tabTransitionAlpha = std::min(255.0f, m_tabTransitionAlpha + 24.0f);
    }
"""
    assert old_upd in code, "old_upd not found"
    code = code.replace(old_upd, new_upd, 1)
    print("[4] Added 60 FPS animation updates in update()")

# 5. Add buttonPressAnim trigger to onButtonPress()
if "m_buttonPressAnim = 1.0f;" not in code:
    old_btn = "void App::onButtonPress(int button) {\n"
    new_btn = "void App::onButtonPress(int button) {\n    m_buttonPressAnim = 1.0f;\n"
    assert old_btn in code, "old_btn not found"
    code = code.replace(old_btn, new_btn, 1)
    print("[5] Added buttonPressAnim trigger in onButtonPress()")

# 6. Remove intermediate Categories check on B button
old_b_back = """    // Standard Nintendo Switch [B] button
    if (button == 1 /* B - Back */) {
        if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::GameGrid) {
            m_catalogViewMode = CatalogViewMode::Categories;
            return;
        }"""
new_b_back = """    // Standard Nintendo Switch [B] button
    if (button == 1 /* B - Back */) {"""
if old_b_back in code:
    code = code.replace(old_b_back, new_b_back, 1)
    print("[6] Removed intermediate Categories check from [B] button")

# 7. Replace onButtonPress for Tab::Catalog
idx_btn_cat = code.find("} else if (m_activeTab == Tab::Catalog) {")
idx_btn_dl = code.find("} else if (m_activeTab == Tab::Downloads) {", idx_btn_cat)
assert idx_btn_cat != -1 and idx_btn_dl != -1, "onButtonPress Tab::Catalog not found"

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
                    openFullscreenPreviewForCatalogGame(curGame, 0);
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
code = code[:idx_btn_cat] + new_btn_cat + code[idx_btn_dl:]
print("[7] Replaced onButtonPress for Tab::Catalog")

# 8. Animated Equalizer bars in renderHeader()
old_eq = """    // Left Branding: App Name + Tag Badge
    // Triple accent bars (TorrentShopNX style logo)
    drawRoundedRect(30, 24, 4, 18, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(38, 20, 4, 26, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(46, 25, 4, 16, 2, Theme::COLOR_FOCUS_CYAN);"""

new_eq = """    // Left Branding: App Name + Tag Badge
    // Triple animated equalizer accent bars (Cyber Audio Visualizer)
    int h0 = static_cast<int>(m_equalizerHeights[0]);
    int h1 = static_cast<int>(m_equalizerHeights[1]);
    int h2 = static_cast<int>(m_equalizerHeights[2]);
    drawRoundedRect(30, 42 - h0, 4, h0, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(38, 44 - h1, 4, h1, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(46, 42 - h2, 4, h2, 2, Theme::COLOR_FOCUS_CYAN);"""
if old_eq in code:
    code = code.replace(old_eq, new_eq, 1)
    print("[8] Added animated equalizer in renderHeader()")

# 9. Update renderFooter for Tab::Catalog
idx_foot_cat = code.find("} else if (m_activeTab == Tab::Catalog) {")
# Note: the second occurrence is in renderFooter()!
idx_foot_cat = code.find("} else if (m_activeTab == Tab::Catalog) {", idx_btn_dl)
idx_foot_mg = code.find("} else if (m_activeTab == Tab::MyGames) {", idx_foot_cat)
assert idx_foot_cat != -1 and idx_foot_mg != -1, "renderFooter Tab::Catalog not found"

new_foot_cat = """} else if (m_activeTab == Tab::Catalog) {
        drawPrompt("A", "Выбрать", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("B", "Назад", Theme::COLOR_TEXT_MUTED);
        drawPrompt("ZL", "Просмотр", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("-", "В избр. ★", Theme::COLOR_FOCUS_PINK);
        drawPrompt("L/R", "Разделы", Theme::COLOR_FOCUS_CYAN);
        drawPrompt("Y", "Поиск", Theme::COLOR_TEXT_PRIMARY);
        drawPrompt("X", "Сортировка", Theme::COLOR_TEXT_PRIMARY);
    """
code = code[:idx_foot_cat] + new_foot_cat + code[idx_foot_mg:]
print("[9] Updated renderFooter for Tab::Catalog")

# 10. Update Home tab Sub-card 2
old_sc2_start = code.find("// Sub-card 2: Main Collections & Quick Action")
idx_mg_func = code.find("void App::renderTabMyGames() {")
assert old_sc2_start != -1 and idx_mg_func != -1, "Sub-card 2 not found"

new_sc2 = """// Sub-card 2: Main Collections & Quick Action (560px wide, highlighted)
    drawGlassCard(sc2X, subY, cardW, subH, true, true);
    drawText("РАЗДЕЛЫ КАТАЛОГА", sc2X + 22, subY + 18, Theme::COLOR_TEXT_MUTED, 12);
    drawTextRight("4IFIR Engine", sc2X + cardW - 22, subY + 18, Theme::COLOR_FOCUS_CYAN, 12);

    size_t totalCatAll = m_catalogManager.getGamesCount();
    size_t totalFavAll = m_favoriteKeys.size();
    struct PillData {
        std::string label;
        Color borderCol;
        Color fillCol;
    };
    PillData pData[3] = {
        {"Весь каталог (" + std::to_string(totalCatAll) + ")", Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_FILL},
        {"Избранное (" + std::to_string(totalFavAll) + ")", Theme::COLOR_FOCUS_PINK, Color{0xEC, 0x48, 0x99, 0x24}},
        {"Поиск [Y]", Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_FILL}
    };

    int curPillX = sc2X + 22;
    for (int p = 0; p < 3; ++p) {
        int pw = measureTextWidth(pData[p].label, 11) + 20;
        drawRoundedRect(curPillX, subY + 64, pw, 26, 6, pData[p].fillCol);
        drawRoundedOutline(curPillX, subY + 64, pw, 26, 6, pData[p].borderCol, pData[p].borderCol, 1);
        drawTextCentered(pData[p].label, curPillX + pw / 2, subY + 70, pData[p].borderCol, 11);
        curPillX += pw + 10;
    }

    drawText("(A) Открыть каталог • (X) Избранное • (Y) Поиск", sc2X + 22, subY + 136, Theme::COLOR_FOCUS_CYAN, 12, cardW - 44);
}

"""
code = code[:old_sc2_start] + new_sc2 + code[idx_mg_func:]
print("[10] Updated Home tab Sub-card 2")

# 11. Replace renderCategoriesView with empty stub delegating to renderTabCatalog()
idx_cat_view = code.find("void App::renderCategoriesView() {")
idx_vi_func = code.find("void App::renderTabVideoIcons() {")
assert idx_cat_view != -1 and idx_vi_func != -1, "renderCategoriesView boundaries not found"

empty_cat_view = """void App::renderCategoriesView() {
    renderTabCatalog();
}

"""
code = code[:idx_cat_view] + empty_cat_view + code[idx_vi_func:]
print("[11] Replaced renderCategoriesView with direct delegation to renderTabCatalog")

# 12. Redesign renderTabCatalog completely
idx_tab_cat = code.find("void App::renderTabCatalog() {")
idx_tab_dl = code.find("void App::renderTabDownloads() {")
assert idx_tab_cat != -1 and idx_tab_dl != -1, "renderTabCatalog boundaries not found"

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
print("[12] Redesigned renderTabCatalog")

# 13. Update Touch Handling for Tab::Catalog
idx_touch_cat = code.find("else if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::Categories && mx >= 340")
idx_touch_mg = code.find("else if (m_activeTab == Tab::MyGames)", idx_touch_cat)
assert idx_touch_cat != -1 and idx_touch_mg != -1, "Touch Tab::Catalog boundaries not found"

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
code = code[:idx_touch_cat] + new_touch_cat + code[idx_touch_mg:]
print("[13] Updated touch handling for Tab::Catalog")

# 14. drawTileIconVector rendering texture icons (size 96/88)
old_tile_vec = """void App::drawTileIconVector(int cx, int cy, int tileIdx, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color accent = isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY;"""

new_tile_vec = """void App::drawTileIconVector(int cx, int cy, int tileIdx, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    // 1. If high-res pre-rendered 4IFIR Cyber-Glass icon texture is loaded, render it!
    if (tileIdx >= 0 && tileIdx < 5 && m_tabIconTextures[tileIdx]) {
        int iconSize = isFocused ? 96 : 88;
        SDL_Rect dst{cx - iconSize / 2, cy - iconSize / 2 - 2, iconSize, iconSize};
        SDL_RenderCopy(m_renderer, m_tabIconTextures[tileIdx], nullptr, &dst);
        return;
    }

    Color accent = isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY;"""

assert old_tile_vec in code, "old_tile_vec not found"
code = code.replace(old_tile_vec, new_tile_vec, 1)
print("[14] Added texture rendering to drawTileIconVector")

# 15. drawDashboardTile with bouncy scale & neon breathing outline
old_dash = """void App::drawDashboardTile(int x, int y, int w, int h, int tileIdx, const std::string& title, const std::string& sub, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    Color bg = isFocused ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_TILE;
    drawRoundedRect(x, y, w, h, 24, bg);

    if (isFocused) {
        drawRoundedRect(x, y, w, h, 24, Theme::COLOR_FOCUS_FILL);
        drawNeonRoundedOutline(x, y, w, h, 24, 3);
    } else {
        drawRoundedOutline(x, y, w, h, 24, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }

    // Subtle top gloss highlight
    drawRoundedRect(x + 18, y + 2, w - 36, 2, 1, {0xFF, 0xFF, 0xFF, 0x1A});

    // Centered vector icon in upper area of tile
    int iconCx = x + w / 2;
    int iconCy = y + 72;
    drawTileIconVector(iconCx, iconCy, tileIdx, isFocused);

    // Centered Title underneath (measured pixel width, never overflows or shifts!)
    drawTextCentered(title, x + w / 2, y + h - 36, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
#else
    (void)x; (void)y; (void)w; (void)h; (void)tileIdx; (void)title; (void)sub; (void)isFocused;
#endif
}"""

new_dash = """void App::drawDashboardTile(int x, int y, int w, int h, int tileIdx, const std::string& title, const std::string& sub, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    // Smooth bouncy scale animation
    float scale = (tileIdx >= 0 && tileIdx < 5) ? m_tileAnimScale[tileIdx] : (isFocused ? 1.055f : 1.0f);
    int drawW = static_cast<int>(w * scale);
    int drawH = static_cast<int>(h * scale);
    int drawX = x - (drawW - w) / 2;
    int drawY = y - (drawH - h) / 2;

    Color bg = isFocused ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_TILE;
    drawRoundedRect(drawX, drawY, drawW, drawH, 24, bg);

    if (isFocused) {
        drawRoundedRect(drawX, drawY, drawW, drawH, 24, Theme::COLOR_FOCUS_FILL);
        // Breathing cyber neon glow
        uint8_t alpha = static_cast<uint8_t>(std::clamp(m_glowPulse * 255.0f, 160.0f, 255.0f));
        Color cGlow = Theme::COLOR_FOCUS_CYAN; cGlow.a = alpha;
        Color pGlow = Theme::COLOR_FOCUS_PINK; pGlow.a = alpha;
        drawRoundedOutline(drawX, drawY, drawW, drawH, 24, cGlow, pGlow, 3);
    } else {
        drawRoundedOutline(drawX, drawY, drawW, drawH, 24, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }

    // Subtle top gloss highlight
    drawRoundedRect(drawX + 18, drawY + 2, drawW - 36, 2, 1, {0xFF, 0xFF, 0xFF, 0x1A});

    // Centered vector or texture icon in upper area of tile
    int iconCx = drawX + drawW / 2;
    int iconCy = drawY + 70;
    drawTileIconVector(iconCx, iconCy, tileIdx, isFocused);

    // Centered Title underneath (measured pixel width, never overflows or shifts!)
    drawTextCentered(title, drawX + drawW / 2, drawY + drawH - 34, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
#else
    (void)x; (void)y; (void)w; (void)h; (void)tileIdx; (void)title; (void)sub; (void)isFocused;
#endif
}"""

assert old_dash in code, "old_dash not found"
code = code.replace(old_dash, new_dash, 1)
print("[15] Added scale animation and neon breathing to drawDashboardTile")

with open(app_cpp, "w", encoding="utf-8") as f:
    f.write(code)

print("\nSUCCESS! All 15 patches applied cleanly to app.cpp!")
