import sys

def main():
    with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
        cpp = f.read()

    # Normalize line endings to \n for uniform patching
    cpp = cpp.replace('\r\n', '\n')

    # 1. onButtonPress: add m_isGamePickerOpen
    target_rec_input = '    // Local Recordings Browser Handler (Feature 3)\n    if (m_isRecordingsBrowserOpen'
    picker_input = '''    // Target Game Picker Handler (Assign video theme to any installed game)
    if (m_isGamePickerOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview) {
        if (SDL_GetTicks() - m_gamePickerOpenedAt < 150) {
            return;
        }
        if (button == 1 /* B */) {
            closeGamePicker();
            return;
        }
        if (button == 11 /* UP */) {
            if (m_gamePickerSelectedIndex > 0) m_gamePickerSelectedIndex--;
            return;
        }
        if (button == 12 /* DOWN */) {
            if (m_gamePickerSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                m_gamePickerSelectedIndex++;
            }
            return;
        }
        if (button == 0 /* A - Select Game */) {
            if (!m_installedGames.empty() && m_gamePickerSelectedIndex >= 0 &&
                m_gamePickerSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& targetGame = m_installedGames[m_gamePickerSelectedIndex];
                m_pendingActionTitleId = targetGame.titleId;
                m_pendingActionVariant = m_gamePickerPendingVariant;
                m_activeDialog = DialogType::ConfirmInstall;
                m_dialogOpenedAt = SDL_GetTicks();
                m_dialogTitle = (m_language == Language::Russian) ? "Назначение видеофона" : "Assign Video Theme";
                m_dialogMessage = (m_language == Language::Russian)
                    ? ("Установить видеофон '" + m_pendingActionVariant.name + "'\\nдля игры: " + targetGame.name + " [" + targetGame.titleId + "]?")
                    : ("Install video theme '" + m_pendingActionVariant.name + "'\\nfor game: " + targetGame.name + " [" + targetGame.titleId + "]?");
                m_dialogFocus = 0;
                closeGamePicker();
            }
            return;
        }
        return;
    }

    // Local Recordings Browser Handler (Feature 3)
    if (m_isRecordingsBrowserOpen'''

    if target_rec_input in cpp:
        cpp = cpp.replace(target_rec_input, picker_input, 1)
        print('[+] Added game picker input handler')
    else:
        print('[-] Could not find target_rec_input')

    # 2. Preview input: add Y button and 0000000000000000 check on A
    target_preview_a = '''            } else if (button == 0 /* A - Install / Save */) {
                closeFullscreenPreview();'''
    repl_preview_a = '''            } else if (button == 3 /* Y - Assign to another game */) {
                openGamePicker(m_previewVariants[m_previewVariantIndex], m_previewGameName);
                return;
            } else if (button == 0 /* A - Install / Save */) {
                if (m_previewTitleId == "0000000000000000") {
                    openGamePicker(m_previewVariants[m_previewVariantIndex], m_previewGameName);
                    return;
                }
                closeFullscreenPreview();'''

    if target_preview_a in cpp:
        cpp = cpp.replace(target_preview_a, repl_preview_a, 1)
        print('[+] Added preview Y button and 0000000000000000 handler')
    else:
        print('[-] Could not find target_preview_a')

    # 3. render(): renderGamePicker
    target_render_rec = '''    if (m_isRecordingsBrowserOpen) {
        renderRecordingsBrowser();
    }'''
    repl_render_picker = target_render_rec + '''
    if (m_isGamePickerOpen) {
        renderGamePicker();
    }'''

    if target_render_rec in cpp:
        cpp = cpp.replace(target_render_rec, repl_render_picker, 1)
        print('[+] Added renderGamePicker call in render()')
    else:
        print('[-] Could not find target_render_rec')

    # 4. renderTabHome: show totalVariants count
    target_home_metric = '''    // Metric Card 3: Available in Catalog
    drawGlassCard(860, 95, 360, 145, false, true);
    drawText(s.statAvailableCatalog, 885, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(catalogCount), 885, 145, Theme::COLOR_FOCUS_CYAN, 44);
    drawRect(885, 202, 190, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(885, 202, 190, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("[-] Обновить каталог", 895, 208, Theme::COLOR_FOCUS_CYAN, 12);'''

    repl_home_metric = '''    size_t totalVariants = m_catalogManager.getTotalVariantsCount();
    // Metric Card 3: Available in Catalog
    drawGlassCard(860, 95, 360, 145, false, true);
    drawText(s.statAvailableCatalog, 885, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(totalVariants), 885, 145, Theme::COLOR_FOCUS_CYAN, 44);
    drawRect(885, 202, 210, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(885, 202, 210, 26, Theme::COLOR_FOCUS_CYAN, 1);
    std::string catSub = std::to_string(catalogCount) + (m_language == Language::Russian ? " игр/коллекций" : " games/groups");
    drawText(catSub, 895, 208, Theme::COLOR_FOCUS_CYAN, 12);'''

    if target_home_metric in cpp:
        cpp = cpp.replace(target_home_metric, repl_home_metric, 1)
        print('[+] Updated Home Tab metric to show total variants count')
    else:
        print('[-] Could not find target_home_metric')

    # 5. renderFullscreenPreview: add [Y] hint and free choice button
    target_preview_btns = '''        // Right side buttons
        if (isActiveVariant) {'''

    repl_preview_btns = '''        // Right side buttons
        if (m_previewTitleId == "0000000000000000") {
            drawRect(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(hudX + 900, hudY + 14, 270, 38, 2);
            drawText("[A/Y] Выбрать игру для фона", hudX + 915, hudY + 24, Theme::COLOR_FOCUS_CYAN, 13);
        } else if (isActiveVariant) {'''

    if target_preview_btns in cpp:
        cpp = cpp.replace(target_preview_btns, repl_preview_btns, 1)
        print('[+] Added free choice button in preview')
    else:
        print('[-] Could not find target_preview_btns')

    target_preview_hints = '''        if (totalV > 1) {
            drawText("[◀ / ▶ D-Pad] Варианты на лету", hudX + 880, hudY + 68, Theme::COLOR_FOCUS_PINK, 12);
        }
        drawText("[B] Закрыть", hudX + 1100, hudY + 68, Theme::COLOR_TEXT_MUTED, 13);'''

    repl_preview_hints = '''        drawText("[Y] Привязать к другой игре", hudX + 680, hudY + 68, Theme::COLOR_FOCUS_CYAN, 12);
        if (totalV > 1) {
            drawText("[◀ / ▶] Вариант", hudX + 930, hudY + 68, Theme::COLOR_FOCUS_PINK, 12);
        }
        drawText("[B] Назад", hudX + 1110, hudY + 68, Theme::COLOR_TEXT_MUTED, 13);'''

    if target_preview_hints in cpp:
        cpp = cpp.replace(target_preview_hints, repl_preview_hints, 1)
        print('[+] Updated preview hints')
    else:
        print('[-] Could not find target_preview_hints')

    # 6. Add openGamePicker, closeGamePicker, renderGamePicker methods
    picker_methods = '''
void App::openGamePicker(const Variant& variant, const std::string& sourceGameName) {
    m_gamePickerPendingVariant = variant;
    m_gamePickerSourceGameName = sourceGameName;
    m_gamePickerSelectedIndex = 0;
    m_gamePickerScrollOffset = 0;
    m_gamePickerOpenedAt = SDL_GetTicks();
    m_isGamePickerOpen = true;
}

void App::closeGamePicker() {
    m_isGamePickerOpen = false;
}

void App::renderGamePicker() {
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
    drawText((m_language == Language::Russian ? "Назначить видеофон на игру" : "Assign Video Theme to Game"),
             bx + 35, by + 25, Theme::COLOR_FOCUS_CYAN, 20);

    std::string subtitle = (m_language == Language::Russian ? "Видеофон: «" : "Video Theme: «") +
                           m_gamePickerPendingVariant.name + "» (" + styleToString(m_gamePickerPendingVariant.style) + ")  |  " +
                           (m_language == Language::Russian ? "Выберите игру на консоли:" : "Select target game on console:");
    drawText(subtitle, bx + 35, by + 55, Theme::COLOR_TEXT_MUTED, 13, bw - 70);

    if (m_installedGames.empty()) {
        drawGlassCard(bx + 40, by + 120, bw - 80, 360, false, false);
        drawText((m_language == Language::Russian ? "На консоли не обнаружено установленных игр." : "No installed games detected on console."),
                 bx + 70, by + 250, Theme::COLOR_WARNING, 18);
    } else {
        int visibleCount = 5;
        if (m_gamePickerSelectedIndex < m_gamePickerScrollOffset) {
            m_gamePickerScrollOffset = m_gamePickerSelectedIndex;
        } else if (m_gamePickerSelectedIndex >= m_gamePickerScrollOffset + visibleCount) {
            m_gamePickerScrollOffset = m_gamePickerSelectedIndex - visibleCount + 1;
        }

        int itemY = by + 95;
        int itemH = 78;
        int maxIdx = std::min(m_gamePickerScrollOffset + visibleCount, static_cast<int>(m_installedGames.size()));

        for (int i = m_gamePickerScrollOffset; i < maxIdx; ++i) {
            bool isFocused = (i == m_gamePickerSelectedIndex);
            const auto& game = m_installedGames[i];

            if (isFocused) {
                drawRect(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(bx + 35, itemY, bw - 70, itemH, 2);
            } else {
                drawRect(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_BG_SURFACE);
                drawRectOutline(bx + 35, itemY, bw - 70, itemH, Theme::COLOR_BORDER, 1);
            }

            // Game Icon / Badge
            drawRect(bx + 55, itemY + 20, 60, 38, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BG_ELEVATED);
            drawText("NSP", bx + 70, itemY + 31, isFocused ? Theme::COLOR_BG_BASE : Theme::COLOR_FOCUS_CYAN, 14);

            // Title & Title ID
            drawText(game.name, bx + 130, itemY + 16, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, bw - 380);
            drawText("Title ID: " + game.titleId, bx + 130, itemY + 44, Theme::COLOR_TEXT_MUTED, 12, bw - 380);

            // Status Pill
            if (game.hasInstalledCover) {
                drawRect(bx + bw - 240, itemY + 26, 125, 26, {0x10, 0xB9, 0x81, 0x22});
                drawRectOutline(bx + bw - 240, itemY + 26, 125, 26, Theme::COLOR_SUCCESS, 1);
                drawText((m_language == Language::Russian ? "ЕСТЬ ФОН" : "HAS COVER"), bx + bw - 212, itemY + 32, Theme::COLOR_SUCCESS, 12);
            } else {
                drawRect(bx + bw - 240, itemY + 26, 125, 26, {0x28, 0x33, 0x47, 0x55});
                drawRectOutline(bx + bw - 240, itemY + 26, 125, 26, Theme::COLOR_BORDER, 1);
                drawText((m_language == Language::Russian ? "НЕТ ФОНА" : "NO COVER"), bx + bw - 212, itemY + 32, Theme::COLOR_TEXT_MUTED, 12);
            }

            itemY += itemH + 10;
        }

        // Counter Indicator
        std::string countStr = std::to_string(m_gamePickerSelectedIndex + 1) + " / " + std::to_string(m_installedGames.size());
        drawText(countStr, bx + bw - 130, by + 30, Theme::COLOR_TEXT_MUTED, 14);
    }

    // Bottom Help Banner
    drawRect(bx + 35, by + bh - 55, bw - 70, 38, Theme::COLOR_BG_BASE);
    drawRectOutline(bx + 35, by + bh - 55, bw - 70, 38, Theme::COLOR_BORDER, 1);
    drawText((m_language == Language::Russian ? "[▲/▼] Выбор игры   |   [A] Установить видеофон для этой игры   |   [B] Отмена"
                                              : "[▲/▼] Select game   |   [A] Install video theme for this game   |   [B] Cancel"),
             bx + 55, by + bh - 43, Theme::COLOR_TEXT_MUTED, 13);
}
'''

    target_eof = '} // namespace ui\n} // namespace h3h'
    if target_eof in cpp:
        cpp = cpp.replace(target_eof, picker_methods + '\n' + target_eof, 1)
        print('[+] Added game picker implementation methods')
    else:
        print('[-] Could not find target_eof')

    with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8') as f:
        f.write(cpp)

    print('app.cpp patched successfully!')

