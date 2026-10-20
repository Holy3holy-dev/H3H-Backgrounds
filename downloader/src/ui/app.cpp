#include "ui/app.hpp"
#include "core/config.hpp"
#include "core/installer.hpp"
#include "core/json.hpp"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <fstream>
#include <filesystem>
#include <cmath>

#ifdef __SWITCH__
#include <switch.h>
#endif

#ifdef HAS_SDL2
#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <SDL2/SDL_image.h>
#endif

namespace h3h {
namespace ui {

App::App(std::unique_ptr<IPlatform> platform)
    : m_platform(std::move(platform)) {}

App::~App() {
    shutdown();
}

bool App::init() {
    if (!m_platform || !m_platform->initialize()) {
        std::cerr << "[-] Failed to initialize platform layer" << std::endl;
        return false;
    }

    m_sysInfo = m_platform->getSystemInfo();

    // Load initial catalog (cache -> romfs -> local dev)
    std::string catError;
    if (!m_catalogManager.loadFromFile(m_platform->getAppDirectory() + "/cache.json", catError)) {
        if (!m_catalogManager.loadFromFile("romfs:/catalog.json", catError)) {
            m_catalogManager.loadFromFile("catalog/data/catalog.json", catError);
        }
    }

    // Clean up duplicate legacy NRO at sdmc:/switch/H3H-Backgrounds.nro if we are running in subfolder
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
    }

    refreshInstalledGames();

#ifdef HAS_SDL2
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER) != 0) {
        std::cerr << "[-] SDL_Init failed: " << SDL_GetError() << std::endl;
        return false;
    }

    if (TTF_Init() != 0) {
        std::cerr << "[-] TTF_Init failed: " << TTF_GetError() << std::endl;
    }

#ifdef __SWITCH__
    PlFontData fontData;
    Result rc = plGetSharedFontByType(&fontData, PlSharedFontType_Standard);
    if (R_SUCCEEDED(rc) && fontData.address && fontData.size > 0) {
        m_fontMemBuffer = fontData.address;
        m_fontMemSize = fontData.size;
        std::cout << "[+] Loaded Switch Horizon shared font (" << fontData.size << " bytes)" << std::endl;
    } else {
        std::cerr << "[-] plGetSharedFontByType returned 0x" << std::hex << rc << std::endl;
    }
#endif

    m_window = SDL_CreateWindow(
        "H3H Backgrounds",
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        Theme::SCREEN_WIDTH,
        Theme::SCREEN_HEIGHT,
        SDL_WINDOW_SHOWN
    );

    if (!m_window) {
        std::cerr << "[-] SDL_CreateWindow failed: " << SDL_GetError() << std::endl;
        return false;
    }

    m_renderer = SDL_CreateRenderer(
        m_window,
        -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC
    );

    if (!m_renderer) {
        std::cerr << "[-] SDL_CreateRenderer failed: " << SDL_GetError() << std::endl;
        return false;
    }

    // Enable high-quality alpha blending for 4IFIR frosted glass effects
    SDL_SetRenderDrawBlendMode(m_renderer, SDL_BLENDMODE_BLEND);

    // Register 1:1 physical Switch button mapping in SDL2 GameController database:
    // Physical Joy-Con / Pro Controller layout:
    // A = Button 0 (East / Right) -> SDL_CONTROLLER_BUTTON_A
    // B = Button 1 (South / Bottom) -> SDL_CONTROLLER_BUTTON_B
    // X = Button 2 (North / Top) -> SDL_CONTROLLER_BUTTON_X
    // Y = Button 3 (West / Left) -> SDL_CONTROLLER_BUTTON_Y
    //
    // By default, devkitPro SDL2 uses Xbox-style layout: a:b1, b:b0, x:b3, y:b2
    // which inverts A <-> B and X <-> Y.
    // Registering 1:1 mappings ensures that physical button A confirms/installs,
    // and physical button B cancels/returns.
    const char* switchGuid = "000038f853776974636820436f6e7400";
    std::string defaultSwitchMapping = std::string(switchGuid) + ",Switch Controller,"
        "a:b0,b:b1,back:b11,dpdown:b15,dpleft:b12,dpright:b14,dpup:b13,"
        "leftshoulder:b6,leftstick:b4,lefttrigger:b8,leftx:a0,lefty:a1,"
        "rightshoulder:b7,rightstick:b5,righttrigger:b9,rightx:a2,righty:a3,"
        "start:b10,x:b2,y:b3,";
    SDL_GameControllerAddMapping(defaultSwitchMapping.c_str());

    for (int i = 0; i < SDL_NumJoysticks(); ++i) {
        SDL_JoystickGUID guid = SDL_JoystickGetDeviceGUID(i);
        char guidStr[64];
        SDL_JoystickGetGUIDString(guid, guidStr, sizeof(guidStr));
        std::string customMapping = std::string(guidStr) + ",Switch Controller,"
            "a:b0,b:b1,back:b11,dpdown:b15,dpleft:b12,dpright:b14,dpup:b13,"
            "leftshoulder:b6,leftstick:b4,lefttrigger:b8,leftx:a0,lefty:a1,"
            "rightshoulder:b7,rightstick:b5,righttrigger:b9,rightx:a2,righty:a3,"
            "start:b10,x:b2,y:b3,";
        SDL_GameControllerAddMapping(customMapping.c_str());
        if (SDL_IsGameController(i)) {
            SDL_GameControllerOpen(i);
        }
    }
#endif

    std::cout << "[+] H3H Backgrounds App initialized successfully." << std::endl;
    return true;
}

void App::shutdown() {
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

#ifdef HAS_SDL2
    for (auto& pair : m_fonts) {
        if (pair.second) {
            TTF_CloseFont(pair.second);
        }
    }
    m_fonts.clear();

    if (m_renderer) {
        SDL_DestroyRenderer(m_renderer);
        m_renderer = nullptr;
    }
    if (m_window) {
        SDL_DestroyWindow(m_window);
        m_window = nullptr;
    }
    TTF_Quit();
    SDL_Quit();
#endif
    if (m_platform) {
        m_platform->shutdown();
    }
}

void App::refreshInstalledGames() {
    m_platform->listInstalledTitles(m_installedGames);
    m_catalogManager.matchInstalledTitles(m_installedGames);
}

void App::fetchRemoteCatalog() {
    if (m_isFetchingCatalog.load()) {
        m_statusNotification = (m_language == Language::Russian)
            ? "Каталог уже загружается..."
            : "Catalog download is already in progress...";
        m_notificationFramesRemaining = 90;
        return;
    }

    m_statusNotification = (m_language == Language::Russian)
        ? "Загрузка каталога с GitHub..."
        : "Fetching catalog from GitHub...";
    m_notificationFramesRemaining = 120;
    m_isFetchingCatalog = true;

    if (m_catalogThread.joinable()) {
        m_catalogThread.join();
    }

    m_catalogThread = std::thread([this]() {
        std::string jsonStr;
        std::string err;
        bool ok = m_platform->fetchCatalog(Config::DEFAULT_CATALOG_URL, jsonStr, err);
        {
            std::lock_guard<std::mutex> lock(m_catalogMutex);
            m_fetchedJson = std::move(jsonStr);
            m_fetchError = std::move(err);
            m_fetchSuccess = ok;
        }
        m_catalogFetchDone.store(true);
        m_isFetchingCatalog.store(false);
    });
}

