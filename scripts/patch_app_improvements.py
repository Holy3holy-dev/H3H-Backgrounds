# Comprehensive patch script for downloader/src/ui/app.cpp
import re
from pathlib import Path

app_path = Path("downloader/src/ui/app.cpp")
content = app_path.read_text(encoding="utf-8")

# 1. Add utf8ToLower helper in anonymous namespace
old_anon = """#ifdef HAS_SDL2
namespace {
static SDL_Texture* loadTextureFromFile(SDL_Renderer* renderer, const std::string& path) {
    if (!renderer || path.empty()) return nullptr;
    FILE* fp = fopen(path.c_str(), "rb");
    if (!fp) return nullptr;
    SDL_RWops* rw = SDL_RWFromFP(fp, SDL_TRUE);
    if (!rw) {
        fclose(fp);
        return nullptr;
    }
    SDL_Surface* surf = IMG_Load_RW(rw, 1);
    if (!surf) return nullptr;
    SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
    SDL_FreeSurface(surf);
    if (tex) {
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_NONE);
    }
    return tex;
}
} // anonymous namespace
#endif"""

new_anon = """#ifdef HAS_SDL2
namespace {
static SDL_Texture* loadTextureFromFile(SDL_Renderer* renderer, const std::string& path) {
    if (!renderer || path.empty()) return nullptr;
    FILE* fp = fopen(path.c_str(), "rb");
    if (!fp) return nullptr;
    SDL_RWops* rw = SDL_RWFromFP(fp, SDL_TRUE);
    if (!rw) {
        fclose(fp);
        return nullptr;
    }
    SDL_Surface* surf = IMG_Load_RW(rw, 1);
    if (!surf) return nullptr;
    SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
    SDL_FreeSurface(surf);
    if (tex) {
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_NONE);
    }
    return tex;
}

// UTF-8 lowercase conversion for English and Russian Cyrillic
static std::string utf8ToLower(const std::string& s) {
    std::string result;
    result.reserve(s.size());
    for (size_t i = 0; i < s.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        if (c < 0x80) {
            result.push_back(static_cast<char>(std::tolower(c)));
        } else if (c == 0xD0 && i + 1 < s.size()) {
            unsigned char c2 = static_cast<unsigned char>(s[i + 1]);
            if (c2 == 0x81) { // Ё -> ё (0xD1 0x91)
                result.push_back(static_cast<char>(0xD1));
                result.push_back(static_cast<char>(0x91));
                i++;
            } else if (c2 >= 0x90 && c2 <= 0x9F) { // А..П -> а..п (0xD0 0xB0..0xBF)
                result.push_back(static_cast<char>(0xD0));
                result.push_back(static_cast<char>(c2 + 0x20));
                i++;
            } else if (c2 >= 0xA0 && c2 <= 0xAF) { // Р..Я -> р..я (0xD1 0x80..0x8F)
                result.push_back(static_cast<char>(0xD1));
                result.push_back(static_cast<char>(c2 - 0x20));
                i++;
            } else {
                result.push_back(s[i]);
            }
        } else {
            result.push_back(s[i]);
        }
    }
    return result;
}
} // anonymous namespace
#endif"""

assert old_anon in content, "old_anon not found!"
content = content.replace(old_anon, new_anon, 1)
print("[+] Added utf8ToLower to app.cpp")

# 2. Patch handleInput dialog and preview touch hit testing
old_dialog_touch = """            // If dialog is open, handle direct taps on dialog buttons
            if (m_activeDialog != DialogType::None) {
                if (my >= 400 && my <= 450 && mx >= 440 && mx <= 610) {
                    m_dialogFocus = 0;
                    onButtonPress(0 /* A - Confirm */);
                } else if (my >= 400 && my <= 450 && mx >= 650 && mx <= 820) {
                    m_dialogFocus = 1;
                    onButtonPress(1 /* B - Cancel */);
                } else if (mx < 315 || mx > 965 || my < 235 || my > 485) {
                    m_activeDialog = DialogType::None;
                }
                continue;
            }

            // If Fullscreen Preview is active, tap closes preview
            if (m_isFullscreenPreview) {
                closeFullscreenPreview();
                continue;
            }"""

