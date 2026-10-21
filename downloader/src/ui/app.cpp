
#include "ui/app.hpp"
#include "core/installed_registry.hpp"
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

#ifdef HAS_SDL2
namespace {
static SDL_Texture* loadTextureFromFile(SDL_Renderer* renderer, const std::string& path) {
    if (!renderer || path.empty()) return nullptr;
    FILE* fp = fopen(path.c_str(), "rb");
    if (!fp) return nullptr;
    SDL_RWops* rw = SDL_RWFromFP(fp, SDL_TRUE);
    if (!rw) {
        fclose(fp);
        return nullptr;
    }
    SDL_Surface* surf = IMG_Load_RW(rw, 1);
    if (!surf) return nullptr;
    SDL_Texture* tex = SDL_CreateTextureFromSurface(renderer, surf);
    SDL_FreeSurface(surf);
    if (tex) {
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_NONE);
    }
    return tex;
}
} // anonymous namespace
#endif

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

    // Safe initialization - never delete running binary

    refreshInstalledGames();
    rebuildCatalogFilter();

#ifdef HAS_SDL2
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER) != 0) {
        std::cerr << "[-] SDL_Init failed: " << SDL_GetError() << std::endl;
        return false;
    }

    if (TTF_Init() != 0) {
        std::cerr << "[-] TTF_Init failed: " << TTF_GetError() << std::endl;
    }

    int imgFlags = IMG_INIT_JPG | IMG_INIT_PNG;
    if ((IMG_Init(imgFlags) & imgFlags) != imgFlags) {
        std::cerr << "[-] IMG_Init warning: " << IMG_GetError() << std::endl;
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
        Config::APP_NAME,
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

    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
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
    if (m_startupUpdateThread.joinable()) {
        m_startupUpdateThread.join();
    }
    m_videoPlayer.close();
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
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
    IMG_Quit();
    SDL_Quit();
#endif
    if (m_platform) {
        m_platform->shutdown();
    }
}

void App::refreshInstalledGames() {
    m_platform->listInstalledTitles(m_installedGames);
    m_catalogManager.matchInstalledTitles(m_installedGames);

    // In After Dark build, pin the After Dark Collection (0000000000000000) at top if present in catalog
    if (Config::isAfterDark()) {
        const auto* match = m_catalogManager.findByTitleId("0000000000000000");
        if (match && !match->variants.empty()) {
            bool found = false;
            for (const auto& ig : m_installedGames) {
                if (ig.titleId == "0000000000000000") { found = true; break; }
            }
            if (!found) {
                InstalledTitle collTitle;
                collTitle.titleId = "0000000000000000";
                collTitle.name = match->title;
                collTitle.author = match->publisher;
                collTitle.hasCatalogMatch = true;
                collTitle.catalogEntry = *match;
                collTitle.hasInstalledCover = false;
                m_installedGames.insert(m_installedGames.begin(), collTitle);
            }
        }
    }

    // Resolve exact installed variant IDs from persistent registry
    InstalledRegistry::instance().load(m_platform->getAppDirectory());
    for (auto& game : m_installedGames) {
        if (game.hasInstalledCover) {
            std::string regVarId = InstalledRegistry::instance().getVariantId(game.titleId);
            if (!regVarId.empty()) {
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
            }

            // If not found in registry (e.g. initial scan), match closest size
            if (game.installedVariantId.empty() && !game.catalogEntry.variants.empty()) {
                if (game.catalogEntry.variants.size() == 1) {
                    game.installedVariantId = game.catalogEntry.variants[0].id;
                } else {
                    int64_t bestDiff = INT64_MAX;
                    std::string bestId;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.sizeBytes > 0 && game.installedCoverSizeBytes > 0) {
                            int64_t diff = std::abs((int64_t)v.sizeBytes - (int64_t)game.installedCoverSizeBytes);
                            if (diff < bestDiff) {
                                bestDiff = diff;
                                bestId = v.id;
                            }
                        }
                    }
                    if (!bestId.empty()) {
                        game.installedVariantId = bestId;
                    } else {
                        game.installedVariantId = game.catalogEntry.variants[0].id;
                    }
                }
                InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), game.titleId, game.installedVariantId);
            }
        }
    }
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

void App::update() {
#ifdef HAS_SDL2
    std::string previewPath;
    std::string vidPath;
    {
        std::lock_guard<std::mutex> lock(m_previewMutex);
        if (!m_pendingPreviewFileToLoad.empty()) {
            previewPath = m_pendingPreviewFileToLoad;
            m_pendingPreviewFileToLoad.clear();
        }
        if (!m_pendingVideoToOpen.empty()) {
            vidPath = m_pendingVideoToOpen;
            m_pendingVideoToOpen.clear();
        }
    }
    std::string pendingCollThumb;
    {
        std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
        pendingCollThumb = m_pendingCollectionThumbToLoad;
        m_pendingCollectionThumbToLoad.clear();
    }
    if (!pendingCollThumb.empty() && m_renderer && m_isCollectionBrowserOpen) {
        SDL_Texture* newTex = loadTextureFromFile(m_renderer, pendingCollThumb);
        if (newTex) {
            if (m_collectionThumbTexture) SDL_DestroyTexture(m_collectionThumbTexture);
            m_collectionThumbTexture = newTex;
        }
    }
    if (!previewPath.empty() && m_renderer) {
        SDL_Texture* newTex = loadTextureFromFile(m_renderer, previewPath);
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
        }
    }
    if (!vidPath.empty() && m_renderer && m_isFullscreenPreview) {
        if (!m_videoPlayer.open(vidPath, m_renderer)) {
            // Failed to open -> remove corrupted cache file so it won't hang on black screen
            std::error_code ec;
            std::filesystem::remove(vidPath, ec);
        }
    }
    if (m_isFullscreenPreview && m_videoPlayer.isPlaying()) {
        m_videoPlayer.update();
    }
