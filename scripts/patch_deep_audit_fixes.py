# Deep audit fixes for downloader/src/ui/app.cpp
from pathlib import Path

app_path = Path("downloader/src/ui/app.cpp")
content = app_path.read_text(encoding="utf-8")

# 1. Shutdown cleanup
old_shutdown = """void App::shutdown() {
    saveFavorites();
    m_cancelQueue.store(true);
    if (m_queueThread.joinable()) {
        m_queueThread.join();
    }
    if (m_catalogThread.joinable()) {
        m_catalogThread.join();
    }
    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }
    if (m_startupUpdateThread.joinable()) {
        m_startupUpdateThread.join();
    }
    m_videoPlayer.close();
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }

#ifdef HAS_SDL2"""

new_shutdown = """void App::shutdown() {
    saveFavorites();
    m_cancelQueue.store(true);
    if (m_queueThread.joinable()) {
        m_queueThread.join();
    }
    if (m_catalogThread.joinable()) {
        m_catalogThread.join();
    }
    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }
    if (m_startupUpdateThread.joinable()) {
        m_startupUpdateThread.join();
    }
    m_videoPlayer.close();
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }
    m_cancelCollectionThumb.store(true);
    if (m_collectionThumbThread.joinable()) {
        m_collectionThumbThread.join();
    }

#ifdef HAS_SDL2
    if (m_collectionThumbTexture) {
        SDL_DestroyTexture(m_collectionThumbTexture);
        m_collectionThumbTexture = nullptr;
    }
    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }"""

assert old_shutdown in content, "old_shutdown not found!"
content = content.replace(old_shutdown, new_shutdown, 1)
print("[+] Patched App::shutdown() thread and texture safety")

# 2. Controller device removed handler in handleInput
old_controller_event = """        } else if (event.type == SDL_CONTROLLERDEVICEADDED) {
            if (SDL_IsGameController(event.cdevice.which)) {
                SDL_GameControllerOpen(event.cdevice.which);
            }
        } else if (event.type == SDL_CONTROLLERAXISMOTION) {"""

new_controller_event = """        } else if (event.type == SDL_CONTROLLERDEVICEADDED) {
            if (SDL_IsGameController(event.cdevice.which)) {
                SDL_GameControllerOpen(event.cdevice.which);
            }
        } else if (event.type == SDL_CONTROLLERDEVICEREMOVED) {
            SDL_GameController* pad = SDL_GameControllerFromInstanceID(event.cdevice.which);
            if (pad) {
                SDL_GameControllerClose(pad);
            }
        } else if (event.type == SDL_CONTROLLERAXISMOTION) {"""

assert old_controller_event in content, "old_controller_event not found!"
content = content.replace(old_controller_event, new_controller_event, 1)
print("[+] Patched SDL_CONTROLLERDEVICEREMOVED handling")

# 3. SD card safety buffer check in processSingleDownloadTask
old_proc_task = """    DownloadTask currentTask;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        if (taskIdx < 0 || taskIdx >= static_cast<int>(m_downloadQueue.size())) {
            m_isProcessingQueue.store(false);
            return;
        }
        m_downloadQueue[taskIdx].state = TaskState::Downloading;
        currentTask = m_downloadQueue[taskIdx];
    }

    std::string err;"""

new_proc_task = """    DownloadTask currentTask;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        if (taskIdx < 0 || taskIdx >= static_cast<int>(m_downloadQueue.size())) {
            m_isProcessingQueue.store(false);
            return;
        }
        m_downloadQueue[taskIdx].state = TaskState::Downloading;
        currentTask = m_downloadQueue[taskIdx];
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
    }

    std::string err;"""

assert old_proc_task in content, "old_proc_task not found!"
content = content.replace(old_proc_task, new_proc_task, 1)
print("[+] Patched SD storage safety buffer check in processSingleDownloadTask")

# 4. Retry failed tasks with [A] in Tab::Downloads
old_downloads_btn = """    } else if (m_activeTab == Tab::Downloads) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;"""

new_downloads_btn = """    } else if (m_activeTab == Tab::Downloads) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 0 /* A - Retry failed tasks */) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            int retried = 0;
            for (auto& t : m_downloadQueue) {
                if (t.state == TaskState::Failed) {
                    t.state = TaskState::Pending;
                    t.errorMessage.clear();
                    retried++;
                }
            }
            if (retried > 0) {
                m_statusNotification = (m_language == Language::Russian)
                    ? ("Перезапуск неудачных загрузок: " + std::to_string(retried))
                    : ("Retrying failed tasks: " + std::to_string(retried));
                m_notificationFramesRemaining = 120;
            }
            return;"""

assert old_downloads_btn in content, "old_downloads_btn not found!"
content = content.replace(old_downloads_btn, new_downloads_btn, 1)
print("[+] Patched [A] button to retry failed downloads in Tab::Downloads")

# 5. Update footer hint for Tab::Downloads
old_downloads_hint = """    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [X] Очистить завершённые   [Y] Добавить все недостающие   [B] Назад";"""

new_downloads_hint = """    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [A] Повторить сбои   [ZL/ZR] ±5   [X] Очистить   [Y] Все недостающие   [B] Назад";"""

assert old_downloads_hint in content, "old_downloads_hint not found!"
content = content.replace(old_downloads_hint, new_downloads_hint, 1)
print("[+] Patched Tab::Downloads footer hints")

app_path.write_text(content, encoding="utf-8")
print("[SUCCESS] All deep audit fixes applied to app.cpp successfully!")