void App::updateApplicationNro() {
    if (m_isUpdatingNro.load()) {
        return;
    }

    m_nroUpdateBytesDownloaded.store(0);
    m_nroUpdateTotalBytes.store(10614212); // Expected release size
    m_activeDialog = DialogType::UpdateProgress;
    m_dialogTitle = (m_language == Language::Russian) ? "Проверка обновлений..." : "Checking for updates...";
    m_dialogMessage = (m_language == Language::Russian)
        ? "Связь с GitHub Releases и проверка версии..."
        : "Checking latest version on GitHub...";
    m_isUpdatingNro = true;

    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }

    m_nroUpdateThread = std::thread([this]() {
        // Step 1: Check remote version without downloading NRO
        std::string versionJsonStr;
        std::string checkErr;
        bool checkOk = m_platform->fetchCatalog(Config::VERSION_CHECK_URL, versionJsonStr, checkErr);

        std::string latestVer = Config::APP_VERSION;
        std::string releaseNotes = "Пакет улучшений 4IFIR Cyber-Glass";
        if (checkOk && !versionJsonStr.empty()) {
            try {
                auto vJson = nlohmann::json::parse(versionJsonStr);
                if (vJson.contains("latestVersion")) {
                    latestVer = vJson["latestVersion"].get<std::string>();
                }
                if (vJson.contains("releaseNotes")) {
                    releaseNotes = vJson["releaseNotes"].get<std::string>();
                }
            } catch (...) {
                // Ignore parse errors, fallback to direct download if needed
            }
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
        m_dialogTitle = (m_language == Language::Russian)
            ? ("Загрузка обновления v" + latestVer)
            : ("Downloading update v" + latestVer);
        m_dialogMessage = (m_language == Language::Russian)
            ? ("Загрузка H3H-Backgrounds.nro с GitHub (" + releaseNotes + ")...")
            : ("Downloading new release from GitHub...");

        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        
        std::vector<std::string> targetNros = {
            appDir + "/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds/H3H-Backgrounds.nro",
            "sdmc:/switch/H3H-Backgrounds.nro"
        };
        if (!m_runningNroPath.empty()) {
            targetNros.insert(targetNros.begin(), m_runningNroPath);
        }

        std::atomic<bool> cancel{false};
        std::string err;
        auto progressCb = [this](uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps) {
            (void)speedBps;
            m_nroUpdateBytesDownloaded.store(bytesDownloaded);
            if (totalBytes > 0) m_nroUpdateTotalBytes.store(totalBytes);
        };

        bool ok = m_platform->downloadFile(nroUrl, tempNro, progressCb, cancel, err);
        bool success = false;
        if (ok) {
            // Release romfs handle so Horizon OS FAT32 unlocks the executing .nro file
            m_platform->releaseRomfs();

            for (const auto& targetNro : targetNros) {
                std::error_code ec;
                std::filesystem::create_directories(std::filesystem::path(targetNro).parent_path(), ec);

                // 1. Try atomic rename
                std::remove(targetNro.c_str());
                if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                    success = true;
                    break;
                }

                // 2. Binary stream copy fallback (overwrites existing open FAT32 files safely)
                std::ifstream src(tempNro, std::ios::binary);
                if (src.is_open()) {
                    std::ofstream dst(targetNro, std::ios::binary | std::ios::trunc);
                    if (dst.is_open()) {
                        dst << src.rdbuf();
                        dst.flush();
                        success = true;
                        break;
                    }
                }
            }

            std::remove(tempNro.c_str());
            m_platform->restoreRomfs();

            if (!success) {
                err = "Failed to replace H3H-Backgrounds.nro file";
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

void App::update() {
    // Process background catalog fetch result safely on the main thread
    if (m_catalogFetchDone.exchange(false)) {
        std::string jsonStr;
        std::string err;
        bool ok = false;
        {
            std::lock_guard<std::mutex> lock(m_catalogMutex);
            jsonStr = std::move(m_fetchedJson);
            err = std::move(m_fetchError);
            ok = m_fetchSuccess;
        }
        if (m_catalogThread.joinable()) {
            m_catalogThread.join();
        }

        if (ok && !jsonStr.empty()) {
            std::string parseErr;
            if (m_catalogManager.loadFromJsonString(jsonStr, parseErr)) {
                m_catalogManager.saveToCacheFile(m_platform->getAppDirectory() + "/cache.json");
                m_catalogManager.matchInstalledTitles(m_installedGames);
                m_statusNotification = (m_language == Language::Russian)
                    ? ("Каталог успешно обновлён (" + std::to_string(m_catalogManager.getGamesCount()) + " игр)")
                    : ("Catalog updated successfully (" + std::to_string(m_catalogManager.getGamesCount()) + " games)");
                m_notificationFramesRemaining = 180;
            } else {
                m_statusNotification = (m_language == Language::Russian)
                    ? ("Ошибка структуры каталога: " + parseErr)
                    : ("Catalog schema error: " + parseErr);
                m_notificationFramesRemaining = 240;
            }
        } else {
            m_statusNotification = (m_language == Language::Russian)
                ? ("Ошибка сети: " + err)
                : ("Network error: " + err);
            m_notificationFramesRemaining = 240;
        }
    }

    // Process background NRO update result safely on the main thread
    if (m_nroUpdateDone.exchange(false)) {
        std::string err;
        bool ok = false;
        {
            std::lock_guard<std::mutex> lock(m_nroMutex);
            err = std::move(m_nroUpdateError);
            ok = m_nroUpdateSuccess;
        }
        if (m_nroUpdateThread.joinable()) {
            m_nroUpdateThread.join();
        }

        if (ok) {
            m_activeDialog = DialogType::UpdateSuccess;
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление завершено!" : "Update Complete!";
            m_dialogMessage = (m_language == Language::Russian)
                ? "Приложение H3H-Backgrounds.nro успешно обновлено до актуальной версии!\nНажмите [A], чтобы перезапустить сейчас, или [B] для продолжения."
                : "H3H-Backgrounds.nro updated successfully!\nPress [A] to restart now, or [B] to continue.";
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Приложение обновлено!" : "Updated!";
        } else if (err == "ALREADY_UP_TO_DATE") {
            m_activeDialog = DialogType::MessageAlert;
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление не требуется" : "Up to date";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("У вас уже установлена актуальная версия:\nH3H-Backgrounds v" + std::string(Config::APP_VERSION) + ".\nНовых версий на сервере не найдено.")
                : ("You are already running the latest version:\nv" + std::string(Config::APP_VERSION) + ".");
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Установлена последняя версия" : "Up to date";
        } else {
            m_activeDialog = DialogType::MessageAlert;
            m_dialogTitle = (m_language == Language::Russian) ? "Ошибка обновления" : "Update Error";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("Не удалось проверить или применить обновление: " + err)
                : ("Failed to apply update: " + err);
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? ("Ошибка: " + err) : ("Error: " + err);
        }
        m_notificationFramesRemaining = 240;
    }

    // Process background queue task completion
    if (m_queueTaskFinished.exchange(false)) {
        refreshInstalledGames();
    }

    // Process next pending download task in background
    if (!m_isProcessingQueue.load()) {
        if (m_queueThread.joinable()) {
            m_queueThread.join();
        }

        int nextPendingIdx = -1;
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            for (size_t i = 0; i < m_downloadQueue.size(); ++i) {
                if (m_downloadQueue[i].state == TaskState::Pending) {
                    nextPendingIdx = static_cast<int>(i);
                    break;
                }
            }
        }

        if (nextPendingIdx != -1) {
            m_isProcessingQueue.store(true);
            m_queueThread = std::thread([this, nextPendingIdx]() {
                processSingleDownloadTask(nextPendingIdx);
            });
        }
    }
}

int App::getMissingCoversCount() const {
    int count = 0;
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
                count++;
            }
        }
    }
    return count;
}

void App::installAllMissing() {
    int missing = getMissingCoversCount();
    if (missing == 0) {
        m_statusNotification = (m_language == Language::Russian)
            ? "Все доступные видеофоны уже установлены или находятся в очереди!"
            : "All available video covers are already installed or in queue!";
        m_notificationFramesRemaining = 180;
        return;
    }

    m_activeDialog = DialogType::ConfirmInstallAll;
    m_dialogTitle = (m_language == Language::Russian)
        ? "Установка всех недостающих"
        : "Install All Missing Covers";
    m_dialogMessage = (m_language == Language::Russian)
        ? ("Найдено игр без видеофона: " + std::to_string(missing) + ".\nЗагрузить и установить видеофоны для всех?")
        : ("Found " + std::to_string(missing) + " games without covers.\nDownload and install covers for all?");
    m_dialogFocus = 0;
}

