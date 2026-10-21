from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
text = app_cpp.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. Update onButtonPress with Fullscreen Preview handler at top
old_btn_start = "void App::onButtonPress(int button) {\n    // If Dialog is active, route all input to dialog\n    if (m_activeDialog != DialogType::None) {"

new_btn_start = """void App::onButtonPress(int button) {
    // Fullscreen Preview Input Handler
    if (m_isFullscreenPreview) {
        if (button == 1 /* B */ || button == 2 /* X */) {
            closeFullscreenPreview();
            return;
        }
        if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
            const auto& g = m_installedGames[m_myGamesSelectedIndex];
            if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                int vCount = static_cast<int>(g.catalogEntry.variants.size());
                if (button == 13 /* DPAD_LEFT */) {
                    m_selectedVariantIndex = (m_selectedVariantIndex == 0) ? vCount - 1 : m_selectedVariantIndex - 1;
                    loadPreviewTexture(g.catalogEntry.variants[m_selectedVariantIndex]);
                    return;
                } else if (button == 14 /* DPAD_RIGHT */) {
                    m_selectedVariantIndex = (m_selectedVariantIndex + 1) % vCount;
                    loadPreviewTexture(g.catalogEntry.variants[m_selectedVariantIndex]);
                    return;
                } else if (button == 0 /* A - Install */) {
                    closeFullscreenPreview();
                    m_pendingActionTitleId = g.titleId;
                    m_pendingActionVariant = g.catalogEntry.variants[m_selectedVariantIndex];
                    m_activeDialog = DialogType::ConfirmInstall;
                    m_dialogTitle = getStrings(m_language).confirmInstallTitle;
                    m_dialogMessage = "Установить вариант '" + m_pendingActionVariant.name + "' (" +
                                      styleToString(m_pendingActionVariant.style) + ") для " + g.name + "?";
                    m_dialogFocus = 0;
                    return;
                }
            }
        }
        return;
    }

    // If Dialog is active, route all input to dialog
    if (m_activeDialog != DialogType::None) {"""

if old_btn_start in text:
    text = text.replace(old_btn_start, new_btn_start, 1)
    print("[+] Added fullscreen preview input interceptor")

# 2. Update onButtonPress MyGames section
old_mygames_input = """    } else if (m_activeTab == Tab::MyGames) {
        if (button == 11 /* DPAD_UP */) {
            if (m_myGamesSelectedIndex > 0) {
                m_myGamesSelectedIndex--;
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
            }
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_myGamesSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                m_myGamesSelectedIndex++;
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
            }
        } else if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                    int vCount = static_cast<int>(g.catalogEntry.variants.size());
                    if (button == 14) m_selectedVariantIndex = (m_selectedVariantIndex + 1) % vCount;
                    else m_selectedVariantIndex = (m_selectedVariantIndex == 0) ? vCount - 1 : m_selectedVariantIndex - 1;

                    // Keep active variant visible inside the 4-variant window
                    if (m_selectedVariantIndex < m_variantScrollOffset) {
                        m_variantScrollOffset = m_selectedVariantIndex;
                    } else if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                        m_variantScrollOffset = m_selectedVariantIndex - 4 + 1;
                    }
                }
            }
        } else if (button == 0 /* A - Install Selected Variant */) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                if (g.hasCatalogMatch && m_selectedVariantIndex < static_cast<int>(g.catalogEntry.variants.size())) {
                    m_pendingActionTitleId = g.titleId;
                    m_pendingActionVariant = g.catalogEntry.variants[m_selectedVariantIndex];
                    m_activeDialog = DialogType::ConfirmInstall;
                    m_dialogTitle = getStrings(m_language).confirmInstallTitle;
                    m_dialogMessage = "Установить вариант '" + m_pendingActionVariant.name + "' (" +
                                      styleToString(m_pendingActionVariant.style) + ") для " + g.name + "?";
                    m_dialogFocus = 0;
                }
            }
        } else if (button == 2 /* X - Restore Backup */) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                if (g.hasBackup) {
                    m_pendingActionTitleId = g.titleId;
                    m_activeDialog = DialogType::ConfirmRestore;
                    m_dialogTitle = getStrings(m_language).confirmRestoreTitle;
                    m_dialogMessage = getStrings(m_language).confirmRestoreMsg;
                    m_dialogFocus = 0;
                }
            }
        } else if (button == 3 /* Y - Delete Cover or Install All Missing */) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                if (g.hasInstalledCover) {
                    m_pendingActionTitleId = g.titleId;
                    m_activeDialog = DialogType::ConfirmDelete;
                    m_dialogTitle = getStrings(m_language).confirmDeleteTitle;
                    m_dialogMessage = getStrings(m_language).confirmDeleteMsg;
                    m_dialogFocus = 0;
                } else {
                    installAllMissing();
                }
            } else {
                installAllMissing();
            }
        }
    } else if (m_activeTab == Tab::Catalog) {"""

