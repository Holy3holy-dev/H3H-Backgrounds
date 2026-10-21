"""
Script to apply complete 4IFIR Cyber-Glass UI, vertical variant scrolling,
and in-app NRO self-updater to downloader/src/ui/app.cpp.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

APP_CPP = Path("downloader/src/ui/app.cpp")

with open(APP_CPP, "r", encoding="utf-8") as f:
    code = f.read()

# Normalize line endings
code = code.replace("\r\n", "\n")

# 1. Enable SDL_BLENDMODE_BLEND in init()
target_init = """    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }"""

replacement_init = """    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }

    // Enable high-quality alpha blending for 4IFIR frosted glass effects
    SDL_SetRenderDrawBlendMode(m_renderer, SDL_BLENDMODE_BLEND);"""

if target_init in code:
    code = code.replace(target_init, replacement_init, 1)
    print("[+] Patched init() with SDL_BLENDMODE_BLEND")
else:
    print("[-] target_init not matched")

# 2. Add drawing primitives: drawNeonGradientOutline, drawGlassCard, drawCapsuleProgressBar
target_draw = """void App::drawRectOutline(int x, int y, int w, int h, Color color, int thickness) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    for (int t = 0; t < thickness; ++t) {
        SDL_Rect r{x + t, y + t, w - 2 * t, h - 2 * t};
        SDL_RenderDrawRect(m_renderer, &r);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)color; (void)thickness;
#endif
}"""

replacement_draw = """void App::drawRectOutline(int x, int y, int w, int h, Color color, int thickness) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    for (int t = 0; t < thickness; ++t) {
        SDL_Rect r{x + t, y + t, w - 2 * t, h - 2 * t};
        SDL_RenderDrawRect(m_renderer, &r);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)color; (void)thickness;
#endif
}

void App::drawNeonGradientOutline(int x, int y, int w, int h, int thickness) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    // Signature 4IFIR Cyber-Glow: Vertical Gradient from Electric Cyan (#00E5FF) to Neon Magenta (#EC4899)
    for (int t = 0; t < thickness; ++t) {
        int curX = x + t;
        int curY = y + t;
        int curW = w - 2 * t;
        int curH = h - 2 * t;
        if (curW <= 0 || curH <= 0) break;

        // Top horizontal edge: Electric Cyan
        SDL_SetRenderDrawColor(m_renderer, 0x00, 0xE5, 0xFF, 0xFF);
        SDL_RenderDrawLine(m_renderer, curX, curY, curX + curW - 1, curY);

        // Bottom horizontal edge: Neon Magenta
        SDL_SetRenderDrawColor(m_renderer, 0xEC, 0x48, 0x99, 0xFF);
        SDL_RenderDrawLine(m_renderer, curX, curY + curH - 1, curX + curW - 1, curY + curH - 1);

        // Vertical edges: smooth linear color interpolation
        for (int row = 0; row < curH; ++row) {
            float factor = static_cast<float>(row) / static_cast<float>(std::max(1, curH - 1));
            uint8_t r = static_cast<uint8_t>(0x00 + factor * 0xEC);
            uint8_t g = static_cast<uint8_t>(0xE5 + factor * (0x48 - 0xE5));
            uint8_t b = static_cast<uint8_t>(0xFF + factor * (0x99 - 0xFF));
            SDL_SetRenderDrawColor(m_renderer, r, g, b, 0xFF);
            SDL_RenderDrawPoint(m_renderer, curX, curY + row);
            SDL_RenderDrawPoint(m_renderer, curX + curW - 1, curY + row);
        }
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)thickness;
#endif
}

void App::drawGlassCard(int x, int y, int w, int h, bool isFocused, bool isElevated) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color bg = isElevated ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_SURFACE;
    drawRect(x, y, w, h, bg);

    if (isFocused) {
        drawRect(x, y, w, h, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(x, y, w, h, 2);
    } else {
        drawRectOutline(x, y, w, h, Theme::COLOR_BORDER, 1);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)isFocused; (void)isElevated;
#endif
}

void App::drawCapsuleProgressBar(int x, int y, int w, int h, double percent) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    // Dark track background
    drawRect(x, y, w, h, {0x1C, 0x22, 0x30, 0xFF});
    drawRectOutline(x, y, w, h, {0x2D, 0x37, 0x48, 0xFF}, 1);

    // Cyan filled portion
    int fillW = static_cast<int>(w * std::clamp(percent / 100.0, 0.0, 1.0));
    if (fillW > 0) {
        drawRect(x, y, fillW, h, Theme::COLOR_FOCUS_CYAN);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)percent;