#endif
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
                rebuildCatalogFilter();
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

    // Proactive background update check after UI has settled (after 2 seconds)
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
    m_dialogOpenedAt = SDL_GetTicks();
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление завершено!" : "Update Complete!";
            m_dialogMessage = (m_language == Language::Russian)
                ? "Приложение H3H-Backgrounds.nro успешно обновлено до актуальной версии!\nНажмите [A], чтобы перезапустить сейчас, или [B] для продолжения."
                : "H3H-Backgrounds.nro updated successfully!\nPress [A] to restart now, or [B] to continue.";
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Приложение обновлено!" : "Updated!";
        } else if (err == "ALREADY_UP_TO_DATE") {
            m_activeDialog = DialogType::MessageAlert;
    m_dialogOpenedAt = SDL_GetTicks();
            m_dialogTitle = (m_language == Language::Russian) ? "Обновление не требуется" : "Up to date";
            m_dialogMessage = (m_language == Language::Russian)
                ? ("У вас уже установлена актуальная версия:\nH3H-Backgrounds v" + std::string(Config::APP_VERSION) + ".\nНовых версий на сервере не найдено.")
                : ("You are already running the latest version:\nv" + std::string(Config::APP_VERSION) + ".");
            m_dialogFocus = 0;
            m_statusNotification = (m_language == Language::Russian) ? "Установлена последняя версия" : "Up to date";
        } else {
            m_activeDialog = DialogType::MessageAlert;
    m_dialogOpenedAt = SDL_GetTicks();
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
    m_dialogOpenedAt = SDL_GetTicks();
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
                InstalledRegistry::instance().setVariantId(
                    m_platform->getAppDirectory(),
                    currentTask.titleId,
                    currentTask.variant.id
                );
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
        InstalledRegistry::instance().remove(m_platform->getAppDirectory(), titleId);
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
        } else if (event.type == SDL_CONTROLLERDEVICEADDED) {
            if (SDL_IsGameController(event.cdevice.which)) {
                SDL_GameControllerOpen(event.cdevice.which);
            }
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
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(9 /* LEFTSHOULDER / ZL */);
                    m_lastTriggerTime = now;
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(10 /* RIGHTSHOULDER / ZR */);
                    m_lastTriggerTime = now;
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
            // MyGames Tab: "[+] Записи 4IFIR (SD)" button: x in [1000, 1230], y in [195, 240]
            else if (m_activeTab == Tab::MyGames && mx >= 1000 && mx <= 1230 && my >= 195 && my <= 240) {
                if (!m_installedGames.empty() && m_myGamesSelectedIndex >= 0 &&
                    m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    openRecordingsBrowser(g.titleId, g.name);
                }
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
            // Catalog Tab: Search Bar click: x in [480, 780], y in [90, 140]
            else if (m_activeTab == Tab::Catalog && mx >= 480 && mx <= 780 && my >= 90 && my <= 140) {
                onButtonPress(3 /* Y - Open Keyboard / Search */);
            }
            // Catalog Tab: Sort Pill click: x in [795, 1060], y in [90, 140]
            else if (m_activeTab == Tab::Catalog && mx >= 795 && mx <= 1060 && my >= 90 && my <= 140) {
                onButtonPress(2 /* X - Cycle Sort Mode */);
            }
            // Catalog Tab: Reset/Refresh button: x in [1075, 1220], y in [90, 140]
            else if (m_activeTab == Tab::Catalog && mx >= 1075 && mx <= 1220 && my >= 90 && my <= 140) {
                onButtonPress(4 /* Minus / Reset or Refresh */);
            }
            // Catalog Tab: click directly on an item in the list
            else if (m_activeTab == Tab::Catalog && mx >= 60 && mx <= 1220 && my >= 160 && my <= 640) {
                int clickedIndex = m_catalogScrollOffset + (my - 160) / 94;
                int totalGames = static_cast<int>(m_filteredCatalogGames.size());
                if (clickedIndex >= 0 && clickedIndex < totalGames) {
                    if (m_catalogSelectedIndex == clickedIndex || mx >= 950) {
                        m_catalogSelectedIndex = clickedIndex;
                        openCollectionBrowser(m_filteredCatalogGames[clickedIndex]);
                    } else {
                        m_catalogSelectedIndex = clickedIndex;
                    }
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
    // Collection Browser Modal Handler (Browse variants by name with static mini-previews)
    if (m_isCollectionBrowserOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview && !m_isGamePickerOpen) {
        if (SDL_GetTicks() - m_collectionOpenedAt < 150) {
            return;
        }
        if (button == 1 /* B - Back to Catalog */) {
            closeCollectionBrowser();
            return;
        }
        int vCount = static_cast<int>(m_collectionVariants.size());
        if (button == 11 /* UP */) {
            if (m_collectionSelectedIndex > 0) {
                m_collectionSelectedIndex--;
                if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                    m_collectionScrollOffset = m_collectionSelectedIndex;
                }
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 12 /* DOWN */) {
            if (m_collectionSelectedIndex + 1 < vCount) {
                m_collectionSelectedIndex++;
                if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                    m_collectionScrollOffset = m_collectionSelectedIndex - 5 + 1;
                }
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_collectionSelectedIndex = std::max(0, m_collectionSelectedIndex - 5);
            if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                m_collectionScrollOffset = m_collectionSelectedIndex;
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            m_collectionSelectedIndex = std::min(vCount - 1, m_collectionSelectedIndex + 5);
            if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                m_collectionScrollOffset = std::max(0, m_collectionSelectedIndex - 5 + 1);
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 0 /* A */ || button == 3 /* Y - Assign to game */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                openGamePicker(m_collectionVariants[m_collectionSelectedIndex], m_collectionGameName);
            }
            return;
        }
        if (button == 2 /* X - Fullscreen live video */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                openFullscreenPreviewForCatalogGame(m_collectionEntry, m_collectionSelectedIndex);
            }
            return;
        }
        return;
    }


    // Target Game Picker Handler (Assign video theme to any installed game)
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
                    ? ("Установить видеофон '" + m_pendingActionVariant.name + "'\nдля игры: " + targetGame.name + " [" + targetGame.titleId + "]?")
                    : ("Install video theme '" + m_pendingActionVariant.name + "'\nfor game: " + targetGame.name + " [" + targetGame.titleId + "]?");
                m_dialogFocus = 0;
                closeGamePicker();
            }
            return;
        }
        return;
    }

    // Local Recordings Browser Handler (Feature 3)
    if (m_isRecordingsBrowserOpen && m_activeDialog == DialogType::None && !m_isFullscreenPreview) {
        if (SDL_GetTicks() - m_recordingsOpenedAt < 150) {
            return;
        }
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
                m_videoPlayer.open(rec.fullPath, m_renderer);
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
    m_dialogOpenedAt = SDL_GetTicks();
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
    if (m_isFullscreenPreview) {
        if (SDL_GetTicks() - m_previewOpenedAt < 200) {
            return;
        }
        if (button == 1 /* B */ || button == 2 /* X */) {
            closeFullscreenPreview();
    closeCollectionBrowser();
            return;
        }
        if (!m_previewVariants.empty()) {
            int vCount = static_cast<int>(m_previewVariants.size());
            if (button == 13 /* DPAD_LEFT */) {
                m_previewVariantIndex = (m_previewVariantIndex == 0) ? vCount - 1 : m_previewVariantIndex - 1;
                loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
                return;
            } else if (button == 14 /* DPAD_RIGHT */) {
                m_previewVariantIndex = (m_previewVariantIndex + 1) % vCount;
                loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
                return;
            } else if (button == 3 /* Y - Assign to another game */) {
                openGamePicker(m_previewVariants[m_previewVariantIndex], m_previewGameName);
                return;
            } else if (button == 0 /* A - Install / Save */) {
                if (m_previewTitleId == "0000000000000000") {
                    openGamePicker(m_previewVariants[m_previewVariantIndex], m_previewGameName);
                    return;
                }
                closeFullscreenPreview();
                m_pendingActionTitleId = m_previewTitleId;
                m_pendingActionVariant = m_previewVariants[m_previewVariantIndex];
                m_activeDialog = DialogType::ConfirmInstall;
    m_dialogOpenedAt = SDL_GetTicks();
                m_dialogTitle = getStrings(m_language).confirmInstallTitle;
                if (m_previewIsGameInstalled) {
                    m_dialogMessage = "Установить вариант '" + m_pendingActionVariant.name + "' (" +
                                      styleToString(m_pendingActionVariant.style) + ") для игры " + m_previewGameName + "?";
                } else {
                    m_dialogMessage = "Игра " + m_previewGameName + " пока не установлена на Switch.\n\n"
                                      "Сохранить видеофон '" + m_pendingActionVariant.name +
                                      "' в recordings/covers заранее, чтобы он активировался при установке игры?";
                }
                m_dialogFocus = 0;
                return;
            }
        }
        return;
    }

    // If Dialog is active, route all input to dialog
    if (m_activeDialog != DialogType::None) {
        if (SDL_GetTicks() - m_dialogOpenedAt < 150) {
            return;
        }
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
        if (m_activeDialog == DialogType::MessageAlert || m_activeDialog == DialogType::IntegrityCheckResult) {
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
        }

        if (button == 13 /* DPAD_LEFT */ || button == 14 /* DPAD_RIGHT */) {
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
        }
        return;
    }

    // Universal Minus (-) button: Global Refresh
    if (button == 4 /* SDL_CONTROLLER_BUTTON_BACK (Minus / -) */) {
        fetchRemoteCatalog();
        return;
    }

    // Standard Nintendo Switch [B] button
    if (button == 1 /* B - Back */) {
        if (m_activeTab == Tab::MyGames && m_myGamesActivePane == MyGamesPane::VariantsList) {
            m_myGamesActivePane = MyGamesPane::GamesList;
            return;
        }
        if (m_activeTab != Tab::Home) {
            m_activeTab = Tab::Home;
            return;
        }
    }

    // Tab switching with Shoulder buttons (L/R)
    if (button == 9 /* LEFTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 0) ? 4 : tabInt - 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }
    if (button == 10 /* RIGHTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            int tabInt = static_cast<int>(m_activeTab);
            tabInt = (tabInt == 4) ? 0 : tabInt + 1;
            m_activeTab = static_cast<Tab>(tabInt);
            m_lastTabSwitchTime = now;
        }
        return;
    }

    // View-specific input handling
    if (m_activeTab == Tab::Home) {
        if (button == 1 /* B - Exit to hbmenu */) {
            m_running = false;
            return;
        }
        if (button == 0 /* A - Enter My Games */) {
            m_activeTab = Tab::MyGames;
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        } else if (button == 2 /* X - Refresh */) {
            fetchRemoteCatalog();
        }
    } else if (m_activeTab == Tab::MyGames) {
        // Feature 3: L3 (Left Stick click) opens 4IFIR SD Recordings browser immediately
        if (button == 7 /* SDL_CONTROLLER_BUTTON_LEFTSTICK (L3) */) {
            if (!m_installedGames.empty()) {
                int idx = std::clamp(m_myGamesSelectedIndex, 0, static_cast<int>(m_installedGames.size()) - 1);
                const auto& g = m_installedGames[idx];
                openRecordingsBrowser(g.titleId, g.name);
                return;
            } else {
                m_statusNotification = "Нет установленных игр для привязки";
                m_notificationFramesRemaining = 120;
                return;
            }
        }

        if (m_myGamesActivePane == MyGamesPane::GamesList) {
            // LEFT COLUMN: Games List navigation
            if (button == 1 /* B - Exit to hbmenu */) {
                m_running = false;
                return;
            }
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
            } else if (button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) {
                // Move focus to right variants column or open collection browser
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                        openCollectionBrowser(g.catalogEntry);
                    } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_myGamesActivePane = MyGamesPane::VariantsList;
                        m_selectedVariantIndex = 0;
                    }
                }
            } else if (button == 2 /* X - Fullscreen Preview */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        openFullscreenPreviewForGame(g, m_selectedVariantIndex);
                    } else {
                        m_activeTab = Tab::Catalog;
                    }
                }
            } else if (button == 3 /* Y - Delete / Install Missing */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.hasInstalledCover) {
                        m_pendingActionTitleId = g.titleId;
                        m_activeDialog = DialogType::ConfirmDelete;
    m_dialogOpenedAt = SDL_GetTicks();
                        m_dialogTitle = "Удаление активного фона";
                        m_dialogMessage = "Удалить установленный видеофон для игры " + g.name + "?\n\n(Фон будет удалён с консоли, а варианты в каталоге останутся доступны для повторной установки в любой момент)";
                        m_dialogFocus = 0;
                    } else {
                        installAllMissing();
                    }
                }
            }
        } else if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            // RIGHT COLUMN: Variants navigation
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& g = m_installedGames[m_myGamesSelectedIndex];
                int vCount = static_cast<int>(g.catalogEntry.variants.size());
                if (button == 11 /* DPAD_UP */) {
                    if (m_selectedVariantIndex > 0) {
                        m_selectedVariantIndex--;
                        if (m_selectedVariantIndex < m_variantScrollOffset) {
                            m_variantScrollOffset = m_selectedVariantIndex;
                        }
                    }
                } else if (button == 12 /* DPAD_DOWN */) {
                    if (m_selectedVariantIndex + 1 < vCount) {
                        m_selectedVariantIndex++;
                        if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                            m_variantScrollOffset = m_selectedVariantIndex - 4 + 1;
                        }
                    }
                } else if (button == 13 /* DPAD_LEFT */ || button == 1 /* B */) {
                    // Return focus back to left games column
                    m_myGamesActivePane = MyGamesPane::GamesList;
                } else if (button == 0 /* A - Install Variant */) {
                    m_pendingActionTitleId = g.titleId;
                    m_pendingActionVariant = g.catalogEntry.variants[m_selectedVariantIndex];
                    m_activeDialog = DialogType::ConfirmInstall;
    m_dialogOpenedAt = SDL_GetTicks();
                    m_dialogTitle = getStrings(m_language).confirmInstallTitle;
                    m_dialogMessage = "Установить вариант '" + m_pendingActionVariant.name + "' (" +
                                      styleToString(m_pendingActionVariant.style) + ") для " + g.name + "?";
                    m_dialogFocus = 0;
                } else if (button == 2 /* X - Fullscreen Preview */) {
                    openFullscreenPreviewForGame(g, m_selectedVariantIndex);
                } else if (button == 3 /* Y - Delete */) {
                    if (g.hasInstalledCover) {
                        m_pendingActionTitleId = g.titleId;
                        m_activeDialog = DialogType::ConfirmDelete;
    m_dialogOpenedAt = SDL_GetTicks();
                        m_dialogTitle = "Удаление активного фона";
                        m_dialogMessage = "Удалить установленный видеофон для игры " + g.name + "?\n\n(Фон будет удалён с консоли, а варианты в каталоге останутся доступны для повторной установки в любой момент)";
                        m_dialogFocus = 0;
                    }
                }
            }
        }
    } else if (m_activeTab == Tab::Catalog) {
        int totalGames = static_cast<int>(m_filteredCatalogGames.size());
        if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) m_catalogSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) m_catalogSelectedIndex++;
        } else if (button == 13 /* DPAD_LEFT - Page Up 5 */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
        } else if (button == 14 /* DPAD_RIGHT - Page Down 5 */) {
            if (totalGames > 0) m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
        } else if (button == 0 /* A - Enter Collection Browser */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = m_filteredCatalogGames[m_catalogSelectedIndex];
                openCollectionBrowser(entry);
            }
        } else if (button == 2 /* X - Cycle Sort Mode */) {
            cycleCatalogSortMode();
        } else if (button == 3 /* Y - Open Horizon Software Keyboard (Search) */) {
            openCatalogKeyboard();
        } else if (button == 4 /* MINUS - Clear Search or Refresh */) {
            if (!m_catalogSearchQuery.empty()) {
                m_catalogSearchQuery.clear();
                rebuildCatalogFilter();
                m_statusNotification = (m_language == Language::Russian) ? "Поиск сброшен (показаны все игры)" : "Search cleared";
                m_notificationFramesRemaining = 90;
            } else {
                fetchRemoteCatalog();
            }
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

    if (m_isFullscreenPreview) {
        renderFullscreenPreview();
        SDL_RenderPresent(m_renderer);
        return;
    }

    // Clear background with hardware buffer clear
    SDL_SetRenderDrawColor(m_renderer, Theme::COLOR_BG_BASE.r, Theme::COLOR_BG_BASE.g, Theme::COLOR_BG_BASE.b, 255);
    SDL_RenderClear(m_renderer);

    renderHeader();

    switch (m_activeTab) {
        case Tab::Home:      renderTabHome(); break;
        case Tab::MyGames:   renderTabMyGames(); break;
        case Tab::Catalog:   renderTabCatalog(); break;
        case Tab::Downloads: renderTabDownloads(); break;
        case Tab::Settings:  renderTabSettings(); break;
    }

    renderFooter();

    if (m_isRecordingsBrowserOpen) {
        renderRecordingsBrowser();
    }
    if (m_isCollectionBrowserOpen) {
        renderCollectionBrowser();
    }
    if (m_isGamePickerOpen) {
        renderGamePicker();
    }

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
        hints = "[L/R] Вкладки   [A] Мои игры   [B] Выход из приложения   [Y] Установить все   [-] Обновить";
    } else if (m_activeTab == Tab::MyGames) {
        if (m_language == Language::Russian) {
            hints = "[A] Выбрать   [X] Видео   [Y] Удалить   [B] Назад / Выход   [L/R] Вкладки   [-] Каталог";
        } else {
            hints = "[A] Select   [X] Fullscreen   [Y] Delete   [B] Back   [L/R] Tabs   [-] Catalog";
        }
    } else if (m_activeTab == Tab::Catalog) {
        if (!m_catalogSearchQuery.empty()) {
            hints = "[▲/▼] Выбор   [◀/▶] ±5   [A] Открыть   [Y] Поиск   [X] Сортировка   [-] Сбросить поиск   [B] Назад";
        } else {
            hints = "[▲/▼] Выбор   [◀/▶] ±5   [A] Открыть   [Y] Поиск   [X] Сортировка   [-] Обновить   [B] Назад";
        }
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

    size_t totalVariants = m_catalogManager.getTotalVariantsCount();
    // Metric Card 3: Available in Catalog
    drawGlassCard(860, 95, 360, 145, false, true);
    drawText(s.statAvailableCatalog, 885, 115, Theme::COLOR_TEXT_MUTED, 15);
    drawText(std::to_string(totalVariants), 885, 145, Theme::COLOR_FOCUS_CYAN, 44);
    drawRect(885, 202, 210, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(885, 202, 210, 26, Theme::COLOR_FOCUS_CYAN, 1);
    std::string catSub = std::to_string(catalogCount) + (m_language == Language::Russian ? " игр/коллекций" : " games/groups");
    drawText(catSub, 895, 208, Theme::COLOR_FOCUS_CYAN, 12);

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
        bool isFocused = (m_myGamesActivePane == MyGamesPane::GamesList && isSelected);
        drawGlassCard(35, startY, 440, 60, isFocused, isSelected);

        drawText(game.name, 48, startY + 10, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15, 310);
        drawText(game.titleId, 48, startY + 34, Theme::COLOR_TEXT_MUTED, 12, 310);

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

        drawText(selGame.name, 530, 110, Theme::COLOR_TEXT_PRIMARY, 22, 410);
        drawText("Title ID: " + selGame.titleId + "  |  " + selGame.author, 530, 145, Theme::COLOR_TEXT_MUTED, 14, 410);

        // Status details
        std::string coverInfo = selGame.hasInstalledCover ?
            std::string(m_language == Language::Russian ? "Активный фон на консоли: " : "Active cover: ") +
            Config::getTargetCoverFileName(selGame.titleId) + " (" +
            std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)" :
            std::string(m_language == Language::Russian ? "Видеофон не установлен" : "No video background installed");
        drawText(coverInfo, 530, 175, selGame.hasInstalledCover ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);

        // Prominent Action Buttons (positioned below status, safe from top-right Tesla monitor HUD)
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
        }

        // Available variants from catalog (concise header to avoid collision with hints)
        int totalVariants = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
        std::string varHeader = "Варианты (" + std::to_string(totalVariants) + "):";
        drawText(varHeader, 530, 248, Theme::COLOR_TEXT_PRIMARY, 16);

        if (m_myGamesActivePane == MyGamesPane::VariantsList) {
            drawText("◀ [B] К играм   |   [X] На весь экран", 870, 250, Theme::COLOR_FOCUS_CYAN, 12);
        } else {
            drawText("▶ [A] К вариантам   |   [X] На весь экран", 870, 250, Theme::COLOR_TEXT_MUTED, 12);
        }

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
                bool isVarFocused = (m_myGamesActivePane == MyGamesPane::VariantsList && isVarSelected);
                drawGlassCard(525, vY, 700, 72, isVarFocused, isVarSelected);

                // Variant Title & Style (bounded so it never overlaps install button)
                std::string vTitle = std::to_string(vIdx + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
                drawText(vTitle, 545, vY + 12, isVarSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 450);

                // Tech Specs Line (Width capped at 230 to avoid overlap with badges)
                std::string meta = std::to_string(v.width) + "x" + std::to_string(v.height) + " @" +
                                   std::to_string(static_cast<int>(v.fps)) + "fps  |  " +
                                   ([&]() {
                    double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
                    char buf[16];
                    if (mb >= 0.1) snprintf(buf, sizeof(buf), "%.1f MB", mb);
                    else snprintf(buf, sizeof(buf), "~3.5 MB");
                    return std::string(buf);
                })();
                drawText(meta, 545, vY + 41, Theme::COLOR_TEXT_MUTED, 12, 230);

                // Active installed background badge - EXACT MATCH ONLY
                bool isActiveOnConsole = (selGame.hasInstalledCover && v.id == selGame.installedVariantId);
                if (isActiveOnConsole) {
                    drawRect(785, vY + 38, 105, 22, {0x10, 0xB9, 0x81, 0x44});
                    drawRectOutline(785, vY + 38, 105, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("УСТАНОВЛЕН", 797, vY + 43, Theme::COLOR_SUCCESS, 10);
                }

                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(905, vY + 38, 70, 22, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(905, vY + 38, 70, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", 924, vY + 43, Theme::COLOR_SUCCESS, 10);
                } else {
                    drawRect(905, vY + 38, 85, 22, {0x28, 0x33, 0x47, 0x44});
                    drawRectOutline(905, vY + 38, 85, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", 916, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                }

                if (isVarSelected) {
                    drawRect(1005, vY + 18, 205, 36, Theme::COLOR_FOCUS_FILL);
                    drawRectOutline(1005, vY + 18, 205, 36, Theme::COLOR_FOCUS_CYAN, 1);
                    std::string btnText = isActiveOnConsole ? "[A] Переустановить" : "[A] Установить";
                    drawText(btnText, 1025, vY + 27, Theme::COLOR_FOCUS_CYAN, 13);
                }

                vY += 80;
            }

            // Scroll indicator BELOW
            if (endVIdx < totalVariants) {
                std::string belowStr = "▼ Еще варианты ниже: " + std::to_string(totalVariants - endVIdx) + " шт. (используйте D-Pad Вправо)";
                drawText(belowStr, 720, vY + 6, Theme::COLOR_FOCUS_PINK, 12);
            }
        } else {
            drawText((m_language == Language::Russian
                ? "Прямых вариантов для этой игры пока нет в каталоге."
                : "No direct variants found for this game in the catalog."),
                530, 290, Theme::COLOR_TEXT_MUTED, 14);

            drawText((m_language == Language::Russian
                ? "Вы можете привязать ЛЮБОЙ видеофон из каталога:"
                : "You can assign ANY video theme from the catalog:"),
                530, 318, Theme::COLOR_FOCUS_CYAN, 13);

            drawGlassCard(530, 350, 480, 56, true, false);
            drawText((m_language == Language::Russian ? "[X] Открыть каталог After Dark" : "[X] Open After Dark Catalog"),
                     555, 368, Theme::COLOR_FOCUS_CYAN, 16);
        }
    }
}

void App::renderTabCatalog() {
    const auto& s = getStrings(m_language);

    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 80, 1220, 570, false, false);

    // Title & Info
    drawText("Онлайн-библиотека видеофонов 4IFIR", 60, 100, Theme::COLOR_TEXT_PRIMARY, 20);

    // 1. Search Bar Card [Y]: x in [480, 780], y in [92, 134]
    bool hasQuery = !m_catalogSearchQuery.empty();
    drawGlassCard(480, 92, 300, 42, hasQuery, false);
    if (!hasQuery) {
        drawText("🔍 [Y] Поиск по названию...", 495, 105, Theme::COLOR_TEXT_MUTED, 13, 270);
    } else {
        drawText("🔍 [Y] \"" + m_catalogSearchQuery + "\"", 495, 105, Theme::COLOR_FOCUS_CYAN, 13, 270);
    }

    // 2. Sort Pill [X]: x in [795, 1060], y in [92, 134]
    bool customSort = (m_catalogSortMode != CatalogSortMode::Default);
    drawGlassCard(795, 92, 265, 42, customSort, false);
    std::string sortLabel = "[X] Сорт: ";
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: sortLabel += "По умолчанию"; break;
        case CatalogSortMode::Alphabetical: sortLabel += "А-Я (по имени)"; break;
        case CatalogSortMode::VariantsCount: sortLabel += "По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: sortLabel += "Только со звуком"; break;
        case CatalogSortMode::InstalledOnly: sortLabel += "Установленные"; break;
    }
    drawText(sortLabel, 808, 105, customSort ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_MUTED, 13, 245);

    // 3. Reset / Refresh button [-]: x in [1075, 1220], y in [92, 134]
    drawGlassCard(1075, 92, 145, 42, true, false);
    if (hasQuery) {
        drawText("[-] Сброс", 1105, 105, Theme::COLOR_FOCUS_PINK, 13);
    } else {
        drawText("[-] Обновить", 1095, 105, Theme::COLOR_FOCUS_CYAN, 13);
    }

    int totalFiltered = static_cast<int>(m_filteredCatalogGames.size());
    int totalAll = static_cast<int>(m_catalogManager.getAllGames().size());

    if (totalFiltered == 0) {
        if (hasQuery) {
            drawText("По запросу \"" + m_catalogSearchQuery + "\" ничего не найдено.", 60, 200, Theme::COLOR_FOCUS_PINK, 18);
            drawText("Нажмите [Y], чтобы изменить запрос, или [-] для сброса фильтра.", 60, 235, Theme::COLOR_TEXT_MUTED, 15);
        } else {
            drawText("Каталог пуст или ещё не загружен.", 60, 180, Theme::COLOR_TEXT_MUTED, 16);
            drawText("Нажмите кнопку [-], чтобы загрузить актуальный список видеофонов с GitHub.", 60, 215, Theme::COLOR_FOCUS_CYAN, 15);
        }
        return;
    }

    const int visibleCount = 5;

    if (m_catalogSelectedIndex < m_catalogScrollOffset) {
        m_catalogScrollOffset = m_catalogSelectedIndex;
    }
    if (m_catalogSelectedIndex >= m_catalogScrollOffset + visibleCount) {
        m_catalogScrollOffset = m_catalogSelectedIndex - visibleCount + 1;
    }

    std::string pageInfo = "Игр: " + std::to_string(totalFiltered) + " из " + std::to_string(totalAll) +
                           "   (Выбрано: " + std::to_string(m_catalogSelectedIndex + 1) + " / " + std::to_string(totalFiltered) + ")" +
                           (hasQuery ? ("   Фильтр: \"" + m_catalogSearchQuery + "\"") : "");
    drawText(pageInfo, 60, 135, Theme::COLOR_TEXT_MUTED, 13);

    int y = 160;
    int endIdx = std::min(totalFiltered, m_catalogScrollOffset + visibleCount);
    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_catalogSelectedIndex);
        const auto& g = m_filteredCatalogGames[i];

        // 4IFIR Frosted Card for each catalog entry
        drawGlassCard(60, y, 1160, 80, isSelected, false);

        // Title
        drawText(g.title, 85, y + 16, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 17, 680);

        // Check if game is installed on console
        bool isInstalledOnSwitch = false;
        bool hasActiveCover = false;
        for (const auto& ig : m_installedGames) {
            if (ig.titleId == g.titleId) {
                isInstalledOnSwitch = true;
                hasActiveCover = ig.hasInstalledCover;
                break;
            }
        }

        // Check audio badge for game
        bool hasAudioVariant = false;
        for (const auto& v : g.variants) {
            if (v.hasAudio) { hasAudioVariant = true; break; }
        }

        std::string meta = "Title ID: " + g.titleId + "   |   Вариантов фона: " + std::to_string(g.variants.size());
        drawText(meta, 85, y + 44, Theme::COLOR_TEXT_MUTED, 13);

        // Audio badge
        if (hasAudioVariant) {
            drawRect(640, y + 40, 75, 22, {0x18, 0x38, 0x24, 0xCC});
            drawRectOutline(640, y + 40, 75, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", 658, y + 44, Theme::COLOR_SUCCESS, 10);
        }

        // Status badges on card
        if (isInstalledOnSwitch) {
            if (hasActiveCover) {
                drawRect(730, y + 40, 185, 22, {0x10, 0xB9, 0x81, 0x33});
                drawRectOutline(730, y + 40, 185, 22, Theme::COLOR_SUCCESS, 1);
                drawText("НА SWITCH (ФОН ЕСТЬ)", 740, y + 44, Theme::COLOR_SUCCESS, 10);
            } else {
                drawRect(730, y + 40, 165, 22, {0x02, 0x84, 0xC7, 0x33});
                drawRectOutline(730, y + 40, 165, 22, Theme::COLOR_FOCUS_CYAN, 1);
                drawText("УСТАНОВЛЕНА НА SWITCH", 740, y + 44, Theme::COLOR_FOCUS_CYAN, 10);
            }
        } else {
            drawRect(730, y + 40, 140, 22, {0x28, 0x33, 0x47, 0x44});
            drawRectOutline(730, y + 40, 140, 22, Theme::COLOR_BORDER, 1);
            drawText("В ОНЛАЙН-КАТАЛОГЕ", 740, y + 44, Theme::COLOR_TEXT_MUTED, 10);
        }

        // Action button on right
        if (isSelected) {
            int vCount = static_cast<int>(g.variants.size());
            if (vCount > 1) {
                drawRect(915, y + 22, 285, 36, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(915, y + 22, 285, 36, 2);
                drawText("[A] Все фоны (" + std::to_string(vCount) + " шт.) ▶", 930, y + 31, Theme::COLOR_FOCUS_CYAN, 14);
            } else {
                drawRect(960, y + 22, 240, 36, Theme::COLOR_FOCUS_FILL);
                drawNeonGradientOutline(960, y + 22, 240, 36, 2);
                drawText("[A] Смотреть фон ▶", 975, y + 31, Theme::COLOR_FOCUS_CYAN, 14);
            }
        }

        y += 80 + 14;
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

    drawText(std::string("4IFIR System Settings  |  ") + Config::APP_NAME, 60, 105, Theme::COLOR_TEXT_PRIMARY, 22);
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
        drawText(m_dialogTitle, dx + 35, dy + 25, Theme::COLOR_FOCUS_CYAN, 20, dw - 70);
        drawText(m_dialogMessage, dx + 35, dy + 70, Theme::COLOR_TEXT_PRIMARY, 15, dw - 70);

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
        drawText("Обновление безопасно заменяет файл на SD карте без перезаписи в Horizon OS", dx + 35, dy + 185, Theme::COLOR_TEXT_MUTED, 12, dw - 70);
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

    // Specialized dialog: Alert with auto word-wrap
    if (m_activeDialog == DialogType::MessageAlert) {
        std::stringstream ss(m_dialogMessage);
        std::string rawLine;
        int msgY = dy + 70;
        while (std::getline(ss, rawLine, '\n')) {
            std::stringstream wordStream(rawLine);
            std::string word;
            std::string currentLine;
            while (wordStream >> word) {
                if (currentLine.empty()) {
                    currentLine = word;
                } else if (currentLine.length() + 1 + word.length() <= 54) {
                    currentLine += " " + word;
                } else {
                    drawText(currentLine, dx + 35, msgY, Theme::COLOR_WARNING, 15, dw - 70);
                    msgY += 26;
                    currentLine = word;
                }
            }
            if (!currentLine.empty()) {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_WARNING, 15, dw - 70);
                msgY += 26;
            }
        }

        int btnW = 160;
        int btnH = 40;
        int btnY = dy + 195;
        drawRect(dx + 270, btnY, btnW, btnH, Theme::COLOR_BG_SURFACE);
        drawRectOutline(dx + 270, btnY, btnW, btnH, Theme::COLOR_BORDER, 1);
        drawText("[A] Закрыть", dx + 310, btnY + 12, Theme::COLOR_TEXT_PRIMARY, 14);
        return;
    }

    // Standard Confirmation Dialogs with auto word-wrap
    std::stringstream ss(m_dialogMessage);
    std::string rawLine;
    int msgY = dy + 70;
    while (std::getline(ss, rawLine, '\n')) {
        std::stringstream wordStream(rawLine);
        std::string word;
        std::string currentLine;
        while (wordStream >> word) {
            if (currentLine.empty()) {
                currentLine = word;
            } else if (currentLine.length() + 1 + word.length() <= 54) {
                currentLine += " " + word;
            } else {
                drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14, dw - 70);
                msgY += 24;
                currentLine = word;
            }
        }
        if (!currentLine.empty()) {
            drawText(currentLine, dx + 35, msgY, Theme::COLOR_TEXT_MUTED, 14, dw - 70);
            msgY += 24;
        }
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

void App::drawText(const std::string& text, int x, int y, Color color, int sizePx, int maxWidth) {
#ifdef HAS_SDL2
    if (text.empty() || !m_renderer) return;

    TTF_Font* font = getFont(sizePx);
    if (font) {
        SDL_Color sdlColor = {color.r, color.g, color.b, color.a};
        SDL_Surface* surf = TTF_RenderUTF8_Blended(font, text.c_str(), sdlColor);
        if (surf) {
            SDL_Texture* tex = SDL_CreateTextureFromSurface(m_renderer, surf);
            if (tex) {
                int drawW = surf->w;
                if (maxWidth > 0 && drawW > maxWidth) {
                    drawW = maxWidth;
                }
                SDL_Rect srcRect = {0, 0, drawW, surf->h};
                SDL_Rect dstRect = {x, y, drawW, surf->h};
                SDL_RenderCopy(m_renderer, tex, &srcRect, &dstRect);
                SDL_DestroyTexture(tex);
            }
            SDL_FreeSurface(surf);
            return;
        }
    }

    drawBitmapTextFallback(text, x, y, color);
#else
    (void)text; (void)x; (void)y; (void)color; (void)sizePx; (void)maxWidth;
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




void App::renderFullscreenPreview() {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    SDL_SetRenderDrawColor(m_renderer, 0, 0, 0, 255);
    SDL_RenderClear(m_renderer);

    SDL_Rect fullScreenRect = {0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT};

    // 1. Draw Live Motion Video or Static Background Image or Dark Frosted Canvas
    if (m_videoPlayer.isPlaying()) {
        m_videoPlayer.render(m_renderer, &fullScreenRect);

        // Status badge: LIVE VIDEO
        drawRect(30, 20, 280, 32, {0x0F, 0x17, 0x2A, 0xDD});
        drawRectOutline(30, 20, 280, 32, Theme::COLOR_SUCCESS, 1);
        drawText("▶ ЖИВОЙ ВИДЕОФОН (30 FPS)", 45, 28, Theme::COLOR_SUCCESS, 13);
    } else if (m_previewTexture) {
        SDL_RenderCopy(m_renderer, m_previewTexture, nullptr, &fullScreenRect);

        if (m_videoDownloading) {
            drawRect(30, 20, 270, 32, {0x0F, 0x17, 0x2A, 0xDD});
            drawRectOutline(30, 20, 270, 32, Theme::COLOR_FOCUS_CYAN, 1);
            int dotCount = (SDL_GetTicks() / 350) % 4;
            std::string dots = std::string(dotCount, '.');
            drawText("▶ Буферизация ролика" + dots, 45, 28, Theme::COLOR_FOCUS_CYAN, 13);
        } else {
            drawRect(30, 20, 290, 32, {0x0F, 0x17, 0x2A, 0xDD});
            drawRectOutline(30, 20, 290, 32, Theme::COLOR_BORDER, 1);
            drawText("▶ Предпросмотр (Статичный кадр)", 45, 28, Theme::COLOR_TEXT_MUTED, 13);
        }
    } else {
        // Fallback canvas with subtle Cyber-Glass animated glow
        drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x08, 0x0C, 0x14, 0xFF});
        drawNeonGradientOutline(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, 3);

        if (m_previewLoading || m_videoDownloading) {
            drawText("Загрузка видеофона (1280x720 HD)...", 400, 320, Theme::COLOR_FOCUS_CYAN, 20);
            drawText("Пожалуйста, подождите несколько секунд...", 450, 360, Theme::COLOR_TEXT_MUTED, 14);
        } else {
            drawText("Видеофон недоступен офлайн (нет подключения)", 390, 320, Theme::COLOR_WARNING, 20);
            drawText("Нажмите [A], чтобы установить видеофон из кэша", 430, 360, Theme::COLOR_TEXT_MUTED, 14);
        }
    }

    // 2. Bottom 4IFIR Cyber-Glass HUD overlay
    int hudX = 40;
    int hudY = 585;
    int hudW = 1200;
    int hudH = 105;
    // Solid dark obsidian to prevent underlying video text/artifacts from bleeding through
    drawRect(hudX, hudY, hudW, hudH, {0x0D, 0x11, 0x1A, 0xF6});
    drawNeonGradientOutline(hudX, hudY, hudW, hudH, 2);

    if (!m_previewVariants.empty()) {
        int totalV = static_cast<int>(m_previewVariants.size());
        int curV = std::clamp(m_previewVariantIndex, 0, totalV - 1);
        const auto& v = m_previewVariants[curV];

        // Game Name (Left top)
        drawText(m_previewGameName, hudX + 25, hudY + 12, Theme::COLOR_TEXT_PRIMARY, 19, 580);

        // Variant Name & Style (Left middle)
        std::string varTitle = std::to_string(curV + 1) + ". " + v.name + " (" + styleToString(v.style) + ")";
        drawText(varTitle, hudX + 25, hudY + 38, Theme::COLOR_FOCUS_CYAN, 16, 580);

        // Tech specs + Audio pill (Left bottom)
        double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
        char mbBuf[16];
        if (mb >= 0.1) snprintf(mbBuf, sizeof(mbBuf), "%.1f MB", mb);
        else snprintf(mbBuf, sizeof(mbBuf), "~3.5 MB");

        std::string specs = "1280x720 @30fps  |  " + std::string(mbBuf) +
                            "  |  Вариант " + std::to_string(curV + 1) + " из " + std::to_string(totalV);
        drawText(specs, hudX + 25, hudY + 68, Theme::COLOR_TEXT_MUTED, 13, 390);

        if (v.hasAudio) {
            drawRect(hudX + 430, hudY + 66, 75, 22, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(hudX + 430, hudY + 66, 75, 22, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", hudX + 451, hudY + 70, Theme::COLOR_SUCCESS, 10);
        } else {
            drawRect(hudX + 430, hudY + 66, 85, 22, {0x28, 0x33, 0x47, 0x44});
            drawRectOutline(hudX + 430, hudY + 66, 85, 22, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ЗВУКА", hudX + 439, hudY + 70, Theme::COLOR_TEXT_MUTED, 10);
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
        }

        // Right side buttons
        if (m_previewTitleId == "0000000000000000") {
            drawRect(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(hudX + 900, hudY + 14, 270, 38, 2);
            drawText("[A/Y] Выбрать игру для фона", hudX + 915, hudY + 24, Theme::COLOR_FOCUS_CYAN, 13);
        } else if (isActiveVariant) {
            drawRect(hudX + 900, hudY + 14, 270, 38, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_SUCCESS, 1);
            drawText("[A] Переустановить", hudX + 950, hudY + 24, Theme::COLOR_SUCCESS, 14);
        } else if (m_previewIsGameInstalled) {
            drawRect(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_FILL);
            drawRectOutline(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_FOCUS_CYAN, 1);
            drawText("[A] Установить видеофон", hudX + 930, hudY + 24, Theme::COLOR_FOCUS_CYAN, 14);
        } else {
            drawRect(hudX + 900, hudY + 14, 270, 38, {0x16, 0x20, 0x32, 0xAA});
            drawRectOutline(hudX + 900, hudY + 14, 270, 38, Theme::COLOR_BORDER, 1);
            drawText("[A] Скачать заранее", hudX + 942, hudY + 24, Theme::COLOR_TEXT_MUTED, 14);
        }

        drawText("[Y] Привязать к другой игре", hudX + 680, hudY + 68, Theme::COLOR_FOCUS_CYAN, 12);
        if (totalV > 1) {
            drawText("[◀ / ▶] Вариант", hudX + 930, hudY + 68, Theme::COLOR_FOCUS_PINK, 12);
        }
        drawText("[B] Назад", hudX + 1110, hudY + 68, Theme::COLOR_TEXT_MUTED, 13);
    }
#endif
}

void App::openFullscreenPreviewForGame(const InstalledTitle& g, int variantIndex) {
#ifdef HAS_SDL2
    if (!g.hasCatalogMatch || g.catalogEntry.variants.empty()) return;

    m_previewTitleId = g.titleId;
    m_previewGameName = g.name;
    m_previewVariants = g.catalogEntry.variants;
    m_previewVariantIndex = std::clamp(variantIndex, 0, static_cast<int>(m_previewVariants.size()) - 1);
    m_previewIsGameInstalled = true;
    m_previewHasInstalledCover = g.hasInstalledCover;
    m_previewInstalledVariantId = g.installedVariantId;
    m_previewInstalledCoverSizeBytes = g.installedCoverSizeBytes;
    m_previewInstalledCoverPath = g.installedCoverPath;

    m_previewOpenedAt = SDL_GetTicks();
    m_isFullscreenPreview = true;
    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#endif
}

void App::openFullscreenPreviewForCatalogGame(const GameCatalogEntry& entry, int variantIndex) {
#ifdef HAS_SDL2
    if (entry.variants.empty()) return;

    m_previewTitleId = entry.titleId;
    m_previewGameName = entry.title;
    m_previewVariants = entry.variants;
    m_previewVariantIndex = std::clamp(variantIndex, 0, static_cast<int>(m_previewVariants.size()) - 1);

    m_previewIsGameInstalled = false;
    m_previewHasInstalledCover = false;
    m_previewInstalledVariantId.clear();
    m_previewInstalledCoverSizeBytes = 0;
    m_previewInstalledCoverPath.clear();

    for (const auto& g : m_installedGames) {
        if (g.titleId == entry.titleId) {
            m_previewIsGameInstalled = true;
            m_previewHasInstalledCover = g.hasInstalledCover;
            m_previewInstalledVariantId = g.installedVariantId;
            m_previewInstalledCoverSizeBytes = g.installedCoverSizeBytes;
            m_previewInstalledCoverPath = g.installedCoverPath;
            break;
        }
    }

    m_previewOpenedAt = SDL_GetTicks();
    m_isFullscreenPreview = true;
    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#endif
}

void App::loadPreviewTexture(const std::string& titleId, const Variant& variant) {
#ifdef HAS_SDL2
    m_videoPlayer.close();

    std::string cacheKey = titleId + "_" + variant.id;
    m_previewCurrentVariantId = cacheKey;

    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string thumbFile = thumbDir + "/" + cacheKey + ".jpg";
    std::string vidFile = thumbDir + "/" + cacheKey + ".mp4";

    // 1. Check if THIS SPECIFIC VARIANT is the active installed cover on console
    bool isThisVariantInstalled = (m_previewHasInstalledCover &&
                                   variant.id == m_previewInstalledVariantId &&
                                   !m_previewInstalledCoverPath.empty() &&
                                   std::filesystem::exists(m_previewInstalledCoverPath, ec));

    if (isThisVariantInstalled) {
        // Play directly from SD card with 0 network delay!
        m_videoPlayer.open(m_previewInstalledCoverPath, m_renderer);
    } else if (std::filesystem::exists(vidFile, ec)) {
        uint64_t cachedSz = std::filesystem::file_size(vidFile, ec);
        if (cachedSz > 50000) {
            if (!m_videoPlayer.open(vidFile, m_renderer)) {
                // Corrupted cache -> purge so it can redownload cleanly
                std::filesystem::remove(vidFile, ec);
                // keep thumbFile intact
            }
        } else {
            std::filesystem::remove(vidFile, ec);
        }
    }

    // 2. Load static image if exists
    if (std::filesystem::exists(thumbFile, ec)) {
        SDL_Texture* newTex = loadTextureFromFile(m_renderer, thumbFile);
        if (newTex) {
            if (m_previewTexture) SDL_DestroyTexture(m_previewTexture);
            m_previewTexture = newTex;
        }
    }

    // 3. If video is already playing, no need to download
    if (m_videoPlayer.isPlaying()) {
        m_previewLoading = false;
        m_videoDownloading = false;
        return;
    }

    // 4. Download snapshot and video in background
    std::string thumbUrl = variant.previewUrl;
    size_t szPos = thumbUrl.find("sz=w640");
    if (szPos != std::string::npos) {
        thumbUrl.replace(szPos, 7, "sz=w1280");
    }
    std::string videoUrl = variant.url;

    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }
    m_cancelPreview.store(false);

    m_previewLoading = true;
    m_videoDownloading = true;

    m_previewThread = std::thread([this, thumbUrl, videoUrl, thumbFile, vidFile, key = cacheKey]() {
        // First download thumbnail image if not already cached
        std::error_code ec2;
        if (!std::filesystem::exists(thumbFile, ec2) && !thumbUrl.empty()) {
            std::string err;
            bool ok = m_platform->downloadFile(thumbUrl, thumbFile, nullptr, m_cancelPreview, err);
            m_previewLoading = false;
            if (ok && m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                std::lock_guard<std::mutex> lock(m_previewMutex);
                m_pendingPreviewFileToLoad = thumbFile;
            }
        } else {
            m_previewLoading = false;
        }

        // Then download live video MP4 to temporary file first, validate before saving
        if (!m_cancelPreview.load() && !videoUrl.empty() && !std::filesystem::exists(vidFile, ec2)) {
            std::string err;
            std::string tmpVid = vidFile + ".tmp";
            bool ok = m_platform->downloadFile(videoUrl, tmpVid, nullptr, m_cancelPreview, err);
            m_videoDownloading = false;
            if (ok && std::filesystem::exists(tmpVid, ec2)) {
                std::string valErr;
                if (Installer::validateVideoFile(tmpVid, valErr)) {
                    std::filesystem::rename(tmpVid, vidFile, ec2);
                    if (m_isFullscreenPreview && m_previewCurrentVariantId == key) {
                        std::lock_guard<std::mutex> lock(m_previewMutex);
                        m_pendingVideoToOpen = vidFile;
                    }
                } else {
                    // Corrupted or server error HTML -> purge so it does not poison cache
                    std::filesystem::remove(tmpVid, ec2);
                }
            } else {
                std::filesystem::remove(tmpVid, ec2);
            }
        } else {
            m_videoDownloading = false;
        }
    });
#endif
}

void App::closeFullscreenPreview() {
#ifdef HAS_SDL2
    m_isFullscreenPreview = false;
    m_videoPlayer.close();
    m_cancelPreview.store(true);
    if (m_previewThread.joinable()) {
        m_previewThread.join();
    }
    if (m_previewTexture) {
        SDL_DestroyTexture(m_previewTexture);
        m_previewTexture = nullptr;
    }
    m_previewCurrentVariantId.clear();
    m_previewTitleId.clear();
    m_previewGameName.clear();
    m_previewVariants.clear();
    m_previewVariantIndex = 0;
#endif
}



void App::openRecordingsBrowser(const std::string& titleId, const std::string& gameName) {
    m_recordingsTargetTitleId = titleId;
    m_recordingsTargetGameName = gameName;
    m_localRecordings = Installer::listLocalRecordings(m_platform->getRecordingsDirectory());
    m_recordingsSelectedIndex = 0;
    m_recordingsScrollOffset = 0;
    m_recordingsOpenedAt = SDL_GetTicks();
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
    m_dialogOpenedAt = SDL_GetTicks();
    }
}

void App::runIntegrityCheck() {
    IntegrityReport report = Installer::validateAllInstalledCovers(m_platform->getCoversDirectory());
    m_lastIntegrityTotalChecked = report.totalChecked;

    if (report.issues.empty()) {
        m_activeDialog = DialogType::IntegrityCheckResult;
    m_dialogOpenedAt = SDL_GetTicks();
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
    m_dialogOpenedAt = SDL_GetTicks();
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

// ----------------- Collection / Variant Browser Implementation -----------------




void App::openCollectionBrowser(const GameCatalogEntry& entry) {
    if (entry.variants.empty()) return;
    m_collectionEntry = entry;
    m_collectionTitleId = entry.titleId;
    m_collectionGameName = entry.title;
    m_collectionVariants = entry.variants;
    m_collectionSelectedIndex = 0;
    m_collectionScrollOffset = 0;
    m_collectionOpenedAt = SDL_GetTicks();
    m_isCollectionBrowserOpen = true;
    loadCollectionThumbnail(m_collectionVariants[0]);
}

void App::closeCollectionBrowser() {
    m_isCollectionBrowserOpen = false;
    m_cancelCollectionThumb.store(true);
    if (m_collectionThumbThread.joinable()) {
        m_collectionThumbThread.join();
    }
    m_cancelCollectionThumb.store(false);
    if (m_collectionThumbTexture) {
        SDL_DestroyTexture(m_collectionThumbTexture);
        m_collectionThumbTexture = nullptr;
    }
    m_collectionCurrentThumbVariantId.clear();
    m_pendingCollectionThumbToLoad.clear();
    m_collectionVariants.clear();
}

void App::loadCollectionThumbnail(const Variant& variant) {
#ifdef HAS_SDL2
    m_cancelCollectionThumb.store(true);
    if (m_collectionThumbThread.joinable()) {
        m_collectionThumbThread.join();
    }
    m_cancelCollectionThumb.store(false);

    if (m_collectionThumbTexture) {
        SDL_DestroyTexture(m_collectionThumbTexture);
        m_collectionThumbTexture = nullptr;
    }
    m_collectionCurrentThumbVariantId = variant.id;

    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    std::filesystem::create_directories(thumbDir, ec);
    std::string cacheKey = m_collectionTitleId + "_" + variant.id;
    std::string thumbFile = thumbDir + "/" + cacheKey + ".jpg";

    if (std::filesystem::exists(thumbFile, ec)) {
        m_collectionThumbTexture = loadTextureFromFile(m_renderer, thumbFile);
        m_collectionThumbLoading = false;
        return;
    }

    m_collectionThumbLoading = true;
    std::string thumbUrl = variant.previewUrl;
    if (thumbUrl.empty()) {
        thumbUrl = variant.url;
    }

    m_collectionThumbThread = std::thread([this, thumbUrl, thumbFile, key = variant.id]() {
        std::string err;
        std::error_code ec;
        std::filesystem::create_directories(std::filesystem::path(thumbFile).parent_path(), ec);
        bool ok = m_platform->downloadFile(thumbUrl, thumbFile, nullptr, m_cancelCollectionThumb, err);
        m_collectionThumbLoading = false;
        if (ok && !m_cancelCollectionThumb.load() && m_isCollectionBrowserOpen && m_collectionCurrentThumbVariantId == key) {
            std::lock_guard<std::mutex> lock(m_collectionThumbMutex);
            m_pendingCollectionThumbToLoad = thumbFile;
        }
    });
#endif
}

void App::renderCollectionBrowser() {
#ifdef HAS_SDL2
    // Dim background overlay
    drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x02, 0x05, 0x0C, 0xFA});

    // 4IFIR Frosted Glass Modal Container
    int bw = 1220;
    int bh = 660;
    int bx = (Theme::SCREEN_WIDTH - bw) / 2;
    int by = (Theme::SCREEN_HEIGHT - bh) / 2;

    drawGlassCard(bx, by, bw, bh, false, true);
    drawNeonGradientOutline(bx, by, bw, bh, 2);

    // Header
    bool isAD = Config::isAfterDark();
    if (isAD) {
        drawRect(bx + 25, by + 18, 175, 26, {0xEC, 0x48, 0x99, 0x33});
        drawRectOutline(bx + 25, by + 18, 175, 26, Theme::COLOR_FOCUS_PINK, 1);
        drawText("🌸 AFTER DARK 18+", bx + 35, by + 24, Theme::COLOR_FOCUS_PINK, 12);
    } else {
        drawRect(bx + 25, by + 18, 160, 26, {0x00, 0xF0, 0xFF, 0x33});
        drawRectOutline(bx + 25, by + 18, 160, 26, Theme::COLOR_FOCUS_CYAN, 1);
        drawText("★ КОЛЛЕКЦИЯ 4IFIR", bx + 35, by + 24, Theme::COLOR_FOCUS_CYAN, 12);
    }

    drawText(m_collectionGameName, bx + 215, by + 17, Theme::COLOR_TEXT_PRIMARY, 21, 750);

    int totalV = static_cast<int>(m_collectionVariants.size());
    std::string countStr = std::to_string(m_collectionSelectedIndex + 1) + " / " + std::to_string(totalV);
    drawText(countStr, bx + bw - 140, by + 20, Theme::COLOR_FOCUS_CYAN, 16);

    // Divider line
    drawRect(bx + 25, by + 54, bw - 50, 1, Theme::COLOR_BORDER);

    // Left Column: Variants List (Width 640)
    int lx = bx + 25;
    int ly = by + 68;
    int lw = 635;
    int visibleCount = 5;

    if (m_collectionSelectedIndex < m_collectionScrollOffset) {
        m_collectionScrollOffset = m_collectionSelectedIndex;
    }
    if (m_collectionSelectedIndex >= m_collectionScrollOffset + visibleCount) {
        m_collectionScrollOffset = m_collectionSelectedIndex - visibleCount + 1;
    }

    if (m_collectionScrollOffset > 0) {
        drawText("▲ Еще фоны выше (◀ -5)", lx + 200, ly - 14, Theme::COLOR_FOCUS_CYAN, 12);
    }

    int cardY = ly;
    int cardH = 88;
    int cardGap = 8;
    int endIdx = std::min(totalV, m_collectionScrollOffset + visibleCount);

    for (int i = m_collectionScrollOffset; i < endIdx; ++i) {
        bool isSelected = (i == m_collectionSelectedIndex);
        const auto& v = m_collectionVariants[i];

        if (isSelected) {
            drawRect(lx, cardY, lw, cardH, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(lx, cardY, lw, cardH, 2);
        } else {
            drawRect(lx, cardY, lw, cardH, {0x13, 0x1A, 0x2A, 0x99});
            drawRectOutline(lx, cardY, lw, cardH, Theme::COLOR_BORDER, 1);
        }

        // Title line
        std::string titleStr = std::to_string(i + 1) + ". " + v.name;
        drawText(titleStr, lx + 16, cardY + 14, isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, lw - 70);

        // Metadata badges
        int bxPos = lx + 16;

        // Style badge
        std::string styleStr = styleToString(v.style);
        drawRect(bxPos, cardY + 46, 110, 24, {0x28, 0x33, 0x47, 0x66});
        drawRectOutline(bxPos, cardY + 46, 110, 24, Theme::COLOR_BORDER, 1);
        drawText(styleStr, bxPos + 10, cardY + 51, Theme::COLOR_TEXT_MUTED, 11);
        bxPos += 120;

        // Audio badge
        if (v.hasAudio) {
            drawRect(bxPos, cardY + 46, 65, 24, {0x10, 0xB9, 0x81, 0x33});
            drawRectOutline(bxPos, cardY + 46, 65, 24, Theme::COLOR_SUCCESS, 1);
            drawText("ЗВУК", bxPos + 14, cardY + 51, Theme::COLOR_SUCCESS, 11);
            bxPos += 75;
        } else {
            drawRect(bxPos, cardY + 46, 85, 24, {0x28, 0x33, 0x47, 0x44});
            drawRectOutline(bxPos, cardY + 46, 85, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ЗВУКА", bxPos + 10, cardY + 51, Theme::COLOR_TEXT_MUTED, 10);
            bxPos += 95;
        }

        // Specs text
        double mb = static_cast<double>(v.sizeBytes) / (1024.0 * 1024.0);
        char szBuf[32];
        if (mb >= 0.1) snprintf(szBuf, sizeof(szBuf), "%.1f MB", mb);
        else snprintf(szBuf, sizeof(szBuf), "~3.5 MB");

        std::string metaLine = std::to_string(v.width) + "x" + std::to_string(v.height) + " @" +
                               std::to_string((int)v.fps) + "fps  |  " + std::string(szBuf) +
                               (!v.codec.empty() ? ("  |  " + v.codec) : "");
        drawText(metaLine, bxPos, cardY + 51, Theme::COLOR_TEXT_MUTED, 12, lw - bxPos - 30);

        if (isSelected) {
            drawText("▶", lx + lw - 30, cardY + 33, Theme::COLOR_FOCUS_CYAN, 18);
        }

        cardY += cardH + cardGap;
    }

    if (endIdx < totalV) {
        std::string belowStr = "▼ Еще варианты ниже: " + std::to_string(totalV - endIdx) + " шт. (▶ +5)";
        drawText(belowStr, lx + 180, ly + (cardH + cardGap) * visibleCount + 2, Theme::COLOR_FOCUS_PINK, 12);
    }

    // Right Column: Static Mini-Preview Panel (Width 520)
    int rx = bx + 675;
    int ry = by + 68;
    int rw = 520;
    int rh = 530;

    drawGlassCard(rx, ry, rw, rh, false, false);

    // Static Preview Box (Exact 16:9 ratio: 480 x 270)
    int px = rx + 20;
    int py = ry + 20;
    int pw = 480;
    int ph = 270;

    drawRect(px, py, pw, ph, {0x08, 0x0D, 0x16, 0xFA});
    drawNeonGradientOutline(px, py, pw, ph, 2);

    if (m_collectionThumbTexture) {
        SDL_Rect dst{px + 2, py + 2, pw - 4, ph - 4};
        SDL_RenderCopy(m_renderer, m_collectionThumbTexture, nullptr, &dst);
    } else if (m_collectionThumbLoading) {
        drawText("⏳ Загрузка мини-превью...", px + 140, py + 125, Theme::COLOR_FOCUS_CYAN, 16);
    } else {
        drawText("📷 Статическое превью...", px + 145, py + 125, Theme::COLOR_TEXT_MUTED, 15);
    }

    // Details below preview
    if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
        m_collectionSelectedIndex < totalV) {
        const auto& selVar = m_collectionVariants[m_collectionSelectedIndex];

        drawText(selVar.name, px, py + ph + 18, Theme::COLOR_TEXT_PRIMARY, 17, pw);

        double mb = static_cast<double>(selVar.sizeBytes) / (1024.0 * 1024.0);
        char szBuf[32];
        if (mb >= 0.1) snprintf(szBuf, sizeof(szBuf), "%.1f MB", mb);
        else snprintf(szBuf, sizeof(szBuf), "~3.5 MB");

        std::string detailStr = styleToString(selVar.style) + "  •  " +
                                std::to_string(selVar.width) + "x" + std::to_string(selVar.height) +
                                " @" + std::to_string((int)selVar.fps) + "fps  •  " +
                                std::string(szBuf) + (!selVar.codec.empty() ? ("  •  " + selVar.codec) : "") +
                                (selVar.hasAudio ? "  •  Звук" : "  •  Без звука");
        drawText(detailStr, px, py + ph + 46, Theme::COLOR_TEXT_MUTED, 12, pw);

        // Buttons
        // [A] Assign to game button
        int b1w = 230;
        int b1h = 42;
        int b1x = px;
        int b1y = py + ph + 80;
        drawRect(b1x, b1y, b1w, b1h, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(b1x, b1y, b1w, b1h, 2);
        drawText("[A] Назначить на игру", b1x + 22, b1y + 12, Theme::COLOR_FOCUS_CYAN, 13);

        // [X] Fullscreen live video button
        int b2w = 230;
        int b2h = 42;
        int b2x = px + 250;
        int b2y = b1y;
        drawRect(b2x, b2y, b2w, b2h, {0x16, 0x20, 0x32, 0xDD});
        drawRectOutline(b2x, b2y, b2w, b2h, Theme::COLOR_BORDER, 1);
        drawText("[X] На весь экран (видео)", b2x + 18, b2y + 12, Theme::COLOR_FOCUS_CYAN, 13);

        drawText("Совет: Нажмите [A], чтобы выбрать игру на Switch для этого фона", px, b1y + 54, Theme::COLOR_TEXT_MUTED, 12, pw);
    }

    // Bottom Navigation Bar
    int footY = by + bh - 42;
    drawRect(bx + 25, footY, bw - 50, 32, {0x0D, 0x13, 0x1F, 0xDD});
    drawRectOutline(bx + 25, footY, bw - 50, 32, Theme::COLOR_BORDER, 1);
    drawText("[▲/▼] Список   |   [◀/▶] Страница (±5)   |   [A] Назначить на игру Switch   |   [X] Видео   |   [B] Назад",
             bx + 60, footY + 8, Theme::COLOR_TEXT_MUTED, 12);
#endif
}


// ----------------- Catalog Filtering, Sorting & Horizon OS Keyboard -----------------

void App::rebuildCatalogFilter() {
    const auto& allGames = m_catalogManager.getAllGames();
    m_filteredCatalogGames.clear();

    std::string qLower = m_catalogSearchQuery;
    std::transform(qLower.begin(), qLower.end(), qLower.begin(), [](unsigned char c) {
        return std::tolower(c);
    });

    for (const auto& g : allGames) {
        // 1. Search Query filter
        if (!qLower.empty()) {
            std::string titleLower = g.title;
            std::transform(titleLower.begin(), titleLower.end(), titleLower.begin(), [](unsigned char c) {
                return std::tolower(c);
            });
            std::string tidLower = g.titleId;
            std::transform(tidLower.begin(), tidLower.end(), tidLower.begin(), [](unsigned char c) {
                return std::tolower(c);
            });

            bool match = (titleLower.find(qLower) != std::string::npos) ||
                         (tidLower.find(qLower) != std::string::npos);
            if (!match) {
                for (const auto& v : g.variants) {
                    std::string vname = v.name;
                    std::transform(vname.begin(), vname.end(), vname.begin(), [](unsigned char c) {
                        return std::tolower(c);
                    });
                    if (vname.find(qLower) != std::string::npos) {
                        match = true;
                        break;
                    }
                }
            }
            if (!match) continue;
        }

        // 2. Installed Only filter
        if (m_catalogSortMode == CatalogSortMode::InstalledOnly) {
            bool isInst = false;
            for (const auto& ig : m_installedGames) {
                if (ig.titleId == g.titleId) {
                    isInst = true;
                    break;
                }
            }
            if (!isInst) continue;
        }

        // 3. Audio Only filter
        if (m_catalogSortMode == CatalogSortMode::AudioOnly) {
            bool hasAud = false;
            for (const auto& v : g.variants) {
                if (v.hasAudio) {
                    hasAud = true;
                    break;
                }
            }
            if (!hasAud) continue;
        }

        m_filteredCatalogGames.push_back(g);
    }

    // 4. Sorting
    if (m_catalogSortMode == CatalogSortMode::Alphabetical) {
        std::sort(m_filteredCatalogGames.begin(), m_filteredCatalogGames.end(), [](const GameCatalogEntry& a, const GameCatalogEntry& b) {
            return a.title < b.title;
        });
    } else if (m_catalogSortMode == CatalogSortMode::VariantsCount) {
        std::sort(m_filteredCatalogGames.begin(), m_filteredCatalogGames.end(), [](const GameCatalogEntry& a, const GameCatalogEntry& b) {
            return a.variants.size() > b.variants.size();
        });
    }

    // Safe bounds clamp
    if (m_catalogSelectedIndex >= static_cast<int>(m_filteredCatalogGames.size())) {
        m_catalogSelectedIndex = std::max(0, static_cast<int>(m_filteredCatalogGames.size()) - 1);
    }
    m_catalogScrollOffset = 0;
}

void App::cycleCatalogSortMode() {
    int nextMode = (static_cast<int>(m_catalogSortMode) + 1) % 5;
    m_catalogSortMode = static_cast<CatalogSortMode>(nextMode);
    rebuildCatalogFilter();

    std::string modeDesc;
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: modeDesc = "Сортировка: По умолчанию"; break;
        case CatalogSortMode::Alphabetical: modeDesc = "Сортировка: По алфавиту (А-Я)"; break;
        case CatalogSortMode::VariantsCount: modeDesc = "Сортировка: По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: modeDesc = "Фильтр: Только со звуком [ЗВУК]"; break;
        case CatalogSortMode::InstalledOnly: modeDesc = "Фильтр: Только установленные игры"; break;
    }
    m_statusNotification = modeDesc;
    m_notificationFramesRemaining = 120;
}

void App::openCatalogKeyboard() {
#ifdef __SWITCH__
    SwkbdConfig kbd;
    char textBuf[256] = {0};
    if (!m_catalogSearchQuery.empty()) {
        strncpy(textBuf, m_catalogSearchQuery.c_str(), sizeof(textBuf) - 1);
    }

    Result rc = swkbdCreate(&kbd, 0);
    if (R_SUCCEEDED(rc)) {
        swkbdConfigMakePresetDefault(&kbd);
        swkbdConfigSetHeaderText(&kbd, "Поиск по каталогу H3H Backgrounds");
        swkbdConfigSetGuideText(&kbd, "Введите название игры, Title ID или персонажа (напр. Mario, Zelda, NFS)");
        swkbdConfigSetOkButtonText(&kbd, "Найти");
        swkbdConfigSetInitialText(&kbd, textBuf);
        swkbdConfigSetStringLenMax(&kbd, 64);

        rc = swkbdShow(&kbd, textBuf, sizeof(textBuf));
        if (R_SUCCEEDED(rc)) {
            m_catalogSearchQuery = std::string(textBuf);
            // Trim whitespace
            while (!m_catalogSearchQuery.empty() && std::isspace(static_cast<unsigned char>(m_catalogSearchQuery.back()))) {
                m_catalogSearchQuery.pop_back();
            }
            while (!m_catalogSearchQuery.empty() && std::isspace(static_cast<unsigned char>(m_catalogSearchQuery.front()))) {
                m_catalogSearchQuery.erase(m_catalogSearchQuery.begin());
            }
            rebuildCatalogFilter();
            m_statusNotification = m_catalogSearchQuery.empty()
                ? "Поиск сброшен (показаны все игры)"
                : ("Результаты поиска для: \"" + m_catalogSearchQuery + "\" (" + std::to_string(m_filteredCatalogGames.size()) + " игр)");
            m_notificationFramesRemaining = 150;
        }
        swkbdClose(&kbd);
    }
#else
    // Desktop simulator
    if (m_catalogSearchQuery.empty()) {
        m_catalogSearchQuery = "Mario";
    } else {
        m_catalogSearchQuery.clear();
    }
    rebuildCatalogFilter();
    m_statusNotification = "Desktop test: " + m_catalogSearchQuery;
    m_notificationFramesRemaining = 120;
#endif
}

} // namespace ui
} // namespace h3h
