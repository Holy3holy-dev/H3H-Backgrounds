from pathlib import Path

app_cpp = Path("downloader/src/ui/app.cpp")
content = app_cpp.read_text(encoding="utf-8")

# 1. Remove dangerous duplicate legacy NRO cleanup
dup_cleanup = """    // Clean up duplicate legacy NRO at sdmc:/switch/H3H-Backgrounds.nro if we are running in subfolder
    FILE* checkOld = fopen("sdmc:/switch/H3H-Backgrounds.nro", "rb");
    FILE* checkNew = fopen("sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro", "rb");
    if (checkOld && checkNew) {
        fclose(checkOld);
        fclose(checkNew);
        std::remove("sdmc:/switch/H3H-Backgrounds.nro");
        std::cout << "[+] Cleaned up duplicate legacy sdmc:/switch/H3H-Backgrounds.nro" << std::endl;
    } else {
        if (checkOld) fclose(checkOld);
        if (checkNew) fclose(checkNew);
    }"""

if dup_cleanup in content:
    content = content.replace(dup_cleanup, "    // Safe initialization - never delete running binary")
    print("[+] Removed duplicate legacy cleanup")
else:
    print("[-] dup_cleanup not found exactly, searching substring...")
    import re
    content = re.sub(
        r"    // Clean up duplicate legacy NRO.*?if \(checkNew\) fclose\(checkNew\);\n    \}",
        "    // Safe initialization - never delete running binary",
        content,
        flags=re.DOTALL
    )
    print("[+] Replaced regex duplicate cleanup")

# 2. Remove checkForUpdatesStartupAsync() from init()
old_init_end = """    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
    checkForUpdatesStartupAsync();
    return true;"""

new_init_end = """    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
    return true;"""

assert old_init_end in content, "old_init_end not found"
content = content.replace(old_init_end, new_init_end)
print("[+] Removed detached update call from init()")

# 3. Add m_startupUpdateThread join to shutdown()
old_shutdown = """    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }"""

new_shutdown = """    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }
    if (m_startupUpdateThread.joinable()) {
        m_startupUpdateThread.join();
    }"""

assert old_shutdown in content, "old_shutdown not found"
content = content.replace(old_shutdown, new_shutdown)
print("[+] Added startup thread join to shutdown()")

# 4. Replace entire updateApplicationNro with atomic, verified updater
old_nro_updater_start = "void App::updateApplicationNro() {"
old_nro_updater_end = "void App::update() {"

start_idx = content.find(old_nro_updater_start)
end_idx = content.find(old_nro_updater_end)
assert start_idx != -1 and end_idx != -1, "updateApplicationNro block bounds not found"

