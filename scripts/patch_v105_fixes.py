from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. Fix header text collision in MyGames
old_header_block = """        // Available variants from catalog
        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = "Доступные варианты видеофона (" + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 248, Theme::COLOR_TEXT_PRIMARY, 16);

        if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            drawText("◀ [B] К списку игр   |   [X] На весь экран", 800, 250, Theme::COLOR_FOCUS_CYAN, 12);
        } else {
            drawText("▶ [A] К вариантам   |   [X] На весь экран", 800, 250, Theme::COLOR_TEXT_MUTED, 12);
        }"""

new_header_block = """        // Available variants from catalog (concise header to avoid collision with hints)
        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = "Варианты (" + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 248, Theme::COLOR_TEXT_PRIMARY, 16);

        if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            drawText("◀ [B] К играм   |   [X] На весь экран", 870, 250, Theme::COLOR_FOCUS_CYAN, 12);
        } else {
            drawText("▶ [A] К вариантам   |   [X] На весь экран", 870, 250, Theme::COLOR_TEXT_MUTED, 12);
        }"""

if old_header_block in text:
    text = text.replace(old_header_block, new_header_block, 1)
    print("[+] Fixed header collision in renderTabMyGames")

# 2. Fix active cover info and button text
old_cover_status = """        // Status details
        std::string coverInfo = selGame.hasInstalledCover ?
            std::string(m_language == Language::Russian ? "Установлен: " : "Installed: ") +
            Config::getTargetCoverFileName(selGame.titleId) + " (" +
            std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)" :
            std::string(m_language == Language::Russian ? "Видеофон отсутствует" : "No video background");
        drawText(coverInfo, 530, 175, selGame.hasInstalledCover ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);

        // Prominent Action Buttons (positioned below status, safe from top-right Tesla monitor HUD)
        if (selGame.hasInstalledCover) {
            drawRect(530, 202, 220, 32, {0xEF, 0x44, 0x44, 0x33});
            drawRectOutline(530, 202, 220, 32, Theme::COLOR_DANGER, 1);
            drawText("[Y] Удалить видеофон", 545, 210, Theme::COLOR_DANGER, 13);"""

new_cover_status = """        // Status details
        std::string coverInfo = selGame.hasInstalledCover ?
            std::string(m_language == Language::Russian ? "Активный фон на консоли: " : "Active cover: ") +
            Config::getTargetCoverFileName(selGame.titleId) + " (" +
            std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)" :
            std::string(m_language == Language::Russian ? "Видеофон не установлен" : "No video background installed");
        drawText(coverInfo, 530, 175, selGame.hasInstalledCover ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);

        // Prominent Action Buttons (positioned below status, safe from top-right Tesla monitor HUD)
        if (selGame.hasInstalledCover) {
            drawRect(530, 202, 230, 32, {0xEF, 0x44, 0x44, 0x33});
            drawRectOutline(530, 202, 230, 32, Theme::COLOR_DANGER, 1);
            drawText("[Y] Удалить активный фон", 545, 210, Theme::COLOR_DANGER, 13);"""

if old_cover_status in text:
    text = text.replace(old_cover_status, new_cover_status, 1)
    print("[+] Updated active cover status and button text")

# 3. Fix delete dialog message to be clear
old_del_dlg = 'm_dialogTitle = getStrings(m_language).confirmDeleteTitle;\n                        m_dialogMessage = getStrings(m_language).confirmDeleteMsg;'
new_del_dlg = """m_dialogTitle = "Удаление активного фона";
                        m_dialogMessage = "Удалить установленный видеофон для игры " + g.name + "?\\n\\n(Фон будет удалён с консоли, а варианты в каталоге останутся доступны для повторной установки в любой момент)";"""

text = text.replace(old_del_dlg, new_del_dlg)

# 4. Fix loadPreviewTexture paths: avoid '..' by using getAppDirectory() + "/thumbs"
old_load_tex = """    std::string thumbDir = m_platform->getCoversDirectory() + "/../thumbs";
    std::string thumbFile = thumbDir + "/" + variant.id + ".jpg";

    std::error_code ec;
    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_RWops* rw = SDL_RWFromFile(thumbFile.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
                return;
            }
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
    }).detach();"""

new_load_tex = """    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
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
    }).detach();"""

if old_load_tex in text:
    text = text.replace(old_load_tex, new_load_tex, 1)
    print("[+] Fixed loadPreviewTexture with canonical thumbs directory")

# 5. Fix App::update() pending texture loading and close rw
old_update_tex = """        SDL_RWops* rw = SDL_RWFromFile(path.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
            }
        }"""

new_update_tex = """        SDL_RWops* rw = SDL_RWFromFile(path.c_str(), "rb");
        if (rw) {
            SDL_Surface* surf = IMG_LoadJPG_RW(rw);
            if (surf) {
                if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
                m_previewTexture = SDL_CreateTextureFromSurface(m_renderer, surf);
                SDL_FreeSurface(surf);
            }
            SDL_RWclose(rw);
        }"""

text = text.replace(old_update_tex, new_update_tex)

app_cpp.write_text(text, encoding="utf-8")
print("[+] Applied patch_v105_fixes.py successfully!")