new_dialog_touch = """            // If dialog is open, handle direct taps on dialog buttons
            if (m_activeDialog != DialogType::None) {
                int dw = 700;
                int dh = 270;
                int dx = (Theme::SCREEN_WIDTH - dw) / 2;
                int dy = (Theme::SCREEN_HEIGHT - dh) / 2;
                int btnY = dy + 190;

                if (m_activeDialog == DialogType::MessageAlert || m_activeDialog == DialogType::IntegrityCheckResult) {
                    if (mx >= dx + 260 && mx <= dx + 440 && my >= dy + 190 && my <= dy + 240) {
                        m_activeDialog = DialogType::None;
                    } else if (mx < dx || mx > dx + dw || my < dy || my > dy + dh) {
                        m_activeDialog = DialogType::None;
                    }
                } else if (m_activeDialog == DialogType::UpdateSuccess) {
                    if (mx >= dx + 240 && mx <= dx + 460 && my >= dy + 190 && my <= dy + 245) {
                        onButtonPress(0 /* A - Restart */);
                    }
                } else {
                    if (my >= btnY && my <= btnY + 46 && mx >= dx + 120 && mx <= dx + 320) {
                        m_dialogFocus = 0;
                        onButtonPress(0 /* A - Confirm */);
                    } else if (my >= btnY && my <= btnY + 46 && mx >= dx + 380 && mx <= dx + 580) {
                        m_dialogFocus = 1;
                        onButtonPress(1 /* B - Cancel */);
                    } else if (mx < dx || mx > dx + dw || my < dy || my > dy + dh) {
                        m_activeDialog = DialogType::None;
                    }
                }
                continue;
            }

            // If Fullscreen Preview is active, handle touch HUD buttons and swipe/taps
            if (m_isFullscreenPreview) {
                int hudX = 40;
                int hudY = 585;
                if (mx >= hudX + 900 && mx <= hudX + 1170 && my >= hudY + 14 && my <= hudY + 52) {
                    onButtonPress(0 /* A - Install / Save */);
                } else if (mx >= hudX + 690 && mx <= hudX + 885 && my >= hudY + 14 && my <= hudY + 52) {
                    onButtonPress(9 /* L - Favorite */);
                } else if (mx >= hudX + 540 && mx <= hudX + 750 && my >= hudY + 60 && my <= hudY + 95) {
                    onButtonPress(3 /* Y - Assign */);
                } else if (mx <= 120 && my >= 200 && my <= 520) {
                    onButtonPress(13 /* DPAD_LEFT - Prev */);
                } else if (mx >= 1160 && my >= 200 && my <= 520) {
                    onButtonPress(14 /* DPAD_RIGHT - Next */);
                } else {
                    closeFullscreenPreview();
                }
                continue;
            }"""

assert old_dialog_touch in content, "old_dialog_touch not found!"
content = content.replace(old_dialog_touch, new_dialog_touch, 1)
print("[+] Patched dialog and preview touch handling")

# 3. Patch CollectionBrowser Favorite button touch
old_coll_fav = """                        // Button [L] В избранное
                        else if (mx >= px && mx <= px + 230 && my >= b3y && my <= b3y + 36) {
                            onButtonPress(9 /* L - Favorite */);
                        }
                        // Button [B] Закрыть
                        else if (mx >= px + 245 && mx <= px + 475 && my >= b3y && my <= b3y + 36) {
                            closeCollectionBrowser();
                        }"""

new_coll_fav = """                        // Button [L / R3] В избранное (full width 480)
                        else if (mx >= px && mx <= px + 480 && my >= b3y && my <= b3y + 36) {
                            onButtonPress(9 /* L - Favorite */);
                        }"""