new_nro_updater = """void App::updateApplicationNro() {
    if (m_isUpdatingNro.load()) {
        return;
    }

    m_nroUpdateBytesDownloaded.store(0);
    m_nroUpdateTotalBytes.store(25165824); // ~24 MB expected release size
    m_activeDialog = DialogType::UpdateProgress;
    m_dialogOpenedAt = SDL_GetTicks();
    m_dialogTitle = (m_language == Language::Russian) ? "Проверка обновлений..." : "Checking for updates...";
    m_dialogMessage = (m_language == Language::Russian)
        ? "Связь с GitHub Releases и проверка версии..."
        : "Checking latest version on GitHub...";
    m_isUpdatingNro = true;

    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }

    m_nroUpdateThread = std::thread([this]() {
        // Step 1: Check remote version without downloading NRO (with cache-buster query)
        std::string versionJsonStr;
        std::string checkErr;
        std::string checkUrl = std::string(Config::VERSION_CHECK_URL) + "?t=" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
        bool checkOk = m_platform->fetchCatalog(checkUrl, versionJsonStr, checkErr);

        std::string latestVer = Config::APP_VERSION;
        std::string releaseNotes = "Пакет обновлений H3H Backgrounds";
        if (checkOk && !versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
                if (vJson.contains("latestVersion")) {
                    latestVer = vJson["latestVersion"].get<std::string>();
                }
                if (vJson.contains("releaseNotes")) {
                    releaseNotes = vJson["releaseNotes"].get<std::string>();
                }
            } catch (...) {}
        }

        // If current version is already up to date, skip download completely
        if (latestVer == Config::APP_VERSION) {
            {
                std::lock_guard<std::mutex> lock(m_nroMutex);
                m_nroUpdateError = "ALREADY_UP_TO_DATE";
                m_nroUpdateSuccess = false;
            }
            m_nroUpdateDone.store(true);
            m_isUpdatingNro.store(false);
            return;
        }

        // Step 2: New version found -> download and install
#ifdef H3H_AFTER_DARK
        std::string nroFileName = "H3H-AfterDark.nro";
        std::string defaultNroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-AfterDark.nro";
        std::string targetSubdir = "H3H-AfterDark";
#else
        std::string nroFileName = "H3H-Backgrounds.nro";
        std::string defaultNroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string targetSubdir = "H3H-Backgrounds";
#endif

        m_dialogTitle = (m_language == Language::Russian)
            ? ("Загрузка обновления v" + latestVer)
            : ("Downloading update v" + latestVer);
        m_dialogMessage = (m_language == Language::Russian)
            ? ("Загрузка " + nroFileName + " с GitHub...")
            : ("Downloading " + nroFileName + " from GitHub...");

        std::string nroUrl = defaultNroUrl;
        if (!versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
#ifdef H3H_AFTER_DARK
                if (vJson.contains("afterDarkDownloadUrl")) {
                    nroUrl = vJson["afterDarkDownloadUrl"].get<std::string>();
                }
#else
                if (vJson.contains("downloadUrl")) {
                    nroUrl = vJson["downloadUrl"].get<std::string>();
                }
#endif
            } catch (...) {}
        }

        // Determine exact destination on MicroSD
        std::string targetNro = m_runningNroPath;
        if (targetNro.empty()) {
            std::string appDir = m_platform->getAppDirectory();
            targetNro = appDir + "/" + nroFileName;
        }

        // Ensure target directory exists
        {
            std::error_code ec;
            std::filesystem::create_directories(std::filesystem::path(targetNro).parent_path(), ec);
        }

        // Temporary download and backup paths in the EXACT same directory to guarantee atomic operations
        std::string tempNro = targetNro + ".new";
        std::string bakNro  = targetNro + ".bak";

        std::atomic<bool> cancel{false};
        std::string err;
        auto progressCb = [this](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
            (void)speedBps;
            m_nroUpdateBytesDownloaded.store(bytesDownloaded);
            if (totalBytes > 0) m_nroUpdateTotalBytes.store(totalBytes);
        };

        // Remove any stale temp download before starting
        std::remove(tempNro.c_str());

        bool ok = m_platform->downloadFile(nroUrl, tempNro, progressCb, cancel, err);
        bool success = false;

        if (ok) {
            // CRITICAL STEP: Integrity Verification before touching existing binary
            bool validNro = false;
            FILE* fp = fopen(tempNro.c_str(), "rb");
            if (fp) {
                fseek(fp, 0, SEEK_END);
                long fsize = ftell(fp);
                // Minimum size for valid H3H NRO with FFmpeg is 15 MB
                if (fsize >= 15 * 1024 * 1024) {
                    fseek(fp, 0x10, SEEK_SET);
                    char magic[4] = {0};
                    if (fread(magic, 1, 4, fp) == 4) {
                        if (magic[0] == 'N' && magic[1] == 'R' && magic[2] == 'O' && magic[3] == '0') {
                            validNro = true;
                        }
                    }
                }
                fclose(fp);
            }

            if (!validNro) {
                std::remove(tempNro.c_str());
                err = (m_language == Language::Russian)
                    ? "Ошибка проверки целостности: загруженный файл поврежден или неполон"
                    : "Integrity check failed: downloaded NRO is incomplete or corrupted";
            } else {
                // Release RomFS so devoptab closes internal handle to argv[0]
                m_platform->releaseRomfs();

                // Safe swap:
                // 1. Rename existing running NRO to .bak
                std::remove(bakNro.c_str());
                std::rename(targetNro.c_str(), bakNro.c_str());

                // 2. Rename .new to targetNro
                if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                    // Success! Remove backup
                    std::remove(bakNro.c_str());
                    success = true;
                } else {
                    // Rename failed (e.g. locked). Try chunked C stream copy
                    FILE* fsrc = fopen(tempNro.c_str(), "rb");
                    FILE* fdst = fopen(targetNro.c_str(), "wb");
                    if (fsrc && fdst) {
                        std::vector<char> buf(64 * 1024);
                        size_t bytesRead;
                        bool copyOk = true;
                        while ((bytesRead = fread(buf.data(), 1, buf.size(), fsrc)) > 0) {
                            if (fwrite(buf.data(), 1, bytesRead, fdst) != bytesRead) {
                                copyOk = false;
                                break;
                            }
                        }
                        fflush(fdst);
                        fclose(fdst);
                        fclose(fsrc);
                        if (copyOk) {
                            std::remove(tempNro.c_str());
                            std::remove(bakNro.c_str());
                            success = true;
                        }
                    } else {
                        if (fsrc) fclose(fsrc);
                        if (fdst) fclose(fdst);
                    }

                    if (!success) {
                        // Rollback from backup! Target is guaranteed intact!
                        std::remove(targetNro.c_str());
                        std::rename(bakNro.c_str(), targetNro.c_str());
                        std::remove(tempNro.c_str());
                        err = "Failed to swap NRO on MicroSD (original preserved)";
                    }
                }
            }
        }

        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            m_nroUpdateError = std::move(err);
            m_nroUpdateSuccess = success;
        }
        m_nroUpdateDone.store(true);
        m_isUpdatingNro.store(false);
    });
}

"""