void App::processSingleDownloadTask(int taskIdx) {
    DownloadTask currentTask;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        if (taskIdx < 0 || taskIdx >= static_cast<int>(m_downloadQueue.size())) {
            m_isProcessingQueue.store(false);
            return;
        }
        m_downloadQueue[taskIdx].state = TaskState::Downloading;
        currentTask = m_downloadQueue[taskIdx];
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
        currentTask.variant.url,
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

    InstallResult res = Installer::installVariant(
        m_platform->getCoversDirectory(),
        currentTask.titleId,
        currentTask.tempFilePath,
        currentTask.variant.sha256,
        currentTask.variant.sizeBytes,
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
}

void App::queueDownload(const InstalledTitle& title, const Variant& variant) {
    DownloadTask task;
    task.id = title.titleId + "_" + variant.id;
    task.titleId = title.titleId;
    task.gameTitle = title.name;
    task.variant = variant;
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
        ? ("Добавлено в очередь: " + title.name + " (" + variant.name + ")")
        : ("Added to queue: " + title.name + " (" + variant.name + ")");
    m_notificationFramesRemaining = 180;
}

void App::executeRestoreBackup(const std::string& titleId) {
    InstallResult res = Installer::restoreBackup(m_platform->getCoversDirectory(), titleId);
    if (res.success) {
        m_statusNotification = "Копия успешно восстановлена!";
    } else {
        m_statusNotification = "Ошибка: " + res.message;
    }
    m_notificationFramesRemaining = 200;
    refreshInstalledGames();
}

void App::executeDeleteCover(const std::string& titleId) {
    bool deleted = Installer::deleteCover(m_platform->getCoversDirectory(), titleId, false);
    if (deleted) {
        m_statusNotification = "Видеофон удалён (копия .bak сохранена)";
    } else {
        m_statusNotification = "Видеофон не найден";
    }
    m_notificationFramesRemaining = 180;
    refreshInstalledGames();
}

void App::handleInput() {
#ifdef HAS_SDL2
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_QUIT) {
            m_running = false;
        } else if (event.type == SDL_CONTROLLERBUTTONDOWN) {
            onButtonPress(event.cbutton.button);
        } else if (event.type == SDL_CONTROLLERAXISMOTION) {
            // Analog stick scrolling (Left Stick Y / X)
            if (event.caxis.axis == SDL_CONTROLLER_AXIS_LEFTY) {
                uint32_t now = SDL_GetTicks();
                if (now - m_lastStickScrollTime > 160) {
                    if (event.caxis.value > 16000) {
                        onButtonPress(12 /* DPAD_DOWN */);
                        m_lastStickScrollTime = now;
                    } else if (event.caxis.value < -16000) {
                        onButtonPress(11 /* DPAD_UP */);
                        m_lastStickScrollTime = now;
                    }
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_LEFTX) {
                uint32_t now = SDL_GetTicks();
                if (now - m_lastStickScrollTime > 200) {
                    if (event.caxis.value > 18000) {
                        onButtonPress(14 /* DPAD_RIGHT */);
                        m_lastStickScrollTime = now;
                    } else if (event.caxis.value < -18000) {
                        onButtonPress(13 /* DPAD_LEFT */);
                        m_lastStickScrollTime = now;
                    }
                }
            }
        } else if (event.type == SDL_MOUSEWHEEL) {
            if (event.wheel.y > 0) {
                onButtonPress(11 /* DPAD_UP */);
            } else if (event.wheel.y < 0) {
                onButtonPress(12 /* DPAD_DOWN */);
            }
        } else if (event.type == SDL_MOUSEBUTTONDOWN) {
            // Touch / mouse support on Nintendo Switch
            int mx = event.button.x;
            int my = event.button.y;

            // If dialog is open, handle direct taps on dialog buttons
            if (m_activeDialog != DialogType::None) {
                // Confirm button: x in [440, 610], y in [400, 450]
                if (my >= 400 && my <= 450 && mx >= 440 && mx <= 610) {
                    m_dialogFocus = 0;
                    onButtonPress(0 /* A - Confirm */);
                }
                // Cancel button: x in [650, 820], y in [400, 450]
                else if (my >= 400 && my <= 450 && mx >= 650 && mx <= 820) {
                    m_dialogFocus = 1;
                    onButtonPress(1 /* B - Cancel */);
                }
                // Outside dialog: dismiss
                else if (mx < 315 || mx > 965 || my < 235 || my > 485) {
                    m_activeDialog = DialogType::None;
                }
                continue;
            }

            // Top Header tabs: y in [10, 55]
            if (my >= 10 && my <= 55) {
                if (mx >= 340 && mx < 460) m_activeTab = Tab::Home;
                else if (mx >= 460 && mx < 580) m_activeTab = Tab::MyGames;
                else if (mx >= 580 && mx < 700) m_activeTab = Tab::Catalog;
                else if (mx >= 700 && mx < 820) m_activeTab = Tab::Downloads;
                else if (mx >= 820 && mx < 940) m_activeTab = Tab::Settings;
            }
            // Home Tab: click on Action Card "Установить все недостающие" (y in [260, 380])
            else if (m_activeTab == Tab::Home && mx >= 60 && mx <= 1220 && my >= 260 && my <= 380) {
                installAllMissing();
            }
            // Home Tab: click on Metric Cards
            else if (m_activeTab == Tab::Home && my >= 100 && my <= 240) {
                if (mx >= 60 && mx <= 820) m_activeTab = Tab::MyGames;
                else if (mx >= 860 && mx <= 1220) fetchRemoteCatalog();
            }
            // Home Tab: quick navigation cards at y in [400, 490]
            else if (m_activeTab == Tab::Home && my >= 400 && my <= 490) {
                if (mx >= 60 && mx <= 620) m_activeTab = Tab::MyGames;
                else if (mx >= 660 && mx <= 1220) fetchRemoteCatalog();
            }
            // MyGames Tab: top-right "Установить все" button: x in [950, 1230], y in [95, 140]
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
            }
            // Catalog Tab: top-right "[-] Обновить" button: x in [980, 1220], y in [95, 145]
            else if (m_activeTab == Tab::Catalog && mx >= 980 && mx <= 1220 && my >= 95 && my <= 145) {
                onButtonPress(4 /* Minus / Refresh */);
            }
            // Catalog Tab: top-right "Установить недостающие" button: x in [680, 960], y in [95, 145]
            else if (m_activeTab == Tab::Catalog && mx >= 680 && mx <= 960 && my >= 95 && my <= 145) {
                installAllMissing();
            }
            // Catalog Tab: click directly on an item in the list
            else if (m_activeTab == Tab::Catalog && mx >= 60 && mx <= 1220 && my >= 160 && my <= 640) {
                int clickedIndex = m_catalogScrollOffset + (my - 160) / 95;
                if (clickedIndex >= 0 && clickedIndex < static_cast<int>(m_catalogManager.getAllGames().size())) {
                    m_catalogSelectedIndex = clickedIndex;
                }
            }
            // Settings Tab: buttons at y in [300, 350]
            else if (m_activeTab == Tab::Settings && my >= 300 && my <= 350) {
                if (mx >= 60 && mx <= 340) onButtonPress(2 /* Clear Cache */);
                else if (mx >= 370 && mx <= 690) onButtonPress(3 /* Refresh Catalog */);
                else if (mx >= 720 && mx <= 1060) onButtonPress(6 /* Update NRO */);
            }
            // Footer bar click on refresh: y in [660, 720]
            else if (my >= 660 && mx >= 1050) {
                onButtonPress(4 /* Minus / Refresh */);
            }
        } else if (event.type == SDL_KEYDOWN) {
            // Keyboard simulation on PC
            switch (event.key.keysym.sym) {
                case SDLK_UP:     onButtonPress(SDL_CONTROLLER_BUTTON_DPAD_UP); break;
                case SDLK_DOWN:   onButtonPress(SDL_CONTROLLER_BUTTON_DPAD_DOWN); break;
                case SDLK_LEFT:   onButtonPress(SDL_CONTROLLER_BUTTON_DPAD_LEFT); break;
                case SDLK_RIGHT:  onButtonPress(SDL_CONTROLLER_BUTTON_DPAD_RIGHT); break;
                case SDLK_RETURN:
                case SDLK_a:      onButtonPress(SDL_CONTROLLER_BUTTON_A); break;
                case SDLK_ESCAPE:
                case SDLK_b:      onButtonPress(SDL_CONTROLLER_BUTTON_B); break;
                case SDLK_x:      onButtonPress(SDL_CONTROLLER_BUTTON_X); break;
                case SDLK_y:      onButtonPress(SDL_CONTROLLER_BUTTON_Y); break;
                case SDLK_q:      onButtonPress(SDL_CONTROLLER_BUTTON_LEFTSHOULDER); break;
                case SDLK_e:      onButtonPress(SDL_CONTROLLER_BUTTON_RIGHTSHOULDER); break;
                case SDLK_MINUS:
                case SDLK_m:
                case SDLK_r:      onButtonPress(SDL_CONTROLLER_BUTTON_BACK); break; // Minus (Refresh)
                case SDLK_EQUALS:
                case SDLK_PLUS:
                case SDLK_p:      onButtonPress(SDL_CONTROLLER_BUTTON_START); break; // Plus (Update NRO)
                default: break;
            }
        }
    }