assert old_coll_fav in content, "old_coll_fav not found!"
content = content.replace(old_coll_fav, new_coll_fav, 1)
print("[+] Patched CollectionBrowser touch favorite button")

# 4. Patch Tab::MyGames and Tab::Downloads touch handling in handleInput
old_mygames_touch = """            // MyGames Tab: top-right "Установить все" button: x in [950, 1230], y in [95, 140]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 95 && my <= 140) {
                installAllMissing();
            }
            // MyGames Tab: "Удалить видеофон" button: x in [950, 1230], y in [155, 200]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 155 && my <= 200) {
                onButtonPress(3 /* Y - Delete */);
            }
            // MyGames Tab: "[+] Записи 4IFIR (SD)" button: x in [1000, 1230], y in [195, 240]
            else if (m_activeTab == Tab::MyGames && mx >= 1000 && mx <= 1230 && my >= 195 && my <= 240) {
                if (!m_installedGames.empty() && m_myGamesSelectedIndex >= 0 &&
                    m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    openRecordingsBrowser(g.titleId, g.name);
                }
            }
            // MyGames Tab: "Восстановить (.bak)" button: x in [950, 1230], y in [205, 250]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 205 && my <= 250) {
                onButtonPress(2 /* X - Restore */);
            }
            // MyGames Tab: click directly on an item in left list
            else if (m_activeTab == Tab::MyGames && mx >= 30 && mx <= 480 && my >= 105 && my <= 640) {
                int clickedIndex = m_myGamesScrollOffset + (my - 105) / 66;
                if (clickedIndex >= 0 && clickedIndex < static_cast<int>(m_installedGames.size())) {
                    m_myGamesSelectedIndex = clickedIndex;
                    m_selectedVariantIndex = 0;
                }
            }
            // MyGames Tab: click on variant install button in right pane
            else if (m_activeTab == Tab::MyGames && mx >= 1050 && mx <= 1220 && my >= 285 && my <= 600) {
                onButtonPress(0 /* A - Install */);
            }"""

new_mygames_touch = """            // MyGames Tab: synchronized pixel-perfect touch zones
            else if (m_activeTab == Tab::MyGames) {
                // Left Column: Games list item selection (x in [30, 480], y in [105, 640])
                if (mx >= 30 && mx <= 480 && my >= 105 && my <= 640) {
                    int clickedIdx = m_myGamesScrollOffset + (my - 105) / 66;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_installedGames.size())) {
                        if (m_myGamesSelectedIndex == clickedIdx) {
                            const auto& g = m_installedGames[clickedIdx];
                            if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                                openCollectionBrowser(g.catalogEntry);
                            } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                                m_myGamesActivePane = MyGamesPane::VariantsList;
                            }
                        } else {
                            m_myGamesSelectedIndex = clickedIdx;
                            m_selectedVariantIndex = 0;
                            m_variantScrollOffset = 0;
                            m_myGamesActivePane = MyGamesPane::GamesList;
                        }
                    }
                }
                // Right Column Action buttons at y in [200, 240]
                else if (my >= 200 && my <= 240) {
                    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                        if (selGame.hasInstalledCover) {
                            // "[Y] Удалить активный фон": x in [530, 760]
                            if (mx >= 530 && mx <= 760) {
                                onButtonPress(3 /* Y - Delete */);
                            }
                            // "[R] Восстановить (.bak)": x in [770, 1000]
                            else if (mx >= 770 && mx <= 1000 && selGame.hasBackup) {
                                executeRestoreBackup(selGame.titleId);
                            }
                            // "[+] Записи 4IFIR (SD)": x in [1015, 1225]
                            else if (mx >= 1015 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        } else {
                            // "[Y] Установить все": x in [530, 780]
                            if (mx >= 530 && mx <= 780 && getMissingCoversCount() > 0) {
                                installAllMissing();
                            }
                            // "[+] Записи 4IFIR (SD)": x in [1015, 1225]
                            else if (mx >= 1015 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        }
                    }
                }
                // Right Column Variant Cards (y in [280, 600])
                else if (mx >= 525 && mx <= 1225 && my >= 280 && my <= 600) {
                    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                        int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                        if (totalV > 0) {
                            int vClicked = m_variantScrollOffset + (my - 280) / 80;
                            if (vClicked >= 0 && vClicked < totalV) {
                                m_selectedVariantIndex = vClicked;
                                m_myGamesActivePane = MyGamesPane::VariantsList;
                                if (mx >= 1005 && mx <= 1210) {
                                    onButtonPress(0 /* A - Install */);
                                }
                            }
                        } else {
                            // No direct variants: "Открыть каталог" button at x in [530, 1010], y in [350, 410]
                            if (mx >= 530 && mx <= 1010 && my >= 350 && my <= 410) {
                                m_activeTab = Tab::Catalog;
                            }
                        }
                    }
                }
            }
            // Downloads Tab: touch clear button
            else if (m_activeTab == Tab::Downloads) {
                if (my >= 660 && mx >= 30 && mx <= 350) {
                    onButtonPress(2 /* X - Clear */);
                }
            }"""

