import os

app_cpp_path = "e:/videofon/downloader/src/ui/app.cpp"
with open(app_cpp_path, "r", encoding="utf-8") as f:
    code = f.read().replace("\r\n", "\n")

# 1. Categories input handling replacement
idx_cat_in_start = code.find("if (m_catalogViewMode == CatalogViewMode::Categories) {")
assert idx_cat_in_start != -1, "cat input start not found"
idx_cat_in_end = code.find("int totalGames = static_cast<int>(m_filteredCatalogGames.size());", idx_cat_in_start)
assert idx_cat_in_end != -1, "cat input end not found"

new_cat_input = """if (m_catalogViewMode == CatalogViewMode::Categories) {
            if (button == 1 /* B - Back to Home */) {
                m_activeTab = Tab::Home;
                return;
            }
            // Category navigation: 2 options only: 0 = Весь каталог, 1 = Избранное
            if (button == 13 /* DPAD_LEFT */ || button == 11 /* DPAD_UP */) {
                m_categorySelectedIndex = 0;
                return;
            }
            if (button == 14 /* DPAD_RIGHT */ || button == 12 /* DPAD_DOWN */) {
                m_categorySelectedIndex = 1;
                return;
            }
            if (button == 0 /* A - Open category */) {
                if (m_categorySelectedIndex == 0) {
                    m_activeCategoryName = "Весь каталог";
                    m_catalogSortMode = CatalogSortMode::Default;
                } else {
                    m_activeCategoryName = "Избранное";
                    m_catalogSortMode = CatalogSortMode::FavoritesOnly;
                }
                m_catalogViewMode = CatalogViewMode::GameGrid;
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                return;
            }
            if (button == 2 /* X - Full List */) {
                m_activeCategoryName = "Весь каталог";
                m_catalogSortMode = CatalogSortMode::Default;
                m_catalogViewMode = CatalogViewMode::GameGrid;
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                return;
            }
            if (button == 3 /* Y - Search keyboard */) {
                openCatalogKeyboard();
                if (!m_catalogSearchQuery.empty()) {
                    m_activeCategoryName = "Поиск: " + m_catalogSearchQuery;
                    m_catalogViewMode = CatalogViewMode::GameGrid;
                    m_catalogSelectedIndex = 0;
                    m_catalogScrollOffset = 0;
                    rebuildCatalogFilter();
                }
                return;
            }
            if (button == 4 /* MINUS - Refresh */) {
                fetchRemoteCatalog();
                return;
            }
            return;
        }

        """

code = code[:idx_cat_in_start] + new_cat_input + code[idx_cat_in_end:]
print("[+] Replaced Categories input handler")

# 2. In GameGrid mode, pressing L/R/X toggles between Весь каталог and Избранное
old_grid_toggle = """        } else if (button == 2 /* X - Cycle Sort Mode */) {
            cycleCatalogSortMode();"""

new_grid_toggle = """        } else if (button == 7 /* L */ || button == 8 /* R */ || button == 2 /* X - Toggle Tabs */) {
            if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
                m_catalogSortMode = CatalogSortMode::Default;
                m_activeCategoryName = "Весь каталог";
                m_statusNotification = "Каталог: Весь каталог";
            } else {
                m_catalogSortMode = CatalogSortMode::FavoritesOnly;
                m_activeCategoryName = "Избранное";
                m_statusNotification = "Каталог: Избранное";
            }
            m_catalogSelectedIndex = 0;
            m_catalogScrollOffset = 0;
            m_notificationFramesRemaining = 90;
            rebuildCatalogFilter();
            return;"""

assert old_grid_toggle in code, "old_grid_toggle not found"
code = code.replace(old_grid_toggle, new_grid_toggle, 1)
print("[+] Added L/R/X tab toggle to GameGrid")

# 3. Touch zone update for 2 wide cards
old_touch = """            // Catalog Categories View: Main Sections & Genre Cards click
            else if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::Categories && mx >= 60 && mx <= 1220 && my >= 140 && my <= 650) {
                int cardW = 270, gapX = 22;
                int col = std::clamp((mx - 60) / (cardW + gapX), 0, 3);
                if (my >= 144 && my <= 232) {
                    int idx = col;
                    if (m_categorySelectedIndex == idx) onButtonPress(0 /* A */);
                    else m_categorySelectedIndex = idx;
                } else if (my >= 272 && my <= 650) {
                    int row = (my - 272) / 98;
                    int idx = 4 + row * 4 + col;
                    if (idx >= 4 && idx < 18) {
                        if (m_categorySelectedIndex == idx) onButtonPress(0 /* A */);
                        else m_categorySelectedIndex = idx;
                    }
                }
            }"""

new_touch = """            // Catalog Categories View: 2 Wide Cards click (Весь каталог / Избранное)
            else if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::Categories && mx >= 60 && mx <= 1220 && my >= 165 && my <= 625) {
                int clickedCard = (mx < 640) ? 0 : 1;
                if (m_categorySelectedIndex == clickedCard) {
                    onButtonPress(0 /* A - Open selected */);
                } else {
                    m_categorySelectedIndex = clickedCard;
                }
            }"""

if old_touch in code:
    code = code.replace(old_touch, new_touch, 1)
    print("[+] Updated touch zone for 2 wide cards")
else:
    print("[!] old_touch not found, check lines")

# 4. Update renderTabHome Sub-card 2
idx_sc2 = code.find("// Sub-card 2: Main Collections & Quick Action")
idx_sc2_end = code.find("void App::renderTabMyGames() {")
if idx_sc2 != -1 and idx_sc2_end != -1:
    old_sc2_block = code[idx_sc2:idx_sc2_end]
    new_sc2_block = """// Sub-card 2: Main Collections & Quick Action (560px wide, highlighted)
    drawGlassCard(sc2X, subY, cardW, subH, true, true);
    drawText("РАЗДЕЛЫ КАТАЛОГА", sc2X + 22, subY + 18, Theme::COLOR_TEXT_MUTED, 12);
    drawTextRight("4IFIR Engine", sc2X + cardW - 22, subY + 18, Theme::COLOR_FOCUS_CYAN, 12);

    // 3 4IFIR Cyber-Glass pills: Весь каталог, Избранное, Поиск
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
    code = code[:idx_sc2] + new_sc2_block + code[idx_sc2_end:]
    print("[+] Updated renderTabHome Sub-card 2")

with open(app_cpp_path, "w", encoding="utf-8") as f:
    f.write(code)

print("\nAll v1.4.2 changes applied successfully!")