#endif
}"""

if target_draw in code:
    code = code.replace(target_draw, replacement_draw, 1)
    print("[+] Patched drawing primitives")
else:
    print("[-] target_draw not matched")

# 3. Patch updateApplicationNro with progress tracking and modal popup
target_update_nro = """void App::updateApplicationNro() {
    if (m_isUpdatingNro.load()) {
        return;
    }

    m_statusNotification = (m_language == Language::Russian)
        ? "Загрузка обновления H3H-Backgrounds.nro..."
        : "Downloading H3H-Backgrounds.nro update...";
    m_notificationFramesRemaining = 120;
    m_isUpdatingNro = true;

    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }

    m_nroUpdateThread = std::thread([this]() {
        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        
        std::vector<std::string> targetNros = {
            appDir + "/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds.nro"
        };

        std::atomic<bool> cancel{false};
        std::string err;
        bool ok = m_platform->downloadFile(nroUrl, tempNro, nullptr, cancel, err);
        bool success = false;
        if (ok) {
            // Release romfs handle so Horizon OS FAT32 unlocks the executing .nro file
            m_platform->releaseRomfs();

            for (const auto& targetNro : targetNros) {
                std::error_code ec;
                std::filesystem::create_directories(std::filesystem::path(targetNro).parent_path(), ec);

                // 1. Try rename
                std::remove(targetNro.c_str());
                if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                    success = true;
                    break;
                }

                // 2. Binary stream copy fallback
                std::ifstream src(tempNro, std::ios::binary);
                if (src.is_open()) {
                    std::ofstream dst(targetNro, std::ios::binary | std::ios::trunc);
                    if (dst.is_open()) {
                        dst << src.rdbuf();
                        dst.flush();
                        success = true;
                        break;
                    }
                }
            }

            std::remove(tempNro.c_str());
            m_platform->restoreRomfs();

            if (!success) {
                err = "Failed to replace H3H-Backgrounds.nro file";
            }
        }
        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            m_nroUpdateError = std::move(err);
            m_nroUpdateSuccess = success;
        }
        m_nroUpdateDone.store(true);
        m_isUpdatingNro.store(false);
    });
}"""

replacement_update_nro = """void App::updateApplicationNro() {
    if (m_isUpdatingNro.load()) {
        return;
    }

    m_nroUpdateBytesDownloaded.store(0);
    m_nroUpdateTotalBytes.store(10549492); // ~10.5 MB default expected
    m_activeDialog = DialogType::UpdateProgress;
    m_dialogTitle = (m_language == Language::Russian) ? "Обновление системы H3H" : "H3H System Update";
    m_dialogMessage = (m_language == Language::Russian)
        ? "Загрузка новой версии H3H-Backgrounds.nro с GitHub..."
        : "Downloading new H3H-Backgrounds.nro from GitHub...";
    m_isUpdatingNro = true;

    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }

    m_nroUpdateThread = std::thread([this]() {
        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        
        std::vector<std::string> targetNros = {
            appDir + "/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds.nro"
        };
        if (!m_runningNroPath.empty()) {
            targetNros.insert(targetNros.begin(), m_runningNroPath);
        }

        std::atomic<bool> cancel{false};
        std::string err;
        auto progressCb = [this](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
            (void)speedBps;
            m_nroUpdateBytesDownloaded.store(bytesDownloaded);
            if (totalBytes > 0) m_nroUpdateTotalBytes.store(totalBytes);
        };

        bool ok = m_platform->downloadFile(nroUrl, tempNro, progressCb, cancel, err);
        bool success = false;
        if (ok) {
            // Release romfs handle so Horizon OS FAT32 unlocks the executing .nro file
            m_platform->releaseRomfs();

            for (const auto& targetNro : targetNros) {
                std::error_code ec;
                std::filesystem::create_directories(std::filesystem::path(targetNro).parent_path(), ec);

                // 1. Try atomic rename
                std::remove(targetNro.c_str());
                if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                    success = true;
                    break;
                }

                // 2. Binary stream copy fallback (overwrites existing open FAT32 files safely)
                std::ifstream src(tempNro, std::ios::binary);
                if (src.is_open()) {
                    std::ofstream dst(targetNro, std::ios::binary | std::ios::trunc);
                    if (dst.is_open()) {
                        dst << src.rdbuf();
                        dst.flush();
                        success = true;
                        break;
                    }
                }
            }

            std::remove(tempNro.c_str());
            m_platform->restoreRomfs();

            if (!success) {
                err = "Failed to replace H3H-Backgrounds.nro file";
            }
        }
        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            m_nroUpdateError = std::move(err);
            m_nroUpdateSuccess = success;
        }
        m_nroUpdateDone.store(true);
        m_isUpdatingNro.store(false);
    });
}"""

if target_update_nro in code:
    code = code.replace(target_update_nro, replacement_update_nro, 1)
    print("[+] Patched updateApplicationNro()")
else:
    print("[-] target_update_nro not matched")

# 4. Patch update() handler for NRO completion
target_update_loop = """        if (ok) {
            m_statusNotification = (m_language == Language::Russian)
                ? "Приложение H3H-Backgrounds.nro успешно обновлено!"
                : "H3H-Backgrounds.nro updated successfully!";
        } else {
            m_statusNotification = (m_language == Language::Russian)
                ? ("Ошибка обновления: " + err)
                : ("Update failed: " + err);
        }
        m_notificationFramesRemaining = 240;"""

replacement_update_loop = """        if (ok) {
            m_activeDialog = DialogType::UpdateSuccess;
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление завершено!" : "Update Complete!";
            m_dialogMessage = (m_language == Language::Russian)
                ? "Приложение H3H-Backgrounds.nro успешно обновлено до актуальной версии!\\nНажмите [A], чтобы перезапустить сейчас, или [B] для продолжения."
                : "H3H-Backgrounds.nro updated successfully!\\nPress [A] to restart now, or [B] to continue.";
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Приложение обновлено!" : "Updated!";
        } else {
            m_activeDialog = DialogType::MessageAlert;
            m_dialogTitle = (m_language == Language::Russian) ? "Ошибка обновления" : "Update Error";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("Не удалось применить обновление: " + err)
                : ("Failed to apply update: " + err);
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? ("Ошибка: " + err) : ("Error: " + err);
        }
        m_notificationFramesRemaining = 240;"""

if target_update_loop in code:
    code = code.replace(target_update_loop, replacement_update_loop, 1)
    print("[+] Patched NRO completion handler")
else:
    print("[-] target_update_loop not matched")

# Save file
with open(APP_CPP, "w", encoding="utf-8") as f:
    f.write(code)

print("[+] Script patch step 1 finished.")