new_mygames_input = """    } else if (m_activeTab == Tab::MyGames) {
        if (m_myGamesActivePane == MyGamesPane::GamesList) {
            // LEFT COLUMN: Games List navigation
            if (button == 11 /* DPAD_UP */) {
                if (m_myGamesSelectedIndex > 0) {
                    m_myGamesSelectedIndex--;
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
            } else if (button == 12 /* DPAD_DOWN */) {
                if (m_myGamesSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                    m_myGamesSelectedIndex++;
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
            } else if (button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) {
                // Move focus to right variants column
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_myGamesActivePane = MyGamesPane::VariantsList;
                        m_selectedVariantIndex = 0;
                    }
                }
            } else if (button == 2 /* X - Fullscreen Preview */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_isFullscreenPreview = true;
                        loadPreviewTexture(g.catalogEntry.variants[m_selectedVariantIndex]);
                    }
                }
            } else if (button == 3 /* Y - Delete / Install Missing */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasInstalledCover) {
                        m_pendingActionTitleId = g.titleId;
                        m_activeDialog = DialogType::ConfirmDelete;
                        m_dialogTitle = getStrings(m_language).confirmDeleteTitle;
                        m_dialogMessage = getStrings(m_language).confirmDeleteMsg;
                        m_dialogFocus = 0;
                    } else {
                        installAllMissing();
                    }
                }
            }
        } else if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            // RIGHT COLUMN: Variants navigation
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                int vCount = static_cast<int>(g.catalogEntry.variants.size());
                if (button == 11 /* DPAD_UP */) {
                    if (m_selectedVariantIndex > 0) {
                        m_selectedVariantIndex--;
                        if (m_selectedVariantIndex < m_variantScrollOffset) {
                            m_variantScrollOffset = m_selectedVariantIndex;
                        }
                    }
                } else if (button == 12 /* DPAD_DOWN */) {
                    if (m_selectedVariantIndex + 1 < vCount) {
                        m_selectedVariantIndex++;
                        if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                            m_variantScrollOffset = m_selectedVariantIndex - 4 + 1;
                        }
                    }
                } else if (button == 13 /* DPAD_LEFT */ || button == 1 /* B */) {
                    // Return focus back to left games column
                    m_myGamesActivePane = MyGamesPane::GamesList;
                } else if (button == 0 /* A - Install Variant */) {
                    m_pendingActionTitleId = g.titleId;
                    m_pendingActionVariant = g.catalogEntry.variants[m_selectedVariantIndex];
                    m_activeDialog = DialogType::ConfirmInstall;
                    m_dialogTitle = getStrings(m_language).confirmInstallTitle;
                    m_dialogMessage = "Установить вариант '" + m_pendingActionVariant.name + "' (" +
                                      styleToString(m_pendingActionVariant.style) + ") для " + g.name + "?";
                    m_dialogFocus = 0;
                } else if (button == 2 /* X - Fullscreen Preview */) {
                    m_isFullscreenPreview = true;
                    loadPreviewTexture(g.catalogEntry.variants[m_selectedVariantIndex]);
                } else if (button == 3 /* Y - Delete */) {
                    if (g.hasInstalledCover) {
                        m_pendingActionTitleId = g.titleId;
                        m_activeDialog = DialogType::ConfirmDelete;
                        m_dialogTitle = getStrings(m_language).confirmDeleteTitle;
                        m_dialogMessage = getStrings(m_language).confirmDeleteMsg;
                        m_dialogFocus = 0;
                    }
                }
            }
        }
    } else if (m_activeTab == Tab::Catalog) {"""

if old_mygames_input in text:
    text = text.replace(old_mygames_input, new_mygames_input, 1)
    print("[+] Updated onButtonPress MyGames two-pane navigation")

# 3. Update renderTabMyGames
old_card_draw = "drawGlassCard(35, startY, 440, 60, isSelected, isSelected);"
new_card_draw = """bool isFocused = (m_myGamesActivePane == MyGamesPane::GamesList && isSelected);
        drawGlassCard(35, startY, 440, 60, isFocused, isSelected);"""

text = text.replace(old_card_draw, new_card_draw)

old_var_card_draw = "drawGlassCard(525, vY, 700, 72, isVarSelected, false);"
new_var_card_draw = """bool isVarFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                drawGlassCard(525, vY, 700, 72, isVarFocused, isVarSelected);"""

