# scripts/patch_app_cpp_v120.py
from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
text = p.read_text(encoding="utf-8")

# 1. Update refreshInstalledGames() to recognize local recordings
old_refresh = """            if (!regVarId.empty()) {
                for (const auto& v : game.catalogEntry.variants) {
                    if (v.id == regVarId) {
                        game.installedVariantId = regVarId;
                        break;
                    }
                }
            }"""

new_refresh = """            if (!regVarId.empty()) {
                if (regVarId.rfind("local:", 0) == 0) {
                    game.installedVariantId = regVarId;
                    std::string clipName = regVarId.substr(6);
                    bool hasLocal = false;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.id == regVarId) { hasLocal = true; break; }
                    }
                    if (!hasLocal) {
                        Variant localVar;
                        localVar.id = regVarId;
                        localVar.name = "Запись 4IFIR: " + clipName;
                        localVar.style = CoverStyle::Gameplay;
                        localVar.url = game.installedCoverPath;
                        localVar.previewUrl = game.installedCoverPath;
                        localVar.notes = "Собственный клип из sdmc:/recordings/";
                        game.catalogEntry.variants.insert(game.catalogEntry.variants.begin(), localVar);
                    }
                } else {
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.id == regVarId) {
                            game.installedVariantId = regVarId;
                            break;
                        }
                    }
                }
            }"""

text = text.replace(old_refresh, new_refresh)

# 2. Add local recording card & footer hint in renderTabMyGames
old_mygames_hint = """hints = "[L/R] Вкладки   [▲/▼] Игры   [A] Выбор / Варианты   [X] Предпросмотр   [Y] Удалить   [B] Восстановить";"""
new_mygames_hint = """hints = "[▲/▼] Навигация   [A] Выбор/Панель   [X] Предпросмотр   [+] Записи SD   [Y] Удалить";"""
text = text.replace(old_mygames_hint, new_mygames_hint)

# 3. In renderTabSettings, adjust rows to 6 items and spacing
old_settings_rows = """    std::string freeGb = std::to_string(m_sysInfo.freeStorageBytes / (1024 * 1024 * 1024)) + " GB свободно";
    std::vector<SettingRow> rows = {
        {"Обновление приложения (NRO)", "Проверить и установить новую версию H3H-Backgrounds.nro с GitHub", std::string("v") + Config::APP_VERSION + " [A - Проверить]", Theme::COLOR_FOCUS_CYAN},
        {"Обновление каталога видеофонов", "Загрузить новейший каталог игр и обложек без обновления NRO", "GitHub Releases [A]", Theme::COLOR_FOCUS_CYAN},
        {"Язык интерфейса / Language", "Выбор языка отображения меню и подсказок управления", (m_language == Language::Russian ? "Русский [A]" : "English [A]"), Theme::COLOR_TEXT_PRIMARY},
        {"Очистить локальный кэш каталога", "Сбросить локальный файл cache.json и пересканировать игры", "[A / X] Сброс", Theme::COLOR_WARNING},
        {"Память на карте MicroSD", "Доступное свободное пространство для загрузки видеофонов", freeGb, Theme::COLOR_SUCCESS}
    };

    int rowY = 175;
    for (size_t i = 0; i < rows.size(); ++i) {
        bool isFocused = (static_cast<int>(i) == m_settingsSelectedIndex);

        // Row background
        if (isFocused) {
            drawRect(50, rowY, 1180, 72, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(50, rowY, 1180, 72, 2);
        } else {
            drawRect(50, rowY, 1180, 72, Theme::COLOR_BG_SURFACE);
            drawRectOutline(50, rowY, 1180, 72, Theme::COLOR_BORDER, 1);
        }

        // Title and description
        drawText(rows[i].title, 75, rowY + 14, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17, 850);
        drawText(rows[i].desc, 75, rowY + 42, Theme::COLOR_TEXT_MUTED, 13, 850);

        // Right value pill
        drawText(rows[i].value, 950, rowY + 26, rows[i].valColor, 15, 260);

        rowY += 84;
    }"""

