from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
code = p.read_text(encoding="utf-8")

# 1. Fullscreen Preview: Fix overlap of badges & hints
old_preview_hud = '''        if (v.hasAudio) {
            drawRect(hudX + 430, hudY + 66, 75, 22, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(hudX + 430, hudY + 66, 75, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", hudX + 451, hudY + 70, Theme::COLOR_SUCCESS, 10);
        } else {
            drawRect(hudX + 430, hudY + 66, 85, 22, {0x28, 0x33, 0x47, 0x44});
            drawRectOutline(hudX + 430, hudY + 66, 85, 22, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ЗВУКА", hudX + 439, hudY + 70, Theme::COLOR_TEXT_MUTED, 10);
        }

        if (v.hasIcon) {
            drawRect(hudX + 520, hudY + 66, 120, 22, {0x0E, 0x74, 0x90, 0x44});
            drawRectOutline(hudX + 520, hudY + 66, 120, 22, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("4IFIR ИКОНКА", hudX + 530, hudY + 70, Theme::COLOR_FOCUS_CYAN, 10);
        }

        // Active variant identification: exactly matches the installed variant
        bool isActiveVariant = (m_previewHasInstalledCover && v.id == m_previewInstalledVariantId);

        if (isActiveVariant) {
            drawRect(hudX + 530, hudY + 66, 185, 22, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(hudX + 530, hudY + 66, 185, 22, Theme::COLOR_SUCCESS, 1);
            drawText("УСТАНОВЛЕН НА SWITCH", hudX + 542, hudY + 70, Theme::COLOR_SUCCESS, 10);
        } else if (!m_previewIsGameInstalled) {
            drawRect(hudX + 530, hudY + 66, 185, 22, {0x1E, 0x29, 0x3B, 0xAA});
            drawRectOutline(hudX + 530, hudY + 66, 185, 22, Theme::COLOR_BORDER, 1);
            drawText("ИГРА НЕ УСТАНОВЛЕНА", hudX + 542, hudY + 70, Theme::COLOR_TEXT_MUTED, 10);
        }'''

new_preview_hud = '''        // Sequential dynamic badges starting at hudX + 285
        int badgeX = hudX + 285;

        if (v.hasAudio) {
            drawRect(badgeX, hudY + 66, 65, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(badgeX, hudY + 66, 65, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", badgeX + 16, hudY + 71, Theme::COLOR_SUCCESS, 11);
            badgeX += 73;
        } else {
            drawRect(badgeX, hudY + 66, 80, 24, {0x28, 0x33, 0x47, 0x44});
            drawRectOutline(badgeX, hudY + 66, 80, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ЗВУКА", badgeX + 10, hudY + 71, Theme::COLOR_TEXT_MUTED, 11);
            badgeX += 88;
        }

        if (v.hasIcon) {
            drawRect(badgeX, hudY + 66, 95, 24, {0x0E, 0x74, 0x90, 0x44});
            drawRectOutline(badgeX, hudY + 66, 95, 24, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("🔲 ИКОНКА", badgeX + 10, hudY + 71, Theme::COLOR_FOCUS_CYAN, 11);
            badgeX += 103;
        }

        // Active variant identification: exactly matches the installed variant
        bool isActiveVariant = (m_previewHasInstalledCover && v.id == m_previewInstalledVariantId);

        if (isActiveVariant) {
            drawRect(badgeX, hudY + 66, 155, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(badgeX, hudY + 66, 155, 24, Theme::COLOR_SUCCESS, 1);
            drawText("АКТИВЕН НА SWITCH", badgeX + 10, hudY + 71, Theme::COLOR_SUCCESS, 11);
        } else if (!m_previewIsGameInstalled) {
            drawRect(badgeX, hudY + 66, 155, 24, {0x1E, 0x29, 0x3B, 0xAA});
            drawRectOutline(badgeX, hudY + 66, 155, 24, Theme::COLOR_BORDER, 1);
            drawText("ИГРА НЕ УСТАНОВЛЕНА", badgeX + 10, hudY + 71, Theme::COLOR_TEXT_MUTED, 11);
        }'''

assert old_preview_hud in code, "old_preview_hud not found"
code = code.replace(old_preview_hud, new_preview_hud, 1)

# Fix hints on preview HUD
old_preview_hints = '''        drawText("[R3/L] ★ В избранное   |   [Y] Привязать к игре", hudX + 540, hudY + 68, Theme::COLOR_FOCUS_CYAN, 12);
        if (totalV > 1) {
            drawText("[◀ / ▶] Вариант", hudX + 930, hudY + 68, Theme::COLOR_FOCUS_PINK, 12);
        }
        drawText("[B] Назад", hudX + 1110, hudY + 68, Theme::COLOR_TEXT_MUTED, 13);'''

new_preview_hints = '''        drawText("[R3/L] ★ В избранное", hudX + 680, hudY + 71, Theme::COLOR_TEXT_MUTED, 13);
        drawText("[Y] Привязать", hudX + 850, hudY + 71, Theme::COLOR_FOCUS_CYAN, 13);
        if (totalV > 1) {
            drawText("[◀/▶] Вариант", hudX + 975, hudY + 71, Theme::COLOR_FOCUS_PINK, 13);
        }
        drawText("[B] Назад", hudX + 1100, hudY + 71, Theme::COLOR_TEXT_MUTED, 13);'''

assert old_preview_hints in code, "old_preview_hints not found"
code = code.replace(old_preview_hints, new_preview_hints, 1)

# Also shorten specs width to 250 in preview
code = code.replace(
    'drawText(specs, hudX + 25, hudY + 68, Theme::COLOR_TEXT_MUTED, 13, 390);',
    'drawText(specs, hudX + 25, hudY + 71, Theme::COLOR_TEXT_MUTED, 13, 255);'
)