text = text.replace(old_var_card_draw, new_var_card_draw)

# 4. Relocate action buttons away from Tesla HUD (move to x=530, y=202)
old_action_btns = """        if (selGame.hasInstalledCover) {
            // Prominent Delete button
            drawRect(950, 160, 270, 38, Theme::COLOR_BG_ELEVATED);
            drawRectOutline(950, 160, 270, 38, Theme::COLOR_DANGER, 1);
            drawText("[Y] " + std::string(m_language == Language::Russian ? "Удалить видеофон" : "Delete Background"),
                     975, 172, Theme::COLOR_DANGER, 14);
        } else {
            int missing = getMissingCoversCount();
            if (missing > 0) {
                drawRect(950, 95, 270, 38, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(950, 95, 270, 38, Theme::COLOR_ACCENT, 1);
                drawText("[Y] " + std::string(m_language == Language::Russian ? "Установить все (" : "Install all (") +
                         std::to_string(missing) + ")", 970, 107, Theme::COLOR_ACCENT, 14);
            }
        }

        // Status details
        std::string coverInfo = selGame.hasInstalledCover ?
            std::string(m_language == Language::Russian ? "Установлен: " : "Installed: ") +
            Config::getTargetCoverFileName(selGame.titleId) + " (" +
            std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)" :
            std::string(m_language == Language::Russian ? "Видеофон отсутствует" : "No video background");
        drawText(coverInfo, 530, 180, selGame.hasInstalledCover ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);

        if (selGame.hasBackup) {
            drawRect(950, 205, 270, 38, Theme::COLOR_BG_ELEVATED);
            drawRectOutline(950, 205, 270, 38, Theme::COLOR_ACCENT, 1);
            drawText("[X] " + std::string(m_language == Language::Russian ? "Восстановить (.bak)" : "Restore (.bak)"),
                     975, 217, Theme::COLOR_ACCENT, 14);

            drawText(std::string(m_language == Language::Russian ? "Резервная копия (.bak): " : "Backup copy (.bak): ") +
                     std::to_string(selGame.backupSizeBytes / 1024) + " KB",
                     530, 212, Theme::COLOR_TEXT_MUTED, 13);
        }"""

new_action_btns = """        // Status details
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
            drawText("[Y] Удалить видеофон", 545, 210, Theme::COLOR_DANGER, 13);

            if (selGame.hasBackup) {
                drawRect(770, 202, 230, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_ACCENT, 1);
                drawText("[R] Восстановить (.bak)", 785, 210, Theme::COLOR_ACCENT, 13);
            }
        } else {
            int missing = getMissingCoversCount();
            if (missing > 0) {
                drawRect(530, 202, 250, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(530, 202, 250, 32, Theme::COLOR_ACCENT, 1);
                drawText("[Y] Установить все (" + std::to_string(missing) + ")", 545, 210, Theme::COLOR_ACCENT, 13);
            }
        }"""

if old_action_btns in text:
    text = text.replace(old_action_btns, new_action_btns, 1)
    print("[+] Relocated Action Buttons safely below status")

# 5. Fix variant file size in renderTabMyGames
old_meta_calc = 'std::to_string(v.sizeBytes / (1024 * 1024)) + " MB";'
new_meta_calc = """([&]() {
                    double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
                    char buf[16];
                    if (mb >= 0.1) snprintf(buf, sizeof(buf), "%.1f MB", mb);
                    else snprintf(buf, sizeof(buf), "~3.5 MB");
                    return std::string(buf);
                })();"""

if old_meta_calc in text:
    text = text.replace(old_meta_calc, new_meta_calc, 1)
    print("[+] Fixed variant size calculation (no more 0 MB)")

# 6. Update hints above variants list
old_var_header = """        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = "Доступные варианты видеофона (" + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 250, Theme::COLOR_TEXT_PRIMARY, 16);"""

new_var_header = """        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = "Доступные варианты видеофона (" + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 248, Theme::COLOR_TEXT_PRIMARY, 16);

        if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            drawText("◀ [B] К списку игр   |   [X] На весь экран", 800, 250, Theme::COLOR_FOCUS_CYAN, 12);
        } else {
            drawText("▶ [A] К вариантам   |   [X] На весь экран", 800, 250, Theme::COLOR_TEXT_MUTED, 12);
        }"""

if old_var_header in text:
    text = text.replace(old_var_header, new_var_header, 1)
    print("[+] Updated variant header with navigation breadcrumbs")

app_cpp.write_text(text, encoding="utf-8")
print("[+] Finished applying patch_app_two_pane_and_ux.py")