new_settings_rows = """    std::string freeGb = std::to_string(m_sysInfo.freeStorageBytes / (1024 * 1024 * 1024)) + " GB свободно";
    std::vector<SettingRow> rows = {
        {"Обновление приложения (NRO)", "Проверить и установить новую версию H3H-Backgrounds.nro с GitHub", std::string("v") + Config::APP_VERSION + " [A - Проверить]", Theme::COLOR_FOCUS_CYAN},
        {"Обновление каталога видеофонов", "Загрузить новейший каталог игр и обложек без обновления NRO", "GitHub Releases [A]", Theme::COLOR_FOCUS_CYAN},
        {"Язык интерфейса / Language", "Выбор языка отображения меню и подсказок управления", (m_language == Language::Russian ? "Русский [A]" : "English [A]"), Theme::COLOR_TEXT_PRIMARY},
        {"Очистить локальный кэш каталога", "Сбросить локальный файл cache.json и пересканировать игры", "[A / X] Сброс", Theme::COLOR_WARNING},
        {"Память на карте MicroSD", "Доступное свободное пространство для загрузки видеофонов", freeGb, Theme::COLOR_SUCCESS},
        {"Проверка целостности фонов", "Сканирование установленных видеофонов на ошибки и битые файлы", "[A] Сканировать", Theme::COLOR_FOCUS_CYAN}
    };

    int rowY = 165;
    for (size_t i = 0; i < rows.size(); ++i) {
        bool isFocused = (static_cast<int>(i) == m_settingsSelectedIndex);

        // Row background
        if (isFocused) {
            drawRect(50, rowY, 1180, 62, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(50, rowY, 1180, 62, 2);
        } else {
            drawRect(50, rowY, 1180, 62, Theme::COLOR_BG_SURFACE);
            drawRectOutline(50, rowY, 1180, 62, Theme::COLOR_BORDER, 1);
        }

        // Title and description
        drawText(rows[i].title, 75, rowY + 11, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 850);
        drawText(rows[i].desc, 75, rowY + 36, Theme::COLOR_TEXT_MUTED, 12, 850);

        // Right value pill
        drawText(rows[i].value, 940, rowY + 20, rows[i].valColor, 15, 270);

        rowY += 70;
    }"""

text = text.replace(old_settings_rows, new_settings_rows)

# 4. In render(), render recordings browser if open
old_render_call = """    renderFooter();

    if (m_activeDialog != DialogType::None) {
        renderDialog();
    }"""

new_render_call = """    renderFooter();

    if (m_isRecordingsBrowserOpen) {
        renderRecordingsBrowser();
    }

    if (m_activeDialog != DialogType::None) {
        renderDialog();
    }"""

text = text.replace(old_render_call, new_render_call)

# 5. In onButtonPress, handle dialogs and recordings browser
old_dialog_checks = """        if (m_activeDialog == DialogType::MessageAlert) {
            if (button == 0 || button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }"""

new_dialog_checks = """        if (m_activeDialog == DialogType::MessageAlert || m_activeDialog == DialogType::IntegrityCheckResult) {
            if (button == 0 || button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::ConfirmInstallLocalRecording) {
            if (button == 0) {
                m_activeDialog = DialogType::None;
                executeInstallLocalRecording();
            } else if (button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::ConfirmDeleteCorrupted) {
            if (button == 13 || button == 14) {
                m_dialogFocus = 1 - m_dialogFocus;
            } else if (button == 0) {
                if (m_dialogFocus == 0) {
                    m_activeDialog = DialogType::None;
                    executeDeleteCorruptedCovers();
                } else {
                    m_activeDialog = DialogType::None;
                }
            } else if (button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }"""

text = text.replace(old_dialog_checks, new_dialog_checks)

# 6. Add recordings browser input handler at top of onButtonPress
old_on_button = """void App::onButtonPress(int button) {
    // Fullscreen Preview Input Handler
    if (m_isFullscreenPreview) {"""

