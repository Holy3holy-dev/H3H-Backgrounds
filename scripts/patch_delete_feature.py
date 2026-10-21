with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Update MyGames details panel (buttons for Delete and Restore)
old_panel = """        int missing = getMissingCoversCount();
        if (missing > 0) {
            drawRect(950, 95, 280, 40, Theme::COLOR_BG_ELEVATED);
            drawRectOutline(950, 95, 280, 40, Theme::COLOR_ACCENT, 1);
            drawText("[Y] Установить все (" + std::to_string(missing) + ")", 970, 107, Theme::COLOR_ACCENT, 14);
        }

        // Status details
        std::string coverInfo = selGame.hasInstalledCover ?
            "Установлен: " + Config::getTargetCoverFileName(selGame.titleId) + " (" +
            std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)" : "Видеофон отсутствует";
        drawText(coverInfo, 530, 180, selGame.hasInstalledCover ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);

        if (selGame.hasBackup) {
            drawText("Резервная копия (.bak) сохранена (" + std::to_string(selGame.backupSizeBytes / 1024) + " KB) -> [X] Восстановить",
                     530, 205, Theme::COLOR_ACCENT, 13);
        }"""

new_panel = """        if (selGame.hasInstalledCover) {
            // Prominent Delete button
            drawRect(950, 160, 270, 38, Theme::COLOR_BG_ELEVATED);
            drawRectOutline(950, 160, 270, 38, Theme::COLOR_ERROR, 1);
            drawText("[Y] " + std::string(m_language == Language::Russian ? "Удалить видеофон" : "Delete Background"),
                     975, 172, Theme::COLOR_ERROR, 14);
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

# 2. Update touch handling
old_touch = """            // MyGames Tab: top-right "Установить все" button: x in [950, 1230], y in [95, 140]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 95 && my <= 140) {
                installAllMissing();
            }"""

new_touch = """            // MyGames Tab: top-right "Установить все" button: x in [950, 1230], y in [95, 140]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 95 && my <= 140) {
                installAllMissing();
            }
            // MyGames Tab: "Удалить видеофон" button: x in [950, 1230], y in [155, 200]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 155 && my <= 200) {
                onButtonPress(3 /* Y - Delete */);
            }
            // MyGames Tab: "Восстановить (.bak)" button: x in [950, 1230], y in [205, 250]
            else if (m_activeTab == Tab::MyGames && mx >= 950 && mx <= 1230 && my >= 205 && my <= 250) {
                onButtonPress(2 /* X - Restore */);
            }"""

# 3. Update hints bar for MyGames
old_hints = """    case Tab::MyGames:
        hints = "[L/R] Вкладки   [A] Установить   [B] Назад   [X] Восстановить   [Y] Удалить / Все   [-] Обновить";
        break;"""

new_hints = """    case Tab::MyGames: {
        bool hasCover = false;
        if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
            hasCover = m_installedGames[m_myGamesSelectedIndex].hasInstalledCover;
        }
        if (m_language == Language::Russian) {
            hints = hasCover ?
                "[L/R] Вкладки   [A] Сменить вариант   [Y] Удалить фон   [X] Восстановить   [B] Главная   [-] Каталог" :
                "[L/R] Вкладки   [A] Установить   [Y] Установить все   [B] Главная   [-] Каталог";
        } else {
            hints = hasCover ?
                "[L/R] Tabs   [A] Change variant   [Y] Delete background   [X] Restore   [B] Home   [-] Catalog" :
                "[L/R] Tabs   [A] Install   [Y] Install all   [B] Home   [-] Catalog";
        }
        break;
    }"""

def replace_block(content, old, new):
    if old in content:
        return content.replace(old, new, 1)
    old_crlf = old.replace('\n', '\r\n')
    new_crlf = new.replace('\n', '\r\n')
    if old_crlf in content:
        return content.replace(old_crlf, new_crlf, 1)
    print("WARNING: Block not found:")
    print(old[:60])
    return content

c = replace_block(c, old_panel, new_panel)
c = replace_block(c, old_touch, new_touch)
c = replace_block(c, old_hints, new_hints)

with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8') as f:
    f.write(c)

print("Patch applied to downloader/src/ui/app.cpp")
