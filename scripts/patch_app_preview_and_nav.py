from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. Add #include <SDL2/SDL_image.h>
if "#include <SDL2/SDL_image.h>" not in text:
    text = "#include <SDL2/SDL_image.h>\n" + text
    print("[+] Added SDL_image.h include")

# 2. In App::init(), call IMG_Init
old_ttf_init = """    if (TTF_Init() != 0) {
        std::cerr << "[-] TTF_Init failed: " << TTF_GetError() << std::endl;
    }"""
new_ttf_init = """    if (TTF_Init() != 0) {
        std::cerr << "[-] TTF_Init failed: " << TTF_GetError() << std::endl;
    }
    IMG_Init(IMG_INIT_JPG | IMG_INIT_PNG);"""

if old_ttf_init in text:
    text = text.replace(old_ttf_init, new_ttf_init, 1)
    print("[+] Added IMG_Init to App::init")

# 3. In App::update(), handle pending texture load
old_update_top = "void App::update() {"
new_update_top = """void App::update() {
#ifdef HAS_SDL2
    if (!m_pendingPreviewFileToLoad.empty() && m_renderer) {
        std::string path = m_pendingPreviewFileToLoad;
        m_pendingPreviewFileToLoad.clear();
        SDL_Surface* surf = IMG_Load(path.c_str());
        if (surf) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
            SDL_FreeSurface(surf);
        }
    }
#endif"""

if old_update_top in text:
    text = text.replace(old_update_top, new_update_top, 1)
    print("[+] Added pending preview texture loader to App::update")

# 4. In App::render(), check fullscreen preview
old_render_top = """void App::render() {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    // Clear background
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, Theme::COLOR_BG_BASE);"""

new_render_top = """void App::render() {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    if (m_isFullscreenPreview) {
        renderFullscreenPreview();
        SDL_RenderPresent(m_renderer);
        return;
    }

    // Clear background
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, Theme::COLOR_BG_BASE);"""

if old_render_top in text:
    text = text.replace(old_render_top, new_render_top, 1)
    print("[+] Added fullscreen preview hook in App::render")