new_on_button = """void App::onButtonPress(int button) {
    // Local Recordings Browser Handler (Feature 3)
    if (m_isRecordingsBrowserOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview) {
        if (button == 1 /* B */) {
            closeRecordingsBrowser();
            return;
        }
        if (button == 11 /* UP */) {
            if (m_recordingsSelectedIndex > 0) m_recordingsSelectedIndex--;
            return;
        }
        if (button == 12 /* DOWN */) {
            if (m_recordingsSelectedIndex + 1 < static_cast<int>(m_localRecordings.size())) {
                m_recordingsSelectedIndex++;
            }
            return;
        }
        if (button == 2 /* X - Preview clip */) {
            if (!m_localRecordings.empty() && m_recordingsSelectedIndex >= 0 &&
                m_recordingsSelectedIndex < static_cast<int>(m_localRecordings.size())) {
                const auto& rec = m_localRecordings[m_recordingsSelectedIndex];
                Variant clipVar;
                clipVar.id = "local:" + rec.filename;
                clipVar.name = rec.filename;
                clipVar.style = CoverStyle::Gameplay;
                clipVar.url = rec.fullPath;
                clipVar.previewUrl = rec.fullPath;
                m_previewVariants = {clipVar};
                m_previewVariantIndex = 0;
                m_previewTitleId = m_recordingsTargetTitleId;
                m_previewGameName = m_recordingsTargetGameName;
                m_previewIsGameInstalled = true;
                m_previewHasInstalledCover = false;
                m_isFullscreenPreview = true;
                m_videoPlayer.open(rec.fullPath);
            }
            return;
        }
        if (button == 0 /* A - Install clip */) {
            if (!m_localRecordings.empty() && m_recordingsSelectedIndex >= 0 &&
                m_recordingsSelectedIndex < static_cast<int>(m_localRecordings.size())) {
                const auto& rec = m_localRecordings[m_recordingsSelectedIndex];
                m_pendingRecordingToInstallPath = rec.fullPath;
                m_pendingRecordingToInstallName = rec.filename;
                m_activeDialog = DialogType::ConfirmInstallLocalRecording;
                m_dialogTitle = "Установка видеофона";
                m_dialogMessage = "Установить запись '" + rec.filename +
                                  "' в качестве видеофона для игры " + m_recordingsTargetGameName + "?";
                m_dialogFocus = 0;
            }
            return;
        }
        return;
    }

    // Fullscreen Preview Input Handler
    if (m_isFullscreenPreview) {"""

text = text.replace(old_on_button, new_on_button)

# 7. Add [+] (Plus) button in MyGames
old_mygames_input = """        } else if (button == 3 /* Y - Delete / Backup action */) {"""
new_mygames_input = """        } else if (button == 6 /* Plus - Browse SD Recordings */) {
            if (!m_installedGames.empty() && m_myGamesSelectedIndex >= 0 &&
                m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                openRecordingsBrowser(selGame.titleId, selGame.name);
                return;
            }
        } else if (button == 3 /* Y - Delete / Backup action */) {"""
text = text.replace(old_mygames_input, new_mygames_input, 1)

# 8. In Settings input handling, allow 6 rows and trigger integrity check
old_settings_input = """        if (button == 11 /* DPAD_UP */) {
            if (m_settingsSelectedIndex > 0) m_settingsSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_settingsSelectedIndex < 4) m_settingsSelectedIndex++;
        } else if (button == 0 /* A - Activate Selected Setting */) {
            if (m_settingsSelectedIndex == 0) {
                updateApplicationNro();
            } else if (m_settingsSelectedIndex == 1) {
                fetchRemoteCatalog();
            } else if (m_settingsSelectedIndex == 2) {
                m_language = (m_language == Language::Russian ? Language::English : Language::Russian);
            } else if (m_settingsSelectedIndex == 3) {
                std::string cachePath = m_platform->getAppDirectory() + "/cache.json";
                std::error_code ec;
                std::filesystem::remove(cachePath, ec);
                refreshInstalledGames();
                m_statusNotification = (m_language == Language::Russian)
                    ? "Локальный кэш каталога очищен!"
                    : "Local catalog cache cleared!";
                m_notificationFramesRemaining = 120;
            }
        }"""

new_settings_input = """        if (button == 11 /* DPAD_UP */) {
            if (m_settingsSelectedIndex > 0) m_settingsSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_settingsSelectedIndex < 5) m_settingsSelectedIndex++;
        } else if (button == 0 /* A - Activate Selected Setting */) {
            if (m_settingsSelectedIndex == 0) {
                updateApplicationNro();
            } else if (m_settingsSelectedIndex == 1) {
                fetchRemoteCatalog();
            } else if (m_settingsSelectedIndex == 2) {
                m_language = (m_language == Language::Russian ? Language::English : Language::Russian);
            } else if (m_settingsSelectedIndex == 3) {
                std::string cachePath = m_platform->getAppDirectory() + "/cache.json";
                std::error_code ec;
                std::filesystem::remove(cachePath, ec);
                refreshInstalledGames();
                m_statusNotification = (m_language == Language::Russian)
                    ? "Локальный кэш каталога очищен!"
                    : "Local catalog cache cleared!";
                m_notificationFramesRemaining = 120;
            } else if (m_settingsSelectedIndex == 5) {
                runIntegrityCheck();
            }
        }"""

text = text.replace(old_settings_input, new_settings_input)

