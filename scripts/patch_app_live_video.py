from pathlib import Path

path = Path("downloader/src/ui/app.cpp")
content = path.read_text(encoding="utf-8")

# 1. shutdown()
old_shutdown = """    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }"""
new_shutdown = """    m_videoPlayer.close();
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }"""
assert old_shutdown in content, "old_shutdown not found"
content = content.replace(old_shutdown, new_shutdown, 1)

# 2. update()
old_update = """#ifdef HAS_SDL2
    std::string previewPath;
    {
        std::lock_guard<std::mutex> lock(m_previewMutex);
        if (!m_pendingPreviewFileToLoad.empty()) {
            previewPath = m_pendingPreviewFileToLoad;
            m_pendingPreviewFileToLoad.clear();
        }
    }
    if (!previewPath.empty() && m_renderer) {
        SDL_RWops* rw = SDL_RWFromFile(previewPath.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
            }
            SDL_RWclose(rw);
        }
    }
#endif"""

new_update = """#ifdef HAS_SDL2
    std::string previewPath;
    std::string vidPath;
    {
        std::lock_guard<std::mutex> lock(m_previewMutex);
        if (!m_pendingPreviewFileToLoad.empty()) {
            previewPath = m_pendingPreviewFileToLoad;
            m_pendingPreviewFileToLoad.clear();
        }
        if (!m_pendingVideoToOpen.empty()) {
            vidPath = m_pendingVideoToOpen;
            m_pendingVideoToOpen.clear();
        }
    }
    if (!previewPath.empty() && m_renderer) {
        SDL_RWops* rw = SDL_RWFromFile(previewPath.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
            }
            SDL_RWclose(rw);
        }
    }
    if (!vidPath.empty() && m_renderer && m_isFullscreenPreview) {
        m_videoPlayer.open(vidPath, m_renderer);
    }
    if (m_isFullscreenPreview && m_videoPlayer.isPlaying()) {
        m_videoPlayer.update();
    }
#endif"""
assert old_update in content, "old_update not found"
content = content.replace(old_update, new_update, 1)

# 3. renderTabMyGames variant card active cover badge
old_var_card = """                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(975, vY + 38, 80, 20, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(975, vY + 38, 80, 20, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", 998, vY + 42, Theme::COLOR_SUCCESS, 10);
                } else {
                    drawRect(975, vY + 38, 80, 20, {0x28, 0x33, 0x47, 0x44});
                    drawRectOutline(975, vY + 38, 80, 20, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", 982, vY + 42, Theme::COLOR_TEXT_MUTED, 10);
                }"""

new_var_card = """                // Active installed background badge
                bool isActiveOnConsole = false;
                if (selGame.hasInstalledCover && selGame.installedCoverSizeBytes > 0 && v.sizeBytes > 0) {
                    if (std::abs((int64_t)v.sizeBytes - (int64_t)selGame.installedCoverSizeBytes) <= 2048) {
                        isActiveOnConsole = true;
                    }
                }
                if (isActiveOnConsole) {
                    drawRect(845, vY + 38, 120, 20, {0x10, 0xB9, 0x81, 0x44});
                    drawRectOutline(845, vY + 38, 120, 20, Theme::COLOR_SUCCESS, 1);
                    drawText("УСТАНОВЛЕН", 858, vY + 42, Theme::COLOR_SUCCESS, 10);
                }

                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(975, vY + 38, 80, 20, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(975, vY + 38, 80, 20, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", 998, vY + 42, Theme::COLOR_SUCCESS, 10);
                } else {
                    drawRect(975, vY + 38, 80, 20, {0x28, 0x33, 0x47, 0x44});
                    drawRectOutline(975, vY + 38, 80, 20, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", 982, vY + 42, Theme::COLOR_TEXT_MUTED, 10);
                }"""
assert old_var_card in content, "old_var_card not found"
content = content.replace(old_var_card, new_var_card, 1)

# 4. renderFullscreenPreview live video and active badge
old_render_prev = """    // 1. Draw Background Image or Dark Frosted Canvas
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
    }"""

