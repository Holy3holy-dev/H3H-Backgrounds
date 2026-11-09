import os

app_cpp_path = "e:/videofon/downloader/src/ui/app.cpp"
with open(app_cpp_path, "r", encoding="utf-8") as f:
    code = f.read().replace("\r\n", "\n")

# 1. Add loadTabIcons and freeTabIcons implementations
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

# Place tab_icon_funcs right before App::~App()
idx_dtor = code.find("App::~App()")
assert idx_dtor != -1, "App::~App() not found"
code = code[:idx_dtor] + tab_icon_funcs + "\n" + code[idx_dtor:]

# Call loadTabIcons() in init() after SDL_CreateRenderer
old_init_renderer = """    m_renderer = SDL_CreateRenderer(
        m_window,
        -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
    );

    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }"""

new_init_renderer = """    m_renderer = SDL_CreateRenderer(
        m_window,
        -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
    );
    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }

    loadTabIcons();"""

assert old_init_renderer in code, "old_init_renderer not found"
code = code.replace(old_init_renderer, new_init_renderer, 1)

# Call freeTabIcons() in shutdown()
old_shutdown = """#ifdef HAS_SDL2
    if (m_collectionThumbTexture) {"""

new_shutdown = """#ifdef HAS_SDL2
    freeTabIcons();
    if (m_collectionThumbTexture) {"""

assert old_shutdown in code, "old_shutdown not found"
code = code.replace(old_shutdown, new_shutdown, 1)

# 2. Add animation updates to App::update()
old_update_head = """void App::update() {
#ifdef HAS_SDL2"""