# 9. In loadPreviewTexture, handle local: variant id immediately without download
old_preview_check = """    bool isThisVariantInstalled = (m_previewHasInstalledCover && variant.id == m_previewInstalledVariantId);
    if (isThisVariantInstalled && !m_previewInstalledCoverPath.empty()) {
        m_pendingVideoToOpen = m_previewInstalledCoverPath;
        m_previewLoading = false;
        m_videoDownloading = false;
        return;
    }"""

new_preview_check = """    bool isThisVariantInstalled = (m_previewHasInstalledCover && variant.id == m_previewInstalledVariantId);
    if (variant.id.rfind("local:", 0) == 0 || (isThisVariantInstalled && !m_previewInstalledCoverPath.empty())) {
        m_pendingVideoToOpen = !m_previewInstalledCoverPath.empty() ? m_previewInstalledCoverPath : variant.url;
        m_previewLoading = false;
        m_videoDownloading = false;
        return;
    }"""

text = text.replace(old_preview_check, new_preview_check)

# 10. Implement new methods at the end of app.cpp
new_methods = """
void App::openRecordingsBrowser(const std::string& titleId, const std::string& gameName) {
    m_recordingsTargetTitleId = titleId;
    m_recordingsTargetGameName = gameName;
    m_localRecordings = Installer::listLocalRecordings(m_platform->getRecordingsDirectory());
    m_recordingsSelectedIndex = 0;
    m_recordingsScrollOffset = 0;
    m_isRecordingsBrowserOpen = true;
}

void App::closeRecordingsBrowser() {
    m_isRecordingsBrowserOpen = false;
}

void App::renderRecordingsBrowser() {
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x02, 0x05, 0x0C, 0xEE});

    // 4IFIR Frosted Glass Modal Container
    int bw = 1140;
    int bh = 600;
    int bx = (Theme::SCREEN_WIDTH - bw) / 2;
    int by = (Theme::SCREEN_HEIGHT - bh) / 2;

    drawGlassCard(bx, by, bw, bh, false, true);
    drawNeonGradientOutline(bx, by, bw, bh, 2);

    // Header
    drawText("4IFIR Recordings Library  |  sdmc:/recordings/", bx + 35, by + 25, Theme::COLOR_FOCUS_CYAN, 20);
    std::string subtitle = "Привязать геймплейную запись к: " + m_recordingsTargetGameName + " [" + m_recordingsTargetTitleId + "]";
    drawText(subtitle, bx + 35, by + 55, Theme::COLOR_TEXT_MUTED, 13, bw - 70);

    if (m_localRecordings.empty()) {
        drawGlassCard(bx + 40, by + 120, bw - 80, 360, false, false);
        drawText("В папке sdmc:/recordings/ не найдено видеофайлов (.mp4).", bx + 70, by + 240, Theme::COLOR_WARNING, 18);
        drawText("Запишите геймплей на Switch через рекордер 4IFIR, и ваши ролики появятся здесь!", bx + 70, by + 280, Theme::COLOR_TEXT_MUTED, 14);
    } else {
        int visibleCount = 5;
        if (m_recordingsSelectedIndex < m_recordingsScrollOffset) {
            m_recordingsScrollOffset = m_recordingsSelectedIndex;
        } else if (m_recordingsSelectedIndex >= m_recordingsScrollOffset + visibleCount) {
            m_recordingsScrollOffset = m_recordingsSelectedIndex - visibleCount + 1;
        }

        int itemY = by + 95;
        int itemH = 78;
        int maxIdx = std::min(m_recordingsScrollOffset + visibleCount, static_cast<int>(m_localRecordings.size()));

        for (int i = m_recordingsScrollOffset; i < maxIdx; ++i) {
            bool isFocused = (i == m_recordingsSelectedIndex);
            const auto& rec = m_localRecordings[i];

            if (isFocused) {
                drawRect(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(bx + 35, itemY, bw - 70, itemH, 2);
            } else {
                drawRect(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_BG_SURFACE);
                drawRectOutline(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_BORDER, 1);
            }

            // Video Tag
            drawRect(bx + 55, itemY + 20, 60, 38, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BG_ELEVATED);
            drawText("MP4", bx + 70, itemY + 31, isFocused ? Theme::COLOR_BG_BASE : Theme::COLOR_FOCUS_CYAN, 14);

            // Filename & Path
            drawText(rec.filename, bx + 130, itemY + 16, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, bw - 380);
            drawText(rec.fullPath, bx + 130, itemY + 44, Theme::COLOR_TEXT_MUTED, 12, bw - 380);

            // Size Pill
            drawText(rec.formattedSize, bx + bw - 220, itemY + 28, Theme::COLOR_FOCUS_CYAN, 15);

            itemY += itemH + 10;
        }

        // Counter Indicator
        std::string countStr = std::to_string(m_recordingsSelectedIndex + 1) + " / " + std::to_string(m_localRecordings.size());
        drawText(countStr, bx + bw - 130, by + 30, Theme::COLOR_TEXT_MUTED, 14);
    }

    // Bottom Help Banner
    drawRect(bx + 35, by + bh - 55, bw - 70, 38, Theme::COLOR_BG_BASE);
    drawRectOutline(bx + 35, by + bh - 55, bw - 70, 38, Theme::COLOR_BORDER, 1);
    if (!m_localRecordings.empty()) {
        drawText("[▲/▼] Выбор   |   [X] Предпросмотр   |   [A] Установить как видеофон   |   [B] Назад", bx + 55, by + bh - 43, Theme::COLOR_TEXT_MUTED, 13);
    } else {
        drawText("[B] Назад в меню", bx + 55, by + bh - 43, Theme::COLOR_TEXT_MUTED, 13);
    }
}

void App::executeInstallLocalRecording() {
    if (m_pendingRecordingToInstallPath.empty() || m_recordingsTargetTitleId.empty()) {
        return;
    }

    InstallResult res = Installer::installLocalRecording(
        m_platform->getCoversDirectory(),
        m_recordingsTargetTitleId,
        m_pendingRecordingToInstallPath,
        true
    );

    if (res.success) {
        std::string varId = "local:" + m_pendingRecordingToInstallName;
        InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), m_recordingsTargetTitleId, varId);
        refreshInstalledGames();
        closeRecordingsBrowser();
        m_statusNotification = "Запись 4IFIR успешно установлена!";
        m_notificationFramesRemaining = 180;
    } else {
        m_dialogTitle = "Ошибка установки записи";
        m_dialogMessage = res.message;
        m_activeDialog = DialogType::MessageAlert;
    }
}

void App::runIntegrityCheck() {
    IntegrityReport report = Installer::validateAllInstalledCovers(m_platform->getCoversDirectory());
    m_lastIntegrityTotalChecked = report.totalChecked;

    if (report.issues.empty()) {
        m_activeDialog = DialogType::IntegrityCheckResult;
        m_dialogTitle = "Целостность видеофонов";
        if (report.totalChecked == 0) {
            m_dialogMessage = "В папке recordings/covers/ пока нет установленных видеофонов.";
        } else {
            m_dialogMessage = "Проверено видеофонов: " + std::to_string(report.totalChecked) +
                              "\n\nВсе установленные файлы полностью исправны, не повреждены и готовы к работе в меню Switch!";
        }
    } else {
        m_detectedIntegrityIssues = report.issues;
        m_activeDialog = DialogType::ConfirmDeleteCorrupted;
        m_dialogTitle = "Обнаружены повреждённые видеофоны!";
        std::string msg = "Найдено повреждений: " + std::to_string(report.issues.size()) +
                          " из " + std::to_string(report.totalChecked) + " файлов:\n";
        for (size_t i = 0; i < report.issues.size() && i < 3; ++i) {
            msg += "• " + report.issues[i].filename + " (" + report.issues[i].reason + ")\n";
        }
        if (report.issues.size() > 3) {
            msg += "• ... и ещё " + std::to_string(report.issues.size() - 3) + " файл(ов)\n";
        }
        msg += "\nУдалить повреждённые файлы во избежание сбоя или зависания меню Switch?";
        m_dialogMessage = msg;
        m_dialogFocus = 0;
    }
}

void App::executeDeleteCorruptedCovers() {
    int deleted = Installer::deleteCorruptedCovers(m_detectedIntegrityIssues);
    for (const auto& issue : m_detectedIntegrityIssues) {
        InstalledRegistry::instance().remove(m_platform->getAppDirectory(), issue.titleId);
    }
    refreshInstalledGames();

    m_detectedIntegrityIssues.clear();
    m_statusNotification = "Удалено повреждённых видеофонов: " + std::to_string(deleted);
    m_notificationFramesRemaining = 180;
}
"""

last_closing_brace = text.rfind("} // namespace ui")
if last_closing_brace != -1:
    text = text[:last_closing_brace] + new_methods + "\n} // namespace ui\n} // namespace h3h\n"
    p.write_text(text, encoding="utf-8")
    print("Patched app.cpp successfully")
else:
    print("Could not find closing namespace brace in app.cpp")
