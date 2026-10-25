"""
Patch script for standalone video icons in H3H Switch Downloader (app.cpp).
"""
import sys
from pathlib import Path

def patch_app_cpp():
    app_path = Path("downloader/src/ui/app.cpp")
    content = app_path.read_text(encoding="utf-8")

    # 1. Patch processSingleDownloadTask to support iconOnly
    old_task_storage = """    // Safety check: ensure MicroSD has sufficient free storage space + safety buffer
    SystemInfo sysStorage = m_platform->getSystemInfo();
    if (sysStorage.freeStorageBytes > 0 && currentTask.variant.sizeBytes > 0) {
        if (sysStorage.freeStorageBytes < currentTask.variant.sizeBytes + Config::STORAGE_SAFETY_BUFFER_BYTES) {
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                    m_downloadQueue[taskIdx].state = TaskState::Failed;
                    m_downloadQueue[taskIdx].errorMessage = "Недостаточно места на MicroSD (резерв 20 MB)";
                }
            }
            m_queueTaskFinished.store(true);
            m_isProcessingQueue.store(false);
            return;
        }
    }"""

    new_task_storage = """    // Standalone Video Icon Task Handler
    if (currentTask.iconOnly) {
        SystemInfo sysStorage = m_platform->getSystemInfo();
        uint64_t neededIconBytes = (currentTask.variant.iconSizeBytes > 0 ? currentTask.variant.iconSizeBytes : 500 * 1024) + Config::STORAGE_SAFETY_BUFFER_BYTES;
        if (sysStorage.freeStorageBytes > 0 && sysStorage.freeStorageBytes < neededIconBytes) {
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                    m_downloadQueue[taskIdx].state = TaskState::Failed;
                    m_downloadQueue[taskIdx].errorMessage = "Недостаточно места на MicroSD";
                }
            }
            m_queueTaskFinished.store(true);
            m_isProcessingQueue.store(false);
            return;
        }

        std::string err;
        auto progressCb = [this, taskIdx](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                m_downloadQueue[taskIdx].bytesDownloaded = bytesDownloaded;
                if (totalBytes > 0) {
                    m_downloadQueue[taskIdx].totalBytes = totalBytes;
                    m_downloadQueue[taskIdx].progressPercent = (static_cast<double>(bytesDownloaded) / totalBytes) * 100.0;
                }
                m_downloadQueue[taskIdx].downloadSpeedBps = speedBps;
            }
        };

        bool ok = m_platform->downloadFile(
            currentTask.variant.iconUrl,
            currentTask.tempFilePath,
            progressCb,
            m_cancelQueue,
            err
        );

        if (!ok) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                m_downloadQueue[taskIdx].state = TaskState::Failed;
                m_downloadQueue[taskIdx].errorMessage = err;
            }
            m_queueTaskFinished.store(true);
            m_isProcessingQueue.store(false);
            return;
        }

        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                m_downloadQueue[taskIdx].state = TaskState::Verifying;
            }
        }

        InstallResult res = Installer::installIcon(
            m_platform->getIconsDirectory(),
            currentTask.titleId,
            currentTask.tempFilePath,
            currentTask.variant.iconSizeBytes,
            true
        );

        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                if (res.success) {
                    m_downloadQueue[taskIdx].state = TaskState::Completed;
                    m_downloadQueue[taskIdx].progressPercent = 100.0;
                } else {
                    m_downloadQueue[taskIdx].state = TaskState::Failed;
                    m_downloadQueue[taskIdx].errorMessage = res.message;
                }
            }
        }

        m_queueTaskFinished.store(true);
        m_isProcessingQueue.store(false);
        return;
    }

    // Safety check: ensure MicroSD has sufficient free storage space + safety buffer
    SystemInfo sysStorage = m_platform->getSystemInfo();
    if (sysStorage.freeStorageBytes > 0 && currentTask.variant.sizeBytes > 0) {
        if (sysStorage.freeStorageBytes < currentTask.variant.sizeBytes + Config::STORAGE_SAFETY_BUFFER_BYTES) {
            {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                if (taskIdx >= 0 && taskIdx < static_cast<int>(m_downloadQueue.size())) {
                    m_downloadQueue[taskIdx].state = TaskState::Failed;
                    m_downloadQueue[taskIdx].errorMessage = "Недостаточно места на MicroSD (резерв 20 MB)";
                }
            }
            m_queueTaskFinished.store(true);
            m_isProcessingQueue.store(false);
            return;
        }
    }"""

    assert old_task_storage in content, "old_task_storage not found"
    content = content.replace(old_task_storage, new_task_storage, 1)

    # 2. Patch cover-only check in standard installation
    old_icon_install = """    // If variant includes a 4IFIR video icon, download and install it as well
    if (res.success && currentTask.variant.hasIcon && !currentTask.variant.iconUrl.empty()) {"""

    new_icon_install = """    // If variant includes a 4IFIR video icon (and coverOnly is false), download and install it as well
    if (res.success && !currentTask.coverOnly && currentTask.variant.hasIcon && !currentTask.variant.iconUrl.empty()) {"""

    assert old_icon_install in content, "old_icon_install not found"
    content = content.replace(old_icon_install, new_icon_install, 1)

    # 3. Add queueDownloadIconOnly, queueDownloadCoverOnly, executeDeleteIcon
    old_queue = """void App::queueDownload(const InstalledTitle& title, const Variant& variant) {"""
    new_queue = """void App::queueDownloadIconOnly(const InstalledTitle& title, const Variant& variant) {
    if (!variant.hasIcon || variant.iconUrl.empty()) {
        m_statusNotification = (m_language == Language::Russian)
            ? "У этого варианта нет видеоиконки"
            : "This variant has no video icon";
        m_notificationFramesRemaining = 180;
        return;
    }

    DownloadTask task;
    task.id = title.titleId + "_" + variant.id + "_icon";
    task.titleId = title.titleId;
    task.gameTitle = title.name;
    task.variant = variant;
    task.iconOnly = true;
    task.coverOnly = false;
    task.tempFilePath = m_platform->getIconsDirectory() + "/" + Config::getTempIconFileName(title.titleId);
    task.targetFilePath = m_platform->getIconsDirectory() + "/" + Config::getTargetIconFileName(title.titleId);
    task.backupFilePath = m_platform->getIconsDirectory() + "/" + Config::getBackupIconFileName(title.titleId);
    task.state = TaskState::Pending;
    task.totalBytes = (variant.iconSizeBytes > 0) ? variant.iconSizeBytes : 350 * 1024;

    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        m_downloadQueue.push_back(std::move(task));
    }
    m_statusNotification = (m_language == Language::Russian)
        ? ("В очередь: Иконка " + title.name + " (" + variant.name + ")")
        : ("Added to queue: Icon " + title.name + " (" + variant.name + ")");
    m_notificationFramesRemaining = 180;
}

void App::queueDownloadCoverOnly(const InstalledTitle& title, const Variant& variant) {
    DownloadTask task;
    task.id = title.titleId + "_" + variant.id + "_cover";
    task.titleId = title.titleId;
    task.gameTitle = title.name;
    task.variant = variant;
    task.iconOnly = false;
    task.coverOnly = true;
    task.tempFilePath = m_platform->getCoversDirectory() + "/" + Config::getTempCoverFileName(title.titleId);
    task.targetFilePath = m_platform->getCoversDirectory() + "/" + Config::getTargetCoverFileName(title.titleId);
    task.backupFilePath = m_platform->getCoversDirectory() + "/" + Config::getBackupCoverFileName(title.titleId);
    task.state = TaskState::Pending;
    task.totalBytes = variant.sizeBytes;

    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        m_downloadQueue.push_back(std::move(task));
    }
    m_statusNotification = (m_language == Language::Russian)
        ? ("В очередь: Только фон " + title.name + " (" + variant.name + ")")
        : ("Added to queue: Cover only " + title.name + " (" + variant.name + ")");
    m_notificationFramesRemaining = 180;
}

void App::executeDeleteIcon(const std::string& titleId) {
    bool deleted = Installer::deleteIcon(m_platform->getIconsDirectory(), titleId);
    if (deleted) {
        m_statusNotification = (m_language == Language::Russian)
            ? "Видеоиконка 4IFIR успешно удалена"
            : "4IFIR video icon deleted";
    } else {
        m_statusNotification = (m_language == Language::Russian)
            ? "Видеоиконка не найдена"
            : "Video icon not found";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
}

void App::queueDownload(const InstalledTitle& title, const Variant& variant) {"""

    assert old_queue in content, "old_queue not found"
    content = content.replace(old_queue, new_queue, 1)

    # 4. Patch Dialog inputs in onButtonPress: ConfirmInstall and ConfirmDelete
    old_dialog_input = """        if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            m_dialogFocus = 1 - m_dialogFocus;
        } else if (button == 0 /* A - Confirm */) {
            if (m_dialogFocus == 0) { // Yes / Confirm
                if (m_activeDialog == DialogType::ConfirmInstall) {
                    bool queued = false;
                    for (const auto& g : m_installedGames) {
                        if (g.titleId == m_pendingActionTitleId) {
                            queueDownload(g, m_pendingActionVariant);
                            queued = true;
                            break;
                        }
                    }
                    if (!queued) {
                        InstalledTitle dummy;
                        dummy.titleId = m_pendingActionTitleId;
                        dummy.name = m_previewGameName;
                        dummy.hasCatalogMatch = true;
                        queueDownload(dummy, m_pendingActionVariant);
                    }
                } else if (m_activeDialog == DialogType::ConfirmInstallAll) {
                    for (const auto& g : m_installedGames) {
                        if (!g.hasInstalledCover && g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                            bool alreadyInQueue = false;
                            for (const auto& task : m_downloadQueue) {
                                if (task.titleId == g.titleId && task.state != TaskState::Failed) {
                                    alreadyInQueue = true;
                                    break;
                                }
                            }
                            if (!alreadyInQueue) {
                                queueDownload(g, g.catalogEntry.variants[0]);
                            }
                        }
                    }
                    m_activeTab = Tab::Downloads;
                } else if (m_activeDialog == DialogType::ConfirmRestore) {
                    executeRestoreBackup(m_pendingActionTitleId);
                } else if (m_activeDialog == DialogType::ConfirmDelete) {
                    executeDeleteCover(m_pendingActionTitleId);
                }
            }
            m_activeDialog = DialogType::None;
        } else if (button == 1 /* B - Cancel */) {
            m_activeDialog = DialogType::None;
        }"""

    new_dialog_input = """        bool isInstallWithIcon = (m_activeDialog == DialogType::ConfirmInstall && m_pendingActionVariant.hasIcon);
        bool isDeleteBoth = false;
        if (m_activeDialog == DialogType::ConfirmDelete) {
            for (const auto& g : m_installedGames) {
                if (g.titleId == m_pendingActionTitleId) {
                    if (g.hasInstalledCover && g.hasInstalledIcon) {
                        isDeleteBoth = true;
                    }
                    break;
                }
            }
        }

        if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            if (isInstallWithIcon || isDeleteBoth) {
                m_dialogFocus = (button == 13) ? ((m_dialogFocus + 3) % 4) : ((m_dialogFocus + 1) % 4);
            } else {
                m_dialogFocus = 1 - m_dialogFocus;
            }
            return;
        }

        // Direct Quick Shortcuts for Multi-Option Dialogs:
        // [X] -> Only Icon
        if (button == 2 /* X */) {
            if (isInstallWithIcon) {
                InstalledTitle targetGame;
                bool found = false;
                for (const auto& g : m_installedGames) {
                    if (g.titleId == m_pendingActionTitleId) { targetGame = g; found = true; break; }
                }
                if (!found) { targetGame.titleId = m_pendingActionTitleId; targetGame.name = m_previewGameName; targetGame.hasCatalogMatch = true; }
                queueDownloadIconOnly(targetGame, m_pendingActionVariant);
                m_activeDialog = DialogType::None;
                return;
            } else if (isDeleteBoth) {
                executeDeleteIcon(m_pendingActionTitleId);
                m_activeDialog = DialogType::None;
                return;
            }
        }
        // [Y] -> Only Video Cover
        if (button == 3 /* Y */) {
            if (isInstallWithIcon) {
                InstalledTitle targetGame;
                bool found = false;
                for (const auto& g : m_installedGames) {
                    if (g.titleId == m_pendingActionTitleId) { targetGame = g; found = true; break; }
                }
                if (!found) { targetGame.titleId = m_pendingActionTitleId; targetGame.name = m_previewGameName; targetGame.hasCatalogMatch = true; }
                queueDownloadCoverOnly(targetGame, m_pendingActionVariant);
                m_activeDialog = DialogType::None;
                return;
            } else if (isDeleteBoth) {
                executeDeleteCover(m_pendingActionTitleId);
                m_activeDialog = DialogType::None;
                return;
            }
        }

        if (button == 0 /* A - Confirm */) {
            if (m_activeDialog == DialogType::ConfirmInstall) {
                InstalledTitle targetGame;
                bool found = false;
                for (const auto& g : m_installedGames) {
                    if (g.titleId == m_pendingActionTitleId) { targetGame = g; found = true; break; }
                }
                if (!found) { targetGame.titleId = m_pendingActionTitleId; targetGame.name = m_previewGameName; targetGame.hasCatalogMatch = true; }

                if (isInstallWithIcon) {
                    if (m_dialogFocus == 0) {
                        // Install Both (Cover + Icon)
                        queueDownload(targetGame, m_pendingActionVariant);
                    } else if (m_dialogFocus == 1) {
                        // Install ONLY Icon
                        queueDownloadIconOnly(targetGame, m_pendingActionVariant);
                    } else if (m_dialogFocus == 2) {
                        // Install ONLY Cover
                        queueDownloadCoverOnly(targetGame, m_pendingActionVariant);
                    }
                    // focus == 3 is cancel
                } else {
                    if (m_dialogFocus == 0) {
                        queueDownload(targetGame, m_pendingActionVariant);
                    }
                }
            } else if (m_activeDialog == DialogType::ConfirmInstallAll) {
                if (m_dialogFocus == 0) {
                    for (const auto& g : m_installedGames) {
                        if (!g.hasInstalledCover && g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                            bool alreadyInQueue = false;
                            for (const auto& task : m_downloadQueue) {
                                if (task.titleId == g.titleId && task.state != TaskState::Failed) {
                                    alreadyInQueue = true;
                                    break;
                                }
                            }
                            if (!alreadyInQueue) {
                                queueDownload(g, g.catalogEntry.variants[0]);
                            }
                        }
                    }
                    m_activeTab = Tab::Downloads;
                }
            } else if (m_activeDialog == DialogType::ConfirmRestore) {
                if (m_dialogFocus == 0) {
                    executeRestoreBackup(m_pendingActionTitleId);
                }
            } else if (m_activeDialog == DialogType::ConfirmDelete) {
                if (isDeleteBoth) {
                    if (m_dialogFocus == 0) {
                        executeDeleteCover(m_pendingActionTitleId);
                        executeDeleteIcon(m_pendingActionTitleId);
                    } else if (m_dialogFocus == 1) {
                        executeDeleteIcon(m_pendingActionTitleId);
                    } else if (m_dialogFocus == 2) {
                        executeDeleteCover(m_pendingActionTitleId);
                    }
                } else {
                    if (m_dialogFocus == 0) {
                        bool hadCover = false;
                        for (const auto& g : m_installedGames) {
                            if (g.titleId == m_pendingActionTitleId) { hadCover = g.hasInstalledCover; break; }
                        }
                        if (hadCover) executeDeleteCover(m_pendingActionTitleId);
                        else executeDeleteIcon(m_pendingActionTitleId);
                    }
                }
            }
            m_activeDialog = DialogType::None;
        } else if (button == 1 /* B - Cancel */) {
            m_activeDialog = DialogType::None;
        }"""

    assert old_dialog_input in content, "old_dialog_input not found"
    content = content.replace(old_dialog_input, new_dialog_input, 1)

    # 5. Patch Action buttons at y = 202 in MyGames
    old_actions = """        // Prominent Action Buttons (positioned below status, safe from top-right Tesla monitor HUD)
        if (selGame.hasInstalledCover) {
            drawRect(530, 202, 230, 32, {0xEF, 0x44, 0x44, 0x33});
            drawRectOutline(530, 202, 230, 32, Theme::COLOR_DANGER, 1);
            drawText("[Y] Удалить активный фон", 545, 210, Theme::COLOR_DANGER, 13);

            if (selGame.hasBackup) {
                drawRect(770, 202, 230, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_ACCENT, 1);
                drawText("[R] Восстановить (.bak)", 785, 210, Theme::COLOR_ACCENT, 13);
            }

            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
        } else {
            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
            int missing = getMissingCoversCount();
            if (missing > 0) {
                drawRect(530, 202, 250, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(530, 202, 250, 32, Theme::COLOR_ACCENT, 1);
                drawText("[Y] Установить все (" + std::to_string(missing) + ")", 545, 210, Theme::COLOR_ACCENT, 13);
            }
        }"""

    new_actions = """        // Prominent Action Buttons (positioned below status, safe from top-right Tesla monitor HUD)
        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
            drawRect(530, 202, 185, 32, {0xEF, 0x44, 0x44, 0x33});
            drawRectOutline(530, 202, 185, 32, Theme::COLOR_DANGER, 1);
            drawText("[Y] Удалить фон", 545, 210, Theme::COLOR_DANGER, 13);

            drawRect(725, 202, 190, 32, {0x0E, 0x74, 0x90, 0x33});
            drawRectOutline(725, 202, 190, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("⚡ Удалить иконку", 735, 210, Theme::COLOR_FOCUS_CYAN, 12);

            if (selGame.hasBackup) {
                drawRect(925, 202, 140, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(925, 202, 140, 32, Theme::COLOR_ACCENT, 1);
                drawText("[R] Копия", 940, 210, Theme::COLOR_ACCENT, 12);
            }

            drawGlassCard(1075, 202, 150, 32, true, false);
            drawText("[+] Записи (SD)", 1088, 210, Theme::COLOR_FOCUS_CYAN, 12);
        } else if (selGame.hasInstalledCover) {
            drawRect(530, 202, 230, 32, {0xEF, 0x44, 0x44, 0x33});
            drawRectOutline(530, 202, 230, 32, Theme::COLOR_DANGER, 1);
            drawText("[Y] Удалить активный фон", 545, 210, Theme::COLOR_DANGER, 13);

            if (selGame.hasBackup) {
                drawRect(770, 202, 230, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(770, 202, 230, 32, Theme::COLOR_ACCENT, 1);
                drawText("[R] Восстановить (.bak)", 785, 210, Theme::COLOR_ACCENT, 13);
            }

            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
        } else if (selGame.hasInstalledIcon) {
            drawRect(530, 202, 230, 32, {0x0E, 0x74, 0x90, 0x33});
            drawRectOutline(530, 202, 230, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("[Y] Удалить иконку", 545, 210, Theme::COLOR_FOCUS_CYAN, 13);

            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
        } else {
            drawGlassCard(1015, 202, 210, 32, true, false);
            drawText("[+] Записи 4IFIR (SD)", 1030, 210, Theme::COLOR_FOCUS_CYAN, 13);
            int missing = getMissingCoversCount();
            if (missing > 0) {
                drawRect(530, 202, 250, 32, Theme::COLOR_BG_ELEVATED);
                drawRectOutline(530, 202, 250, 32, Theme::COLOR_ACCENT, 1);
                drawText("[Y] Установить все (" + std::to_string(missing) + ")", 545, 210, Theme::COLOR_ACCENT, 13);
            }
        }"""

    assert old_actions in content, "old_actions not found"
    content = content.replace(old_actions, new_actions, 1)

    # 6. Patch Variant Card buttons in MyGames (Lines 2314-2325)
    old_var_btn = """                // Install / Reinstall Button (Interactive touch zone)
                bool isFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                Color btnFill = isFocused ? Theme::COLOR_FOCUS_FILL : (isVarSelected ? Color{0x00, 0x55, 0x77, 0x33} : Color{0x15, 0x20, 0x30, 0x55});
                Color btnBorder = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER;
                Color btnTextCol = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED;

                drawRect(1005, vY + 18, 205, 36, btnFill);
                drawRectOutline(1005, vY + 18, 205, 36, btnBorder, 1);
                std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                drawText(btnText, 1025, vY + 27, btnTextCol, 13);"""

    new_var_btn = """                // Install / Reinstall Button (Interactive touch zone)
                bool isFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                Color btnFill = isFocused ? Theme::COLOR_FOCUS_FILL : (isVarSelected ? Color{0x00, 0x55, 0x77, 0x33} : Color{0x15, 0x20, 0x30, 0x55});
                Color btnBorder = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER;
                Color btnTextCol = (isFocused || isVarSelected) ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED;

                if (v.hasIcon) {
                    drawRect(980, vY + 18, 125, 36, btnFill);
                    drawRectOutline(980, vY + 18, 125, 36, btnBorder, 1);
                    std::string btnText = isActiveOnConsole ? "[A] Фон" : "[A] Всё";
                    drawText(btnText, 995, vY + 27, btnTextCol, 13);

                    Color icoBtnFill = {0x0E, 0x74, 0x90, 0x33};
                    drawRect(1115, vY + 18, 95, 36, icoBtnFill);
                    drawRectOutline(1115, vY + 18, 95, 36, Theme::COLOR_FOCUS_CYAN, 1);
                    drawText("⚡ Иконка", 1125, vY + 27, Theme::COLOR_FOCUS_CYAN, 12);
                } else {
                    drawRect(1005, vY + 18, 205, 36, btnFill);
                    drawRectOutline(1005, vY + 18, 205, 36, btnBorder, 1);
                    std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                    drawText(btnText, 1025, vY + 27, btnTextCol, 13);
                }"""

    assert old_var_btn in content, "old_var_btn not found"
    content = content.replace(old_var_btn, new_var_btn, 1)

    # 7. Patch renderDialog for multi-option modals
    old_dialog_render = """    int btnW = 180;
    int btnH = 42;
    int btnY = dy + 190;

    // Confirm button
    bool focusConfirm = (m_dialogFocus == 0);
    drawGlassCard(dx + 130, btnY, btnW, btnH, focusConfirm, false);
    drawText("[A] Подтвердить", dx + 155, btnY + 12, focusConfirm ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14);

    // Cancel button
    bool focusCancel = (m_dialogFocus == 1);
    drawGlassCard(dx + 390, btnY, btnW, btnH, focusCancel, false);
    drawText("[B] Отмена", dx + 435, btnY + 12, focusCancel ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14);
}"""

    new_dialog_render = """    bool isInstallWithIcon = (m_activeDialog == DialogType::ConfirmInstall && m_pendingActionVariant.hasIcon);
    bool isDeleteBoth = false;
    if (m_activeDialog == DialogType::ConfirmDelete) {
        for (const auto& g : m_installedGames) {
            if (g.titleId == m_pendingActionTitleId) {
                if (g.hasInstalledCover && g.hasInstalledIcon) {
                    isDeleteBoth = true;
                }
                break;
            }
        }
    }

    int btnY = dy + 190;
    int btnH = 42;

    if (isInstallWithIcon) {
        // Option 0: [A] Фон + Иконка
        bool f0 = (m_dialogFocus == 0);
        drawGlassCard(dx + 25, btnY, 155, btnH, f0, false);
        drawText("[A] Фон+Иконка", dx + 38, btnY + 12, f0 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 1: [X] Только иконка
        bool f1 = (m_dialogFocus == 1);
        drawGlassCard(dx + 190, btnY, 150, btnH, f1, false);
        drawText("[X] ⚡ Иконка", dx + 210, btnY + 12, f1 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 2: [Y] Только фон
        bool f2 = (m_dialogFocus == 2);
        drawGlassCard(dx + 350, btnY, 150, btnH, f2, false);
        drawText("[Y] 🎬 Только фон", dx + 365, btnY + 12, f2 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 3: [B] Отмена
        bool f3 = (m_dialogFocus == 3);
        drawGlassCard(dx + 510, btnY, 155, btnH, f3, false);
        drawText("[B] Отмена", dx + 555, btnY + 12, f3 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);
        return;
    }

    if (isDeleteBoth) {
        // Option 0: [A] Удалить всё
        bool f0 = (m_dialogFocus == 0);
        drawGlassCard(dx + 25, btnY, 155, btnH, f0, false);
        drawText("[A] Удалить всё", dx + 42, btnY + 12, f0 ? Theme::COLOR_DANGER : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 1: [X] Только иконку
        bool f1 = (m_dialogFocus == 1);
        drawGlassCard(dx + 190, btnY, 150, btnH, f1, false);
        drawText("[X] ⚡ Иконку", dx + 215, btnY + 12, f1 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 2: [Y] Только видеофон
        bool f2 = (m_dialogFocus == 2);
        drawGlassCard(dx + 350, btnY, 150, btnH, f2, false);
        drawText("[Y] 🎬 Видеофон", dx + 370, btnY + 12, f2 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);

        // Option 3: [B] Отмена
        bool f3 = (m_dialogFocus == 3);
        drawGlassCard(dx + 510, btnY, 155, btnH, f3, false);
        drawText("[B] Отмена", dx + 555, btnY + 12, f3 ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);
        return;
    }

    int btnW = 180;
    // Confirm button
    bool focusConfirm = (m_dialogFocus == 0);
    drawGlassCard(dx + 130, btnY, btnW, btnH, focusConfirm, false);
    drawText("[A] Подтвердить", dx + 155, btnY + 12, focusConfirm ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14);

    // Cancel button
    bool focusCancel = (m_dialogFocus == 1);
    drawGlassCard(dx + 390, btnY, btnW, btnH, focusCancel, false);
    drawText("[B] Отмена", dx + 435, btnY + 12, focusCancel ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 14);
}"""

    assert old_dialog_render in content, "old_dialog_render not found"
    content = content.replace(old_dialog_render, new_dialog_render, 1)

    # 8. Patch handleTouchTap for modal buttons, action buttons, and variant cards
    old_touch_dialog = """                } else {
                    if (my >= btnY && my <= btnY + 46 && mx >= dx + 120 && mx <= dx + 320) {
                        m_dialogFocus = 0;
                        onButtonPress(0 /* A - Confirm */);
                    } else if (my >= btnY && my <= btnY + 46 && mx >= dx + 380 && mx <= dx + 580) {
                        m_dialogFocus = 1;
                        onButtonPress(1 /* B - Cancel */);
                    } else if (mx < dx || mx > dx + dw || my < dy || my > dy + dh) {
                        m_activeDialog = DialogType::None;
                    }
                }"""

    new_touch_dialog = """                } else {
                    bool isInstallWithIcon = (m_activeDialog == DialogType::ConfirmInstall && m_pendingActionVariant.hasIcon);
                    bool isDeleteBoth = false;
                    if (m_activeDialog == DialogType::ConfirmDelete) {
                        for (const auto& g : m_installedGames) {
                            if (g.titleId == m_pendingActionTitleId) {
                                if (g.hasInstalledCover && g.hasInstalledIcon) { isDeleteBoth = true; }
                                break;
                            }
                        }
                    }

                    if (isInstallWithIcon || isDeleteBoth) {
                        if (my >= btnY && my <= btnY + 46) {
                            if (mx >= dx + 25 && mx <= dx + 180) {
                                m_dialogFocus = 0;
                                onButtonPress(0 /* A - Option 1 */);
                            } else if (mx >= dx + 190 && mx <= dx + 340) {
                                m_dialogFocus = 1;
                                onButtonPress(0 /* A - Option 2 */);
                            } else if (mx >= dx + 350 && mx <= dx + 500) {
                                m_dialogFocus = 2;
                                onButtonPress(0 /* A - Option 3 */);
                            } else if (mx >= dx + 510 && mx <= dx + 665) {
                                m_activeDialog = DialogType::None;
                            }
                        } else if (mx < dx || mx > dx + dw || my < dy || my > dy + dh) {
                            m_activeDialog = DialogType::None;
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
                }"""

    assert old_touch_dialog in content, "old_touch_dialog not found"
    content = content.replace(old_touch_dialog, new_touch_dialog, 1)

    # 9. Patch touch action buttons at y in [200, 240]
    old_touch_actions = """                // Right Column Action buttons at y in [200, 240]
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
                }"""

    new_touch_actions = """                // Right Column Action buttons at y in [200, 240]
                else if (my >= 200 && my <= 240) {
                    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
                            if (mx >= 530 && mx <= 720) {
                                executeDeleteCover(selGame.titleId);
                            } else if (mx >= 725 && mx <= 920) {
                                executeDeleteIcon(selGame.titleId);
                            } else if (mx >= 925 && mx <= 1070 && selGame.hasBackup) {
                                executeRestoreBackup(selGame.titleId);
                            } else if (mx >= 1075 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        } else if (selGame.hasInstalledCover) {
                            if (mx >= 530 && mx <= 760) {
                                onButtonPress(3 /* Y - Delete */);
                            } else if (mx >= 770 && mx <= 1000 && selGame.hasBackup) {
                                executeRestoreBackup(selGame.titleId);
                            } else if (mx >= 1015 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        } else if (selGame.hasInstalledIcon) {
                            if (mx >= 530 && mx <= 760) {
                                executeDeleteIcon(selGame.titleId);
                            } else if (mx >= 1015 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        } else {
                            if (mx >= 530 && mx <= 780 && getMissingCoversCount() > 0) {
                                installAllMissing();
                            } else if (mx >= 1015 && mx <= 1225) {
                                openRecordingsBrowser(selGame.titleId, selGame.name);
                            }
                        }
                    }
                }"""

    assert old_touch_actions in content, "old_touch_actions not found"
    content = content.replace(old_touch_actions, new_touch_actions, 1)

    # 10. Patch touch variant cards
    old_touch_var = """                                if (mx >= 1000 && mx <= 1220) {
                                    // Yellow Zone: direct instant download/installation
                                    queueDownload(selGame, selGame.catalogEntry.variants[vClicked]);
                                } else {
                                    // Green Zone (left 525..999): open fullscreen video preview
                                    openFullscreenPreviewForGame(selGame, vClicked);
                                }"""

    new_touch_var = """                                const auto& vChosen = selGame.catalogEntry.variants[vClicked];
                                if (vChosen.hasIcon) {
                                    if (mx >= 980 && mx < 1110) {
                                        queueDownload(selGame, vChosen);
                                    } else if (mx >= 1110 && mx <= 1220) {
                                        queueDownloadIconOnly(selGame, vChosen);
                                    } else {
                                        openFullscreenPreviewForGame(selGame, vClicked);
                                    }
                                } else {
                                    if (mx >= 1000 && mx <= 1220) {
                                        queueDownload(selGame, vChosen);
                                    } else {
                                        openFullscreenPreviewForGame(selGame, vClicked);
                                    }
                                }"""

    assert old_touch_var in content, "old_touch_var not found"
    content = content.replace(old_touch_var, new_touch_var, 1)

    # 11. Patch renderTabDownloads
    old_dl_render = """        // Title and variant
        drawText(task.gameTitle + "  [" + task.variant.name + "]", 85, y + 14, isDownloading ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);

        if (task.state == TaskState::Downloading) {
            // Sleek Capsule Progress Bar
            drawCapsuleProgressBar(85, y + 44, 480, 16, task.progressPercent);

            std::string progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                std::to_string(task.bytesDownloaded / (1024 * 1024)) + " / " +
                std::to_string(task.totalBytes / (1024 * 1024)) + " MB)";
            drawText(progStr, 580, y + 44, Theme::COLOR_FOCUS_CYAN, 13);"""

    new_dl_render = """        // Title and variant
        if (task.iconOnly) {
            drawText(task.gameTitle + "  [🔲 Видеоиконка: " + task.variant.name + "]", 85, y + 14, isDownloading ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
        } else if (task.coverOnly) {
            drawText(task.gameTitle + "  [🎬 Только видеофон: " + task.variant.name + "]", 85, y + 14, isDownloading ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
        } else {
            drawText(task.gameTitle + "  [" + task.variant.name + "]", 85, y + 14, isDownloading ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
        }

        if (task.state == TaskState::Downloading) {
            // Sleek Capsule Progress Bar
            drawCapsuleProgressBar(85, y + 44, 480, 16, task.progressPercent);

            std::string progStr;
            if (task.iconOnly) {
                progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                    std::to_string(task.bytesDownloaded / 1024) + " / " +
                    std::to_string(task.totalBytes / 1024) + " KB)";
            } else {
                progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                    std::to_string(task.bytesDownloaded / (1024 * 1024)) + " / " +
                    std::to_string(task.totalBytes / (1024 * 1024)) + " MB)";
            }
            drawText(progStr, 580, y + 44, Theme::COLOR_FOCUS_CYAN, 13);"""

    assert old_dl_render in content, "old_dl_render not found"
    content = content.replace(old_dl_render, new_dl_render, 1)

    app_path.write_text(content, encoding="utf-8")
    print("SUCCESS: downloader/src/ui/app.cpp successfully patched with standalone video icon support!")

if __name__ == "__main__":
    patch_app_cpp()