#endif
}

void App::onButtonPress(int button) {
    // If Dialog is active, route all input to dialog
    if (m_activeDialog != DialogType::None) {
        if (m_activeDialog == DialogType::UpdateProgress) {
            // While downloading, allow B to hide modal to background
            if (button == 1 /* B */) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::UpdateSuccess) {
            if (button == 0 /* A - Restart App */) {
                m_running = false; // Exit to hbmenu so user launches newly updated NRO
            } else if (button == 1 /* B - Continue */) {
                m_activeDialog = DialogType::None;
            }
            return;
        }
        if (m_activeDialog == DialogType::MessageAlert) {
            if (button == 0 || button == 1) {
                m_activeDialog = DialogType::None;
            }
            return;
        }

        if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            m_dialogFocus = 1 - m_dialogFocus;
        } else if (button == 0 /* A - Confirm */) {
            if (m_dialogFocus == 0) { // Yes / Confirm
                if (m_activeDialog == DialogType::ConfirmInstall) {
                    for (const auto& g : m_installedGames) {
                        if (g.titleId == m_pendingActionTitleId) {
                            queueDownload(g, m_pendingActionVariant);
                            break;
                        }
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
        }
        return;
    }

    // Universal Minus (-) button: Global Refresh
    if (button == 4 /* SDL_CONTROLLER_BUTTON_BACK (Minus / -) */) {
        fetchRemoteCatalog();
        return;
    }

    // Standard Nintendo Switch [B] button: Return to Home tab from any view
    if (button == 1 /* B - Back */) {
        if (m_activeTab != Tab::Home) {
            m_activeTab = Tab::Home;
            return;
        }
    }

    // Tab switching with Shoulder buttons (L/R)
    if (button == 9 /* LEFTSHOULDER */) {
        int tabInt = static_cast<int>(m_activeTab);
        tabInt = (tabInt == 0) ? 4 : tabInt - 1;
        m_activeTab = static_cast<Tab>(tabInt);
        return;
    }
    if (button == 10 /* RIGHTSHOULDER */) {
        int tabInt = static_cast<int>(m_activeTab);
        tabInt = (tabInt == 4) ? 0 : tabInt + 1;
        m_activeTab = static_cast<Tab>(tabInt);
        return;
    }

    // View-specific input handling
    if (m_activeTab == Tab::Home) {
        if (button == 0 /* A - Enter My Games */) {
            m_activeTab = Tab::MyGames;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        } else if (button == 2 /* X - Refresh */) {
            fetchRemoteCatalog();
        }
    } else if (m_activeTab == Tab::MyGames) {
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
    } else if (m_activeTab == Tab::Catalog) {
        int totalGames = static_cast<int>(m_catalogManager.getAllGames().size());
        if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) m_catalogSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) m_catalogSelectedIndex++;
        } else if (button == 2 /* X */ || button == 0 /* A */) {
            fetchRemoteCatalog();
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        }
    } else if (m_activeTab == Tab::Downloads) {
        if (button == 11 /* DPAD_UP */) {
            if (m_downloadsScrollOffset > 0) m_downloadsScrollOffset--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_downloadsScrollOffset + 5 < static_cast<int>(m_downloadQueue.size())) m_downloadsScrollOffset++;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        }
    } else if (m_activeTab == Tab::Settings) {
        if (button == 11 /* DPAD_UP */) {
            if (m_settingsSelectedIndex > 0) m_settingsSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_settingsSelectedIndex < 4) m_settingsSelectedIndex++;
        } else if (button == 0 /* A - Activate Selected Setting */) {
            switch (m_settingsSelectedIndex) {
                case 0: // Check & Update NRO
                    updateApplicationNro();
                    break;
                case 1: // Refresh Catalog
                    fetchRemoteCatalog();
                    break;
                case 2: // Toggle Language
                    m_language = (m_language == Language::Russian) ? Language::English : Language::Russian;
                    m_statusNotification = (m_language == Language::Russian) ? "Язык интерфейса: Русский" : "Interface language: English";
                    m_notificationFramesRemaining = 120;
                    break;
                case 3: // Clear Cache
                    m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
                    refreshInstalledGames();
                    m_statusNotification = getStrings(m_language).cacheClearedMsg;
                    m_notificationFramesRemaining = 120;
                    break;
                case 4: // Storage refresh
                    m_sysInfo = m_platform->getSystemInfo();
                    m_statusNotification = "Память MicroSD обновлена";
                    m_notificationFramesRemaining = 90;
                    break;
            }
        } else if (button == 2 /* X - Clear Cache */) {
            m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
            refreshInstalledGames();
            m_statusNotification = getStrings(m_language).cacheClearedMsg;
            m_notificationFramesRemaining = 120;
        } else if (button == 3 /* Y - Refresh Catalog */) {
            fetchRemoteCatalog();
        } else if (button == 6 /* START / Plus - Update App NRO */) {
            updateApplicationNro();
        }
    }
}

void App::render() {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    // Clear background
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, Theme::COLOR_BG_BASE);

    renderHeader();

    switch (m_activeTab) {
        case Tab::Home:      renderTabHome(); break;
        case Tab::MyGames:   renderTabMyGames(); break;
        case Tab::Catalog:   renderTabCatalog(); break;
        case Tab::Downloads: renderTabDownloads(); break;
        case Tab::Settings:  renderTabSettings(); break;
    }

    renderFooter();

    if (m_activeDialog != DialogType::None) {
        renderDialog();
    }

    // Status notification overlay
    if (m_notificationFramesRemaining > 0) {
        drawRect(340, 630, 600, 36, Theme::COLOR_BG_ELEVATED);
        drawRectOutline(340, 630, 600, 36, Theme::COLOR_ACCENT, 2);
        drawText(m_statusNotification, 360, 640, Theme::COLOR_TEXT_PRIMARY, 14);
        m_notificationFramesRemaining--;
    }

    SDL_RenderPresent(m_renderer);
#endif
}