# 5. Append helper methods: renderFullscreenPreview, loadPreviewTexture, closeFullscreenPreview
helper_methods = """
void App::renderFullscreenPreview() {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    // 1. Draw Background Image or Dark Frosted Canvas
    if (m_previewTexture) {
        SDL_RenderCopy(m_renderer, m_previewTexture, nullptr, nullptr);
    } else {
        // Fallback canvas with subtle Cyber-Glass animated glow
        drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x08, 0x0C, 0x14, 0xFF});
        drawNeonGradientOutline(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, 3);

        if (m_previewLoading) {
            drawText("Загрузка предпросмотра на весь экран (1280x720 HD)...", 380, 320, Theme::COLOR_FOCUS_CYAN, 20);
            drawText("Пожалуйста, подождите несколько секунд...", 450, 360, Theme::COLOR_TEXT_MUTED, 14);
        } else {
            drawText("Предпросмотр недоступен офлайн (нет подключения)", 390, 320, Theme::COLOR_WARNING, 20);
            drawText("Нажмите [A], чтобы установить видеофон из кэша", 430, 360, Theme::COLOR_TEXT_MUTED, 14);
        }
    }

    // 2. Bottom 4IFIR Cyber-Glass HUD overlay
    int hudX = 40;
    int hudY = 585;
    int hudW = 1200;
    int hudH = 105;
    drawGlassCard(hudX, hudY, hudW, hudH, false, true);
    drawNeonGradientOutline(hudX, hudY, hudW, hudH, 2);

    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
        const auto& g = m_installedGames[m_myGamesSelectedIndex];
        if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
            int totalV = static_cast<int>(g.catalogEntry.variants.size());
            int curV = std::clamp(m_selectedVariantIndex, 0, totalV - 1);
            const auto& v = g.catalogEntry.variants[curV];

            // Game Name (Left top)
            drawText(g.name, hudX + 25, hudY + 12, Theme::COLOR_TEXT_PRIMARY, 19, 580);

            // Variant Name & Style (Left middle)
            std::string varTitle = std::to_string(curV + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
            drawText(varTitle, hudX + 25, hudY + 40, Theme::COLOR_FOCUS_CYAN, 16, 580);

            // Tech specs + Audio pill (Left bottom)
            double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
            char mbBuf[16];
            if (mb >= 0.1) snprintf(mbBuf, sizeof(mbBuf), "%.1f MB", mb);
            else snprintf(mbBuf, sizeof(mbBuf), "~3.5 MB");

            std::string specs = "1280x720 @30fps  |  " + std::string(mbBuf) +
                                "  |  Вариант " + std::to_string(curV + 1) + " из " + std::to_string(totalV);
            drawText(specs, hudX + 25, hudY + 68, Theme::COLOR_TEXT_MUTED, 13);

            if (v.hasAudio) {
                drawRect(hudX + 480, hudY + 66, 75, 20, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(hudX + 480, hudY + 66, 75, 20, Theme::COLOR_SUCCESS, 1);
                drawText("ЗВУК", hudX + 501, hudY + 70, Theme::COLOR_SUCCESS, 10);
            } else {
                drawRect(hudX + 480, hudY + 66, 75, 20, {0x28, 0x33, 0x47, 0x44});
                drawRectOutline(hudX + 480, hudY + 66, 75, 20, Theme::COLOR_BORDER, 1);
                drawText("БЕЗ ЗВУКА", hudX + 488, hudY + 70, Theme::COLOR_TEXT_MUTED, 10);
            }

            // Right side buttons
            drawRect(hudX + 900, hudY + 16, 270, 36, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(hudX + 900, hudY + 16, 270, 36, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("[A] Установить видеофон", hudX + 930, hudY + 25, Theme::COLOR_FOCUS_CYAN, 14);

            if (totalV > 1) {
                drawText("[◀ / ▶ D-Pad] Варианты на лету", hudX + 900, hudY + 62, Theme::COLOR_FOCUS_PINK, 13);
            }
            drawText("[B] Закрыть", hudX + 1115, hudY + 62, Theme::COLOR_TEXT_MUTED, 13);
        }
    }
#endif
}

void App::loadPreviewTexture(const Variant& variant) {
#ifdef HAS_SDL2
    if (variant.id == m_previewCurrentVariantId && m_previewTexture) {
        return;
    }
    m_previewCurrentVariantId = variant.id;

    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }

    std::string thumbDir = m_platform->getCoversDirectory() + "/../thumbs";
    std::string thumbFile = thumbDir + "/" + variant.id + ".jpg";

    std::error_code ec;
    if (fs::exists(thumbFile, ec)) {
        SDL_Surface* surf = IMG_Load(thumbFile.c_str());
        if (surf) {
            m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
            SDL_FreeSurface(surf);
            return;
        }
    }

    if (variant.previewUrl.empty()) return;

    std::string url = variant.previewUrl;
    size_t szPos = url.find("sz=w640");
    if (szPos != std::string::npos) {
        url.replace(szPos, 7, "sz=w1280");
    }

    m_previewLoading = true;
    std::thread([this, url, thumbFile, varId = variant.id]() {
        std::atomic<bool> cancelFlag{false};
        std::string err;
        bool ok = m_platform->downloadFile(url, thumbFile, nullptr, cancelFlag, err);
        m_previewLoading = false;
        if (ok && m_isFullscreenPreview && m_previewCurrentVariantId == varId) {
            m_pendingPreviewFileToLoad = thumbFile;
        }
    }).detach();
#endif
}

void App::closeFullscreenPreview() {
#ifdef HAS_SDL2
    m_isFullscreenPreview = false;
    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }
    m_previewCurrentVariantId.clear();
#endif
}
"""

if "void App::renderFullscreenPreview()" not in text:
    text += "\n" + helper_methods
    print("[+] Added renderFullscreenPreview, loadPreviewTexture, closeFullscreenPreview")

app_cpp.write_text(text, encoding="utf-8")
print("[+] Applied patch_app_preview_and_nav.py successfully!")