if __name__ == '__main__':
    main()

def patch_empty_variants():
    with open('downloader/src/ui/app.cpp', 'r', encoding='utf-8') as f:
        c = f.read()

    target = '            drawText("Для этой игры пока нет вариантов в онлайн-библиотеке.", 530, 290, Theme::COLOR_TEXT_MUTED, 14);'

    repl = '''            drawText((m_language == Language::Russian
                ? "Прямых вариантов для этой игры пока нет в каталоге."
                : "No direct variants found for this game in the catalog."),
                530, 290, Theme::COLOR_TEXT_MUTED, 14);

            drawText((m_language == Language::Russian
                ? "Вы можете привязать ЛЮБОЙ видеофон из каталога:"
                : "You can assign ANY video theme from the catalog:"),
                530, 318, Theme::COLOR_FOCUS_CYAN, 13);

            drawGlassCard(530, 350, 480, 56, true, false);
            drawText((m_language == Language::Russian ? "[X] Открыть каталог After Dark" : "[X] Open After Dark Catalog"),
                     555, 368, Theme::COLOR_FOCUS_CYAN, 16);'''

    if target in c:
        c = c.replace(target, repl, 1)
        with open('downloader/src/ui/app.cpp', 'w', encoding='utf-8') as f:
            f.write(c)
        print('Patched MyGames empty variants display successfully')
    else:
        print('Could not find target in app.cpp')

patch_empty_variants()
