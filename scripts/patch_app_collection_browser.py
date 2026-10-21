import sys
from pathlib import Path

# 1. Patch config.hpp
cfg_path = Path("downloader/include/core/config.hpp")
cfg_text = cfg_path.read_text(encoding="utf-8")
assert "#endif" in cfg_text

cfg_target = """    static constexpr const char* DEFAULT_CATALOG_URL       = "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog.json";
#endif"""

cfg_repl = """    static constexpr const char* DEFAULT_CATALOG_URL       = "https://raw.githubusercontent.com/Holy3holy-dev/H3H-Backgrounds/main/catalog/data/catalog.json";
#endif

    static constexpr bool isAfterDark() {
#ifdef H3H_AFTER_DARK
        return true;
#else
        return false;
#endif
    }"""

assert cfg_target in cfg_text.replace("\r\n", "\n")
cfg_text = cfg_text.replace("\r\n", "\n").replace(cfg_target, cfg_repl)
cfg_path.write_text(cfg_text.replace("\n", "\r\n"), encoding="utf-8")
print("[+] config.hpp patched successfully")

# 2. Patch app.hpp
app_hpp_path = Path("downloader/include/ui/app.hpp")
app_hpp_text = app_hpp_path.read_text(encoding="utf-8").replace("\r\n", "\n")

target_funcs = """    // Target Game Picker (Assign background to any installed game)
    void openGamePicker(const Variant& variant, const std::string& sourceGameName);
    void closeGamePicker();
    void renderGamePicker();"""

repl_funcs = """    // Target Game Picker (Assign background to any installed game)
    void openGamePicker(const Variant& variant, const std::string& sourceGameName);
    void closeGamePicker();
    void renderGamePicker();

    // Collection / Variant Browser (Browse variants by name with static mini-previews)
    void openCollectionBrowser(const GameCatalogEntry& entry);
    void closeCollectionBrowser();
    void renderCollectionBrowser();
    void loadCollectionThumbnail(const Variant& variant);"""

assert target_funcs in app_hpp_text
app_hpp_text = app_hpp_text.replace(target_funcs, repl_funcs)

target_members = """    // Game Picker state (Assign background to any installed game)
    bool m_isGamePickerOpen{false};
    int m_gamePickerSelectedIndex{0};
    int m_gamePickerScrollOffset{0};
    uint32_t m_gamePickerOpenedAt{0};
    Variant m_gamePickerPendingVariant;
    std::string m_gamePickerSourceGameName;"""

repl_members = """    // Game Picker state (Assign background to any installed game)
    bool m_isGamePickerOpen{false};
    int m_gamePickerSelectedIndex{0};
    int m_gamePickerScrollOffset{0};
    uint32_t m_gamePickerOpenedAt{0};
    Variant m_gamePickerPendingVariant;
    std::string m_gamePickerSourceGameName;

    // Collection / Variant Browser state
    bool m_isCollectionBrowserOpen{false};
    GameCatalogEntry m_collectionEntry;
    std::string m_collectionTitleId;
    std::string m_collectionGameName;
    std::vector<Variant> m_collectionVariants;
    int m_collectionSelectedIndex{0};
    int m_collectionScrollOffset{0};
    uint32_t m_collectionOpenedAt{0};
    SDL_Texture* m_collectionThumbTexture{nullptr};
    std::string m_collectionCurrentThumbVariantId;
    std::string m_pendingCollectionThumbToLoad;
    std::atomic<bool> m_collectionThumbLoading{false};
    std::thread m_collectionThumbThread;
    std::atomic<bool> m_cancelCollectionThumb{false};
    std::mutex m_collectionThumbMutex;"""

assert target_members in app_hpp_text
app_hpp_text = app_hpp_text.replace(target_members, repl_members)
app_hpp_path.write_text(app_hpp_text.replace("\n", "\r\n"), encoding="utf-8")
print("[+] app.hpp patched successfully")

# 3. Patch app.cpp
app_cpp_path = Path("downloader/src/ui/app.cpp")
app_cpp_text = app_cpp_path.read_text(encoding="utf-8").replace("\r\n", "\n")