void App::renderHeader() {
    const auto& s = getStrings(m_language);

    // 4IFIR Cyber-Glass Top Bar
    drawRect(0, 0, Theme::SCREEN_WIDTH, 60, Theme::COLOR_BG_BASE);
    drawRect(0, 59, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // App Title with Cyber Accent
    drawText(s.appTitle, 30, 18, Theme::COLOR_TEXT_PRIMARY, 20);

    // Frosted Glass Tab Pills
    const char* tabs[] = {s.tabHome, s.tabMyGames, s.tabCatalog, s.tabDownloads, s.tabSettings};
    int tabX = 330;
    for (int i = 0; i < 5; ++i) {
        bool isActive = (static_cast<int>(m_activeTab) == i);
        if (isActive) {
            drawRect(tabX - 8, 12, 114, 36, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(tabX - 8, 12, 114, 36, 2);
        } else {
            drawRect(tabX - 8, 12, 114, 36, {0x13, 0x18, 0x24, 0x55});
            drawRectOutline(tabX - 8, 12, 114, 36, Theme::COLOR_BORDER, 1);
        }
        drawText(tabs[i], tabX + 8, 22, isActive ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 15);
        tabX += 122;
    }

    // 4IFIR Active Badge
    drawRect(960, 14, 130, 32, {0x10, 0xB9, 0x81, 0x22});
    drawRectOutline(960, 14, 130, 32, Theme::COLOR_SUCCESS, 1);
    drawText("4IFIR ACTIVE", 975, 23, Theme::COLOR_SUCCESS, 12);

    // Version Pill
    drawRect(1105, 14, 145, 32, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(1105, 14, 145, 32, Theme::COLOR_FOCUS_CYAN, 1);
    std::string verStr = "v" + std::string(Config::APP_VERSION) + " (" + std::to_string(m_sysInfo.batteryPercent) + "%)";
    drawText(verStr, 1120, 23, Theme::COLOR_FOCUS_CYAN, 13);
}

void App::renderFooter() {
    const auto& s = getStrings(m_language);

    // 4IFIR Translucent Bottom Control Bar
    drawRect(0, 670, Theme::SCREEN_WIDTH, 50, Theme::COLOR_BG_BASE);
    drawRect(0, 670, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    std::string hints;
    if (m_activeTab == Tab::Home) {
        hints = "[L/R] Вкладки   [A] Мои игры   [Y] Установить все недостающие   [X] Обновить   [-] GitHub";
    } else if (m_activeTab == Tab::MyGames) {
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
    } else if (m_activeTab == Tab::Catalog) {
        hints = "[L/R] Вкладки   [B] Назад   [-] / [X] Обновить каталог   [Y] Установить недостающие";
    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [B] Назад   [-] Обновить каталог";
    } else if (m_activeTab == Tab::Settings) {
        hints = "[L/R] Вкладки   [D-Pad Вверх/Вниз] Выбор   [A] Применить   [B] Назад   [X] Сброс кэша";
    }

    drawText(hints, 30, 685, Theme::COLOR_TEXT_MUTED, 14);

    // 4IFIR Cyber-Glass Touch Refresh Button
    drawGlassCard(1070, 675, 180, 38, true, false);
    drawText("[-] " + std::string(s.actionRefresh), 1095, 686, Theme::COLOR_FOCUS_CYAN, 14);
}

void App::renderTabHome() {
    const auto& s = getStrings(m_language);

    size_t detected = m_installedGames.size();
    size_t installedCovers = 0;
    for (const auto& g : m_installedGames) {
        if (g.hasInstalledCover) installedCovers++;
    }
    size_t catalogCount = m_catalogManager.getGamesCount();
    int missing = getMissingCoversCount();

    // 4IFIR Cyber-Glass Metric Cards
    // Metric Card 1: Detected Games
    drawGlassCard(60, 95, 360, 145, false, true);
    drawText(s.statDetectedGames, 85, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(detected), 85, 145, Theme::COLOR_TEXT_PRIMARY, 44);
    drawRect(85, 202, 190, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(85, 202, 190, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("[A] Мои игры", 95, 208, Theme::COLOR_FOCUS_CYAN, 12);

    // Metric Card 2: Installed Covers
    drawGlassCard(460, 95, 360, 145, false, true);
    drawText(s.statInstalledCovers, 485, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(installedCovers), 485, 145, Theme::COLOR_SUCCESS, 44);
    int missingInstalled = (detected > installedCovers) ? static_cast<int>(detected - installedCovers) : 0;
    drawRect(485, 202, 190, 26, {0x10, 0xB9, 0x81, 0x22});
    drawRectOutline(485, 202, 190, 26, Theme::COLOR_SUCCESS, 1);
    std::string missStr = (missingInstalled == 0) ? "Все установлены" : (std::to_string(missingInstalled) + " без видеофона");
    drawText(missStr, 495, 208, Theme::COLOR_SUCCESS, 12);

    // Metric Card 3: Available in Catalog
    drawGlassCard(860, 95, 360, 145, false, true);
    drawText(s.statAvailableCatalog, 885, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(catalogCount), 885, 145, Theme::COLOR_FOCUS_CYAN, 44);
    drawRect(885, 202, 190, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(885, 202, 190, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("[-] Обновить каталог", 895, 208, Theme::COLOR_FOCUS_CYAN, 12);

    // Signature Hero Action Card
    int cardY = 260;
    int cardH = 120;
    if (missing > 0) {
        drawGlassCard(60, cardY, 1160, cardH, true, true);

        // Required Action Badge
        drawRect(85, cardY + 16, 185, 26, Theme::COLOR_FOCUS_FILL);
        drawRectOutline(85, cardY + 16, 185, 26, Theme::COLOR_FOCUS_CYAN, 1);
        drawText("ТРЕБУЕТСЯ ДЕЙСТВИЕ", 95, cardY + 22, Theme::COLOR_FOCUS_CYAN, 12);

        std::string titleStr = "[Y]  Установить все недостающие видеофоны (" + std::to_string(missing) + " шт.)";
        drawText(titleStr, 85, cardY + 52, Theme::COLOR_TEXT_PRIMARY, 20);

        std::string descStr = "Автоматически добавить все игры без видеофонов в очередь и активировать в 4IFIR.";
        drawText(descStr, 85, cardY + 84, Theme::COLOR_TEXT_MUTED, 13);

        // Action button on the right
        drawGlassCard(910, cardY + 35, 280, 50, true, false);
        drawText("[Y] Установить все", 965, cardY + 50, Theme::COLOR_FOCUS_CYAN, 16);
    } else {
        drawGlassCard(60, cardY, 1160, cardH, false, false);
        drawText("✔ Все видеофоны 4IFIR установлены", 85, cardY + 35, Theme::COLOR_SUCCESS, 20);
        drawText("Все установленные на консоли игры имеют активные живые фоны.", 85, cardY + 70, Theme::COLOR_TEXT_MUTED, 14);
    }

    // 4IFIR Cyber-Glass Navigation Cards
    int navY = 405;
    drawGlassCard(60, navY, 560, 95, false, false);
    drawText("[A] Перейти в библиотеку 'Мои игры'", 85, navY + 20, Theme::COLOR_FOCUS_CYAN, 16);
    drawText("Просмотр установленных игр, выбор вариантов обложек и ручная установка", 85, navY + 52, Theme::COLOR_TEXT_MUTED, 13);

    drawGlassCard(660, navY, 560, 95, false, false);
    drawText("[-] Обновить онлайн-каталог фонов", 685, navY + 20, Theme::COLOR_FOCUS_CYAN, 16);
    drawText("Загрузить новейшую базу видеофонов с официального репозитория GitHub", 685, navY + 52, Theme::COLOR_TEXT_MUTED, 13);

    // Applet Warning if applicable
    if (m_sysInfo.isAppletMode) {
        drawGlassCard(60, 525, 1160, 50, false, true);
        drawText(s.appletWarning, 85, 542, Theme::COLOR_WARNING, 14);
    }
}

void App::renderTabMyGames() {
    const auto& s = getStrings(m_language);

    // Left List Pane (450px wide) - 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 450, 570, false, false);

    const int visibleCount = 8;
    int totalCount = static_cast<int>(m_installedGames.size());

    if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex;
    }
    if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + visibleCount) {
        m_myGamesScrollOffset = m_myGamesSelectedIndex - visibleCount + 1;
    }

    if (totalCount > 0) {
        std::string posStr = std::to_string(m_myGamesSelectedIndex + 1) + " / " + std::to_string(totalCount);
        drawText(posStr, 380, 86, Theme::COLOR_FOCUS_CYAN, 12);
    }

    int startY = 105;
    int endIdx = std::min(totalCount, m_myGamesScrollOffset + visibleCount);
    for (int i = m_myGamesScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_myGamesSelectedIndex);
        const auto& game = m_installedGames[i];

        // 4IFIR Card with neon outline on focus
        drawGlassCard(35, startY, 440, 60, isSelected, isSelected);

        drawText(game.name, 48, startY + 10, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);
        drawText(game.titleId, 48, startY + 34, Theme::COLOR_TEXT_MUTED, 12);

        // Status pill
        if (game.hasInstalledCover) {
            drawRect(370, startY + 18, 95, 24, {0x10, 0xB9, 0x81, 0x22});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ФОН ЕСТЬ", 380, startY + 23, Theme::COLOR_SUCCESS, 11);
        } else {
            drawRect(370, startY + 18, 95, 24, {0x28, 0x33, 0x47, 0x55});
            drawRectOutline(370, startY + 18, 95, 24, Theme::COLOR_BORDER, 1);
            drawText("НЕТ ФОНА", 384, startY + 23, Theme::COLOR_TEXT_MUTED, 11);
        }

        startY += 66;
    }

    // Right Details Pane (750px wide) - 4IFIR Cyber-Glass Container
    drawGlassCard(500, 80, 750, 570, false, false);

    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];

        drawText(selGame.name, 530, 110, Theme::COLOR_TEXT_PRIMARY, 22);
        drawText("Title ID: " + selGame.titleId + "  |  " + selGame.author, 530, 145, Theme::COLOR_TEXT_MUTED, 14);

        if (selGame.hasInstalledCover) {
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
        }

        // Available variants from catalog
        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = "Доступные варианты видеофона (" + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 250, Theme::COLOR_TEXT_PRIMARY, 16);

        if (totalVariants > 0) {
            const int visibleVariants = 4;
            if (m_variantScrollOffset < 0) m_variantScrollOffset = 0;
            if (m_selectedVariantIndex < m_variantScrollOffset) {
                m_variantScrollOffset = m_selectedVariantIndex;
            } else if (m_selectedVariantIndex >= m_variantScrollOffset + visibleVariants) {
                m_variantScrollOffset = m_selectedVariantIndex - visibleVariants + 1;
            }

            // Scroll indicator ABOVE
            if (m_variantScrollOffset > 0) {
                drawText("▲ Еще варианты выше (используйте D-Pad Влево)", 780, 252, Theme::COLOR_FOCUS_CYAN, 12);
            }

            int vY = 280;
            int endVIdx = std::min(totalVariants, m_variantScrollOffset + visibleVariants);
            for (int vIdx = m_variantScrollOffset; vIdx < endVIdx; ++vIdx) {
                const auto& v = selGame.catalogEntry.variants[vIdx];
                bool isVarSelected = (vIdx == m_selectedVariantIndex);

                // 4IFIR Cyber-Glass variant card
                drawGlassCard(525, vY, 700, 72, isVarSelected, false);

                // Variant Title & Style
                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                drawText(vTitle, 545, vY + 12, isVarSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);

                // Tech Specs Line
                std::string meta = "Автор: " + v.author + "  |  " + std::to_string(v.width) + "x" +
                                   std::to_string(v.height) + " @" + std::to_string(static_cast<int>(v.fps)) + "fps  |  " +
                                   std::to_string(v.sizeBytes / (1024 * 1024)) + " MB";
                drawText(meta, 545, vY + 40, Theme::COLOR_TEXT_MUTED, 12);

                if (isVarSelected) {
                    drawRect(1070, vY + 18, 140, 36, Theme::COLOR_FOCUS_FILL);
                    drawRectOutline(1070, vY + 18, 140, 36, Theme::COLOR_FOCUS_CYAN, 1);
                    drawText("[A] Установить", 1085, vY + 27, Theme::COLOR_FOCUS_CYAN, 13);
                }

                vY += 80;
            }

            // Scroll indicator BELOW
            if (endVIdx < totalVariants) {
                std::string belowStr = "▼ Еще варианты ниже: " + std::to_string(totalVariants - endVIdx) + " шт. (используйте D-Pad Вправо)";
                drawText(belowStr, 720, vY + 6, Theme::COLOR_FOCUS_PINK, 12);
            }
        } else {
            drawText("Для этой игры пока нет вариантов в онлайн-библиотеке.", 530, 290, Theme::COLOR_TEXT_MUTED, 14);
        }
    }
}

void App::renderTabCatalog() {
    const auto& s = getStrings(m_language);

    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    drawText("Онлайн-библиотека видеофонов 4IFIR", 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);

    // Action buttons on top right
    drawGlassCard(980, 95, 240, 42, true, false);
    drawText("[-] " + std::string(s.actionRefreshCatalog), 1000, 107, Theme::COLOR_FOCUS_CYAN, 14);

    int missing = getMissingCoversCount();
    if (missing > 0) {
        drawGlassCard(680, 95, 280, 42, true, false);
        drawText("[Y] Установить все (" + std::to_string(missing) + ")", 700, 107, Theme::COLOR_FOCUS_CYAN, 14);
    }

    const auto& allGames = m_catalogManager.getAllGames();
    if (allGames.empty()) {
        drawText("Каталог пуст или ещё не загружен.", 60, 180, Theme::COLOR_TEXT_MUTED, 16);
        drawText("Нажмите кнопку [-] или [X], чтобы загрузить актуальный список видеофонов с GitHub.", 60, 215, Theme::COLOR_FOCUS_CYAN, 15);
        return;
    }

    const int visibleCount = 5;
    int totalGames = static_cast<int>(allGames.size());

    if (m_catalogSelectedIndex < m_catalogScrollOffset) {
        m_catalogScrollOffset = m_catalogSelectedIndex;
    }
    if (m_catalogSelectedIndex >= m_catalogScrollOffset + visibleCount) {
        m_catalogScrollOffset = m_catalogSelectedIndex - visibleCount + 1;
    }

    std::string pageInfo = "Игр в каталоге: " + std::to_string(totalGames) +
                           "  (Выбрано: " + std::to_string(m_catalogSelectedIndex + 1) + " / " + std::to_string(totalGames) + ")";
    drawText(pageInfo, 60, 135, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalGames, m_catalogScrollOffset + visibleCount);
    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_catalogSelectedIndex);
        const auto& g = allGames[i];

        // 4IFIR Frosted Card for each catalog entry
        drawGlassCard(60, y, 1160, 80, isSelected, false);

        drawText(g.title, 85, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17);
        std::string meta = "Title ID: " + g.titleId + "   |   Доступных стилей: " + std::to_string(g.variants.size());
        drawText(meta, 85, y + 44, Theme::COLOR_TEXT_MUTED, 13);

        if (isSelected) {
            drawRect(1070, y + 22, 130, 36, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(1070, y + 22, 130, 36, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("В библиотеке", 1085, y + 31, Theme::COLOR_FOCUS_CYAN, 12);
        }

        y += 94;
    }
}

void App::renderTabDownloads() {
    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    drawText("Очередь загрузки видеофонов 4IFIR", 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);

    std::vector<DownloadTask> tasksCopy;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        tasksCopy = m_downloadQueue;
    }

    if (tasksCopy.empty()) {
        drawText("Очередь пуста. Выберите видеофон в разделе 'Мои игры' или установите все недостающие.", 60, 160, Theme::COLOR_TEXT_MUTED, 15);
        drawText("Нажмите [Y] на главной вкладке, чтобы автоматически добавить все игры в очередь.", 60, 195, Theme::COLOR_FOCUS_CYAN, 14);
        return;
    }

    const int visibleTasks = 5;
    int totalTasks = static_cast<int>(tasksCopy.size());
    if (m_downloadsScrollOffset < 0) m_downloadsScrollOffset = 0;
    if (m_downloadsScrollOffset + visibleTasks > totalTasks) {
        m_downloadsScrollOffset = std::max(0, totalTasks - visibleTasks);
    }

    std::string summary = "Задач в очереди: " + std::to_string(totalTasks) +
        "  (Показаны " + std::to_string(m_downloadsScrollOffset + 1) + " - " +
        std::to_string(std::min(totalTasks, m_downloadsScrollOffset + visibleTasks)) + ")";
    drawText(summary, 430, 110, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalTasks, m_downloadsScrollOffset + visibleTasks);
    for (int i = m_downloadsScrollOffset; i < endIdx; ++i) {
        const auto& task = tasksCopy[i];
        bool isDownloading = (task.state == TaskState::Downloading);

        // 4IFIR Frosted Card for each task
        drawGlassCard(60, y, 1160, 80, isDownloading, false);

        // Title and variant
        drawText(task.gameTitle + "  [" + task.variant.name + "]", 85, y + 14, isDownloading ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);

        if (task.state == TaskState::Downloading) {
            // Sleek Capsule Progress Bar
            drawCapsuleProgressBar(85, y + 44, 480, 16, task.progressPercent);

            std::string progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                std::to_string(task.bytesDownloaded / (1024 * 1024)) + " / " +
                std::to_string(task.totalBytes / (1024 * 1024)) + " MB)";
            drawText(progStr, 580, y + 44, Theme::COLOR_FOCUS_CYAN, 13);

            double speedKb = task.downloadSpeedBps / 1024.0;
            std::string speedStr;
            if (speedKb >= 1024.0) {
                speedStr = std::to_string(static_cast<int>(speedKb / 1024.0)) + "." +
                    std::to_string(static_cast<int>((speedKb / 102.4)) % 10) + " MB/s";
            } else {
                speedStr = std::to_string(static_cast<int>(speedKb)) + " KB/s";
            }
            drawText(speedStr, 760, y + 44, Theme::COLOR_TEXT_MUTED, 13);

            drawRect(1010, y + 24, 180, 32, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("Загрузка...", 1055, y + 31, Theme::COLOR_FOCUS_CYAN, 13);
        } else if (task.state == TaskState::Verifying) {
            drawText("Установка в 4IFIR (sdmc:/recordings/covers/)...", 85, y + 44, Theme::COLOR_WARNING, 14);
            drawRect(1010, y + 24, 180, 32, {0xF5, 0x9E, 0x0B, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_WARNING, 1);
            drawText("Установка...", 1050, y + 31, Theme::COLOR_WARNING, 13);
        } else if (task.state == TaskState::Completed) {
            drawText("✔ Успешно активирован в sdmc:/recordings/covers/", 85, y + 44, Theme::COLOR_SUCCESS, 14);
            drawRect(1010, y + 24, 180, 32, {0x10, 0xB9, 0x81, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_SUCCESS, 1);
            drawText("✔ Установлен", 1045, y + 31, Theme::COLOR_SUCCESS, 13);
        } else if (task.state == TaskState::Failed) {
            drawText("Ошибка: " + task.errorMessage, 85, y + 44, Theme::COLOR_DANGER, 13);
            drawRect(1010, y + 24, 180, 32, {0xF4, 0x3F, 0x5E, 0x22});
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_DANGER, 1);
            drawText("✖ Ошибка", 1060, y + 31, Theme::COLOR_DANGER, 13);
        } else { // Pending
            drawText("В очереди ожидания...", 85, y + 44, Theme::COLOR_TEXT_MUTED, 14);
            drawRect(1010, y + 24, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 24, 180, 32, Theme::COLOR_BORDER, 1);
            drawText("Ожидание", 1060, y + 31, Theme::COLOR_TEXT_MUTED, 13);
        }

        y += 94;
    }
}

void App::renderTabSettings() {
    const auto& s = getStrings(m_language);
    (void)s;

    // Main 4IFIR Frosted Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    drawText("4IFIR System Settings  |  H3H Backgrounds", 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);
    drawText("Настройки системы, прямое обновление NRO и управление локальным хранилищем", 60, 135, Theme::COLOR_TEXT_MUTED, 13);

    // Settings list options
    struct SettingRow {
        std::string title;
        std::string desc;
        std::string value;
        Color valColor;
    };

    std::string freeGb = std::to_string(m_sysInfo.freeStorageBytes / (1024 * 1024 * 1024)) + " GB свободно";
    std::vector<SettingRow> rows = {
        {"Обновление приложения (NRO)", "Проверить и установить новую версию H3H-Backgrounds.nro с GitHub", "v1.0.3 [A - Обновить]", Theme::COLOR_FOCUS_CYAN},
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
        drawText(rows[i].title, 75, rowY + 14, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17);
        drawText(rows[i].desc, 75, rowY + 42, Theme::COLOR_TEXT_MUTED, 13);

        // Right value pill
        drawText(rows[i].value, 950, rowY + 26, rows[i].valColor, 15);

        rowY += 84;
    }

    // Bottom Help Banner
    drawRect(50, 600, 1180, 36, Theme::COLOR_BG_BASE);
    drawRectOutline(50, 600, 1180, 36, Theme::COLOR_BORDER, 1);
    drawText("Навигация: [D-Pad Вверх/Вниз] - выбор пункта   |   [A] - применить / обновить   |   [B] - главная", 75, 610, Theme::COLOR_TEXT_MUTED, 13);
}

void App::renderDialog() {
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x00, 0x00, 0x00, 0xCC});

    // 4IFIR Obsidian Glass Modal
    int dw = 700;
    int dh = 270;
    int dx = (Theme::SCREEN_WIDTH - dw) / 2;
    int dy = (Theme::SCREEN_HEIGHT - dh) / 2;

    drawRect(dx, dy, dw, dh, Theme::COLOR_BG_MODAL);
    drawNeonGradientOutline(dx, dy, dw, dh, 2);

    drawText(m_dialogTitle, dx + 35, dy + 25, Theme::COLOR_FOCUS_CYAN, 20);

    // Specialized dialog: Update Progress with Capsule Bar
    if (m_activeDialog == DialogType::UpdateProgress) {
        drawText(m_dialogMessage, dx + 35, dy + 70, Theme::COLOR_TEXT_PRIMARY, 15);

        uint64_t bytes = m_nroUpdateBytesDownloaded.load();
        uint64_t total = m_nroUpdateTotalBytes.load();
        double pct = (total > 0) ? (static_cast<double>(bytes) / total * 100.0) : 0.0;

        // Sleek Capsule Progress Bar
        drawCapsuleProgressBar(dx + 35, dy + 115, dw - 70, 22, pct);

        std::string progStr = std::to_string(bytes / (1024 * 1024)) + "." +
                              std::to_string((bytes / (1024 * 102)) % 10) + " MB / " +
                              std::to_string(total / (1024 * 1024)) + "." +
                              std::to_string((total / (1024 * 102)) % 10) + " MB  (" +
                              std::to_string(static_cast<int>(pct)) + "%)";
        drawText(progStr, dx + 35, dy + 150, Theme::COLOR_FOCUS_CYAN, 14);
        drawText("Обновление безопасно заменяет файл на SD карте без перезаписи в Horizon OS", dx + 35, dy + 185, Theme::COLOR_TEXT_MUTED, 12);
        drawText("[B] Скрыть окно в фон", dx + 490, dy + 225, Theme::COLOR_TEXT_MUTED, 13);
        return;
    }

    // Specialized dialog: Update Success
    if (m_activeDialog == DialogType::UpdateSuccess) {
        std::stringstream ss(m_dialogMessage);
        std::string line;
        int msgY = dy + 70;
        while (std::getline(ss, line, '\n')) {
            drawText(line, dx + 35, msgY, Theme::COLOR_TEXT_PRIMARY, 15);
            msgY += 26;
        }

        int btnW = 200;
        int btnH = 44;
        int btnY = dy + 195;
        drawRect(dx + 250, btnY, btnW, btnH, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(dx + 250, btnY, btnW, btnH, 2);
        drawText("[A] Перезапустить", dx + 275, btnY + 13, Theme::COLOR_FOCUS_CYAN, 15);
        return;
    }

    // Specialized dialog: Alert
    if (m_activeDialog == DialogType::MessageAlert) {
        std::stringstream ss(m_dialogMessage);
        std::string line;
        int msgY = dy + 70;
        while (std::getline(ss, line, '\n')) {
            drawText(line, dx + 35, msgY, Theme::COLOR_WARNING, 15);
            msgY += 26;
        }

        int btnW = 160;
        int btnH = 40;
        int btnY = dy + 195;
        drawRect(dx + 270, btnY, btnW, btnH, Theme::COLOR_BG_SURFACE);
        drawRectOutline(dx + 270, btnY, btnW, btnH, Theme::COLOR_BORDER, 1);
        drawText("[A] Закрыть", dx + 310, btnY + 12, Theme::COLOR_TEXT_PRIMARY, 14);
        return;
    }

    // Standard Confirmation Dialogs
    std::stringstream ss(m_dialogMessage);
    std::string line;
    int msgY = dy + 70;
    while (std::getline(ss, line, '\n')) {
        drawText(line, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14);
        msgY += 24;
    }

    int btnW = 180;
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
}

void App::drawRect(int x, int y, int w, int h, Color color) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    SDL_Rect r{x, y, w, h};
    SDL_RenderFillRect(m_renderer, &r);
#else
    (void)x; (void)y; (void)w; (void)h; (void)color;
#endif
}

void App::drawRectOutline(int x, int y, int w, int h, Color color, int thickness) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    for (int t = 0; t < thickness; ++t) {
        SDL_Rect r{x + t, y + t, w - 2 * t, h - 2 * t};
        SDL_RenderDrawRect(m_renderer, &r);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)color; (void)thickness;
#endif
}

