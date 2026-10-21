from pathlib import Path

path = Path("downloader/src/ui/app.cpp")
content = path.read_text(encoding="utf-8")

# 1. shutdown()
old_shutdown = """    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }"""
new_shutdown = """    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }"""
assert old_shutdown in content, "old_shutdown not found"
content = content.replace(old_shutdown, new_shutdown, 1)

# 2. update()
old_update = """#ifdef HAS_SDL2
    if (!m_pendingPreviewFileToLoad.empty() && m_renderer) {
        std::string path = m_pendingPreviewFileToLoad;
        m_pendingPreviewFileToLoad.clear();
        SDL_RWops* rw = SDL_RWFromFile(path.c_str(), "rb");
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
assert old_update in content, "old_update not found"
content = content.replace(old_update, new_update, 1)

# 3. onButtonPress fullscreen preview dpad
old_prev_dpad = """                if (button == 13 /* DPAD_LEFT */) {
                    m_selectedVariantIndex = (m_selectedVariantIndex == 0) ? vCount - 1 : m_selectedVariantIndex - 1;
                    loadPreviewTexture(g.catalogEntry.variants[m_selectedVariantIndex]);
                    return;
                } else if (button == 14 /* DPAD_RIGHT */) {
                    m_selectedVariantIndex = (m_selectedVariantIndex + 1) % vCount;
                    loadPreviewTexture(g.catalogEntry.variants[m_selectedVariantIndex]);
                    return;"""
new_prev_dpad = """                if (button == 13 /* DPAD_LEFT */) {
                    m_selectedVariantIndex = (m_selectedVariantIndex == 0) ? vCount - 1 : m_selectedVariantIndex - 1;
                    loadPreviewTexture(g.titleId, g.catalogEntry.variants[m_selectedVariantIndex]);
                    return;
                } else if (button == 14 /* DPAD_RIGHT */) {
                    m_selectedVariantIndex = (m_selectedVariantIndex + 1) % vCount;
                    loadPreviewTexture(g.titleId, g.catalogEntry.variants[m_selectedVariantIndex]);
                    return;"""
assert old_prev_dpad in content, "old_prev_dpad not found"
content = content.replace(old_prev_dpad, new_prev_dpad, 1)

# 4. onButtonPress B button
old_b = """    // Standard Nintendo Switch [B] button: Return to Home tab from any view
    if (button == 1 /* B - Back */) {
        if (m_activeTab != Tab::Home) {
            m_activeTab = Tab::Home;
            return;
        }
    }"""
new_b = """    // Standard Nintendo Switch [B] button
    if (button == 1 /* B - Back */) {
        if (m_activeTab == Tab::MyGames && m_myGamesActivePane == MyGamesPane::VariantsList) {
            m_myGamesActivePane = MyGamesPane::GamesList;
            return;
        }
        if (m_activeTab != Tab::Home) {
            m_activeTab = Tab::Home;
            return;
        }
    }"""
assert old_b in content, "old_b not found"
content = content.replace(old_b, new_b, 1)

# 5. onButtonPress MyGames GamesList X button
old_gl_x = """            } else if (button == 2 /* X - Fullscreen Preview */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_isFullscreenPreview = true;
                        loadPreviewTexture(g.catalogEntry.variants[m_selectedVariantIndex]);
                    }
                }
            }"""
new_gl_x = """            } else if (button == 2 /* X - Fullscreen Preview */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_isFullscreenPreview = true;
                        loadPreviewTexture(g.titleId, g.catalogEntry.variants[m_selectedVariantIndex]);
                    }
                }
            }"""
assert old_gl_x in content, "old_gl_x not found"
content = content.replace(old_gl_x, new_gl_x, 1)

# 6. onButtonPress MyGames VariantsList X button
old_vl_x = """                } else if (button == 2 /* X - Fullscreen Preview */) {
                    m_isFullscreenPreview = true;
                    loadPreviewTexture(g.catalogEntry.variants[m_selectedVariantIndex]);
                }"""
new_vl_x = """                } else if (button == 2 /* X - Fullscreen Preview */) {
                    m_isFullscreenPreview = true;
                    loadPreviewTexture(g.titleId, g.catalogEntry.variants[m_selectedVariantIndex]);
                }"""
assert old_vl_x in content, "old_vl_x not found"
content = content.replace(old_vl_x, new_vl_x, 1)

# 7. loadPreviewTexture and closeFullscreenPreview
old_load_prev = """void App::loadPreviewTexture(const Variant& variant) {
#ifdef HAS_SDL2
    if (variant.id == m_previewCurrentVariantId && m_previewTexture) {
        return;
    }
    m_previewCurrentVariantId = variant.id;

    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string thumbFile = thumbDir + "/" + variant.id + ".jpg";

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
}"""

new_load_prev = """void App::loadPreviewTexture(const std::string& titleId, const Variant& variant) {
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

assert old_load_prev in content, "old_load_prev not found"
content = content.replace(old_load_prev, new_load_prev, 1)

path.write_text(content, encoding="utf-8")
print("Successfully patched downloader/src/ui/app.cpp with thread-safe preview!")