# 2. In renderTabCatalog(), display icon indicator for background
old_cat_title = '        drawText(g.title, 118, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17, 560);'
new_cat_title = '''        bool hasIconVariant = false;
        for (const auto& v : g.variants) {
            if (v.hasIcon) { hasIconVariant = true; break; }
        }
        std::string catGameTitle = g.title;
        if (hasIconVariant) {
            catGameTitle += "  [🔲 +Иконка]";
        }
        drawText(catGameTitle, 118, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17, 560);'''

assert old_cat_title in code, "old_cat_title not found"
code = code.replace(old_cat_title, new_cat_title, 1)

old_cat_audio = '''        // Audio badge
        if (hasAudioVariant) {
            drawRect(640, y + 40, 75, 22, {0x18, 0x38, 0x24, 0xCC});
            drawRectOutline(640, y + 40, 75, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", 658, y + 44, Theme::COLOR_SUCCESS, 10);
        }'''

new_cat_audio = '''        // Badges: Audio & Video Icon
        int cBadgeX = 570;
        if (hasAudioVariant) {
            drawRect(cBadgeX, y + 40, 65, 22, {0x18, 0x38, 0x24, 0xCC});
            drawRectOutline(cBadgeX, y + 40, 65, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", cBadgeX + 16, y + 44, Theme::COLOR_SUCCESS, 10);
            cBadgeX += 73;
        }
        if (hasIconVariant) {
            drawRect(cBadgeX, y + 40, 85, 22, {0x0E, 0x74, 0x90, 0x44});
            drawRectOutline(cBadgeX, y + 40, 85, 22, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("🔲 ИКОНКА", cBadgeX + 8, y + 44, Theme::COLOR_FOCUS_CYAN, 10);
            cBadgeX += 93;
        }'''

assert old_cat_audio in code, "old_cat_audio not found"
code = code.replace(old_cat_audio, new_cat_audio, 1)

# 3. In renderTabMyGames(), show icon status in left list & right pane
old_mygames_status = '''        // Status pill
        if (game.hasInstalledCover) {
            drawRect(370, startY + 18, 95, 24, {0x10, 0xB9, 0x81, 0x22});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ФОН ЕСТЬ", 380, startY + 23, Theme::COLOR_SUCCESS, 11);
        } else {
            drawRect(370, startY + 18, 95, 24, {0x28, 0x33, 0x47, 0x55});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_BORDER, 1);
            drawText("НЕТ ФОНА", 384, startY + 23, Theme::COLOR_TEXT_MUTED, 11);
        }'''

new_mygames_status = '''        // Status pill: Cover & Video Icon
        if (game.hasInstalledCover && game.hasInstalledIcon) {
            drawRect(330, startY + 18, 135, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(330, startY + 18, 135, 24, Theme::COLOR_SUCCESS, 1);
            drawText("🎬 ФОН + 🔲 ИКОНКА", 336, startY + 23, Theme::COLOR_SUCCESS, 11);
        } else if (game.hasInstalledCover) {
            drawRect(370, startY + 18, 95, 24, {0x10, 0xB9, 0x81, 0x22});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ФОН ЕСТЬ", 380, startY + 23, Theme::COLOR_SUCCESS, 11);
        } else if (game.hasInstalledIcon) {
            drawRect(355, startY + 18, 110, 24, {0x0E, 0x74, 0x90, 0x33});
            drawRectOutline(355, startY + 18, 110, 24, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("🔲 ИКОНКА ЕСТЬ", 362, startY + 23, Theme::COLOR_FOCUS_CYAN, 11);
        } else {
            drawRect(370, startY + 18, 95, 24, {0x28, 0x33, 0x47, 0x55});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_BORDER, 1);
            drawText("НЕТ ФОНА", 384, startY + 23, Theme::COLOR_TEXT_MUTED, 11);
        }'''

assert old_mygames_status in code, "old_mygames_status not found"
code = code.replace(old_mygames_status, new_mygames_status, 1)

# Right details pane status
old_mygames_details_status = '''        std::string coverInfo = selGame.hasInstalledCover ?
            std::string(m_language == Language::Russian ? "Активный фон на консоли: " : "Active cover: ") +
            Config::getTargetCoverFileName(selGame.titleId) + " (" +
            std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)" :
            std::string(m_language == Language::Russian ? "Видеофон не установлен" : "No video background installed");
        drawText(coverInfo, 530, 175, selGame.hasInstalledCover ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);'''

new_mygames_details_status = '''        std::string coverInfo;
        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: Видеофон (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB) + 🔲 Видеоиконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledCover) {
            coverInfo = "Активный видеофон: " + Config::getTargetCoverFileName(selGame.titleId) + " (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: 🔲 Видеоиконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB, без видеофона)";
        } else {
            coverInfo = "Видеофон и видеоиконка не установлены";
        }
        drawText(coverInfo, 530, 175, (selGame.hasInstalledCover || selGame.hasInstalledIcon) ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);'''

assert old_mygames_details_status in code, "old_mygames_details_status not found"
code = code.replace(old_mygames_details_status, new_mygames_details_status, 1)

# In My Games variants list, show icon indicator in title & badge
old_var_title = '                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";'
new_var_title = '''                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                if (v.hasIcon) {
                    vTitle += "  [🔲 Иконка]";
                }'''

assert old_var_title in code, "old_var_title not found"
code = code.replace(old_var_title, new_var_title, 1)

p.write_text(code, encoding="utf-8")
print("[+] Successfully patched all UI improvements into downloader/src/ui/app.cpp")