void App::drawNeonGradientOutline(int x, int y, int w, int h, int thickness) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    // Signature 4IFIR Cyber-Glow: Vertical Gradient from Electric Cyan (#00E5FF) to Neon Magenta (#EC4899)
    for (int t = 0; t < thickness; ++t) {
        int curX = x + t;
        int curY = y + t;
        int curW = w - 2 * t;
        int curH = h - 2 * t;
        if (curW <= 0 || curH <= 0) break;

        // Top horizontal edge: Electric Cyan
        SDL_SetRenderDrawColor(m_renderer, 0x00, 0xE5, 0xFF, 0xFF);
        SDL_RenderDrawLine(m_renderer, curX, curY, curX + curW - 1, curY);

        // Bottom horizontal edge: Neon Magenta
        SDL_SetRenderDrawColor(m_renderer, 0xEC, 0x48, 0x99, 0xFF);
        SDL_RenderDrawLine(m_renderer, curX, curY + curH - 1, curX + curW - 1, curY + curH - 1);

        // Vertical edges: smooth linear color interpolation
        for (int row = 0; row < curH; ++row) {
            float factor = static_cast<float>(row) / static_cast<float>(std::max(1, curH - 1));
            uint8_t r = static_cast<uint8_t>(0x00 + factor * 0xEC);
            uint8_t g = static_cast<uint8_t>(0xE5 + factor * (0x48 - 0xE5));
            uint8_t b = static_cast<uint8_t>(0xFF + factor * (0x99 - 0xFF));
            SDL_SetRenderDrawColor(m_renderer, r, g, b, 0xFF);
            SDL_RenderDrawPoint(m_renderer, curX, curY + row);
            SDL_RenderDrawPoint(m_renderer, curX + curW - 1, curY + row);
        }
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)thickness;
#endif
}

