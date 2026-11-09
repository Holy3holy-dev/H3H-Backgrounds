import os

app_cpp_path = "e:/videofon/downloader/src/ui/app.cpp"
with open(app_cpp_path, "r", encoding="utf-8") as f:
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
    print("[+] Added loadTabIcons and freeTabIcons")

# 2. Call loadTabIcons() in init()
if "loadTabIcons();" not in code:
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
    assert old_init in code, "old_init not found"
    code = code.replace(old_init, new_init, 1)
    print("[+] Added loadTabIcons() call in init()")

# 3. Call freeTabIcons() in shutdown()
if "freeTabIcons();" not in code:
    old_shut = """#ifdef HAS_SDL2
    if (m_collectionThumbTexture) {"""
    new_shut = """#ifdef HAS_SDL2
    freeTabIcons();
    if (m_collectionThumbTexture) {"""
    assert old_shut in code, "old_shut not found"
    code = code.replace(old_shut, new_shut, 1)
    print("[+] Added freeTabIcons() call in shutdown()")

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
    print("[+] Added 60 FPS animations in update()")

# 5. Add button click bounce trigger to onButtonPress()
if "m_buttonPressAnim = 1.0f;" not in code:
    old_btn = "void App::onButtonPress(int button) {\n"
    new_btn = "void App::onButtonPress(int button) {\n    m_buttonPressAnim = 1.0f;\n"
    assert old_btn in code, "old_btn not found"
    code = code.replace(old_btn, new_btn, 1)
    print("[+] Added buttonPressAnim trigger in onButtonPress()")

# 6. Animated equalizer in renderHeader()
if "Triple animated equalizer accent bars" not in code:
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
    assert old_eq in code, "old_eq not found"
    code = code.replace(old_eq, new_eq, 1)
    print("[+] Added animated equalizer in renderHeader()")

# 7. drawDashboardTile with smooth scaling and neon breathing glow
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

if "drawW = static_cast<int>(w * scale);" not in code:
    assert old_dash in code, "old_dash not found"
    code = code.replace(old_dash, new_dash, 1)
    print("[+] Added scale animation & neon glow in drawDashboardTile()")

# 8. drawTileIconVector texture rendering with size 94/86
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

if "m_tabIconTextures[tileIdx]" not in code:
    assert old_tile_vec in code, "old_tile_vec not found"
    code = code.replace(old_tile_vec, new_tile_vec, 1)
    print("[+] Added high-res AI icon texture rendering to drawTileIconVector()")

# 9. Sub-card 2 on Home dashboard
old_home_sc2_start = code.find("// Sub-card 2: Main Collections & Quick Action")
idx_mygames_start = code.find("void App::renderTabMyGames() {")
if old_home_sc2_start != -1 and idx_mygames_start != -1:
    new_home_sc2 = """// Sub-card 2: Main Collections & Quick Action (560px wide, highlighted)
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
    code = code[:old_home_sc2_start] + new_home_sc2 + code[idx_mygames_start:]
    print("[+] Updated Home tab Sub-card 2")

with open(app_cpp_path, "w", encoding="utf-8") as f:
    f.write(code)

print("\nSUCCESS! apply_all_final.py applied cleanly!")
