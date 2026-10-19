#include "ui/app.hpp"
#include "core/config.hpp"
#include <iostream>
#include <iomanip>
#include <sstream>
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

    m_statusNotification = (m_language == Language::Russian)
        ? "Загрузка обновления H3H-Backgrounds.nro..."
        : "Downloading H3H-Backgrounds.nro update...";
    m_notificationFramesRemaining = 120;
    m_isUpdatingNro = true;

    if (m_nroUpdateThread.joinable()) {
        m_nroUpdateThread.join();
    }

    m_nroUpdateThread = std::thread([this]() {
        std::string nroUrl = "https://github.com/Holy3holy-dev/H3H-Backgrounds/releases/latest/download/H3H-Backgrounds.nro";
        std::string appDir = m_platform->getAppDirectory();
        std::string tempNro = appDir + "/H3H-Backgrounds.nro.tmp";
        std::string targetNro = appDir + "/H3H-Backgrounds.nro";

        std::atomic<bool> cancel{false};
        std::string err;
        bool ok = m_platform->downloadFile(nroUrl, tempNro, nullptr, cancel, err);
        bool success = false;
        if (ok) {
            std::remove(targetNro.c_str());
            if (std::rename(tempNro.c_str(), targetNro.c_str()) == 0) {
                success = true;
            } else {
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
            m_statusNotification = (m_language == Language::Russian)
                ? "Приложение H3H-Backgrounds.nro успешно обновлено!"
                : "H3H-Backgrounds.nro updated successfully!";
        } else {
            m_statusNotification = (m_language == Language::Russian)
                ? ("Ошибка обновления: " + err)
                : ("Update failed: " + err);
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
            }
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_myGamesSelectedIndex + 1 < static_cast<int>(m_installedGames.size())) {
                m_myGamesSelectedIndex++;
                m_selectedVariantIndex = 0;
            }
        } else if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                    int vCount = static_cast<int>(g.catalogEntry.variants.size());
                    if (button == 14) m_selectedVariantIndex = (m_selectedVariantIndex + 1) % vCount;
                    else m_selectedVariantIndex = (m_selectedVariantIndex == 0) ? vCount - 1 : m_selectedVariantIndex - 1;
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
        if (button == 0 /* A */) {
            // Toggle language
            m_language = (m_language == Language::Russian) ? Language::English : Language::Russian;
            m_statusNotification = (m_language == Language::Russian) ? "Язык: Русский" : "Language: English";
            m_notificationFramesRemaining = 120;
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

    // Top Header bar
    drawRect(0, 0, Theme::SCREEN_WIDTH, 60, Theme::COLOR_BG_SURFACE);
    drawRect(0, 59, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // App Title
    drawText(s.appTitle, 30, 18, Theme::COLOR_TEXT_PRIMARY, 20);

    // Tab items
    const char* tabs[] = {s.tabHome, s.tabMyGames, s.tabCatalog, s.tabDownloads, s.tabSettings};
    int tabX = 350;
    for (int i = 0; i < 5; ++i) {
        bool isActive = (static_cast<int>(m_activeTab) == i);
        if (isActive) {
            drawRect(tabX - 10, 12, 110, 36, Theme::COLOR_BG_ELEVATED);
            drawRectOutline(tabX - 10, 12, 110, 36, Theme::COLOR_FOCUS_RING, 2);
        }
        drawText(tabs[i], tabX, 22, isActive ? Theme::COLOR_FOCUS_RING : Theme::COLOR_TEXT_MUTED, 15);
        tabX += 120;
    }

    // System info pills (Battery & 4IFIR)
    drawText(s.cfwActiveStatus, 960, 22, Theme::COLOR_SUCCESS, 13);
}

void App::renderFooter() {
    const auto& s = getStrings(m_language);

    // Bottom action bar
    drawRect(0, 670, Theme::SCREEN_WIDTH, 50, Theme::COLOR_BG_SURFACE);
    drawRect(0, 670, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    std::string hints;
    if (m_activeTab == Tab::Home) {
        hints = "[L/R] Вкладки   [A] Мои игры   [Y] Установить все недостающие   [X] Обновить   [-] GitHub";
    } else if (m_activeTab == Tab::MyGames) {
        hints = "[L/R] Вкладки   [A] Установить   [B] Назад   [X] Восстановить   [Y] Удалить / Все   [-] Обновить";
    } else if (m_activeTab == Tab::Catalog) {
        hints = "[L/R] Вкладки   [B] Назад   [-] / [X] Обновить каталог   [Y] Установить недостающие";
    } else if (m_activeTab == Tab::Downloads) {
        hints = "[L/R] Вкладки   [B] Назад   [-] Обновить каталог";
    } else if (m_activeTab == Tab::Settings) {
        hints = "[L/R] Вкладки   [A] Язык   [B] Назад   [X] " + std::string(s.clearCacheBtn) + "   [-] / [Y] Обновить   [+] " + std::string(s.updateAppBtn);
    }

    drawText(hints, 30, 685, Theme::COLOR_TEXT_MUTED, 14);

    // Prominent "[-] Обновить" touch-button on the bottom right of footer
    drawRect(1070, 675, 180, 38, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(1070, 675, 180, 38, Theme::COLOR_ACCENT, 1);
    drawText("[-] " + std::string(s.actionRefresh), 1095, 686, Theme::COLOR_ACCENT, 14);
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

    // Metric Card 1: Detected Games
    drawRect(60, 95, 360, 145, Theme::COLOR_BG_SURFACE);
    drawRectOutline(60, 95, 360, 145, Theme::COLOR_BORDER, 1);
    drawText(s.statDetectedGames, 80, 115, Theme::COLOR_TEXT_MUTED, 16);
    drawText(std::to_string(detected), 80, 150, Theme::COLOR_TEXT_PRIMARY, 42);
    drawText("[A] Перейти в Мои игры", 80, 205, Theme::COLOR_FOCUS_RING, 13);

    // Metric Card 2: Installed Covers
    drawRect(460, 95, 360, 145, Theme::COLOR_BG_SURFACE);
    drawRectOutline(460, 95, 360, 145, Theme::COLOR_BORDER, 1);
    drawText(s.statInstalledCovers, 480, 115, Theme::COLOR_TEXT_MUTED, 16);
    drawText(std::to_string(installedCovers), 480, 150, Theme::COLOR_SUCCESS, 42);
    int missingInstalled = (detected > installedCovers) ? static_cast<int>(detected - installedCovers) : 0;
    drawText(std::to_string(missingInstalled) + " без видеофона", 480, 205, Theme::COLOR_TEXT_MUTED, 13);

    // Metric Card 3: Available in Catalog
    drawRect(860, 95, 360, 145, Theme::COLOR_BG_SURFACE);
    drawRectOutline(860, 95, 360, 145, Theme::COLOR_BORDER, 1);
    drawText(s.statAvailableCatalog, 880, 115, Theme::COLOR_TEXT_MUTED, 16);
    drawText(std::to_string(catalogCount), 880, 150, Theme::COLOR_ACCENT, 42);
    drawText("[-] " + std::string(s.actionRefreshCatalog), 880, 205, Theme::COLOR_FOCUS_RING, 13);

    // Prominent Action Card: Install All Missing Covers
    int cardY = 260;
    int cardH = 120;
    drawRect(60, cardY, 1160, cardH, Theme::COLOR_BG_SURFACE);
    if (missing > 0) {
        drawRectOutline(60, cardY, 1160, cardH, Theme::COLOR_ACCENT, 2);

        // Badge
        drawRect(80, cardY + 18, 175, 26, Theme::COLOR_FOCUS_FILL);
        drawRectOutline(80, cardY + 18, 175, 26, Theme::COLOR_ACCENT, 1);
        drawText("ТРЕБУЕТСЯ ДЕЙСТВИЕ", 90, cardY + 24, Theme::COLOR_FOCUS_RING, 12);

        std::string titleStr = "[Y]  Установить все недостающие видеофоны (" + std::to_string(missing) + " игр)";
        drawText(titleStr, 80, cardY + 54, Theme::COLOR_TEXT_PRIMARY, 20);

        std::string descStr = "Автоматически добавить все игры без видеофонов в очередь загрузки и установить в 4IFIR.";
        drawText(descStr, 80, cardY + 86, Theme::COLOR_TEXT_MUTED, 13);

        // Action button on the right
        drawRect(910, cardY + 35, 280, 50, Theme::COLOR_ACCENT);
        drawText("[Y] Установить все", 955, cardY + 50, Theme::COLOR_TEXT_PRIMARY, 16);
    } else {
        drawRectOutline(60, cardY, 1160, cardH, Theme::COLOR_SUCCESS, 1);
        drawText("✔ Все видеофоны установлены", 80, cardY + 35, Theme::COLOR_SUCCESS, 20);
        drawText("Все Ваши игры на консоли уже имеют установленные видеофоны 4IFIR.", 80, cardY + 70, Theme::COLOR_TEXT_MUTED, 14);
    }

    // Quick Action Cards
    int navY = 405;
    drawRect(60, navY, 560, 95, Theme::COLOR_BG_SURFACE);
    drawRectOutline(60, navY, 560, 95, Theme::COLOR_BORDER, 1);
    drawText("[A] Перейти к списку 'Мои игры'", 85, navY + 22, Theme::COLOR_TEXT_PRIMARY, 16);
    drawText("Просмотр установленных игр, выбор вариантов обложек и ручная установка", 85, navY + 55, Theme::COLOR_TEXT_MUTED, 13);

    drawRect(660, navY, 560, 95, Theme::COLOR_BG_SURFACE);
    drawRectOutline(660, navY, 560, 95, Theme::COLOR_BORDER, 1);
    drawText("[-] Обновить каталог видеофонов", 685, navY + 22, Theme::COLOR_ACCENT, 16);
    drawText("Загрузить новейшую базу видеофонов с официального репозитория GitHub", 685, navY + 55, Theme::COLOR_TEXT_MUTED, 13);

    // Applet Warning if applicable
    if (m_sysInfo.isAppletMode) {
        drawRect(60, 525, 1160, 50, Theme::COLOR_BG_ELEVATED);
        drawRectOutline(60, 525, 1160, 50, Theme::COLOR_WARNING, 2);
        drawText(s.appletWarning, 80, 542, Theme::COLOR_WARNING, 14);
    }
}

void App::renderTabMyGames() {
    const auto& s = getStrings(m_language);

    // Left List Pane (450px wide)
    drawRect(30, 80, 450, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(30, 80, 450, 570, Theme::COLOR_BORDER, 1);

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
        drawText(posStr, 380, 84, Theme::COLOR_ACCENT, 12);
    }

    int startY = 105;
    int endIdx = std::min(totalCount, m_myGamesScrollOffset + visibleCount);
    for (int i = m_myGamesScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_myGamesSelectedIndex);
        const auto& game = m_installedGames[i];

        if (isSelected) {
            drawRect(35, startY, 440, 60, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(35, startY, 440, 60, Theme::COLOR_FOCUS_RING, 2);
        }

        drawText(game.name, 50, startY + 10, Theme::COLOR_TEXT_PRIMARY, 15);
        drawText(game.titleId, 50, startY + 34, Theme::COLOR_TEXT_MUTED, 12);

        // Status pill
        if (game.hasInstalledCover) {
            drawRect(380, startY + 18, 80, 24, Theme::COLOR_SUCCESS);
            drawText(s.statusInstalled, 390, startY + 22, Theme::COLOR_TEXT_PRIMARY, 11);
        } else {
            drawRect(380, startY + 18, 80, 24, Theme::COLOR_BG_ELEVATED);
            drawText(s.statusNoCover, 392, startY + 22, Theme::COLOR_TEXT_MUTED, 11);
        }

        startY += 66;
    }

    // Right Details Pane (750px wide)
    drawRect(500, 80, 750, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(500, 80, 750, 570, Theme::COLOR_BORDER, 1);

    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];

        drawText(selGame.name, 530, 110, Theme::COLOR_TEXT_PRIMARY, 22);
        drawText("Title ID: " + selGame.titleId + "  |  " + selGame.author, 530, 145, Theme::COLOR_TEXT_MUTED, 14);

        int missing = getMissingCoversCount();
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
        }

        // Available variants from catalog
        drawText("Доступные варианты видеофона:", 530, 250, Theme::COLOR_TEXT_PRIMARY, 16);

        if (selGame.hasCatalogMatch && !selGame.catalogEntry.variants.empty()) {
            int vY = 285;
            for (size_t vIdx = 0; vIdx < selGame.catalogEntry.variants.size(); ++vIdx) {
                const auto& v = selGame.catalogEntry.variants[vIdx];
                bool isVarSelected = (static_cast<int>(vIdx) == m_selectedVariantIndex);

                drawRect(530, vY, 690, 70, isVarSelected ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_BG_ELEVATED);
                drawRectOutline(530, vY, 690, 70, isVarSelected ? Theme::COLOR_FOCUS_RING : Theme::COLOR_BORDER, isVarSelected ? 2 : 1);

                drawText(v.name + " (" + styleToString(v.style) + ")", 550, vY + 12, Theme::COLOR_TEXT_PRIMARY, 15);
                std::string meta = "Автор: " + v.author + " | " + std::to_string(v.width) + "x" +
                                   std::to_string(v.height) + " @" + std::to_string(static_cast<int>(v.fps)) + "fps | " +
                                   std::to_string(v.sizeBytes / (1024 * 1024)) + " MB";
                drawText(meta, 550, vY + 38, Theme::COLOR_TEXT_MUTED, 12);

                if (isVarSelected) {
                    drawText("[A] Установить", 1100, vY + 25, Theme::COLOR_FOCUS_RING, 14);
                }

                vY += 80;
            }
        } else {
            drawText("Для этой игры пока нет вариантов в онлайн-библиотеке.", 530, 290, Theme::COLOR_TEXT_MUTED, 14);
        }
    }
}

void App::renderTabCatalog() {
    const auto& s = getStrings(m_language);

    drawRect(30, 80, 1220, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(30, 80, 1220, 570, Theme::COLOR_BORDER, 1);
    drawText("Онлайн-каталог видеофонов H3H", 60, 110, Theme::COLOR_TEXT_PRIMARY, 20);

    // Refresh button on top right of Catalog tab
    drawRect(980, 95, 240, 42, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(980, 95, 240, 42, Theme::COLOR_ACCENT, 1);
    drawText("[-] " + std::string(s.actionRefreshCatalog), 1000, 107, Theme::COLOR_ACCENT, 14);

    int missing = getMissingCoversCount();
    if (missing > 0) {
        drawRect(680, 95, 280, 42, Theme::COLOR_BG_ELEVATED);
        drawRectOutline(680, 95, 280, 42, Theme::COLOR_ACCENT, 1);
        drawText("[Y] Установить все (" + std::to_string(missing) + ")", 700, 107, Theme::COLOR_ACCENT, 14);
    }

    const auto& allGames = m_catalogManager.getAllGames();
    if (allGames.empty()) {
        drawText("Каталог пуст или ещё не загружен.", 60, 180, Theme::COLOR_TEXT_MUTED, 16);
        drawText("Нажмите кнопку [-] или [X], чтобы загрузить актуальный список видеофонов с GitHub.", 60, 215, Theme::COLOR_ACCENT, 15);
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
        drawRect(60, y, 1160, 80, isSelected ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_BG_ELEVATED);
        drawRectOutline(60, y, 1160, 80, isSelected ? Theme::COLOR_FOCUS_RING : Theme::COLOR_BORDER, isSelected ? 2 : 1);

        drawText(g.title, 80, y + 15, Theme::COLOR_TEXT_PRIMARY, 16);
        drawText("Title ID: " + g.titleId + " | Вариантов: " + std::to_string(g.variants.size()),
                 80, y + 42, Theme::COLOR_TEXT_MUTED, 13);

        y += 95;
    }
}

void App::renderTabDownloads() {
    drawRect(30, 80, 1220, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(30, 80, 1220, 570, Theme::COLOR_BORDER, 1);
    drawText("Очередь загрузки видеофонов", 60, 110, Theme::COLOR_TEXT_PRIMARY, 20);

    std::vector<DownloadTask> tasksCopy;
    {
        std::lock_guard<std::mutex> lock(m_queueMutex);
        tasksCopy = m_downloadQueue;
    }

    if (tasksCopy.empty()) {
        drawText("Очередь пуста. Выберите видеофон в разделе 'Мои игры' или установите все недостающие.", 60, 160, Theme::COLOR_TEXT_MUTED, 15);
        drawText("Нажмите [Y] на главной вкладке, чтобы автоматически установить все недостающие видеофоны.", 60, 195, Theme::COLOR_ACCENT, 14);
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
    drawText(summary, 360, 114, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalTasks, m_downloadsScrollOffset + visibleTasks);
    for (int i = m_downloadsScrollOffset; i < endIdx; ++i) {
        const auto& task = tasksCopy[i];
        drawRect(60, y, 1160, 80, Theme::COLOR_BG_ELEVATED);
        drawRectOutline(60, y, 1160, 80, Theme::COLOR_BORDER, 1);

        // Title and variant
        drawText(task.gameTitle + "  [" + task.variant.name + "]", 80, y + 12, Theme::COLOR_TEXT_PRIMARY, 16);

        if (task.state == TaskState::Downloading) {
            // Progress bar
            int barW = 500;
            int barH = 10;
            drawRect(80, y + 44, barW, barH, Theme::COLOR_BG_SURFACE);
            int fillW = static_cast<int>(barW * std::clamp(task.progressPercent / 100.0, 0.0, 1.0));
            drawRect(80, y + 44, fillW, barH, Theme::COLOR_FOCUS_RING);

            std::string progStr = std::to_string(static_cast<int>(task.progressPercent)) + "% (" +
                std::to_string(task.bytesDownloaded / (1024 * 1024)) + " / " +
                std::to_string(task.totalBytes / (1024 * 1024)) + " MB)";
            drawText(progStr, 600, y + 42, Theme::COLOR_ACCENT, 13);

            double speedKb = task.downloadSpeedBps / 1024.0;
            std::string speedStr;
            if (speedKb >= 1024.0) {
                speedStr = std::to_string(static_cast<int>(speedKb / 1024.0)) + "." +
                    std::to_string(static_cast<int>((speedKb / 102.4)) % 10) + " MB/s";
            } else {
                speedStr = std::to_string(static_cast<int>(speedKb)) + " KB/s";
            }
            drawText(speedStr, 760, y + 42, Theme::COLOR_TEXT_MUTED, 13);

            drawRect(1010, y + 25, 180, 32, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_FOCUS_RING, 1);
            drawText("Загрузка...", 1055, y + 32, Theme::COLOR_FOCUS_RING, 13);
        } else if (task.state == TaskState::Verifying) {
            drawText("Проверка SHA-256 и установка в 4IFIR...", 80, y + 42, Theme::COLOR_WARNING, 14);
            drawRect(1010, y + 25, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_WARNING, 1);
            drawText("Установка...", 1050, y + 32, Theme::COLOR_WARNING, 13);
        } else if (task.state == TaskState::Completed) {
            drawText("Успешно установлен в sdmc:/recordings/covers/", 80, y + 42, Theme::COLOR_SUCCESS, 14);
            drawRect(1010, y + 25, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_SUCCESS, 1);
            drawText("✔ Установлен", 1045, y + 32, Theme::COLOR_SUCCESS, 13);
        } else if (task.state == TaskState::Failed) {
            drawText("Ошибка: " + task.errorMessage, 80, y + 42, Theme::COLOR_DANGER, 13);
            drawRect(1010, y + 25, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_DANGER, 1);
            drawText("✖ Ошибка", 1060, y + 32, Theme::COLOR_DANGER, 13);
        } else { // Pending
            drawText("В очереди ожидания...", 80, y + 42, Theme::COLOR_TEXT_MUTED, 14);
            drawRect(1010, y + 25, 180, 32, Theme::COLOR_BG_SURFACE);
            drawRectOutline(1010, y + 25, 180, 32, Theme::COLOR_BORDER, 1);
            drawText("Ожидание", 1060, y + 32, Theme::COLOR_TEXT_MUTED, 13);
        }

        y += 92;
    }
}

void App::renderTabSettings() {
    const auto& s = getStrings(m_language);

    drawRect(30, 80, 1220, 570, Theme::COLOR_BG_SURFACE);
    drawRectOutline(30, 80, 1220, 570, Theme::COLOR_BORDER, 1);

    drawText("Настройки системы H3H", 60, 110, Theme::COLOR_TEXT_PRIMARY, 20);

    // Option 1: Language
    drawText("Язык интерфейса / Language: " + std::string(m_language == Language::Russian ? "Русский" : "English") + " [Нажмите A для переключения]",
             60, 160, Theme::COLOR_TEXT_PRIMARY, 15);

    // Option 2: Catalog URL
    drawText("Источник каталога: " + std::string(Config::DEFAULT_CATALOG_URL), 60, 205, Theme::COLOR_TEXT_MUTED, 13);

    // Option 3: Storage
    std::string storage = "Свободно на SD: " + std::to_string(m_sysInfo.freeStorageBytes / (1024 * 1024 * 1024)) + " GB";
    drawText(storage, 60, 245, Theme::COLOR_TEXT_MUTED, 14);

    // Option 4: Clear Cache button
    drawRect(60, 300, 280, 45, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(60, 300, 280, 45, Theme::COLOR_BORDER, 1);
    drawText("[X] " + std::string(s.clearCacheBtn), 75, 315, Theme::COLOR_TEXT_PRIMARY, 14);

    // Option 5: Refresh Catalog button
    drawRect(370, 300, 320, 45, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(370, 300, 320, 45, Theme::COLOR_ACCENT, 1);
    drawText("[-] / [Y] " + std::string(s.actionRefreshCatalog), 390, 315, Theme::COLOR_ACCENT, 14);

    // Option 6: Update Application NRO button
    drawRect(720, 300, 340, 45, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(720, 300, 340, 45, Theme::COLOR_SUCCESS, 1);
    drawText("[+] " + std::string(s.updateAppBtn), 740, 315, Theme::COLOR_SUCCESS, 14);
}

void App::renderDialog() {
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x00, 0x00, 0x00, 0xBB});

    // Dialog Box
    int dw = 650;
    int dh = 250;
    int dx = (Theme::SCREEN_WIDTH - dw) / 2;
    int dy = (Theme::SCREEN_HEIGHT - dh) / 2;

    drawRect(dx, dy, dw, dh, Theme::COLOR_BG_ELEVATED);
    drawRectOutline(dx, dy, dw, dh, Theme::COLOR_FOCUS_RING, 2);

    drawText(m_dialogTitle, dx + 30, dy + 25, Theme::COLOR_TEXT_PRIMARY, 20);

    // Render multi-line message
    std::stringstream ss(m_dialogMessage);
    std::string line;
    int msgY = dy + 75;
    while (std::getline(ss, line, '\n')) {
        drawText(line, dx + 30, msgY, Theme::COLOR_TEXT_MUTED, 14);
        msgY += 24;
    }

    // Action buttons
    int btnW = 160;
    int btnH = 40;
    int btnY = dy + 170;

    // Confirm button
    bool focusConfirm = (m_dialogFocus == 0);
    drawRect(dx + 130, btnY, btnW, btnH, focusConfirm ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_BG_SURFACE);
    drawRectOutline(dx + 130, btnY, btnW, btnH, focusConfirm ? Theme::COLOR_FOCUS_RING : Theme::COLOR_BORDER, focusConfirm ? 2 : 1);
    drawText("[A] Подтвердить", dx + 145, btnY + 12, Theme::COLOR_TEXT_PRIMARY, 14);

    // Cancel button
    bool focusCancel = (m_dialogFocus == 1);
    drawRect(dx + 340, btnY, btnW, btnH, focusCancel ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_BG_SURFACE);
    drawRectOutline(dx + 340, btnY, btnW, btnH, focusCancel ? Theme::COLOR_FOCUS_RING : Theme::COLOR_BORDER, focusCancel ? 2 : 1);
    drawText("[B] Отмена", dx + 375, btnY + 12, Theme::COLOR_TEXT_PRIMARY, 14);
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