# A. Cleanup in shutdown()
target_shut = """    closeFullscreenPreview();"""
repl_shut = """    closeFullscreenPreview();
    closeCollectionBrowser();"""
assert target_shut in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_shut, repl_shut, 1)

# B. Texture loading in update()
target_update = """        if (!m_pendingVideoToOpen.empty()) {
            vidPath = m_pendingVideoToOpen;
            m_pendingVideoToOpen.clear();
        }
    }"""
repl_update = """        if (!m_pendingVideoToOpen.empty()) {
            vidPath = m_pendingVideoToOpen;
            m_pendingVideoToOpen.clear();
        }
    }
    std::string pendingCollThumb;
    {
        std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
        pendingCollThumb = m_pendingCollectionThumbToLoad;
        m_pendingCollectionThumbToLoad.clear();
    }
    if (!pendingCollThumb.empty() && m_renderer && m_isCollectionBrowserOpen) {
        SDL_Texture* newTex = loadTextureFromFile(m_renderer, pendingCollThumb);
        if (newTex) {
            if (m_collectionThumbTexture) SDL_DestroyTexture(m_collectionThumbTexture);
            m_collectionThumbTexture = newTex;
        }
    }"""
assert target_update in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_update, repl_update, 1)

# C. Pin After Dark collection at top of installed titles in refreshInstalledGames()
target_refresh = """void App::refreshInstalledGames() {
    m_platform->listInstalledTitles(m_installedGames);
    m_catalogManager.matchInstalledTitles(m_installedGames);"""

repl_refresh = """void App::refreshInstalledGames() {
    m_platform->listInstalledTitles(m_installedGames);
    m_catalogManager.matchInstalledTitles(m_installedGames);

    // In After Dark build, pin the After Dark Collection (0000000000000000) at top if present in catalog
    if (Config::isAfterDark()) {
        const auto* match = m_catalogManager.findByTitleId("0000000000000000");
        if (match && !match->variants.empty()) {
            bool found = false;
            for (const auto& ig : m_installedGames) {
                if (ig.titleId == "0000000000000000") { found = true; break; }
            }
            if (!found) {
                InstalledTitle collTitle;
                collTitle.titleId = "0000000000000000";
                collTitle.name = match->title;
                collTitle.author = match->publisher;
                collTitle.hasCatalogMatch = true;
                collTitle.catalogEntry = *match;
                collTitle.hasInstalledCover = false;
                m_installedGames.insert(m_installedGames.begin(), collTitle);
            }
        }
    }"""
assert target_refresh in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_refresh, repl_refresh, 1)

# D. onButtonPress input handling for Collection Browser
target_btn = """void App::onButtonPress(int button) {
    // Target Game Picker Handler (Assign video theme to any installed game)"""

repl_btn = """void App::onButtonPress(int button) {
    // Collection Browser Modal Handler (Browse variants by name with static mini-previews)
    if (m_isCollectionBrowserOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview && !m_isGamePickerOpen) {
        if (SDL_GetTicks() - m_collectionOpenedAt < 150) {
            return;
        }
        if (button == 1 /* B - Back to Catalog */) {
            closeCollectionBrowser();
            return;
        }
        int vCount = static_cast<int>(m_collectionVariants.size());
        if (button == 11 /* UP */) {
            if (m_collectionSelectedIndex > 0) {
                m_collectionSelectedIndex--;
                if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                    m_collectionScrollOffset = m_collectionSelectedIndex;
                }
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 12 /* DOWN */) {
            if (m_collectionSelectedIndex + 1 < vCount) {
                m_collectionSelectedIndex++;
                if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                    m_collectionScrollOffset = m_collectionSelectedIndex - 5 + 1;
                }
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_collectionSelectedIndex = std::max(0, m_collectionSelectedIndex - 5);
            if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                m_collectionScrollOffset = m_collectionSelectedIndex;
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            m_collectionSelectedIndex = std::min(vCount - 1, m_collectionSelectedIndex + 5);
            if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                m_collectionScrollOffset = std::max(0, m_collectionSelectedIndex - 5 + 1);
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 0 /* A */ || button == 3 /* Y - Assign to game */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                openGamePicker(m_collectionVariants[m_collectionSelectedIndex], m_collectionGameName);
            }
            return;
        }
        if (button == 2 /* X - Fullscreen live video */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                openFullscreenPreviewForCatalogGame(m_collectionEntry, m_collectionSelectedIndex);
            }
            return;
        }
        return;
    }

    // Target Game Picker Handler (Assign video theme to any installed game)"""