assert old_mygames_touch in content, "old_mygames_touch not found!"
content = content.replace(old_mygames_touch, new_mygames_touch, 1)
print("[+] Patched Tab::MyGames and Tab::Downloads touch zones")

# 5. Patch Fullscreen Preview [Y] and [A] in onButtonPress
old_preview_buttons = """            } else if (button == 3 /* Y - Assign to another game */) {
                openGamePicker(m_previewVariants[m_previewVariantIndex], m_previewGameName);
                return;
            } else if (button == 0 /* A - Install / Save */) {
                if (m_previewTitleId == "0000000000000000") {
                    openGamePicker(m_previewVariants[m_previewVariantIndex], m_previewGameName);
                    return;
                }
                closeFullscreenPreview();
                m_pendingActionTitleId = m_previewTitleId;
                m_pendingActionVariant = m_previewVariants[m_previewVariantIndex];
                m_activeDialog = DialogType::ConfirmInstall;"""

new_preview_buttons = """            } else if (button == 3 /* Y - Assign to another game */) {
                Variant var = m_previewVariants[m_previewVariantIndex];
                std::string gName = m_previewGameName;
                closeFullscreenPreview();
                openGamePicker(var, gName);
                return;
            } else if (button == 0 /* A - Install / Save */) {
                if (m_previewTitleId == "0000000000000000") {
                    Variant var = m_previewVariants[m_previewVariantIndex];
                    std::string gName = m_previewGameName;
                    closeFullscreenPreview();
                    openGamePicker(var, gName);
                    return;
                }
                Variant chosenVar = m_previewVariants[m_previewVariantIndex];
                std::string titleId = m_previewTitleId;
                std::string gName = m_previewGameName;
                bool isInstalled = m_previewIsGameInstalled;
                closeFullscreenPreview();
                m_pendingActionTitleId = titleId;
                m_pendingActionVariant = chosenVar;
                if (m_pendingActionVariant.id.rfind("local:", 0) == 0) {
                    m_pendingRecordingToInstallPath = m_pendingActionVariant.url;
                    m_pendingRecordingToInstallName = m_pendingActionVariant.name;
                    m_activeDialog = DialogType::ConfirmInstallLocalRecording;
                    m_dialogOpenedAt = SDL_GetTicks();
                    m_dialogTitle = (m_language == Language::Russian) ? "Установка записи" : "Install Recording";
                    m_dialogMessage = (m_language == Language::Russian)
                        ? ("Установить запись '" + m_pendingRecordingToInstallName + "' в качестве видеофона для игры " + gName + "?")
                        : ("Install recording '" + m_pendingRecordingToInstallName + "' as video theme for " + gName + "?");
                    m_dialogFocus = 0;
                    return;
                }
                m_activeDialog = DialogType::ConfirmInstall;"""