new_render_prev = """    // 1. Draw Live Motion Video or Static Background Image or Dark Frosted Canvas
    if (m_videoPlayer.isPlaying()) {
        m_videoPlayer.render(m_renderer, nullptr);

        // Status badge: LIVE VIDEO
        drawRect(30, 20, 280, 32, {0x0F, 0x17, 0x2A, 0xDD});
        drawRectOutline(30, 20, 280, 32, Theme::COLOR_SUCCESS, 1);
        drawText("▶ ЖИВОЙ ВИДЕОФОН (30 FPS)", 45, 28, Theme::COLOR_SUCCESS, 13);
    } else if (m_previewTexture) {
        SDL_RenderCopy(m_renderer, m_previewTexture, nullptr, nullptr);

        if (m_videoDownloading) {
            drawRect(30, 20, 270, 32, {0x0F, 0x17, 0x2A, 0xDD});
            drawRectOutline(30, 20, 270, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("▶ Буферизация ролика...", 45, 28, Theme::COLOR_FOCUS_CYAN, 13);
        }
    } else {
        // Fallback canvas with subtle Cyber-Glass animated glow
        drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x08, 0x0C, 0x14, 0xFF});
        drawNeonGradientOutline(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, 3);

        if (m_previewLoading || m_videoDownloading) {
            drawText("Загрузка видеофона (1280x720 HD)...", 400, 320, Theme::COLOR_FOCUS_CYAN, 20);
            drawText("Пожалуйста, подождите несколько секунд...", 450, 360, Theme::COLOR_TEXT_MUTED, 14);
        } else {
            drawText("Видеофон недоступен офлайн (нет подключения)", 390, 320, Theme::COLOR_WARNING, 20);
            drawText("Нажмите [A], чтобы установить видеофон из кэша", 430, 360, Theme::COLOR_TEXT_MUTED, 14);
        }
    }"""
assert old_render_prev in content, "old_render_prev not found"
content = content.replace(old_render_prev, new_render_prev, 1)

# 5. renderFullscreenPreview HUD active variant badge and button
old_hud_btn = """            // Right side buttons
            drawRect(hudX + 900, hudY + 16, 270, 36, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(hudX + 900, hudY + 16, 270, 36, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("[A] Установить видеофон", hudX + 930, hudY + 25, Theme::COLOR_FOCUS_CYAN, 14);"""

new_hud_btn = """            bool isActiveVariant = false;
            if (g.hasInstalledCover && g.installedCoverSizeBytes > 0 && v.sizeBytes > 0) {
                if (std::abs((int64_t)v.sizeBytes - (int64_t)g.installedCoverSizeBytes) <= 2048) {
                    isActiveVariant = true;
                }
            }

            if (isActiveVariant) {
                drawRect(hudX + 570, hudY + 66, 175, 20, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(hudX + 570, hudY + 66, 175, 20, Theme::COLOR_SUCCESS, 1);
                drawText("УСТАНОВЛЕН НА SWITCH", hudX + 582, hudY + 70, Theme::COLOR_SUCCESS, 10);
            }

            // Right side buttons
            if (isActiveVariant) {
                drawRect(hudX + 900, hudY + 16, 270, 36, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(hudX + 900, hudY + 16, 270, 36, Theme::COLOR_SUCCESS, 1);
                drawText("[A] Переустановить", hudX + 950, hudY + 25, Theme::COLOR_SUCCESS, 14);
            } else {
                drawRect(hudX + 900, hudY + 16, 270, 36, Theme::COLOR_FOCUS_FILL);
                drawRectOutline(hudX + 900, hudY + 16, 270, 36, Theme::COLOR_FOCUS_CYAN, 1);
                drawText("[A] Установить видеофон", hudX + 930, hudY + 25, Theme::COLOR_FOCUS_CYAN, 14);
            }"""
assert old_hud_btn in content, "old_hud_btn not found"
content = content.replace(old_hud_btn, new_hud_btn, 1)

# 6. loadPreviewTexture and closeFullscreenPreview
old_load_prev2 = """void App::loadPreviewTexture(const std::string& titleId, const Variant& variant) {
#ifdef HAS_SDL2
    std::string cacheKey = titleId + "_" + variant.id;
    if (cacheKey == m_previewCurrentVariantId && m_previewTexture) {
        return;
    }
    m_previewCurrentVariantId = cacheKey;

    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string thumbFile = thumbDir + "/" + cacheKey + ".jpg";

    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_RWops* rw = SDL_RWFromFile(thumbFile.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
                SDL_RWclose(rw);
                return;
            }
            SDL_RWclose(rw);
        }
    }

    if (variant.previewUrl.empty()) return;

    std::string url = variant.previewUrl;
    size_t szPos = url.find("sz=w640");
    if (szPos != std::string::npos) {
        url.replace(szPos, 7, "sz=w1280");
    }

    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }
    m_cancelPreview.store(false);

    m_previewLoading = true;
    m_previewThread = std::thread([this, url, thumbFile, key = cacheKey]() {
        std::string err;
        bool ok = m_platform->downloadFile(url, thumbFile, nullptr, m_cancelPreview, err);
        m_previewLoading = false;
        if (ok && m_isFullscreenPreview && m_previewCurrentVariantId == key) {
            std::lock_guard<std::mutex> lock(m_previewMutex);
            m_pendingPreviewFileToLoad = thumbFile;
        }
    });
#endif
}

void App::closeFullscreenPreview() {
#ifdef HAS_SDL2
    m_isFullscreenPreview = false;
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }
    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }
    m_previewCurrentVariantId.clear();
#endif
}"""