assert target_btn in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_btn, repl_btn, 1)

# E. MyGames tab navigation: pressing A on 0000000000000000 or games with > 8 variants opens collection browser
target_mygames_a = """            } else if (button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) {
                // Move focus to right variants column
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_myGamesActivePane = MyGamesPane::VariantsList;
                        m_selectedVariantIndex = 0;
                    }
                }"""

repl_mygames_a = """            } else if (button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) {
                // Move focus to right variants column or open collection browser
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                        openCollectionBrowser(g.catalogEntry);
                    } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_myGamesActivePane = MyGamesPane::VariantsList;
                        m_selectedVariantIndex = 0;
                    }
                }"""
assert target_mygames_a in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_mygames_a, repl_mygames_a, 1)

# F. Catalog tab input: pressing A opens collection browser, X opens fullscreen video
target_catalog_a = """        } else if (button == 2 /* X */ || button == 0 /* A */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = allGames[m_catalogSelectedIndex];
                openFullscreenPreviewForCatalogGame(entry, 0);
            }"""

repl_catalog_a = """        } else if (button == 0 /* A - Enter Collection Browser */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = allGames[m_catalogSelectedIndex];
                openCollectionBrowser(entry);
            }
        } else if (button == 2 /* X - Quick Video Preview */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = allGames[m_catalogSelectedIndex];
                openFullscreenPreviewForCatalogGame(entry, 0);
            }"""
assert target_catalog_a in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_catalog_a, repl_catalog_a, 1)

# G. renderTabCatalog button UI
target_cat_btn = """        // Action button on right
        if (isSelected) {
            drawRect(935, y + 22, 265, 36, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(935, y + 22, 265, 36, 1);
            drawText("[X / A] Смотреть видео", 975, y + 31, Theme::COLOR_FOCUS_CYAN, 13);
        } else {
            drawRect(975, y + 22, 225, 36, {0x16, 0x20, 0x32, 0x88});
            drawRectOutline(975, y + 22, 225, 36, Theme::COLOR_BORDER, 1);
            drawText("Смотреть видео", 1025, y + 31, Theme::COLOR_TEXT_MUTED, 13);
        }"""

repl_cat_btn = """        // Action button on right
        if (isSelected) {
            int vCount = static_cast<int>(g.variants.size());
            if (vCount > 1) {
                drawRect(915, y + 22, 285, 36, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(915, y + 22, 285, 36, 1);
                std::string btnLabel = "[A] Войти (" + std::to_string(vCount) + ")  [X] Видео";
                drawText(btnLabel, 930, y + 31, Theme::COLOR_FOCUS_CYAN, 13);
            } else {
                drawRect(935, y + 22, 265, 36, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(935, y + 22, 265, 36, 1);
                drawText("[A] Выбрать   [X] Видео", 955, y + 31, Theme::COLOR_FOCUS_CYAN, 13);
            }
        } else {
            drawRect(975, y + 22, 225, 36, {0x16, 0x20, 0x32, 0x88});
            drawRectOutline(975, y + 22, 225, 36, Theme::COLOR_BORDER, 1);
            int vCount = static_cast<int>(g.variants.size());
            std::string btnLabel = (vCount > 1) ? ("Коллекция (" + std::to_string(vCount) + ")") : "Смотреть видео";
            drawText(btnLabel, 1005, y + 31, Theme::COLOR_TEXT_MUTED, 13);
        }"""
assert target_cat_btn in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_cat_btn, repl_cat_btn, 1)

# H. render() calling renderCollectionBrowser
target_render = """    if (m_isRecordingsBrowserOpen) {
        renderRecordingsBrowser();
    }
    if (m_isGamePickerOpen) {
        renderGamePicker();
    }
    if (m_isGamePickerOpen) {
        renderGamePicker();
    }"""

repl_render = """    if (m_isRecordingsBrowserOpen) {
        renderRecordingsBrowser();
    }
    if (m_isCollectionBrowserOpen) {
        renderCollectionBrowser();
    }
    if (m_isGamePickerOpen) {
        renderGamePicker();
    }"""