assert old_preview_buttons in content, "old_preview_buttons not found!"
content = content.replace(old_preview_buttons, new_preview_buttons, 1)
print("[+] Patched Fullscreen Preview [Y] and [A] button handling")

# 6. Patch Tab::MyGames [X] button when game has no direct variants
old_mygames_x = """            } else if (button == 2 /* X - Fullscreen Preview */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        openFullscreenPreviewForGame(g, m_selectedVariantIndex);
                    } else {
                        m_statusNotification = (m_language == Language::Russian)
                            ? "Нет доступных видео для предпросмотра"
                            : "No video preview available";
                        m_notificationFramesRemaining = 120;
                    }
                }
            }"""

new_mygames_x = """            } else if (button == 2 /* X - Fullscreen Preview or Open Catalog */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        openFullscreenPreviewForGame(g, m_selectedVariantIndex);
                    } else {
                        m_activeTab = Tab::Catalog;
                    }
                }
            }"""

assert old_mygames_x in content, "old_mygames_x not found!"
content = content.replace(old_mygames_x, new_mygames_x, 1)
print("[+] Patched Tab::MyGames [X] button fallback to catalog")

# 7. Patch Tab::Downloads ZL/ZR fast scroll
old_downloads_input = """    } else if (m_activeTab == Tab::Downloads) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 2 /* X - Clear finished/failed tasks */) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            m_downloadQueue.erase(
                std::remove_if(m_downloadQueue.begin(), m_downloadQueue.end(),
                    [](const DownloadTask& t) {
                        return t.state == TaskState::Completed || t.state == TaskState::Failed;
                    }),
                m_downloadQueue.end()
            );
            m_statusNotification = (m_language == Language::Russian) ? "Завершённые задачи очищены" : "Finished tasks cleared";
            m_notificationFramesRemaining = 90;
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_downloadsScrollOffset > 0) m_downloadsScrollOffset--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_downloadsScrollOffset + 5 < static_cast<int>(m_downloadQueue.size())) m_downloadsScrollOffset++;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        }
    }"""

new_downloads_input = """    } else if (m_activeTab == Tab::Downloads) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 2 /* X - Clear finished/failed tasks */) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            m_downloadQueue.erase(
                std::remove_if(m_downloadQueue.begin(), m_downloadQueue.end(),
                    [](const DownloadTask& t) {
                        return t.state == TaskState::Completed || t.state == TaskState::Failed;
                    }),
                m_downloadQueue.end()
            );
            m_statusNotification = (m_language == Language::Russian) ? "Завершённые задачи очищены" : "Finished tasks cleared";
            m_notificationFramesRemaining = 90;
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_downloadsScrollOffset > 0) m_downloadsScrollOffset--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_downloadsScrollOffset + 5 < static_cast<int>(m_downloadQueue.size())) m_downloadsScrollOffset++;
        } else if (button == 15 /* ZL - Fast Page Up 5 */) {
            m_downloadsScrollOffset = std::max(0, m_downloadsScrollOffset - 5);
        } else if (button == 16 /* ZR - Fast Page Down 5 */) {
            int maxOff = std::max(0, static_cast<int>(m_downloadQueue.size()) - 5);
            m_downloadsScrollOffset = std::min(maxOff, m_downloadsScrollOffset + 5);
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        }
    }"""

assert old_downloads_input in content, "old_downloads_input not found!"
content = content.replace(old_downloads_input, new_downloads_input, 1)
print("[+] Patched Tab::Downloads ZL/ZR fast scroll")

# 8. Patch renderTabMyGames label for no direct variants
old_ad_label = """            drawGlassCard(530, 350, 480, 56, true, false);
            drawText((m_language == Language::Russian ? "[X] Открыть каталог After Dark" : "[X] Open After Dark Catalog"),
                     555, 368, Theme::COLOR_FOCUS_CYAN, 16);"""