new_update_head = """void App::update() {
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

assert old_update_head in code, "old_update_head not found"
code = code.replace(old_update_head, new_update_head, 1)

# 3. Trigger m_buttonPressAnim and m_tabTransitionAlpha on button press
old_btn_press = """void App::onButtonPress(int button) {
    // If fullscreen preview is active, direct buttons to preview controls
    if (m_isFullscreenPreview) {"""

new_btn_press = """void App::onButtonPress(int button) {
    m_buttonPressAnim = 1.0f;

    // If fullscreen preview is active, direct buttons to preview controls
    if (m_isFullscreenPreview) {"""

assert old_btn_press in code, "old_btn_press not found"
code = code.replace(old_btn_press, new_btn_press, 1)

# 4. Animated Equalizer bars in renderHeader()
old_header_eq = """    // Left Branding: App Name + Tag Badge
    // Triple accent bars (TorrentShopNX style logo)
    drawRoundedRect(30, 24, 4, 18, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(38, 20, 4, 26, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(46, 25, 4, 16, 2, Theme::COLOR_FOCUS_CYAN);"""

new_header_eq = """    // Left Branding: App Name + Tag Badge
    // Triple animated equalizer accent bars (Cyber Audio Visualizer)
    int h0 = static_cast<int>(m_equalizerHeights[0]);
    int h1 = static_cast<int>(m_equalizerHeights[1]);
    int h2 = static_cast<int>(m_equalizerHeights[2]);
    drawRoundedRect(30, 42 - h0, 4, h0, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(38, 44 - h1, 4, h1, 2, Theme::COLOR_FOCUS_CYAN);
    drawRoundedRect(46, 42 - h2, 4, h2, 2, Theme::COLOR_FOCUS_CYAN);"""

assert old_header_eq in code, "old_header_eq not found"
code = code.replace(old_header_eq, new_header_eq, 1)

# 5. drawDashboardTile with smooth scale and pulsing neon glow
old_dash_tile = """void App::drawDashboardTile(int x, int y, int w, int h, int tileIdx, const std::string& title, const std::string& sub, bool isFocused) {
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

new_dash_tile = """void App::drawDashboardTile(int x, int y, int w, int h, int tileIdx, const std::string& title, const std::string& sub, bool isFocused) {
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
    int iconCy = drawY + 72;
    drawTileIconVector(iconCx, iconCy, tileIdx, isFocused);

    // Centered Title underneath (measured pixel width, never overflows or shifts!)
    drawTextCentered(title, drawX + drawW / 2, drawY + drawH - 36, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
#else
    (void)x; (void)y; (void)w; (void)h; (void)tileIdx; (void)title; (void)sub; (void)isFocused;
#endif
}"""

assert old_dash_tile in code, "old_dash_tile not found"
code = code.replace(old_dash_tile, new_dash_tile, 1)

# 6. drawTileIconVector with texture rendering + 60fps animations
old_tile_vector = """void App::drawTileIconVector(int cx, int cy, int tileIdx, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color accent = isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY;

    if (tileIdx == 0) { // Каталог: 4IFIR Cartridge + Storefront (Cyan & Magenta)
        drawRoundedRect(cx - 38, cy - 24, 26, 40, 4, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 38, cy - 24, 26, 40, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawRoundedRect(cx - 36, cy - 22, 22, 8, 2, Theme::COLOR_FOCUS_PINK);
        drawRoundedRect(cx - 36, cy - 11, 22, 22, 2, {0x0B, 0x10, 0x1B, 0xFF});

        drawRoundedRect(cx - 6, cy - 14, 44, 32, 4, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 6, cy - 14, 44, 32, 4, accent, accent, 1);
        drawRoundedRect(cx - 8, cy - 21, 48, 8, 3, Theme::COLOR_FOCUS_CYAN);
        for (int s = 0; s < 4; ++s) {
            drawRoundedRect(cx - 6 + s * 12, cy - 21, 6, 8, 2, Theme::COLOR_FOCUS_PINK);
        }
        drawRoundedRect(cx + 2, cy - 3, 12, 20, 2, {0x00, 0xD2, 0xFF, 0x55});
        drawRoundedRect(cx + 20, cy - 3, 14, 14, 2, {0xEC, 0x48, 0x99, 0x66});
    } else if (tileIdx == 1) { // Видеоиконки: 4IFIR 1:1 Animated Square Frame
        drawRoundedRect(cx - 34, cy - 32, 68, 64, 14, {0x11, 0x18, 0x27, 0xFF});
        drawNeonRoundedOutline(cx - 34, cy - 32, 68, 64, 14, 2);
        // Play triangle in Electric Cyan
        for (int row = -10; row <= 10; ++row) {
            int w = 15 - std::abs(row);
            drawRect(cx - 5, cy - 4 + row, w, 1, Theme::COLOR_FOCUS_CYAN);
        }
        drawRoundedRect(cx - 26, cy + 12, 52, 14, 4, Theme::COLOR_FOCUS_PINK);
        drawTextCentered("256x256", cx, cy + 13, Theme::COLOR_TEXT_PRIMARY, 9);
    } else if (tileIdx == 2) { // Менеджер игр: 4IFIR Case labeled "MY GAMES"
        drawRoundedRect(cx - 34, cy - 16, 68, 44, 8, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 34, cy - 16, 68, 44, 8, accent, accent, 1);
        drawRoundedRect(cx - 24, cy - 27, 20, 14, 3, Theme::COLOR_FOCUS_PINK);
        drawRoundedRect(cx - 2, cy - 29, 20, 16, 3, Theme::COLOR_FOCUS_CYAN);
        drawRoundedRect(cx + 12, cy - 26, 16, 13, 3, {0xA8, 0x55, 0xF7, 0xFF});
        drawRoundedRect(cx - 34, cy + 5, 68, 16, 4, {0x09, 0x0D, 0x16, 0xEE});
        drawRoundedOutline(cx - 34, cy + 5, 68, 16, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered("MY GAMES", cx, cy + 7, Theme::COLOR_FOCUS_CYAN, 10);
    } else if (tileIdx == 3) { // Загрузки: 4IFIR Switch Console (Cyan & Magenta Joy-Cons)
        drawRoundedRect(cx - 40, cy - 15, 12, 40, 5, Theme::COLOR_FOCUS_CYAN);
        drawCircle(cx - 34, cy - 5, 3, {0x09, 0x0D, 0x16, 0xFF}, true);
        drawRoundedRect(cx - 26, cy - 17, 52, 44, 4, {0x0B, 0x10, 0x1B, 0xFF});
        drawRoundedOutline(cx - 26, cy - 17, 52, 44, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawRoundedRect(cx + 28, cy - 15, 12, 40, 5, Theme::COLOR_FOCUS_PINK);
        drawCircle(cx + 34, cy + 7, 3, {0x09, 0x0D, 0x16, 0xFF}, true);

        // Download Arrow pointing into screen
        drawRect(cx - 4, cy - 29, 8, 22, Theme::COLOR_FOCUS_CYAN);
        for (int row = 0; row < 10; ++row) {
            drawRect(cx - row, cy - 7 + row, 2 * row + 1, 1, Theme::COLOR_FOCUS_CYAN);
        }
    } else if (tileIdx == 4) { // Настройки: Cyber Cogwheel Gear (Screenshot 1)
        int rOut = 26;
        int rIn = 12;
        // Gear teeth (8 teeth)
        for (int i = 0; i < 8; ++i) {
            double angle = i * (3.14159265 / 4.0);
            int tx = cx + static_cast<int>(std::cos(angle) * 22);
            int ty = cy + static_cast<int>(std::sin(angle) * 22);
            drawRoundedRect(tx - 4, ty - 4, 8, 8, 2, accent);
        }
        // Central hub
        drawCircle(cx, cy, rOut, {0x26, 0x30, 0x44, 0xFF}, true);
        drawCircle(cx, cy, rOut, accent, false);
        drawCircle(cx, cy, rIn, {0x11, 0x18, 0x27, 0xFF}, true);
        drawCircle(cx, cy, 5, Theme::COLOR_FOCUS_CYAN, true);
    }
#endif
}"""

new_tile_vector = """void App::drawTileIconVector(int cx, int cy, int tileIdx, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color accent = isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY;

    // 1. If high-res pre-rendered 4IFIR Cyber-Glass icon texture is loaded, render it!
    if (tileIdx >= 0 && tileIdx < 5 && m_tabIconTextures[tileIdx]) {
        int iconSize = isFocused ? 76 : 70;
        SDL_Rect dst{cx - iconSize / 2, cy - iconSize / 2 - 2, iconSize, iconSize};
        SDL_RenderCopy(m_renderer, m_tabIconTextures[tileIdx], nullptr, &dst);

        // 60 FPS live animated accents over textures
        if (tileIdx == 4) {
            // Rotating glowing cyan core
            drawCircle(cx, cy - 2, 7, Theme::COLOR_FOCUS_CYAN, true);
            drawCircle(cx, cy - 2, 9, Theme::COLOR_FOCUS_PINK, false);
        } else if (tileIdx == 3) {
            // Bouncing download arrow accent
            int bob = static_cast<int>(m_downloadArrowBob);
            drawRect(cx - 3, cy - 24 + bob, 6, 12, Theme::COLOR_FOCUS_CYAN);
            for (int r = 0; r < 5; ++r) {
                drawRect(cx - r, cy - 12 + bob + r, 2 * r + 1, 1, Theme::COLOR_FOCUS_CYAN);
            }
        } else if (tileIdx == 1) {
            // Pulsing play triangle accent
            int triSize = static_cast<int>(8 + 2 * m_glowPulse);
            for (int r = -triSize; r <= triSize; ++r) {
                int w = (triSize - std::abs(r));
                drawRect(cx - 4, cy - 4 + r, w, 1, Theme::COLOR_FOCUS_CYAN);
            }
        }
        return;
    }

    // 2. High-precision vector fallback with live 60 FPS animations
    if (tileIdx == 0) { // Каталог: 4IFIR Cartridge + Storefront
        int bob = static_cast<int>(m_downloadArrowBob * 0.4f);
        drawRoundedRect(cx - 38, cy - 24 + bob, 26, 40, 4, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 38, cy - 24 + bob, 26, 40, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawRoundedRect(cx - 36, cy - 22 + bob, 22, 8, 2, Theme::COLOR_FOCUS_PINK);
        drawRoundedRect(cx - 36, cy - 11 + bob, 22, 22, 2, {0x0B, 0x10, 0x1B, 0xFF});

        drawRoundedRect(cx - 6, cy - 14, 44, 32, 4, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 6, cy - 14, 44, 32, 4, accent, accent, 1);
        drawRoundedRect(cx - 8, cy - 21, 48, 8, 3, Theme::COLOR_FOCUS_CYAN);
        for (int s = 0; s < 4; ++s) {
            drawRoundedRect(cx - 6 + s * 12, cy - 21, 6, 8, 2, Theme::COLOR_FOCUS_PINK);
        }
        drawRoundedRect(cx + 2, cy - 3, 12, 20, 2, {0x00, 0xD2, 0xFF, 0x55});
        drawRoundedRect(cx + 20, cy - 3, 14, 14, 2, {0xEC, 0x48, 0x99, 0x66});
    } else if (tileIdx == 1) { // Видеоиконки: 4IFIR 1:1 Animated Square Frame
        drawRoundedRect(cx - 34, cy - 32, 68, 64, 14, {0x11, 0x18, 0x27, 0xFF});
        drawNeonRoundedOutline(cx - 34, cy - 32, 68, 64, 14, 2);
        // Play triangle pulsing with m_glowPulse
        int triR = static_cast<int>(10 + 2 * (m_glowPulse - 0.8f));
        for (int row = -triR; row <= triR; ++row) {
            int w = (triR + 4) - std::abs(row);
            drawRect(cx - 5, cy - 4 + row, w, 1, Theme::COLOR_FOCUS_CYAN);
        }
        drawRoundedRect(cx - 26, cy + 12, 52, 14, 4, Theme::COLOR_FOCUS_PINK);
        drawTextCentered("256x256", cx, cy + 13, Theme::COLOR_TEXT_PRIMARY, 9);
    } else if (tileIdx == 2) { // Менеджер игр: 4IFIR Case labeled "MY GAMES"
        drawRoundedRect(cx - 34, cy - 16, 68, 44, 8, {0x13, 0x1B, 0x2E, 0xFF});
        drawRoundedOutline(cx - 34, cy - 16, 68, 44, 8, accent, accent, 1);
        drawRoundedRect(cx - 24, cy - 27, 20, 14, 3, Theme::COLOR_FOCUS_PINK);
        drawRoundedRect(cx - 2, cy - 29, 20, 16, 3, Theme::COLOR_FOCUS_CYAN);
        drawRoundedRect(cx + 12, cy - 26, 16, 13, 3, {0xA8, 0x55, 0xF7, 0xFF});
        drawRoundedRect(cx - 34, cy + 5, 68, 16, 4, {0x09, 0x0D, 0x16, 0xEE});
        drawRoundedOutline(cx - 34, cy + 5, 68, 16, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawTextCentered("MY GAMES", cx, cy + 7, Theme::COLOR_FOCUS_CYAN, 10);
    } else if (tileIdx == 3) { // Загрузки: Switch Console + Bouncing Download Arrow
        drawRoundedRect(cx - 40, cy - 15, 12, 40, 5, Theme::COLOR_FOCUS_CYAN);
        drawCircle(cx - 34, cy - 5, 3, {0x09, 0x0D, 0x16, 0xFF}, true);
        drawRoundedRect(cx - 26, cy - 17, 52, 44, 4, {0x0B, 0x10, 0x1B, 0xFF});
        drawRoundedOutline(cx - 26, cy - 17, 52, 44, 4, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
        drawRoundedRect(cx + 28, cy - 15, 12, 40, 5, Theme::COLOR_FOCUS_PINK);
        drawCircle(cx + 34, cy + 7, 3, {0x09, 0x0D, 0x16, 0xFF}, true);

        // Download Arrow bouncing dynamically into screen
        int bob = static_cast<int>(m_downloadArrowBob);
        drawRect(cx - 4, cy - 29 + bob, 8, 22, Theme::COLOR_FOCUS_CYAN);
        for (int row = 0; row < 10; ++row) {
            drawRect(cx - row, cy - 7 + bob + row, 2 * row + 1, 1, Theme::COLOR_FOCUS_CYAN);
        }
    } else if (tileIdx == 4) { // Настройки: Rotating Cyber Cogwheel Gear!
        int rOut = 26;
        int rIn = 12;
        // Gear teeth rotating continuously at m_gearAngle
        for (int i = 0; i < 8; ++i) {
            double angle = i * (3.14159265 / 4.0) + m_gearAngle;
            int tx = cx + static_cast<int>(std::cos(angle) * 22);
            int ty = cy + static_cast<int>(std::sin(angle) * 22);
            drawRoundedRect(tx - 4, ty - 4, 8, 8, 2, accent);
        }
        // Central hub
        drawCircle(cx, cy, rOut, {0x26, 0x30, 0x44, 0xFF}, true);
        drawCircle(cx, cy, rOut, accent, false);
        drawCircle(cx, cy, rIn, {0x11, 0x18, 0x27, 0xFF}, true);
        drawCircle(cx, cy, 6, Theme::COLOR_FOCUS_CYAN, true);
    }
#endif
}"""

assert old_tile_vector in code, "old_tile_vector not found"
code = code.replace(old_tile_vector, new_tile_vector, 1)

# 7. Simplified 2-Card renderCategoriesView()
idx_cat_start = code.find("void App::renderCategoriesView() {")
idx_cat_end = code.find("void App::renderTabVideoIcons() {")
assert idx_cat_start != -1 and idx_cat_end != -1, "renderCategoriesView boundaries not found"

new_categories_view = """void App::renderCategoriesView() {
    // Top Row: Title + Toggle ([X] Весь список) + Interactive Search Bar
    drawText("Каталог видеофонов", 60, 78, Theme::COLOR_TEXT_PRIMARY, 24);

    // Toggle to Full List button (x=340, y=74, w=185, h=38)
    drawPillButton(340, 74, 185, 38, "[X] Весь список", false, Theme::COLOR_FOCUS_CYAN);

    // Search Bar at top-right (x=700, y=74, w=512, h=38)
    bool hasCatSearch = !m_catalogSearchQuery.empty();
    drawGlassCard(700, 74, 512, 38, hasCatSearch, false);
    drawSearchIcon(718, 93, hasCatSearch ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED);
    std::string catSearchLabel = hasCatSearch
        ? ("Поиск: " + m_catalogSearchQuery)
        : "Поиск по названию игры или TitleID...";
    drawText(catSearchLabel, 734, 84, hasCatSearch ? Theme::COLOR_TEXT_PRIMARY : Theme::COLOR_TEXT_MUTED, 13, 370);
    drawRoundedRect(1118, 80, 84, 26, 6, Theme::COLOR_FOCUS_FILL);
    drawRoundedOutline(1118, 80, 84, 26, 6, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered("[Y] Поиск", 1160, 85, Theme::COLOR_FOCUS_CYAN, 11);

    // Section Header: РАЗДЕЛЫ КАТАЛОГА
    drawRoundedRect(60, 132, 4, 18, 2, Theme::COLOR_FOCUS_CYAN);
    drawText("РАЗДЕЛЫ КАТАЛОГА", 74, 131, Theme::COLOR_FOCUS_CYAN, 14);

    size_t totalCatGames = m_catalogManager.getGamesCount();
    size_t totalFavorites = m_favoriteKeys.size();

    // Two Wide, Elegant 4IFIR Cyber-Glass Cards
    int cardW = 570;
    int cardH = 460;
    int startY = 165;
    int gapX = 20;
    int c1X = 60;
    int c2X = c1X + cardW + gapX;

    // Card 1: ВЕСЬ КАТАЛОГ
    bool f1 = (m_categorySelectedIndex == 0);
    drawRoundedRect(c1X, startY, cardW, cardH, 20, f1 ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_SURFACE);
    if (f1) {
        drawRoundedRect(c1X, startY, cardW, cardH, 20, Theme::COLOR_FOCUS_FILL);
        uint8_t alpha = static_cast<uint8_t>(std::clamp(m_glowPulse * 255.0f, 160.0f, 255.0f));
        Color cGlow = Theme::COLOR_FOCUS_CYAN; cGlow.a = alpha;
        Color pGlow = Theme::COLOR_FOCUS_PINK; pGlow.a = alpha;
        drawRoundedOutline(c1X, startY, cardW, cardH, 20, cGlow, pGlow, 3);
    } else {
        drawRoundedOutline(c1X, startY, cardW, cardH, 20, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }

    // Card 1 Icon & Title
    int emCx = c1X + 70;
    int emCy = startY + 70;
    drawRoundedRect(emCx - 36, emCy - 36, 72, 72, 16, {0x14, 0x1A, 0x28, 0xFF});
    drawRoundedOutline(emCx - 36, emCy - 36, 72, 72, 16, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawCategoryEmblem(emCx, emCy, "all_catalog", Theme::COLOR_FOCUS_CYAN);

    drawText("Весь каталог", c1X + 130, startY + 45, f1 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 22);
    drawText("Полная коллекция видеофонов и иконок", c1X + 130, startY + 78, Theme::COLOR_TEXT_MUTED, 13);

    // Pill: Games count
    std::string count1Str = std::to_string(totalCatGames) + " игр в базе";
    int p1W = measureTextWidth(count1Str, 12) + 24;
    drawRoundedRect(c1X + 45, startY + 140, p1W, 28, 8, Theme::COLOR_FOCUS_FILL);
    drawRoundedOutline(c1X + 45, startY + 140, p1W, 28, 8, Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_CYAN, 1);
    drawTextCentered(count1Str, c1X + 45 + p1W / 2, startY + 146, Theme::COLOR_FOCUS_CYAN, 12);

    // Description
    drawText("• Более 2100 анимированных видеофонов 60 FPS", c1X + 45, startY + 200, Theme::COLOR_TEXT_PRIMARY, 14);
    drawText("• 433 квадратные видеоиконки 256x256 HEVC", c1X + 45, startY + 235, Theme::COLOR_TEXT_PRIMARY, 14);
    drawText("• Полноэкранный живой видеоплеер со звуком", c1X + 45, startY + 270, Theme::COLOR_TEXT_PRIMARY, 14);
    drawText("• Пакетная установка видеофонов в один клик", c1X + 45, startY + 305, Theme::COLOR_TEXT_MUTED, 13);

    // Action button at bottom of card
    int btn1W = cardW - 90;
    drawRoundedRect(c1X + 45, startY + cardH - 65, btn1W, 44, 12, f1 ? Theme::COLOR_FOCUS_FILL : Color{0x18, 0x22, 0x34, 0xEE});
    drawRoundedOutline(c1X + 45, startY + cardH - 65, btn1W, 44, 12, f1 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, f1 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, f1 ? 2 : 1);
    drawTextCentered(f1 ? "[A] Открыть весь каталог" : "Открыть весь каталог", c1X + 45 + btn1W / 2, startY + cardH - 52, f1 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);


    // Card 2: ИЗБРАННОЕ
    bool f2 = (m_categorySelectedIndex == 1);
    drawRoundedRect(c2X, startY, cardW, cardH, 20, f2 ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_SURFACE);
    if (f2) {
        drawRoundedRect(c2X, startY, cardW, cardH, 20, Theme::COLOR_FOCUS_FILL);
        uint8_t alpha = static_cast<uint8_t>(std::clamp(m_glowPulse * 255.0f, 160.0f, 255.0f));
        Color cGlow = Theme::COLOR_FOCUS_PINK; cGlow.a = alpha;
        Color pGlow = Theme::COLOR_FOCUS_CYAN; pGlow.a = alpha;
        drawRoundedOutline(c2X, startY, cardW, cardH, 20, cGlow, pGlow, 3);
    } else {
        drawRoundedOutline(c2X, startY, cardW, cardH, 20, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }

    // Card 2 Icon & Title
    int em2Cx = c2X + 70;
    int em2Cy = startY + 70;
    drawRoundedRect(em2Cx - 36, em2Cy - 36, 72, 72, 16, {0x14, 0x1A, 0x28, 0xFF});
    drawRoundedOutline(em2Cx - 36, em2Cy - 36, 72, 72, 16, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
    drawCategoryEmblem(em2Cx, em2Cy, "favorites", Theme::COLOR_FOCUS_PINK);

    drawText("Избранное", c2X + 130, startY + 45, f2 ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_PRIMARY, 22);
    drawText("Ваши сохранённые видеофоны и темы", c2X + 130, startY + 78, Theme::COLOR_TEXT_MUTED, 13);

    // Pill: Favorites count
    std::string count2Str = std::to_string(totalFavorites) + " игр в избранном";
    int p2W = measureTextWidth(count2Str, 12) + 24;
    drawRoundedRect(c2X + 45, startY + 140, p2W, 28, 8, Color{0xEC, 0x48, 0x99, 0x24});
    drawRoundedOutline(c2X + 45, startY + 140, p2W, 28, 8, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 1);
    drawTextCentered(count2Str, c2X + 45 + p2W / 2, startY + 146, Theme::COLOR_FOCUS_PINK, 12);

    // Description
    drawText("• Быстрый доступ к выбранным темам оформления", c2X + 45, startY + 200, Theme::COLOR_TEXT_PRIMARY, 14);
    drawText("• Добавление в избранное клавишей [R3] или [L]", c2X + 45, startY + 235, Theme::COLOR_TEXT_PRIMARY, 14);
    drawText("• Сохранение персонального набора фонов на SD-карте", c2X + 45, startY + 270, Theme::COLOR_TEXT_PRIMARY, 14);
    drawText("• Мгновенное переключение тем без повторного поиска", c2X + 45, startY + 305, Theme::COLOR_TEXT_MUTED, 13);

    // Action button at bottom of card
    drawRoundedRect(c2X + 45, startY + cardH - 65, btn1W, 44, 12, f2 ? Color{0xEC, 0x48, 0x99, 0x33} : Color{0x18, 0x22, 0x34, 0xEE});
    drawRoundedOutline(c2X + 45, startY + cardH - 65, btn1W, 44, 12, f2 ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_BORDER, f2 ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_BORDER, f2 ? 2 : 1);
    drawTextCentered(f2 ? "[A] Открыть избранное" : "Открыть избранное", c2X + 45 + btn1W / 2, startY + cardH - 52, f2 ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_PRIMARY, 15);
}
"""

code = code[:idx_cat_start] + new_categories_view + code[idx_cat_end:]

# 8. Update renderTabCatalog in GameGrid mode with top tabs [L] Весь каталог and [R] Избранное
old_grid_head = """    // Breadcrumb Header
    std::string navTitle = "Каталог  >  " + m_activeCategoryName;
    drawText(navTitle, 60, 95, Theme::COLOR_TEXT_PRIMARY, 22);

    // Back to Categories Pill Button
    drawPillButton(1040, 90, 185, 34, "(B) К разделам", false, Theme::COLOR_FOCUS_CYAN);

    // Search and Sort Pills
    std::string sortStr = "[X] Сорт: ";
    switch (m_catalogSortMode) {
        case CatalogSortMode::Alphabetical: sortStr += "А-Я"; break;
        case CatalogSortMode::VariantsCount: sortStr += "Варианты"; break;
        case CatalogSortMode::AudioOnly: sortStr += "Звук"; break;
        case CatalogSortMode::IconsOnly: sortStr += "Иконки"; break;
        case CatalogSortMode::InstalledOnly: sortStr += "Установленные"; break;
        case CatalogSortMode::FavoritesOnly: sortStr += "Избранное"; break;
        default: sortStr += "По умолчанию"; break;
    }
    drawPillButton(760, 90, 170, 34, sortStr, false, Theme::COLOR_TEXT_MUTED);

    std::string searchStr = m_catalogSearchQuery.empty() ? "[Y] Поиск" : ("[Y] " + m_catalogSearchQuery);
    drawPillButton(940, 90, 90, 34, searchStr, false, Theme::COLOR_TEXT_MUTED);"""

new_grid_head = """    // Top Tabs: [L] Весь каталог  |  [R] Избранное
    bool isFavTab = (m_catalogSortMode == CatalogSortMode::FavoritesOnly);
    size_t totalCatGames = m_catalogManager.getGamesCount();
    size_t totalFavorites = m_favoriteKeys.size();

    // Tab 1: Весь каталог
    std::string tab1Text = "[L] Весь каталог (" + std::to_string(totalCatGames) + ")";
    int t1W = measureTextWidth(tab1Text, 13) + 24;
    drawRoundedRect(60, 90, t1W, 36, 10, !isFavTab ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_PILL_BG);
    if (!isFavTab) {
        drawNeonRoundedOutline(60, 90, t1W, 36, 10, 2);
    } else {
        drawRoundedOutline(60, 90, t1W, 36, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }
    drawTextCentered(tab1Text, 60 + t1W / 2, 98, !isFavTab ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 13);

    // Tab 2: Избранное
    std::string tab2Text = "[R] Избранное (" + std::to_string(totalFavorites) + ")";
    int t2W = measureTextWidth(tab2Text, 13) + 24;
    int t2X = 60 + t1W + 12;
    drawRoundedRect(t2X, 90, t2W, 36, 10, isFavTab ? Color{0xEC, 0x48, 0x99, 0x24} : Theme::COLOR_PILL_BG);
    if (isFavTab) {
        drawRoundedOutline(t2X, 90, t2W, 36, 10, Theme::COLOR_FOCUS_PINK, Theme::COLOR_FOCUS_PINK, 2);
    } else {
        drawRoundedOutline(t2X, 90, t2W, 36, 10, Theme::COLOR_BORDER, Theme::COLOR_BORDER, 1);
    }
    drawTextCentered(tab2Text, t2X + t2W / 2, 98, isFavTab ? Theme::COLOR_FOCUS_PINK : Theme::COLOR_TEXT_MUTED, 13);

    // Search and Back Buttons
    std::string searchStr = m_catalogSearchQuery.empty() ? "[Y] Поиск" : ("[Y] " + m_catalogSearchQuery);
    drawPillButton(840, 90, 160, 36, searchStr, false, Theme::COLOR_TEXT_PRIMARY);
    drawPillButton(1015, 90, 160, 36, "(B) К разделам", false, Theme::COLOR_FOCUS_CYAN);"""

assert old_grid_head in code, "old_grid_head not found"
code = code.replace(old_grid_head, new_grid_head, 1)

# 9. Update input handling for Categories view (only 2 options: 0 and 1)
old_cat_input = """        if (m_catalogViewMode == CatalogViewMode::Categories) {
            if (button == 1 /* B - Back to Home */) {
                m_activeTab = Tab::Home;
                return;
            }
            // Category navigation (18 total: 0..3 main, 4..17 genres)
            if (button == 13 /* DPAD_LEFT */) {
                if (m_categorySelectedIndex > 0) m_categorySelectedIndex--;
                return;
            }
            if (button == 14 /* DPAD_RIGHT */) {
                if (m_categorySelectedIndex < 17) m_categorySelectedIndex++;
                return;
            }
            if (button == 11 /* DPAD_UP */) {
                if (m_categorySelectedIndex >= 4) m_categorySelectedIndex -= 4;
                return;
            }
            if (button == 12 /* DPAD_DOWN */) {
                if (m_categorySelectedIndex + 4 <= 17) m_categorySelectedIndex += 4;
                return;
            }
            if (button == 0 /* A - Open category */) {
                struct GenreDef {
                    std::string title;
                };
                GenreDef genres[14] = {
                    {"Экшены и приключения"},
                    {"Аркады"},
                    {"Хорроры"},
                    {"Метроидвании"},
                    {"Вечеринки и кооп"},
                    {"Платформеры"},
                    {"Головоломки"},
                    {"Рогалики"},
                    {"RPG / JRPG"},
                    {"Шутеры"},
                    {"Симуляторы и уютные"},
                    {"Стратегии и тактика"},
                    {"Визуальные новеллы"},
                    {"Порты и Homebrew"}
                };

                if (m_categorySelectedIndex == 0) {
                    m_activeCategoryName = "Весь каталог";
                    m_catalogSortMode = CatalogSortMode::Default;
                } else if (m_categorySelectedIndex == 1) {
                    m_activeCategoryName = "Избранное";
                    m_catalogSortMode = CatalogSortMode::FavoritesOnly;
                } else if (m_categorySelectedIndex == 2) {
                    m_activeCategoryName = "Новые релизы";
                    m_catalogSortMode = CatalogSortMode::Default;
                } else if (m_categorySelectedIndex == 3) {
                    m_activeCategoryName = "Топ-100";
                    m_catalogSortMode = CatalogSortMode::VariantsCount;
                } else {
                    int gIdx = m_categorySelectedIndex - 4;
                    if (gIdx >= 0 && gIdx < 14) {
                        m_activeCategoryName = genres[gIdx].title;
                        m_catalogSortMode = CatalogSortMode::Default;
                    }
                }
                m_catalogViewMode = CatalogViewMode::GameGrid;
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                return;
            }
            if (button == 2 /* X - Toggle to Full List Directly */) {
                m_activeCategoryName = "Весь каталог (Списком)";
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
        }"""

new_cat_input = """        if (m_catalogViewMode == CatalogViewMode::Categories) {
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
        }"""

assert old_cat_input in code, "old_cat_input not found"
code = code.replace(old_cat_input, new_cat_input, 1)

# 10. In GameGrid mode, pressing L/R/Minus toggles between Весь каталог and Избранное
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

# 11. Update renderTabHome() sub-card 2 pills
old_home_sub2 = """    // 3 4IFIR Cyber-Glass pills with dynamically measured widths
    struct PillData {
        std::string label;
        Color borderCol;
        Color fillCol;
    };
    PillData pData[3] = {
        {"Эксклюзивы Switch (40)", Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_FILL},
        {"RPG и Экшены (45)", Theme::COLOR_FOCUS_PINK, Color{0xEC, 0x48, 0x99, 0x24}},
        {"Инди-хиты (27)", Theme::COLOR_FOCUS_CYAN, Theme::COLOR_FOCUS_FILL}
    };"""

new_home_sub2 = """    // 3 4IFIR Cyber-Glass pills with dynamically measured widths
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
    };"""

assert old_home_sub2 in code, "old_home_sub2 not found"
code = code.replace(old_home_sub2, new_home_sub2, 1)

with open(app_cpp_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Updated app.cpp with tab icons, animations, and simplified 2-tab catalog!")