assert target_render in app_cpp_text
app_cpp_text = app_cpp_text.replace(target_render, repl_render, 1)

# I. Append collection browser method implementations at the end of app.cpp
collection_methods = """
// ----------------- Collection / Variant Browser Implementation -----------------

void App::openCollectionBrowser(const GameCatalogEntry& entry) {
    if (entry.variants.empty()) return;
    m_collectionEntry = entry;
    m_collectionTitleId = entry.titleId;
    m_collectionGameName = entry.title;
    m_collectionVariants = entry.variants;
    m_collectionSelectedIndex = 0;
    m_collectionScrollOffset = 0;
    m_collectionOpenedAt = SDL_GetTicks();
    m_isCollectionBrowserOpen = true;
    loadCollectionThumbnail(m_collectionVariants[0]);
}

void App::closeCollectionBrowser() {
    m_isCollectionBrowserOpen = false;
    m_cancelCollectionThumb.store(true);
    if (m_collectionThumbThread.joinable()) {
        m_collectionThumbThread.join();
    }
    m_cancelCollectionThumb.store(false);
    if (m_collectionThumbTexture) {
        SDL_DestroyTexture(m_collectionThumbTexture);
        m_collectionThumbTexture = nullptr;
    }
    m_collectionCurrentThumbVariantId.clear();
    m_pendingCollectionThumbToLoad.clear();
    m_collectionVariants.clear();
}

void App::loadCollectionThumbnail(const Variant& variant) {
#ifdef HAS_SDL2
    m_cancelCollectionThumb.store(true);
    if (m_collectionThumbThread.joinable()) {
        m_collectionThumbThread.join();
    }
    m_cancelCollectionThumb.store(false);

    if (m_collectionThumbTexture) {
        SDL_DestroyTexture(m_collectionThumbTexture);
        m_collectionThumbTexture = nullptr;
    }
    m_collectionCurrentThumbVariantId = variant.id;

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string cacheKey = m_collectionTitleId + "_" + variant.id;
    std::string thumbFile = thumbDir + "/" + cacheKey + ".jpg";

    if (std::filesystem::exists(thumbFile, ec)) {
        m_collectionThumbTexture = loadTextureFromFile(m_renderer, thumbFile);
        m_collectionThumbLoading = false;
        return;
    }

    m_collectionThumbLoading = true;
    std::string thumbUrl = variant.previewUrl;
    if (thumbUrl.empty()) {
        thumbUrl = variant.url;
    }

    m_collectionThumbThread = std::thread([this, thumbUrl, thumbFile, key = variant.id]() {
        std::string err;
        std::error_code ec;
        std::filesystem::create_directories(std::filesystem::path(thumbFile).parent_path(), ec);
        bool ok = m_platform->downloadFile(thumbUrl, thumbFile, nullptr, m_cancelCollectionThumb, err);
        m_collectionThumbLoading = false;
        if (ok && !m_cancelCollectionThumb.load() && m_isCollectionBrowserOpen && m_collectionCurrentThumbVariantId == key) {
            std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
            m_pendingCollectionThumbToLoad = thumbFile;
        }
    });
#endif
}

void App::renderCollectionBrowser() {
#ifdef HAS_SDL2
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x02, 0x05, 0x0C, 0xFA});

    // 4IFIR Frosted Glass Modal Container
    int bw = 1220;
    int bh = 660;
    int bx = (Theme::SCREEN_WIDTH - bw) / 2;
    int by = (Theme::SCREEN_HEIGHT - bh) / 2;

    drawGlassCard(bx, by, bw, bh, false, true);
    drawNeonGradientOutline(bx, by, bw, bh, 2);

    // Header
    bool isAD = Config::isAfterDark();
    if (isAD) {
        drawRect(bx + 25, by + 18, 175, 26, {0xEC, 0x48, 0x99, 0x33});
        drawRectOutline(bx + 25, by + 18, 175, 26, Theme::COLOR_FOCUS_PINK, 1);
        drawText("🌸 AFTER DARK 18+", bx + 35, by + 24, Theme::COLOR_FOCUS_PINK, 12);
    } else {
        drawRect(bx + 25, by + 18, 160, 26, {0x00, 0xF0, 0xFF, 0x33});
        drawRectOutline(bx + 25, by + 18, 160, 26, Theme::COLOR_FOCUS_CYAN, 1);
        drawText("★ КОЛЛЕКЦИЯ 4IFIR", bx + 35, by + 24, Theme::COLOR_FOCUS_CYAN, 12);
    }

    drawText(m_collectionGameName, bx + 215, by + 17, Theme::COLOR_TEXT_PRIMARY, 21, 750);

    int totalV = static_cast<int>(m_collectionVariants.size());
    std::string countStr = std::to_string(m_collectionSelectedIndex + 1) + " / " + std::to_string(totalV);
    drawText(countStr, bx + bw - 140, by + 20, Theme::COLOR_FOCUS_CYAN, 16);

    // Divider line
    drawRect(bx + 25, by + 54, bw - 50, 1, Theme::COLOR_BORDER);

    // Left Column: Variants List (Width 640)
    int lx = bx + 25;
    int ly = by + 68;
    int lw = 635;
    int visibleCount = 5;

    if (m_collectionSelectedIndex < m_collectionScrollOffset) {
        m_collectionScrollOffset = m_collectionSelectedIndex;
    }
    if (m_collectionSelectedIndex >= m_collectionScrollOffset + visibleCount) {
        m_collectionScrollOffset = m_collectionSelectedIndex - visibleCount + 1;
    }

    if (m_collectionScrollOffset > 0) {
        drawText("▲ Еще фоны выше (◀ -5)", lx + 200, ly - 14, Theme::COLOR_FOCUS_CYAN, 12);
    }

    int cardY = ly;
    int cardH = 88;
    int cardGap = 8;
    int endIdx = std::min(totalV, m_collectionScrollOffset + visibleCount);

    for (int i = m_collectionScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_collectionSelectedIndex);
        const auto& v = m_collectionVariants[i];

        if (isSelected) {
            drawRect(lx, cardY, lw, cardH, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(lx, cardY, lw, cardH, 2);
        } else {
            drawRect(lx, cardY, lw, cardH, {0x13, 0x1A, 0x2A, 0x99});
            drawRectOutline(lx, cardY, lw, cardH, Theme::COLOR_BORDER, 1);
        }

        // Title line
        std::string titleStr = std::to_string(i + 1) + ". " + v.name;
        drawText(titleStr, lx + 16, cardY + 14, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, lw - 70);

        // Metadata badges
        int bxPos = lx + 16;

        // Style badge
        std::string styleStr = styleToString(v.style);
        drawRect(bxPos, cardY + 46, 110, 24, {0x28, 0x33, 0x47, 0x66});
        drawRectOutline(bxPos, cardY + 46, 110, 24, Theme::COLOR_BORDER, 1);
        drawText(styleStr, bxPos + 10, cardY + 51, Theme::COLOR_TEXT_MUTED, 11);
        bxPos += 120;

        // Audio badge
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
        }

        // Specs text
        double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
        char szBuf[32];
        if (mb >= 0.1) snprintf(szBuf, sizeof(szBuf), "%.1f MB", mb);
        else snprintf(szBuf, sizeof(szBuf), "~3.5 MB");

        std::string metaLine = std::to_string(v.width) + "x" + std::to_string(v.height) + " @" +
                               std::to_string((int)v.fps) + "fps  |  " + std::string(szBuf) +
                               (!v.codec.empty() ? ("  |  " + v.codec) : "");
        drawText(metaLine, bxPos, cardY + 51, Theme::COLOR_TEXT_MUTED, 12, lw - bxPos - 30);

        if (isSelected) {
            drawText("▶", lx + lw - 30, cardY + 33, Theme::COLOR_FOCUS_CYAN, 18);
        }

        cardY += cardH + cardGap;
    }

    if (endIdx < totalV) {
        std::string belowStr = "▼ Еще варианты ниже: " + std::to_string(totalV - endIdx) + " шт. (▶ +5)";
        drawText(belowStr, lx + 180, ly + (cardH + cardGap) * visibleCount + 2, Theme::COLOR_FOCUS_PINK, 12);
    }

    // Right Column: Static Mini-Preview Panel (Width 520)
    int rx = bx + 675;
    int ry = by + 68;
    int rw = 520;
    int rh = 530;

    drawGlassCard(rx, ry, rw, rh, false, false);

    // Static Preview Box (Exact 16:9 ratio: 480 x 270)
    int px = rx + 20;
    int py = ry + 20;
    int pw = 480;
    int ph = 270;

    drawRect(px, py, pw, ph, {0x08, 0x0D, 0x16, 0xFA});
    drawNeonGradientOutline(px, py, pw, ph, 2);

    if (m_collectionThumbTexture) {
        SDL_Rect dst{px + 2, py + 2, pw - 4, ph - 4};
        SDL_RenderCopy(m_renderer, m_collectionThumbTexture, nullptr, &dst);
    } else if (m_collectionThumbLoading) {
        drawText("⏳ Загрузка мини-превью...", px + 140, py + 125, Theme::COLOR_FOCUS_CYAN, 16);
    } else {
        drawText("📷 Статическое превью...", px + 145, py + 125, Theme::COLOR_TEXT_MUTED, 15);
    }

    // Details below preview
    if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
        m_collectionSelectedIndex < totalV) {
        const auto& selVar = m_collectionVariants[m_collectionSelectedIndex];

        drawText(selVar.name, px, py + ph + 18, Theme::COLOR_TEXT_PRIMARY, 17, pw);

        double mb = static_cast<double>(selVar.sizeBytes) / (1024.0 * 1024.0);
        char szBuf[32];
        if (mb >= 0.1) snprintf(szBuf, sizeof(szBuf), "%.1f MB", mb);
        else snprintf(szBuf, sizeof(szBuf), "~3.5 MB");

        std::string detailStr = styleToString(selVar.style) + "  •  " +
                                std::to_string(selVar.width) + "x" + std::to_string(selVar.height) +
                                " @" + std::to_string((int)selVar.fps) + "fps  •  " +
                                std::string(szBuf) + (!selVar.codec.empty() ? ("  •  " + selVar.codec) : "") +
                                (selVar.hasAudio ? "  •  Звук" : "  •  Без звука");
        drawText(detailStr, px, py + ph + 46, Theme::COLOR_TEXT_MUTED, 12, pw);

        // Buttons
        // [A] Assign to game button
        int b1w = 230;
        int b1h = 42;
        int b1x = px;
        int b1y = py + ph + 80;
        drawRect(b1x, b1y, b1w, b1h, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(b1x, b1y, b1w, b1h, 2);
        drawText("[A] Назначить на игру", b1x + 22, b1y + 12, Theme::COLOR_FOCUS_CYAN, 13);

        // [X] Fullscreen live video button
        int b2w = 230;
        int b2h = 42;
        int b2x = px + 250;
        int b2y = b1y;
        drawRect(b2x, b2y, b2w, b2h, {0x16, 0x20, 0x32, 0xDD});
        drawRectOutline(b2x, b2y, b2w, b2h, Theme::COLOR_BORDER, 1);
        drawText("[X] На весь экран (видео)", b2x + 18, b2y + 12, Theme::COLOR_FOCUS_CYAN, 13);

        drawText("Совет: Нажмите [A], чтобы выбрать игру на Switch для этого фона", px, b1y + 54, Theme::COLOR_TEXT_MUTED, 12, pw);
    }

    // Bottom Navigation Bar
    int footY = by + bh - 42;
    drawRect(bx + 25, footY, bw - 50, 32, {0x0D, 0x13, 0x1F, 0xDD});
    drawRectOutline(bx + 25, footY, bw - 50, 32, Theme::COLOR_BORDER, 1);
    drawText("[▲/▼] Список   |   [◀/▶] Страница (±5)   |   [A] Назначить на игру Switch   |   [X] Видео   |   [B] Назад",
             bx + 60, footY + 8, Theme::COLOR_TEXT_MUTED, 12);
#endif
}
"""

app_cpp_text += collection_methods
app_cpp_path.write_text(app_cpp_text.replace("\n", "\r\n"), encoding="utf-8")
print("[+] app.cpp patched successfully")