new_ad_label = """            drawGlassCard(530, 350, 480, 56, true, false);
            std::string catBtnText = Config::isAfterDark()
                ? (m_language == Language::Russian ? "[X] Открыть каталог After Dark" : "[X] Open After Dark Catalog")
                : (m_language == Language::Russian ? "[X] Открыть онлайн-каталог" : "[X] Open Online Catalog");
            drawText(catBtnText, 555, 368, Theme::COLOR_FOCUS_CYAN, 16);"""

assert old_ad_label in content, "old_ad_label not found!"
content = content.replace(old_ad_label, new_ad_label, 1)
print("[+] Patched renderTabMyGames dynamic catalog button label")

# 9. Patch rebuildCatalogFilter with utf8ToLower
old_filter = """void App::rebuildCatalogFilter() {
    const auto& allGames = m_catalogManager.getAllGames();
    m_filteredCatalogGames.clear();

    std::string qLower = m_catalogSearchQuery;
    std::transform(qLower.begin(), qLower.end(), qLower.begin(), [](unsigned char c) {
        return std::tolower(c);
    });

    for (const auto& g : allGames) {
        // 1. Search Query filter
        if (!qLower.empty()) {
            std::string titleLower = g.title;
            std::transform(titleLower.begin(), titleLower.end(), titleLower.begin(), [](unsigned char c) {
                return std::tolower(c);
            });
            std::string tidLower = g.titleId;
            std::transform(tidLower.begin(), tidLower.end(), tidLower.begin(), [](unsigned char c) {
                return std::tolower(c);
            });

            bool match = (titleLower.find(qLower) != std::string::npos) ||
                         (tidLower.find(qLower) != std::string::npos);
            if (!match) {
                for (const auto& v : g.variants) {
                    std::string vname = v.name;
                    std::transform(vname.begin(), vname.end(), vname.begin(), [](unsigned char c) {
                        return std::tolower(c);
                    });
                    if (vname.find(qLower) != std::string::npos) {
                        match = true;
                        break;
                    }
                }
            }
            if (!match) continue;
        }"""

new_filter = """void App::rebuildCatalogFilter() {
    const auto& allGames = m_catalogManager.getAllGames();
    m_filteredCatalogGames.clear();

    std::string qLower = utf8ToLower(m_catalogSearchQuery);

    for (const auto& g : allGames) {
        // 1. Search Query filter (matches Title, Title ID, Publisher, and Variant Names in EN and RU)
        if (!qLower.empty()) {
            std::string titleLower = utf8ToLower(g.title);
            std::string tidLower = utf8ToLower(g.titleId);
            std::string pubLower = utf8ToLower(g.publisher);

            bool match = (titleLower.find(qLower) != std::string::npos) ||
                         (tidLower.find(qLower) != std::string::npos) ||
                         (pubLower.find(qLower) != std::string::npos);
            if (!match) {
                for (const auto& v : g.variants) {
                    std::string vname = utf8ToLower(v.name);
                    if (vname.find(qLower) != std::string::npos) {
                        match = true;
                        break;
                    }
                }
            }
            if (!match) continue;
        }"""

assert old_filter in content, "old_filter not found!"
content = content.replace(old_filter, new_filter, 1)
print("[+] Patched rebuildCatalogFilter with full UTF-8 Cyrillic & English search")

# 10. Patch openCatalogKeyboard header text
old_kbd = """        swkbdConfigMakePresetDefault(&kbd);
        swkbdConfigSetHeaderText(&kbd, "Поиск по каталогу H3H Backgrounds");"""

new_kbd = """        swkbdConfigMakePresetDefault(&kbd);
        swkbdConfigSetHeaderText(&kbd, Config::isAfterDark() ? "Поиск по каталогу H3H After Dark" : "Поиск по каталогу H3H Backgrounds");"""

assert old_kbd in content, "old_kbd not found!"
content = content.replace(old_kbd, new_kbd, 1)
print("[+] Patched openCatalogKeyboard with dynamic header text")

app_path.write_text(content, encoding="utf-8")
print("[SUCCESS] All 10 improvements applied to app.cpp successfully!")