content = content[:start_idx] + new_nro_updater + content[end_idx:]
print("[+] Replaced updateApplicationNro with atomic, integrity-verified updater")

# 5. In update(), add proactive background update check and result handling
old_update_nro_hook = """    // Process background NRO update result safely on the main thread
    if (m_nroUpdateDone.exchange(false)) {"""

new_update_nro_hook = """    // Proactive background update check after UI has settled (after 2 seconds)
    if (!m_startupUpdateChecked && SDL_GetTicks() > 2000) {
        m_startupUpdateChecked = true;
        if (!m_isCheckingUpdateStartup.load() && !m_isUpdatingNro.load()) {
            m_isCheckingUpdateStartup.store(true);
            if (m_startupUpdateThread.joinable()) {
                m_startupUpdateThread.join();
            }
            m_startupUpdateThread = std::thread([this]() {
                std::string versionJsonStr;
                std::string checkErr;
                std::string checkUrl = std::string(Config::VERSION_CHECK_URL) + "?t=" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
                bool checkOk = m_platform->fetchCatalog(checkUrl, versionJsonStr, checkErr);

                if (checkOk && !versionJsonStr.empty()) {
                    try {
                        auto vJson = nlohmann::json::parse(versionJsonStr);
                        if (vJson.contains("latestVersion")) {
                            std::string latestVer = vJson["latestVersion"].get<std::string>();
                            if (latestVer != Config::APP_VERSION) {
                                std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
                                m_startupUpdateLatestVer = latestVer;
                            }
                        }
                    } catch (...) {}
                }
                m_startupUpdateDone.store(true);
                m_isCheckingUpdateStartup.store(false);
            });
        }
    }

    if (m_startupUpdateDone.exchange(false)) {
        if (m_startupUpdateThread.joinable()) {
            m_startupUpdateThread.join();
        }
        std::string newVer;
        {
            std::lock_guard<std::mutex> lock(m_startupUpdateMutex);
            newVer = std::move(m_startupUpdateLatestVer);
        }
        if (!newVer.empty()) {
            m_statusNotification = (m_language == Language::Russian)
                ? ("✨ Обнаружено обновление v" + newVer + "! Нажмите [-] в Настройках")
                : ("✨ New update v" + newVer + " detected! Press [-] in Settings");
            m_notificationFramesRemaining = 240;
        }
    }

    // Process background NRO update result safely on the main thread
    if (m_nroUpdateDone.exchange(false)) {"""

assert old_update_nro_hook in content, "old_update_nro_hook not found"
content = content.replace(old_update_nro_hook, new_update_nro_hook)
print("[+] Added tracked thread startup check in update()")

# 6. Remove old checkForUpdatesStartupAsync() definition
old_fn_def = """void App::checkForUpdatesStartupAsync() {
    std::thread([this]() {
        // Sleep 1 second after startup so the main UI settles cleanly
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        
        std::string versionJsonStr;
        std::string checkErr;
        std::string checkUrl = std::string(Config::VERSION_CHECK_URL) + "?t=" + std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
        bool checkOk = m_platform->fetchCatalog(checkUrl, versionJsonStr, checkErr);

        if (checkOk && !versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
                if (vJson.contains("latestVersion")) {
                    std::string latestVer = vJson["latestVersion"].get<std::string>();
                    if (latestVer != Config::APP_VERSION) {
                        m_statusNotification = (m_language == Language::Russian)
                            ? ("✨ Обнаружено обновление v" + latestVer + "! Нажмите [-] в Настройках")
                            : ("✨ New update v" + latestVer + " detected! Press [-] in Settings");
                        m_notificationFramesRemaining = 240; // ~4 seconds toast at 60 FPS
                    }
                }
            } catch (...) {}
        }
    }).detach();
}"""

if old_fn_def in content:
    content = content.replace(old_fn_def, "")
    print("[+] Removed old checkForUpdatesStartupAsync definition")
else:
    print("[-] Old definition not found verbatim, cleaning via regex...")
    import re
    content = re.sub(
        r"void App::checkForUpdatesStartupAsync\(\)\s*\{.*?\}\)\.detach\(\);\s*\}",
        "",
        content,
        flags=re.DOTALL
    )
    print("[+] Removed via regex")

app_cpp.write_text(content, encoding="utf-8")
print("[SUCCESS] app.cpp patched successfully!")
