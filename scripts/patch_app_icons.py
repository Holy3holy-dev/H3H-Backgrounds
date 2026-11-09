from pathlib import Path

p = Path("downloader/src/ui/app.cpp")
code = p.read_text(encoding="utf-8")

# 1. In refreshInstalledGames(), scan for installed 4IFIR video icons
old_refresh_tail = '''    InstalledRegistry::instance().load(m_platform->getAppDirectory());
    for (auto& game : m_installedGames) {'''

new_refresh_tail = '''    InstalledRegistry::instance().load(m_platform->getAppDirectory());
    for (auto& game : m_installedGames) {
        // Check for 4IFIR video icon on SD card (sdmc:/recordings/icons/<TitleID>.mp4)
        std::string iconPath;
        uint64_t iconSize = 0;
        if (Installer::findExistingIcon(m_platform->getIconsDirectory(), game.titleId, iconPath, iconSize)) {
            game.hasInstalledIcon = true;
            game.installedIconPath = iconPath;
            game.installedIconSizeBytes = iconSize;
        }'''

assert old_refresh_tail in code, "old_refresh_tail not found"
code = code.replace(old_refresh_tail, new_refresh_tail, 1)

# 2. In queue download execution, download and install 4IFIR video icon if present
old_queue_install = '''    InstallResult res = Installer::installVariant(
        m_platform->getCoversDirectory(),
        currentTask.titleId,
        currentTask.tempFilePath,
        currentTask.variant.sha256,
        currentTask.variant.sizeBytes,
        true
    );'''

new_queue_install = '''    InstallResult res = Installer::installVariant(
        m_platform->getCoversDirectory(),
        currentTask.titleId,
        currentTask.tempFilePath,
        currentTask.variant.sha256,
        currentTask.variant.sizeBytes,
        true
    );

    // If variant includes a 4IFIR video icon, download and install it as well
    if (res.success && currentTask.variant.hasIcon && !currentTask.variant.iconUrl.empty()) {
        std::string tempIconPath = m_platform->getIconsDirectory() + "/" + Config::getTempIconFileName(currentTask.titleId);
        std::string iconErr;
        bool iconDownloaded = m_platform->downloadFile(
            currentTask.variant.iconUrl,
            tempIconPath,
            nullptr,
            m_cancelQueue,
            iconErr
        );
        if (iconDownloaded) {
            Installer::installIcon(
                m_platform->getIconsDirectory(),
                currentTask.titleId,
                tempIconPath,
                currentTask.variant.iconSizeBytes,
                true
            );
        }
    }'''

assert old_queue_install in code, "old_queue_install not found"
code = code.replace(old_queue_install, new_queue_install, 1)

# 3. In renderFullscreenPreview(), show 4IFIR Icon badge
old_audio_badge = '''        if (v.hasAudio) {
            drawRect(hudX + 430, hudY + 66, 75, 22, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(hudX + 430, hudY + 66, 75, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", hudX + 451, hudY + 70, Theme::COLOR_SUCCESS, 10);
        } else {
            drawRect(hudX + 430, hudY + 66, 85, 22, {0x28, 0x33, 0x47, 0x44});
            drawRectOutline(hudX + 430, hudY + 66, 85, 22, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ЗВУКА", hudX + 439, hudY + 70, Theme::COLOR_TEXT_MUTED, 10);
        }'''

new_audio_badge = '''        if (v.hasAudio) {
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
        }'''

assert old_audio_badge in code, "old_audio_badge not found"
code = code.replace(old_audio_badge, new_audio_badge, 1)

p.write_text(code, encoding="utf-8")
print("[+] Successfully updated downloader/src/ui/app.cpp with video icon support")