new_load_prev2 = """void App::loadPreviewTexture(const std::string& titleId, const Variant& variant) {
#ifdef HAS_SDL2
    m_videoPlayer.close();

    std::string cacheKey = titleId + "_" + variant.id;
    m_previewCurrentVariantId = cacheKey;

    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string thumbFile = thumbDir + "/" + cacheKey + ".jpg";
    std::string vidFile = thumbDir + "/" + cacheKey + ".mp4";

    // 1. Check if this is the active cover installed on console
    bool isActiveInstalled = false;
    std::string installedCoverPath;
    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
        const auto& g = m_installedGames[m_myGamesSelectedIndex];
        if (g.hasInstalledCover && g.titleId == titleId && g.installedCoverSizeBytes > 0 && variant.sizeBytes > 0) {
            if (std::abs((int64_t)variant.sizeBytes - (int64_t)g.installedCoverSizeBytes) <= 2048) {
                isActiveInstalled = true;
                installedCoverPath = g.installedCoverPath;
            }
        }
    }

    if (isActiveInstalled && !installedCoverPath.empty() && std::filesystem::exists(installedCoverPath, ec)) {
        // Play directly from SD card with 0 network delay!
        m_videoPlayer.open(installedCoverPath, m_renderer);
    } else if (std::filesystem::exists(vidFile, ec) && std::filesystem::file_size(vidFile, ec) > 50000) {
        // Play directly from cached MP4!
        m_videoPlayer.open(vidFile, m_renderer);
    }

    // 2. Load static image if exists
    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_RWops* rw = SDL_RWFromFile(thumbFile.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
            }
            SDL_RWclose(rw);
        }
    }

    // 3. If video is already playing, no need to download
    if (m_videoPlayer.isPlaying()) {
        return;
    }

    // 4. Download snapshot and video in background
    std::string thumbUrl = variant.previewUrl;
    size_t szPos = thumbUrl.find("sz=w640");
    if (szPos != std::string::npos) {
        thumbUrl.replace(szPos, 7, "sz=w1280");
    }
    std::string videoUrl = variant.url;

    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }
    m_cancelPreview.store(false);

    m_previewLoading = true;
    m_videoDownloading = true;

    m_previewThread = std::thread([this, thumbUrl, videoUrl, thumbFile, vidFile, key = cacheKey]() {
        // First download thumbnail image if not already cached
        std::error_code ec2;
        if (!std::filesystem::exists(thumbFile, ec2) && !thumbUrl.empty()) {
            std::string err;
            bool ok = m_platform->downloadFile(thumbUrl, thumbFile, nullptr, m_cancelPreview, err);
            m_previewLoading = false;
            if (ok && m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                std::lock_guard<std::mutex> lock(m_previewMutex);
                m_pendingPreviewFileToLoad = thumbFile;
            }
        } else {
            m_previewLoading = false;
        }

        // Then download live video MP4
        if (!m_cancelPreview.load() && !videoUrl.empty() && !std::filesystem::exists(vidFile, ec2)) {
            std::string err;
            bool ok = m_platform->downloadFile(videoUrl, vidFile, nullptr, m_cancelPreview, err);
            m_videoDownloading = false;
            if (ok && m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                std::lock_guard<std::mutex> lock(m_previewMutex);
                m_pendingVideoToOpen = vidFile;
            }
        } else {
            m_videoDownloading = false;
        }
    });
#endif
}

void App::closeFullscreenPreview() {
#ifdef HAS_SDL2
    m_isFullscreenPreview = false;
    m_videoPlayer.close();
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }
    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }
    m_previewCurrentVariantId.clear();
#endif
}"""

assert old_load_prev2 in content, "old_load_prev2 not found"
content = content.replace(old_load_prev2, new_load_prev2, 1)

path.write_text(content, encoding="utf-8")
print("Patched downloader/src/ui/app.cpp with live video player and active cover badge successfully!")