void App::drawGlassCard(int x, int y, int w, int h, bool isFocused, bool isElevated) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color bg = isElevated ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_SURFACE;
    drawRect(x, y, w, h, bg);

    if (isFocused) {
        drawRect(x, y, w, h, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(x, y, w, h, 2);
    } else {
        drawRectOutline(x, y, w, h, Theme::COLOR_BORDER, 1);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)isFocused; (void)isElevated;
#endif
}

void App::drawCapsuleProgressBar(int x, int y, int w, int h, double percent) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    // Dark track background
    drawRect(x, y, w, h, {0x1C, 0x22, 0x30, 0xFF});
    drawRectOutline(x, y, w, h, {0x2D, 0x37, 0x48, 0xFF}, 1);

    // Cyan filled portion
    int fillW = static_cast<int>(w * std::clamp(percent / 100.0, 0.0, 1.0));
    if (fillW > 0) {
        drawRect(x, y, fillW, h, Theme::COLOR_FOCUS_CYAN);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)percent;
#endif
}

TTF_Font* App::getFont(int sizePx) {
#ifdef HAS_SDL2
    auto it = m_fonts.find(sizePx);
    if (it != m_fonts.end()) {
        return it->second;
    }

#ifdef __SWITCH__
    if (m_fontMemBuffer && m_fontMemSize > 0) {
        SDL_RWops* rw = SDL_RWFromMem(const_cast<void*>(m_fontMemBuffer), static_cast<int>(m_fontMemSize));
        if (rw) {
            TTF_Font* font = TTF_OpenFontRW(rw, 1, sizePx);
            if (font) {
                m_fonts[sizePx] = font;
                return font;
            }
        }
    }
#endif

    const char* fontCandidates[] = {
        "romfs:/font.ttf",
        "sdmc:/switch/H3H-Backgrounds/font.ttf",
        "sdmc:/switch/font.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    };

    for (const char* path : fontCandidates) {
        TTF_Font* font = TTF_OpenFont(path, sizePx);
        if (font) {
            m_fonts[sizePx] = font;
            return font;
        }
    }
#endif
    (void)sizePx;
    return nullptr;
}

void App::drawText(const std::string& text, int x, int y, Color color, int sizePx) {
#ifdef HAS_SDL2
    if (text.empty() || !m_renderer) return;

    TTF_Font* font = getFont(sizePx);
    if (font) {
        SDL_Color sdlColor = {color.r, color.g, color.b, color.a};
        SDL_Surface* surf = TTF_RenderUTF8_Blended(font, text.c_str(), sdlColor);
        if (surf) {
            SDL_Texture* tex = SDL_CreateTextureFromSurface(m_renderer, surf);
            if (tex) {
                SDL_Rect dstRect = {x, y, surf->w, surf->h};
                SDL_RenderCopy(m_renderer, tex, nullptr, &dstRect);
                SDL_DestroyTexture(tex);
            }
            SDL_FreeSurface(surf);
            return;
        }
    }

    drawBitmapTextFallback(text, x, y, color);
#else
    (void)text; (void)x; (void)y; (void)color; (void)sizePx;
#endif
}

void App::drawBitmapTextFallback(const std::string& text, int x, int y, Color color) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, color.r, color.g, color.b, color.a);
    int curX = x;
    for (char c : text) {
        if (c >= 32 && c <= 126) {
            SDL_Rect r{curX, y + 2, 7, 12};
            SDL_RenderDrawRect(m_renderer, &r);
            curX += 9;
        } else {
            curX += 5;
        }
    }
#else
    (void)text; (void)x; (void)y; (void)color;
#endif
}

void App::run() {
    while (m_running) {
        handleInput();
        update();
        render();
#ifdef HAS_SDL2
        SDL_Delay(16); // ~60 FPS cap
#else
        break; // In non-SDL test mode, run one cycle
#endif
    }
}

} // namespace ui
} // namespace h3h
