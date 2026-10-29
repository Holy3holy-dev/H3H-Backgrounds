
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

// UTF-8 lowercase conversion for English and Russian Cyrillic
static std::string utf8ToLower(const std::string& s) {
    std::string result;
    result.reserve(s.size());
    for (size_t i = 0; i < s.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        if (c < 0x80) {
            result.push_back(static_cast<char>(std::tolower(c)));
        } else if (c == 0xD0 && i + 1 < s.size()) {
            unsigned char c2 = static_cast<unsigned char>(s[i + 1]);
            if (c2 == 0x81) { // Ё -> ё (0xD1 0x91)
                result.push_back(static_cast<char>(0xD1));
                result.push_back(static_cast<char>(0x91));
                i++;
            } else if (c2 >= 0x90 && c2 <= 0x9F) { // А..П -> а..п (0xD0 0xB0..0xBF)
                result.push_back(static_cast<char>(0xD0));
                result.push_back(static_cast<char>(c2 + 0x20));
                i++;
            } else if (c2 >= 0xA0 && c2 <= 0xAF) { // Р..Я -> р..я (0xD1 0x80..0x8F)
                result.push_back(static_cast<char>(0xD1));
                result.push_back(static_cast<char>(c2 - 0x20));
                i++;
            } else {
                result.push_back(s[i]);
            }
        } else {
            result.push_back(s[i]);
        }
    }
    return result;
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

    m_videoIconsCatalog.clear();
    for (const auto& game : m_catalogManager.getAllGames()) {
        bool hasIcon = false;
        for (const auto& v : game.variants) {
            if (v.hasIcon && !v.iconUrl.empty()) {
                hasIcon = true;
                break;
            }
        }
        if (hasIcon) {
            m_videoIconsCatalog.push_back(game);
        }
    }
    rebuildVideoIconsFilter();

#ifdef HAS_SDL2
    SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");
    SDL_SetHint(SDL_HINT_MOUSE_TOUCH_EVENTS, "0");

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

    SDL_RenderSetLogicalSize(m_renderer, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT);

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

    loadFavorites();
    refreshStorageStats();

    std::cout << "[+] " << Config::APP_NAME << " App initialized successfully." << std::endl;
    return true;
}

void App::shutdown() {
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
    }
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
        // Check for 4IFIR video icon on SD card (sdmc:/recordings/icons/<TitleID>.mp4)
        std::string iconPath;
        uint64_t iconSize = 0;
        if (Installer::findExistingIcon(m_platform->getIconsDirectory(), game.titleId, iconPath, iconSize)) {
            game.hasInstalledIcon = true;
            game.installedIconPath = iconPath;
            game.installedIconSizeBytes = iconSize;
        }
        if (game.hasInstalledCover) {
            std::string regVarId = InstalledRegistry::instance().getVariantId(game.titleId);
            if (!regVarId.empty()) {
                // Trust registry entry explicitly
                game.installedVariantId = regVarId;
                if (regVarId.rfind("local:", 0) == 0) {
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
                }
            } else if (!game.catalogEntry.variants.empty()) {
                // If not found in registry (e.g. initial scan of manually dropped files):
                // Only associate automatically if exactly 1 variant exists
                if (game.catalogEntry.variants.size() == 1) {
                    game.installedVariantId = game.catalogEntry.variants[0].id;
                    InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), game.titleId, game.installedVariantId);
                } else {
                    // Check if file size matches uniquely within 4 KB margin
                    int64_t bestDiff = INT64_MAX;
                    std::string bestId;
                    int matchCount = 0;
                    for (const auto& v : game.catalogEntry.variants) {
                        if (v.sizeBytes > 0 && game.installedCoverSizeBytes > 0) {
                            int64_t diff = std::abs((int64_t)v.sizeBytes - (int64_t)game.installedCoverSizeBytes);
                            if (diff < 4096) {
                                matchCount++;
                                if (diff < bestDiff) {
                                    bestDiff = diff;
                                    bestId = v.id;
                                }
                            }
                        }
                    }
                    if (matchCount == 1 && !bestId.empty()) {
                        game.installedVariantId = bestId;
                        InstalledRegistry::instance().setVariantId(m_platform->getAppDirectory(), game.titleId, game.installedVariantId);
                    }
                }
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

                m_videoIconsCatalog.clear();
                for (const auto& game : m_catalogManager.getAllGames()) {
                    bool hasIcon = false;
                    for (const auto& v : game.variants) {
                        if (v.hasIcon && !v.iconUrl.empty()) {
                            hasIcon = true;
                            break;
                        }
                    }
                    if (hasIcon) {
                        m_videoIconsCatalog.push_back(game);
                    }
                }
                rebuildVideoIconsFilter();
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
        // Immediately sync completed tasks into in-memory m_installedGames for instant UI responsiveness
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            for (const auto& task : m_downloadQueue) {
                if (task.state == TaskState::Completed) {
                    for (auto& game : m_installedGames) {
                        if (Config::normalizeTitleId(game.titleId) == Config::normalizeTitleId(task.titleId)) {
                            game.hasInstalledCover = true;
                            game.installedVariantId = task.variant.id;
                            game.installedCoverPath = task.targetFilePath;
                            game.installedCoverSizeBytes = task.variant.sizeBytes;
                            game.status = CoverStatus::Installed;
                        }
                    }
                }
            }
        }
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

    // Standalone Video Icon Task Handler
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

    // If variant includes a 4IFIR video icon (and coverOnly is false), download and install it as well
    if (res.success && !currentTask.coverOnly && currentTask.variant.hasIcon && !currentTask.variant.iconUrl.empty()) {
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
    }

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

void App::queueDownloadIconOnly(const InstalledTitle& title, const Variant& variant) {
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
        } else if (event.type == SDL_CONTROLLERDEVICEREMOVED) {
            SDL_GameController* pad = SDL_GameControllerFromInstanceID(event.cdevice.which);
            if (pad) {
                SDL_GameControllerClose(pad);
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
                    onButtonPress(15 /* BUTTON_ZL */);
                    m_lastTriggerTime = now;
                }
            } else if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
                uint32_t now = SDL_GetTicks();
                if (event.caxis.value > 16000 && (now - m_lastTriggerTime > 250)) {
                    onButtonPress(16 /* BUTTON_ZR */);
                    m_lastTriggerTime = now;
                }
            }
        } else if (event.type == SDL_MOUSEWHEEL) {
            if (event.wheel.y > 0) {
                onButtonPress(11 /* DPAD_UP */);
            } else if (event.wheel.y < 0) {
                onButtonPress(12 /* DPAD_DOWN */);
            }
        } else if (event.type == SDL_FINGERDOWN) {
            if (!m_touchDown) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                m_touchDown = true;
                m_activeFingerId = event.tfinger.fingerId;
                m_touchStartX = mx;
                m_touchStartY = my;
                m_touchLastX = mx;
                m_touchLastY = my;
                m_touchStartTime = SDL_GetTicks();
                m_isTouchDragging = false;
                m_touchDragAccumulator = 0;
            }
        } else if (event.type == SDL_FINGERMOTION) {
            if (m_touchDown && event.tfinger.fingerId == m_activeFingerId) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                int diffX = mx - m_touchStartX;
                int diffY = my - m_touchStartY;
                if (!m_isTouchDragging && (std::abs(diffX) > 15 || std::abs(diffY) > 15)) {
                    m_isTouchDragging = true;
                }

                if (m_isTouchDragging) {
                    int dy = my - m_touchLastY;
                    handleTouchDrag(m_touchStartX, m_touchStartY, dy);
                }
                m_touchLastX = mx;
                m_touchLastY = my;
            }
        } else if (event.type == SDL_FINGERUP) {
            if (m_touchDown && event.tfinger.fingerId == m_activeFingerId) {
                int mx = static_cast<int>(std::round(event.tfinger.x * static_cast<float>(Theme::SCREEN_WIDTH)));
                int my = static_cast<int>(std::round(event.tfinger.y * static_cast<float>(Theme::SCREEN_HEIGHT)));
                mx = std::max(0, std::min(mx, Theme::SCREEN_WIDTH - 1));
                my = std::max(0, std::min(my, Theme::SCREEN_HEIGHT - 1));

                if (!m_isTouchDragging) {
                    handleTouchTap(m_touchStartX, m_touchStartY);
                } else {
                    handleTouchSwipe(m_touchStartX, m_touchStartY, mx, my);
                }
                m_touchDown = false;
                m_isTouchDragging = false;
                m_touchDragAccumulator = 0;
            }
        } else if (event.type == SDL_MOUSEBUTTONDOWN) {
            if (event.button.which != SDL_TOUCH_MOUSEID) {
                handleTouchTap(event.button.x, event.button.y);
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
        if (button == 15 /* ZL - Fast Page Up 15 */) {
            m_collectionSelectedIndex = std::max(0, m_collectionSelectedIndex - 15);
            if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                m_collectionScrollOffset = m_collectionSelectedIndex;
            }
            if (!m_collectionVariants.empty()) {
                loadCollectionThumbnail(m_collectionVariants[m_collectionSelectedIndex]);
            }
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 15 */) {
            m_collectionSelectedIndex = std::min(vCount - 1, m_collectionSelectedIndex + 15);
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
        if (button == 8 /* R3 */ || button == 9 /* L - Toggle Favorite */) {
            if (!m_collectionVariants.empty() && m_collectionSelectedIndex >= 0 &&
                m_collectionSelectedIndex < vCount) {
                toggleFavoriteVariant(m_collectionTitleId, m_collectionVariants[m_collectionSelectedIndex]);
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
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_gamePickerSelectedIndex = std::max(0, m_gamePickerSelectedIndex - 5);
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            if (!m_installedGames.empty()) {
                m_gamePickerSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_gamePickerSelectedIndex + 5);
            }
            return;
        }
        if (button == 15 /* ZL - Fast Page Up 10 */) {
            m_gamePickerSelectedIndex = std::max(0, m_gamePickerSelectedIndex - 10);
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 10 */) {
            if (!m_installedGames.empty()) {
                m_gamePickerSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_gamePickerSelectedIndex + 10);
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
        if (button == 13 /* LEFT - Page Up 5 */) {
            m_recordingsSelectedIndex = std::max(0, m_recordingsSelectedIndex - 5);
            return;
        }
        if (button == 14 /* RIGHT - Page Down 5 */) {
            if (!m_localRecordings.empty()) {
                m_recordingsSelectedIndex = std::min(static_cast<int>(m_localRecordings.size()) - 1, m_recordingsSelectedIndex + 5);
            }
            return;
        }
        if (button == 15 /* ZL - Fast Page Up 10 */) {
            m_recordingsSelectedIndex = std::max(0, m_recordingsSelectedIndex - 10);
            return;
        }
        if (button == 16 /* ZR - Fast Page Down 10 */) {
            if (!m_localRecordings.empty()) {
                m_recordingsSelectedIndex = std::min(static_cast<int>(m_localRecordings.size()) - 1, m_recordingsSelectedIndex + 10);
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
        if (button == 8 /* R3 */ || button == 9 /* L - Toggle Favorite */) {
            if (!m_previewVariants.empty() && m_previewVariantIndex >= 0 &&
                m_previewVariantIndex < static_cast<int>(m_previewVariants.size())) {
                toggleFavoriteVariant(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
            }
            return;
        }
        if (button == 1 /* B */ || button == 2 /* X */) {
            closeFullscreenPreview();
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
                Variant var = m_previewVariants[m_previewVariantIndex];
                std::string gName = m_previewGameName;
                closeFullscreenPreview();
                openGamePicker(var, gName);
                return;
            } else if (button == 0 /* A - Install / Save */) {
                if (m_previewTitleId == "0000000000000000") {
                    Variant var = m_previewVariants[m_previewVariantIndex];
                    std::string gName = m_previewGameName;
                    closeFullscreenPreview();
                    openGamePicker(var, gName);
                    return;
                }
                Variant chosenVar = m_previewVariants[m_previewVariantIndex];
                std::string titleId = m_previewTitleId;
                std::string gName = m_previewGameName;
                bool isInstalled = m_previewIsGameInstalled;
                closeFullscreenPreview();
                m_pendingActionTitleId = titleId;
                m_pendingActionVariant = chosenVar;
                if (m_pendingActionVariant.id.rfind("local:", 0) == 0) {
                    m_pendingRecordingToInstallPath = m_pendingActionVariant.url;
                    m_pendingRecordingToInstallName = m_pendingActionVariant.name;
                    m_activeDialog = DialogType::ConfirmInstallLocalRecording;
                    m_dialogOpenedAt = SDL_GetTicks();
                    m_dialogTitle = (m_language == Language::Russian) ? "Установка записи" : "Install Recording";
                    m_dialogMessage = (m_language == Language::Russian)
                        ? ("Установить запись '" + m_pendingRecordingToInstallName + "' в качестве видеофона для игры " + gName + "?")
                        : ("Install recording '" + m_pendingRecordingToInstallName + "' as video theme for " + gName + "?");
                    m_dialogFocus = 0;
                    return;
                }
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

        bool isInstallWithIcon = (m_activeDialog == DialogType::ConfirmInstall && m_pendingActionVariant.hasIcon);
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
        if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::GameGrid) {
            m_catalogViewMode = CatalogViewMode::Categories;
            return;
        }
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
            if (m_activeTab == Tab::Home) {
                m_homeFocusedTile = (m_homeFocusedTile == 0) ? 4 : m_homeFocusedTile - 1;
            } else {
                int tabInt = static_cast<int>(m_activeTab);
                tabInt = (tabInt <= 1) ? 5 : tabInt - 1;
                m_activeTab = static_cast<Tab>(tabInt);
                if (m_activeTab == Tab::VideoIcons) rebuildVideoIconsFilter();
            }
            m_lastTabSwitchTime = now;
        }
        return;
    }
    if (button == 10 /* RIGHTSHOULDER */) {
        uint32_t now = SDL_GetTicks();
        if (now - m_lastTabSwitchTime > 150) {
            if (m_activeTab == Tab::Home) {
                m_homeFocusedTile = (m_homeFocusedTile == 4) ? 0 : m_homeFocusedTile + 1;
            } else {
                int tabInt = static_cast<int>(m_activeTab);
                tabInt = (tabInt >= 5) ? 1 : tabInt + 1;
                m_activeTab = static_cast<Tab>(tabInt);
                if (m_activeTab == Tab::VideoIcons) rebuildVideoIconsFilter();
            }
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
        if (button == 13 /* DPAD_LEFT */) {
            m_homeFocusedTile = (m_homeFocusedTile == 0) ? 4 : m_homeFocusedTile - 1;
            return;
        }
        if (button == 14 /* DPAD_RIGHT */) {
            m_homeFocusedTile = (m_homeFocusedTile == 4) ? 0 : m_homeFocusedTile + 1;
            return;
        }
        if (button == 0 /* A - Activate selected tile */) {
            switch (m_homeFocusedTile) {
                case 0:
                    m_activeTab = Tab::Catalog;
                    m_catalogViewMode = CatalogViewMode::Categories;
                    break;
                case 1:
                    m_activeTab = Tab::VideoIcons;
                    rebuildVideoIconsFilter();
                    break;
                case 2:
                    m_activeTab = Tab::MyGames;
                    break;
                case 3:
                    m_activeTab = Tab::Downloads;
                    break;
                case 4:
                    m_activeTab = Tab::Settings;
                    break;
            }
            return;
        }
        if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
            return;
        }
        if (button == 2 /* X - Refresh */) {
            fetchRemoteCatalog();
            return;
        }
        if (button == 6 /* START (+) - Integrity Check */) {
            runIntegrityCheck();
            return;
        }
        return;
    } else if (m_activeTab == Tab::VideoIcons) {
        int total = static_cast<int>(m_filteredVideoIcons.size());
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        }
        if (button == 11 /* DPAD_UP */) {
            if (m_videoIconsSelectedIndex > 0) {
                m_videoIconsSelectedIndex--;
                if (m_videoIconsSelectedIndex < m_videoIconsScrollOffset) {
                    m_videoIconsScrollOffset = m_videoIconsSelectedIndex;
                }
            }
            return;
        }
        if (button == 12 /* DPAD_DOWN */) {
            if (m_videoIconsSelectedIndex + 1 < total) {
                m_videoIconsSelectedIndex++;
                if (m_videoIconsSelectedIndex >= m_videoIconsScrollOffset + 5) {
                    m_videoIconsScrollOffset = m_videoIconsSelectedIndex - 4;
                }
            }
            return;
        }
        if (button == 15 /* ZL - Page Up 5 */) {
            m_videoIconsSelectedIndex = std::max(0, m_videoIconsSelectedIndex - 5);
            m_videoIconsScrollOffset = std::max(0, m_videoIconsScrollOffset - 5);
            return;
        }
        if (button == 16 /* ZR - Page Down 5 */) {
            if (total > 0) {
                m_videoIconsSelectedIndex = std::min(total - 1, m_videoIconsSelectedIndex + 5);
                m_videoIconsScrollOffset = std::min(std::max(0, total - 5), m_videoIconsScrollOffset + 5);
            }
            return;
        }
        if (button == 0 /* A - Install video icon */) {
            if (m_videoIconsSelectedIndex >= 0 && m_videoIconsSelectedIndex < total) {
                const auto& entry = m_filteredVideoIcons[m_videoIconsSelectedIndex];
                InstalledTitle targetGame;
                targetGame.titleId = entry.titleId;
                targetGame.name = entry.title;
                targetGame.hasCatalogMatch = true;
                targetGame.catalogEntry = entry;

                for (const auto& v : entry.variants) {
                    if (v.hasIcon && !v.iconUrl.empty()) {
                        queueDownloadIconOnly(targetGame, v);
                        m_statusNotification = (m_language == Language::Russian)
                            ? ("Добавлена в загрузки: " + entry.title)
                            : ("Queued download: " + entry.title);
                        m_notificationFramesRemaining = 120;
                        break;
                    }
                }
            }
            return;
        }
        if (button == 2 /* X - Video preview */) {
            if (m_videoIconsSelectedIndex >= 0 && m_videoIconsSelectedIndex < total) {
                openFullscreenVideoIconPreview(m_filteredVideoIcons[m_videoIconsSelectedIndex], 0);
            }
            return;
        }
        if (button == 3 /* Y - Search keyboard */) {
            openVideoIconsKeyboard();
            return;
        }
        if (button == 4 /* MINUS (-) - Filter toggle */) {
            m_videoIconsFilterMode = (m_videoIconsFilterMode + 1) % 3;
            rebuildVideoIconsFilter();
            return;
        }
        return;
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
            if (button == 1 /* B - Back to Home */) {
                m_activeTab = Tab::Home;
                return;
            }
            if (button == 8 /* R3 - Toggle Batch Selection */) {
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    toggleBatchSelection(m_installedGames[m_myGamesSelectedIndex].titleId);
                }
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
            } else if (button == 15 /* ZL - Fast Page Up 10 */) {
                m_myGamesSelectedIndex = std::max(0, m_myGamesSelectedIndex - 10);
                m_selectedVariantIndex = 0;
                m_variantScrollOffset = 0;
                return;
            } else if (button == 16 /* ZR - Fast Page Down 10 */) {
                if (!m_installedGames.empty()) {
                    m_myGamesSelectedIndex = std::min(static_cast<int>(m_installedGames.size()) - 1, m_myGamesSelectedIndex + 10);
                    m_selectedVariantIndex = 0;
                    m_variantScrollOffset = 0;
                }
                return;
            } else if (button == 14 /* DPAD_RIGHT */ || button == 0 /* A */) {
                // Move focus to right variants column or open collection browser
                if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                    const auto& g = m_installedGames[m_myGamesSelectedIndex];
                    if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                        openCollectionBrowser(g.catalogEntry);
                    } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                        m_myGamesActivePane = MyGamesPane::VariantsList;
                        m_selectedVariantIndex = 0;
                    } else {
                        m_statusNotification = (m_language == Language::Russian)
                            ? "Для этой игры пока нет видеофонов в каталоге"
                            : "No video themes available for this game yet";
                        m_notificationFramesRemaining = 120;
                    }
                }
            } else if (button == 2 /* X - Fullscreen Preview or Open Catalog */) {
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
        if (m_catalogViewMode == CatalogViewMode::Categories) {
            if (button == 1 /* B - Back to Home */) {
                m_activeTab = Tab::Home;
                return;
            }
            // Category navigation (18 total: 0..3 main, 4..17 genres)
            if (button == 13 /* DPAD_LEFT */) {
                if (m_categorySelectedIndex > 0) m_categorySelectedIndex--;
                return;
            }
            if (button == 14 /* DPAD_RIGHT */) {
                if (m_categorySelectedIndex < 17) m_categorySelectedIndex++;
                return;
            }
            if (button == 11 /* DPAD_UP */) {
                if (m_categorySelectedIndex >= 4) m_categorySelectedIndex -= 4;
                return;
            }
            if (button == 12 /* DPAD_DOWN */) {
                if (m_categorySelectedIndex + 4 <= 17) m_categorySelectedIndex += 4;
                return;
            }
            if (button == 0 /* A - Open category */) {
                struct GenreDef {
                    std::string title;
                };
                GenreDef genres[14] = {
                    {"Экшены и приключения"},
                    {"Аркады"},
                    {"Хорроры"},
                    {"Метроидвании"},
                    {"Вечеринки и кооп"},
                    {"Платформеры"},
                    {"Головоломки"},
                    {"Рогалики"},
                    {"RPG / JRPG"},
                    {"Шутеры"},
                    {"Симуляторы и уютные"},
                    {"Стратегии и тактика"},
                    {"Визуальные новеллы"},
                    {"Порты и Homebrew"}
                };

                m_catalogSearchQuery.clear();
                if (m_categorySelectedIndex == 0) {
                    m_activeCategoryName = "Весь каталог";
                    m_catalogSortMode = CatalogSortMode::Default;
                } else if (m_categorySelectedIndex == 1) {
                    m_activeCategoryName = "Избранное";
                    m_catalogSortMode = CatalogSortMode::FavoritesOnly;
                } else if (m_categorySelectedIndex == 2) {
                    m_activeCategoryName = "Новые релизы";
                    m_catalogSortMode = CatalogSortMode::Default;
                } else if (m_categorySelectedIndex == 3) {
                    m_activeCategoryName = "Топ-100";
                    m_catalogSortMode = CatalogSortMode::VariantsCount;
                } else {
                    int gIdx = m_categorySelectedIndex - 4;
                    if (gIdx >= 0 && gIdx < 14) {
                        m_activeCategoryName = genres[gIdx].title;
                        m_catalogSortMode = CatalogSortMode::Default;
                    }
                }
                m_catalogViewMode = CatalogViewMode::GameGrid;
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                return;
            }
            if (button == 2 /* X - Switch to Full List View */) {
                m_activeCategoryName = "Весь каталог (Списком)";
                m_catalogSortMode = CatalogSortMode::Default;
                m_catalogViewMode = CatalogViewMode::GameGrid;
                m_catalogSelectedIndex = 0;
                m_catalogScrollOffset = 0;
                rebuildCatalogFilter();
                return;
            }
            if (button == 3 /* Y - Search keyboard */) {
                openCatalogKeyboard();
                if (!m_catalogSearchQuery.empty()) {
                    m_activeCategoryName = "Поиск: " + m_catalogSearchQuery;
                    m_catalogViewMode = CatalogViewMode::GameGrid;
                    m_catalogSelectedIndex = 0;
                    m_catalogScrollOffset = 0;
                    rebuildCatalogFilter();
                }
                return;
            }
            if (button == 4 /* MINUS - Refresh */) {
                fetchRemoteCatalog();
                return;
            }
            return;
        }

        int totalGames = static_cast<int>(m_filteredCatalogGames.size());
        if (button == 1 /* B - Back to Categories */) {
            m_catalogViewMode = CatalogViewMode::Categories;
            return;
        } else if (button == 7 /* L3 */ || button == 8 /* R3 - Toggle Batch Selection */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                toggleBatchSelection(m_filteredCatalogGames[m_catalogSelectedIndex].titleId);
            }
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_catalogSelectedIndex > 0) m_catalogSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_catalogSelectedIndex + 1 < totalGames) m_catalogSelectedIndex++;
        } else if (button == 13 /* DPAD_LEFT - Page Up 5 */) {
            m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 5);
        } else if (button == 14 /* DPAD_RIGHT - Page Down 5 */) {
            if (totalGames > 0) m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 5);
        } else if (button == 15 /* ZL - Batch Install or Fast Scroll Up 15 */) {
            if (!m_batchSelectedTitleIds.empty()) {
                installBatchSelected();
            } else {
                m_catalogSelectedIndex = std::max(0, m_catalogSelectedIndex - 15);
            }
            return;
        } else if (button == 16 /* ZR - Fast Scroll Down 15 */) {
            if (totalGames > 0) {
                m_catalogSelectedIndex = std::min(totalGames - 1, m_catalogSelectedIndex + 15);
            }
            return;
        } else if (button == 0 /* A - Enter Collection Browser */) {
            if (m_catalogSelectedIndex >= 0 && m_catalogSelectedIndex < totalGames) {
                const auto& entry = m_filteredCatalogGames[m_catalogSelectedIndex];
                openCollectionBrowser(entry);
            }
        } else if (button == 2 /* X - Cycle Sort Mode */) {
            cycleCatalogSortMode();
        } else if (button == 3 /* Y - Open Horizon Software Keyboard (Search) */) {
            openCatalogKeyboard();
        } else if (button == 4 /* MINUS - Clear Selection or Search or Refresh */) {
            if (!m_batchSelectedTitleIds.empty()) {
                clearBatchSelection();
            } else if (!m_catalogSearchQuery.empty()) {
                m_catalogSearchQuery.clear();
                rebuildCatalogFilter();
                m_statusNotification = (m_language == Language::Russian) ? "Поиск сброшен (показаны все игры)" : "Search cleared";
                m_notificationFramesRemaining = 90;
            } else {
                fetchRemoteCatalog();
            }
        }
    } else if (m_activeTab == Tab::Downloads) {
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
            return;
        } else if (button == 2 /* X - Clear finished/failed tasks */) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            m_downloadQueue.erase(
                std::remove_if(m_downloadQueue.begin(), m_downloadQueue.end(),
                    [](const DownloadTask& t) {
                        return t.state == TaskState::Completed || t.state == TaskState::Failed;
                    }),
                m_downloadQueue.end()
            );
            m_statusNotification = (m_language == Language::Russian) ? "Завершённые задачи очищены" : "Finished tasks cleared";
            m_notificationFramesRemaining = 90;
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_downloadsScrollOffset > 0) m_downloadsScrollOffset--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_downloadsScrollOffset + 5 < static_cast<int>(m_downloadQueue.size())) m_downloadsScrollOffset++;
        } else if (button == 15 /* ZL - Fast Page Up 5 */) {
            m_downloadsScrollOffset = std::max(0, m_downloadsScrollOffset - 5);
        } else if (button == 16 /* ZR - Fast Page Down 5 */) {
            int maxOff = std::max(0, static_cast<int>(m_downloadQueue.size()) - 5);
            m_downloadsScrollOffset = std::min(maxOff, m_downloadsScrollOffset + 5);
        } else if (button == 3 /* Y - Install all missing */) {
            installAllMissing();
        }
    } else if (m_activeTab == Tab::Settings) {
        if (button == 1 /* B - Back to Home */) {
            m_activeTab = Tab::Home;
            return;
        } else if (button == 11 /* DPAD_UP */) {
            if (m_settingsSelectedIndex > 0) m_settingsSelectedIndex--;
        } else if (button == 12 /* DPAD_DOWN */) {
            if (m_settingsSelectedIndex < 6) m_settingsSelectedIndex++;
        } else if (button == 0 /* A - Activate Selected Setting */) {
            switch (m_settingsSelectedIndex) {
                case 0: // Check & Update NRO
                    updateApplicationNro();
                    break;
                case 1: // Refresh Catalog
                    fetchRemoteCatalog();
                    break;
                case 2: // Clear thumbnail previews cache
                    clearThumbnailCache();
                    break;
                case 3: // Clear video player cache
                    clearVideoPreviewCache();
                    break;
                case 4: // Clear Local Catalog Cache (cache.json)
                    m_catalogManager.loadFromJsonString("{\"schemaVersion\":1,\"updatedAt\":\"\",\"games\":[]}", m_statusNotification);
                    refreshInstalledGames();
                    m_statusNotification = getStrings(m_language).cacheClearedMsg;
                    m_notificationFramesRemaining = 120;
                    break;
                case 5: // Integrity check
                    runIntegrityCheck();
                    break;
                case 6: // Toggle Language
                    m_language = (m_language == Language::Russian) ? Language::English : Language::Russian;
                    m_statusNotification = (m_language == Language::Russian) ? "Язык интерфейса: Русский" : "Interface language: English";
                    m_notificationFramesRemaining = 120;
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
        case Tab::Home:       renderTabHome(); break;
        case Tab::Catalog:    renderTabCatalog(); break;
        case Tab::VideoIcons: renderTabVideoIcons(); break;
        case Tab::MyGames:    renderTabMyGames(); break;
        case Tab::Downloads:  renderTabDownloads(); break;
        case Tab::Settings:   renderTabSettings(); break;
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

    // 4IFIR Cyber-Glass Top Bar (matching TorrentShopNX Header)
    drawRect(0, 0, Theme::SCREEN_WIDTH, 64, Theme::COLOR_BG_HEADER);
    drawRect(0, 63, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // Left Branding: App Name + Tag Badge
    // Triple accent bars (TorrentShopNX style logo)
    drawRect(30, 24, 5, 18, Theme::COLOR_FOCUS_CYAN);
    drawRect(38, 20, 5, 26, Theme::COLOR_FOCUS_CYAN);
    drawRect(46, 25, 5, 16, Theme::COLOR_FOCUS_CYAN);

    // App Title
    drawText(Config::APP_NAME, 62, 18, Theme::COLOR_TEXT_PRIMARY, 20);

    // Version Tag Pill
#ifdef H3H_AFTER_DARK
    std::string tagText = "18+ v" + std::string(Config::APP_VERSION);
#else
    std::string tagText = "NX v" + std::string(Config::APP_VERSION);
#endif
    drawRect(290, 20, 84, 24, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(290, 20, 84, 24, Theme::COLOR_FOCUS_CYAN, 1);
    drawText(tagText, 298, 24, Theme::COLOR_FOCUS_CYAN, 12);

    // Right Side Metadata
    size_t catGames = m_catalogManager.getGamesCount();
    size_t catIcons = m_videoIconsCatalog.size();
    std::string dateStr = m_catalogManager.getUpdatedAt();
    if (dateStr.size() >= 10) dateStr = dateStr.substr(0, 10);
    else dateStr = "28.10.2026";

    std::string metaLine1 = "Каталог: " + std::to_string(catGames) + " игр (" + std::to_string(catIcons) + " иконок) • Обновлен: " + dateStr;

    double freeSdGb = static_cast<double>(m_sysInfo.freeStorageBytes) / (1024.0 * 1024.0 * 1024.0);
    double totalSdGb = static_cast<double>(m_sysInfo.totalStorageBytes) / (1024.0 * 1024.0 * 1024.0);
    if (totalSdGb <= 0.1) {
        totalSdGb = 220.1;
        freeSdGb = 49.2;
    }
    char sdBuf[128];
    std::snprintf(sdBuf, sizeof(sdBuf), "SD: %.1f GB / %.1f GB • NAND: 5.3 GB / 9.4 GB", freeSdGb, totalSdGb);
    std::string metaLine2 = sdBuf;

    drawText(metaLine1, 780, 14, Theme::COLOR_TEXT_SECONDARY, 13);
    drawText(metaLine2, 830, 36, Theme::COLOR_TEXT_MUTED, 13);
}

void App::renderFooter() {
    const auto& s = getStrings(m_language);

    // Bottom Bar Background (matching TorrentShopNX Footer)
    drawRect(0, 665, Theme::SCREEN_WIDTH, 55, Theme::COLOR_STATUS_BAR_BG);
    drawRect(0, 665, Theme::SCREEN_WIDTH, 1, Theme::COLOR_BORDER);

    // Left: Battery glyph & %, Wi-Fi, Clock
    int battX = 30;
    drawRect(battX, 683, 30, 16, {0x1C, 0x24, 0x33, 0xFF});
    drawRectOutline(battX, 683, 30, 16, Theme::COLOR_TEXT_MUTED, 1);
    drawRect(battX + 30, 687, 3, 8, Theme::COLOR_TEXT_MUTED); // nub
    int fillW = std::clamp((m_sysInfo.batteryPercent * 26) / 100, 2, 26);
    Color battCol = (m_sysInfo.batteryPercent < 20) ? Theme::COLOR_DANGER : (m_sysInfo.batteryPercent < 50 ? Theme::COLOR_WARNING : Theme::COLOR_SUCCESS);
    drawRect(battX + 2, 685, fillW, 12, battCol);

    std::string battStr = std::to_string(m_sysInfo.batteryPercent) + "%";
    drawText(battStr, battX + 40, 684, Theme::COLOR_TEXT_PRIMARY, 14);

    // Wi-Fi Status
    drawText("📶", 125, 684, Theme::COLOR_FOCUS_CYAN, 14);
    std::string netStr = m_sysInfo.isNetworkConnected ? "Онлайн" : "Автономно";
    drawText(netStr, 150, 684, m_sysInfo.isNetworkConnected ? Theme::COLOR_SUCCESS : Theme::COLOR_TEXT_MUTED, 13);

    // Digital Clock
    std::time_t now = std::time(nullptr);
    std::tm* tmLocal = std::localtime(&now);
    char timeBuf[32];
    if (tmLocal) {
        std::strftime(timeBuf, sizeof(timeBuf), "%H:%M:%S", tmLocal);
    } else {
        std::snprintf(timeBuf, sizeof(timeBuf), "14:33:44");
    }
    drawText(timeBuf, 245, 684, Theme::COLOR_TEXT_PRIMARY, 14);

    // Right: Circular Joy-Con Button Badges (TorrentShopNX aesthetic)
    int btnX = 660;
    if (m_activeTab == Tab::Home) {
        drawButtonBadge(btnX - 40, 682, "+", "Файловый менеджер", Theme::COLOR_TEXT_PRIMARY);
        drawButtonBadge(btnX + 175, 682, "-", "Добавить", Theme::COLOR_TEXT_PRIMARY);
        drawButtonBadge(btnX + 310, 682, "B", "Назад", Theme::COLOR_TEXT_PRIMARY);
        drawButtonBadge(btnX + 420, 682, "A", "OK", Theme::COLOR_FOCUS_CYAN);
    } else if (m_activeTab == Tab::VideoIcons) {
        drawButtonBadge(btnX - 110, 682, "-", "Фильтр", Theme::COLOR_TEXT_PRIMARY);
        drawButtonBadge(btnX + 0, 682, "Y", "Поиск", Theme::COLOR_TEXT_PRIMARY);
        drawButtonBadge(btnX + 110, 682, "X", "Превью", Theme::COLOR_FOCUS_CYAN);
        drawButtonBadge(btnX + 230, 682, "B", "Назад", Theme::COLOR_TEXT_MUTED);
        drawButtonBadge(btnX + 345, 682, "A", "Установить", Theme::COLOR_FOCUS_CYAN);
    } else if (m_activeTab == Tab::Catalog) {
        if (m_catalogViewMode == CatalogViewMode::Categories) {
            drawButtonBadge(btnX + 60, 682, "Y", "Поиск", Theme::COLOR_FOCUS_CYAN);
            drawButtonBadge(btnX + 175, 682, "-", "Обновить", Theme::COLOR_TEXT_PRIMARY);
            drawButtonBadge(btnX + 310, 682, "B", "Назад", Theme::COLOR_TEXT_PRIMARY);
            drawButtonBadge(btnX + 420, 682, "A", "OK", Theme::COLOR_FOCUS_CYAN);
        } else {
            drawButtonBadge(btnX - 110, 682, "X", "Сортировка", Theme::COLOR_TEXT_PRIMARY);
            drawButtonBadge(btnX + 30, 682, "Y", "Поиск", Theme::COLOR_TEXT_PRIMARY);
            drawButtonBadge(btnX + 150, 682, "ZL", "±15", Theme::COLOR_TEXT_MUTED);
            drawButtonBadge(btnX + 260, 682, "B", "Назад", Theme::COLOR_TEXT_MUTED);
            drawButtonBadge(btnX + 380, 682, "A", "Выбрать", Theme::COLOR_FOCUS_CYAN);
        }
    } else if (m_activeTab == Tab::MyGames) {
        drawButtonBadge(btnX - 80, 682, "X", "Видео", Theme::COLOR_FOCUS_CYAN);
        drawButtonBadge(btnX + 50, 682, "Y", "Удалить", Theme::COLOR_DANGER);
        drawButtonBadge(btnX + 200, 682, "B", "Назад", Theme::COLOR_TEXT_MUTED);
        drawButtonBadge(btnX + 340, 682, "A", "Выбрать", Theme::COLOR_FOCUS_CYAN);
    } else if (m_activeTab == Tab::Downloads) {
        drawButtonBadge(btnX - 50, 682, "X", "Очистить", Theme::COLOR_DANGER);
        drawButtonBadge(btnX + 90, 682, "Y", "Все недостающие", Theme::COLOR_TEXT_PRIMARY);
        drawButtonBadge(btnX + 300, 682, "B", "Назад", Theme::COLOR_TEXT_MUTED);
        drawButtonBadge(btnX + 400, 682, "A", "Повторить", Theme::COLOR_FOCUS_CYAN);
    } else if (m_activeTab == Tab::Settings) {
        drawButtonBadge(btnX + 260, 682, "B", "Назад", Theme::COLOR_TEXT_MUTED);
        drawButtonBadge(btnX + 380, 682, "A", "Применить", Theme::COLOR_FOCUS_CYAN);
    }
}

void App::renderTabHome() {
    const auto& s = getStrings(m_language);

    // 1. Center 5x Dashboard Tiles (w = 225, h = 208, gap = 14, title inside, scaleFocus = true)
    struct TileDef {
        int index;
        std::string title;
    };

    TileDef tiles[5] = {
        {0, "Каталог"},
        {1, "Видеоиконки"},
        {2, "Менеджер игр"},
        {3, "Загрузки"},
        {4, "Настройки"}
    };

    int tileW = 225;
    int tileH = 208;
    int tileGap = 14;
    int totalRowW = 5 * tileW + 4 * tileGap;
    int tileStartX = (Theme::SCREEN_WIDTH - totalRowW) / 2;
    int tileStartY = 104;

    for (int i = 0; i < 5; ++i) {
        bool isFocused = (m_homeFocusedTile == i);
        int tx = tileStartX + i * (tileW + tileGap);
        int ty = tileStartY;
        int drawW = isFocused ? static_cast<int>(tileW * 1.05f) : tileW;
        int drawH = isFocused ? static_cast<int>(tileH * 1.05f) : tileH;
        int drawX = tx - (drawW - tileW) / 2;
        int drawY = ty - (drawH - tileH) / 2;
        drawDashboardTile(drawX, drawY, drawW, drawH, tiles[i].index, tiles[i].title, "", isFocused);
    }

    // 2. Bottom Summary Panel (2 Wide Informative Cards — no redundant Installation Folder card!)
    int boxX = 48;
    int boxY = 368;
    int boxW = 1184;
    int boxH = 258;

    drawGlassCard(boxX, boxY, boxW, boxH, false, false);

    // Outer Container Header
    drawRect(boxX + 24, boxY + 20, 4, 16, Theme::COLOR_FOCUS_CYAN);
    std::string headerTitle = "КАТАЛОГ ВИДЕОФОНОВ 4IFIR ДЛЯ NINTENDO SWITCH";
    if (m_homeFocusedTile == 1) {
        headerTitle = "КАТАЛОГ ВИДЕОИКОНОК 256x256 (ФОРМАТ 4IFIR HEVC)";
    } else if (m_homeFocusedTile == 2) {
        headerTitle = "УСТАНОВЛЕННЫЕ ИГРЫ И АКТИВНЫЕ ВИДЕОФОНЫ НА КОНСОЛИ";
    } else if (m_homeFocusedTile == 3) {
        headerTitle = "МЕНЕДЖЕР ПОТОКОВЫХ ЗАГРУЗОК И ОЧЕРЕДЬ";
    } else if (m_homeFocusedTile == 4) {
        headerTitle = "СИСТЕМНЫЕ НАСТРОЙКИ, КЭШ И ОБНОВЛЕНИЕ OTA";
    }
    drawText(headerTitle, boxX + 36, boxY + 18, Theme::COLOR_FOCUS_CYAN, 13);

    int subY = boxY + 52;
    int subH = 184;
    int cardW = 560;
    int cardGap = 24;
    int sc1X = boxX + 20;
    int sc2X = sc1X + cardW + cardGap;

    // Sub-card 1: Library Stats (560px wide)
    drawGlassCard(sc1X, subY, cardW, subH, false, false);
    drawText(m_homeFocusedTile == 1 ? "БИБЛИОТЕКА ВИДЕОИКОНОК 1:1" : "БИБЛИОТЕКА ВИДЕОФОНОВ И ИКОНОК", sc1X + 22, subY + 18, Theme::COLOR_TEXT_MUTED, 12);
    drawText("18 тематических подборок", sc1X + cardW - 195, subY + 18, Theme::COLOR_FOCUS_CYAN, 12);

    size_t totalGames = m_catalogManager.getGamesCount();
    size_t totalVariants = m_catalogManager.getTotalVariantsCount();
    size_t totalIcons = m_videoIconsCatalog.size();
    std::string bigStat = (m_homeFocusedTile == 1)
        ? (std::to_string(totalIcons) + " тайтлов с иконками")
        : (std::to_string(totalGames) + " тайтлов в базе");
    drawText(bigStat, sc1X + 22, subY + 62, Theme::COLOR_TEXT_PRIMARY, 24);

    // Badge "Полная база"
    drawRect(sc1X + 310, subY + 64, 104, 24, {0x10, 0xB9, 0x81, 0x33});
    drawRectOutline(sc1X + 310, subY + 64, 104, 24, Theme::COLOR_SUCCESS, 1);
    drawText("Полная база", sc1X + 322, subY + 68, Theme::COLOR_SUCCESS, 11);

    drawText(std::to_string(totalVariants) + " видеофонов и 433 видеоиконки • 1080p / 720p 60 FPS • HEVC", sc1X + 22, subY + 136, Theme::COLOR_TEXT_MUTED, 13);

    // Sub-card 2: Main Collections & Quick Action (560px wide, highlighted)
    drawGlassCard(sc2X, subY, cardW, subH, true, true);
    drawText("ОСНОВНЫЕ ПОДБОРКИ И ЖАНРЫ", sc2X + 22, subY + 18, Theme::COLOR_TEXT_MUTED, 12);
    drawText("4IFIR Engine", sc2X + cardW - 110, subY + 18, Theme::COLOR_FOCUS_CYAN, 12);

    // 3 4IFIR Cyber-Glass pills (Cyan & Magenta only)
    drawRect(sc2X + 22, subY + 64, 165, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(sc2X + 22, subY + 64, 165, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("Эксклюзивы Switch (40)", sc2X + 30, subY + 70, Theme::COLOR_FOCUS_CYAN, 11);

    drawRect(sc2X + 198, subY + 64, 150, 26, {0xEC, 0x48, 0x99, 0x24});
    drawRectOutline(sc2X + 198, subY + 64, 150, 26, Theme::COLOR_FOCUS_PINK, 1);
    drawText("RPG и Экшены (45)", sc2X + 208, subY + 70, Theme::COLOR_FOCUS_PINK, 11);

    drawRect(sc2X + 360, subY + 64, 125, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(sc2X + 360, subY + 64, 125, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("Инди-хиты (27)", sc2X + 370, subY + 70, Theme::COLOR_FOCUS_CYAN, 11);

    drawText("(A) Нажмите для перехода к выбранному разделу  •  (Y) Быстрый поиск", sc2X + 22, subY + 136, Theme::COLOR_FOCUS_CYAN, 13);
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

        // Status pill: Cover & Video Icon
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
        std::string coverInfo;
        if (selGame.hasInstalledCover && selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: Видеофон (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB) + 🔲 Видеоиконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledCover) {
            coverInfo = "Активный видеофон: " + Config::getTargetCoverFileName(selGame.titleId) + " (" + std::to_string(selGame.installedCoverSizeBytes / 1024) + " KB)";
        } else if (selGame.hasInstalledIcon) {
            coverInfo = "Активно на консоли: 🔲 Видеоиконка 4IFIR (" + std::to_string(selGame.installedIconSizeBytes / 1024) + " KB, без видеофона)";
        } else {
            coverInfo = "Видеофон и видеоиконка не установлены";
        }
        drawText(coverInfo, 530, 175, (selGame.hasInstalledCover || selGame.hasInstalledIcon) ? Theme::COLOR_SUCCESS : Theme::COLOR_WARNING, 14);

        // Prominent Action Buttons (positioned below status, safe from top-right Tesla monitor HUD)
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
                if (v.hasIcon) {
                    vTitle += "  [🔲 Иконка]";
                }
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

                // Badges row: Active on console, Audio, and Video Icon
                int vBadgeX = 720;
                bool isActiveOnConsole = (selGame.hasInstalledCover && v.id == selGame.installedVariantId);
                if (isActiveOnConsole) {
                    drawRect(vBadgeX, vY + 38, 92, 22, {0x10, 0xB9, 0x81, 0x44});
                    drawRectOutline(vBadgeX, vY + 38, 92, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("УСТАНОВЛЕН", vBadgeX + 8, vY + 43, Theme::COLOR_SUCCESS, 10);
                    vBadgeX += 98;
                }

                // Audio Status Pill
                if (v.hasAudio) {
                    drawRect(vBadgeX, vY + 38, 62, 22, {0x10, 0xB9, 0x81, 0x33});
                    drawRectOutline(vBadgeX, vY + 38, 62, 22, Theme::COLOR_SUCCESS, 1);
                    drawText("ЗВУК", vBadgeX + 15, vY + 43, Theme::COLOR_SUCCESS, 10);
                    vBadgeX += 68;
                } else {
                    drawRect(vBadgeX, vY + 38, 78, 22, Theme::COLOR_MUTED_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 78, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ЗВУКА", vBadgeX + 9, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                    vBadgeX += 84;
                }

                // Video Icon Status Pill (prominent cyan when present, muted when absent)
                if (v.hasIcon) {
                    drawRect(vBadgeX, vY + 38, 72, 22, Theme::COLOR_ICON_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 72, 22, Theme::COLOR_ICON_BADGE, 1);
                    drawText("ИКОНКА", vBadgeX + 11, vY + 43, Theme::COLOR_ICON_BADGE, 10);
                } else {
                    drawRect(vBadgeX, vY + 38, 86, 22, Theme::COLOR_MUTED_BADGE_FILL);
                    drawRectOutline(vBadgeX, vY + 38, 86, 22, Theme::COLOR_BORDER, 1);
                    drawText("БЕЗ ИКОНКИ", vBadgeX + 9, vY + 43, Theme::COLOR_TEXT_MUTED, 10);
                }

                // Install / Reinstall Button (Interactive touch zone)
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
            std::string catBtnText = Config::isAfterDark()
                ? (m_language == Language::Russian ? "[X] Открыть каталог After Dark" : "[X] Open After Dark Catalog")
                : (m_language == Language::Russian ? "[X] Открыть онлайн-каталог" : "[X] Open Online Catalog");
            drawText(catBtnText, 555, 368, Theme::COLOR_FOCUS_CYAN, 16);
        }
    }
}

void App::renderCategoriesView() {
    // Top Row: Title + View Mode Toggle ([X] Списком) + Interactive Search Bar
    drawText("Каталог видеофонов", 60, 78, Theme::COLOR_TEXT_PRIMARY, 24);

    // Toggle to Full List button (x=340, y=74, w=185, h=38)
    drawPillButton(340, 74, 185, 38, "[X] ≡ Весь список", false, Theme::COLOR_FOCUS_CYAN);

    // Search Bar at top-right (x=700, y=74, w=512, h=38)
    bool hasCatSearch = !m_catalogSearchQuery.empty();
    drawGlassCard(700, 74, 512, 38, hasCatSearch, false);
    std::string catSearchLabel = hasCatSearch
        ? ("🔍 Поиск: " + m_catalogSearchQuery)
        : "🔍 Поиск по названию игры, жанру или TitleID...";
    drawText(catSearchLabel, 716, 84, hasCatSearch ? Theme::COLOR_TEXT_PRIMARY : Theme::COLOR_TEXT_MUTED, 13, 390);
    drawRect(1118, 80, 84, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(1118, 80, 84, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("[Y] Поиск", 1128, 85, Theme::COLOR_FOCUS_CYAN, 11);

    // Section 1: | ОСНОВНЫЕ РАЗДЕЛЫ
    drawRect(60, 122, 3, 15, Theme::COLOR_FOCUS_CYAN);
    drawText("ОСНОВНЫЕ РАЗДЕЛЫ", 72, 121, Theme::COLOR_FOCUS_CYAN, 13);

    struct MainSectionDef {
        std::string iconType;
        std::string title;
        std::string desc;
        std::string badge;
        Color col;
    };

    size_t totalCatGames = m_catalogManager.getGamesCount();
    MainSectionDef mainSections[4] = {
        {"all_catalog", "Весь каталог", "Полная база доступных игр", std::to_string(totalCatGames) + " игр", Theme::COLOR_FOCUS_CYAN},
        {"favorites", "Избранное", "Ваши сохранённые игры", std::to_string(m_favoriteKeys.size()) + " игр", Theme::COLOR_FOCUS_PINK},
        {"new_release", "Новые релизы", "Автоматически обновляемые релизы", "42 игры", Theme::COLOR_FOCUS_CYAN},
        {"top_100", "Топ-100", "100 лучших игр всех времён по Metacritic", "100 игр", Theme::COLOR_FOCUS_PINK}
    };

    int cardW = 270;
    int cardH = 88;
    int startX = 60;
    int gapX = 22;

    for (int i = 0; i < 4; ++i) {
        bool isFocused = (m_categorySelectedIndex == i);
        int cx = startX + i * (cardW + gapX);
        int cy = 144;
        drawCategoryCard(cx, cy, cardW, cardH, mainSections[i].iconType, mainSections[i].title, mainSections[i].desc, mainSections[i].badge, isFocused, mainSections[i].col);
    }

    // Section 2: | ЖАНРОВЫЕ И ТЕМАТИЧЕСКИЕ ПОДБОРКИ
    drawRect(60, 250, 3, 15, Theme::COLOR_FOCUS_CYAN);
    drawText("ЖАНРОВЫЕ И ТЕМАТИЧЕСКИЕ ПОДБОРКИ", 72, 249, Theme::COLOR_FOCUS_CYAN, 13);

    struct GenreDef {
        std::string iconType;
        std::string title;
        std::string desc;
        std::string count;
        Color col;
    };

    GenreDef genres[14] = {
        {"action_adventure", "Экшены и приключения", "Приключенческие экшены и динамичные игры", "100 игр", Theme::COLOR_FOCUS_CYAN},
        {"arcade", "Аркады", "Классические и современные аркадные игры", "100 игр", Theme::COLOR_FOCUS_PINK},
        {"horror", "Хорроры", "Сурвайвал и психологические хорроры", "100 игр", Theme::COLOR_FOCUS_PINK},
        {"metroidvania", "Метроидвании", "Исследования, лабиринты и платформеры", "100 игр", Theme::COLOR_FOCUS_CYAN},
        {"party_multiplayer", "Вечеринки и кооп", "Игры для вечеринок и локальный кооператив", "100 игр", Theme::COLOR_FOCUS_CYAN},
        {"platformers", "Платформеры", "Классические 2D и 3D платформеры", "100 игр", Theme::COLOR_FOCUS_PINK},
        {"puzzles", "Головоломки", "Логические задачи и пространственные пазлы", "100 игр", Theme::COLOR_FOCUS_CYAN},
        {"roguelike_roguelite", "Рогалики", "Рогалики, роглайты и колодостроительные", "100 игр", Theme::COLOR_FOCUS_PINK},
        {"rpg_jrpg", "RPG / JRPG", "Ролевые приключения и японские RPG", "100 игр", Theme::COLOR_FOCUS_PINK},
        {"shooters", "Шутеры", "Шутеры от 1-го/3-го лица и классические Shmup", "100 игр", Theme::COLOR_FOCUS_CYAN},
        {"simulation_cozy", "Симуляторы и уютные", "Симуляторы жизни, фермы и уютные игры", "100 игр", Theme::COLOR_FOCUS_CYAN},
        {"strategy_tactics", "Стратегии и тактика", "Пошаговая тактика и глобальные стратегии", "100 игр", Theme::COLOR_FOCUS_PINK},
        {"visual_novels", "Визуальные новеллы", "Интерактивные визуальные новеллы и истории", "100 игр", Theme::COLOR_FOCUS_PINK},
        {"ports_homebrew", "Порты и Homebrew", "Порты классических игр и Homebrew", "100 игр", Theme::COLOR_FOCUS_CYAN}
    };

    int gridStartY = 272;
    for (int i = 0; i < 14; ++i) {
        int col = i % 4;
        int row = i / 4;
        int cx = startX + col * (cardW + gapX);
        int cy = gridStartY + row * (cardH + 10);
        if (cy + cardH > 660) break;
        bool isFocused = (m_categorySelectedIndex == (i + 4));
        drawCategoryCard(cx, cy, cardW, cardH, genres[i].iconType, genres[i].title, genres[i].desc, genres[i].count, isFocused, genres[i].col);
    }

    // Scrollbar on the right edge
    drawRect(1245, 144, 4, 495, {0x1C, 0x24, 0x36, 0x66});
    int thumbH = 130;
    int thumbY = 144 + (m_categorySelectedIndex * (495 - thumbH)) / 17;
    drawRect(1245, thumbY, 4, thumbH, Theme::COLOR_FOCUS_CYAN);
}

void App::renderTabVideoIcons() {
    // 4IFIR Cyber-Glass Container
    drawGlassCard(30, 74, 1220, 576, false, false);

    // Top Row: Section Title + Interactive Search Bar + Filter Button
    drawText("Видеоиконки 1:1", 60, 88, Theme::COLOR_TEXT_PRIMARY, 22);

    // Prominent Search Bar (x=290, y=82, w=620, h=38)
    bool hasIconSearch = !m_videoIconsSearchQuery.empty();
    drawGlassCard(290, 82, 620, 38, hasIconSearch, false);
    std::string iconSearchLabel = hasIconSearch
        ? ("🔍 Поиск: " + m_videoIconsSearchQuery)
        : "🔍 Поиск видеоиконки по названию игры или TitleID...";
    drawText(iconSearchLabel, 308, 92, hasIconSearch ? Theme::COLOR_TEXT_PRIMARY : Theme::COLOR_TEXT_MUTED, 13, 490);
    drawRect(816, 88, 84, 26, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(816, 88, 84, 26, Theme::COLOR_FOCUS_CYAN, 1);
    drawText("[Y] Поиск", 826, 93, Theme::COLOR_FOCUS_CYAN, 11);

    // Filter pill at top-right (x=925, y=82, w=295, h=38)
    const char* filterLabels[] = {"Все (112)", "Установленные", "Не установленные"};
    std::string fText = "[-] Фильтр: " + std::string(filterLabels[m_videoIconsFilterMode % 3]);
    drawPillButton(925, 82, 295, 38, fText, false, Theme::COLOR_FOCUS_CYAN);

    if (m_filteredVideoIcons.empty()) {
        drawText("Видеоиконки не найдены по заданным критериям.", 60, 180, Theme::COLOR_TEXT_MUTED, 16);
        drawText("Нажмите [Y] для смены поискового запроса или [-] для сброса фильтра.", 60, 215, Theme::COLOR_FOCUS_CYAN, 14);
        return;
    }

    const int visibleRows = 5;
    int totalCount = static_cast<int>(m_filteredVideoIcons.size());
    if (m_videoIconsScrollOffset < 0) m_videoIconsScrollOffset = 0;
    if (m_videoIconsScrollOffset + visibleRows > totalCount) {
        m_videoIconsScrollOffset = std::max(0, totalCount - visibleRows);
    }

    int y = 136;
    int endIdx = std::min(totalCount, m_videoIconsScrollOffset + visibleRows);

    for (int i = m_videoIconsScrollOffset; i < endIdx; ++i) {
        const auto& entry = m_filteredVideoIcons[i];
        bool isFocused = (i == m_videoIconsSelectedIndex);
        bool installed = isIconInstalled(entry.titleId);

        drawGlassCard(60, y, 1160, 88, isFocused, isFocused);

        int boxX = 74;
        int boxY = y + 9;
        drawRect(boxX, boxY, 70, 70, {0x14, 0x1A, 0x28, 0xFF});
        drawRectOutline(boxX, boxY, 70, 70, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, 1);
        drawText("🔲", boxX + 22, boxY + 18, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 22);
        drawText("256x256", boxX + 8, boxY + 48, Theme::COLOR_TEXT_MUTED, 10);

        int infoX = boxX + 86;
        drawText(entry.title, infoX, y + 14, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 680);

        drawRect(infoX, y + 42, 170, 22, {0x1C, 0x24, 0x36, 0xAA});
        drawRectOutline(infoX, y + 42, 170, 22, Theme::COLOR_BORDER, 1);
        drawText(entry.titleId, infoX + 8, y + 45, Theme::COLOR_TEXT_MUTED, 11);

        int varCount = static_cast<int>(entry.variants.size());
        std::string varStr = std::to_string(varCount) + " вар. иконки";
        drawRect(infoX + 180, y + 42, 130, 22, Theme::COLOR_FOCUS_FILL);
        drawRectOutline(infoX + 180, y + 42, 130, 22, Theme::COLOR_FOCUS_CYAN, 1);
        drawText(varStr, infoX + 188, y + 45, Theme::COLOR_FOCUS_CYAN, 11);

        drawText("Формат: HEVC 256x256 • 30 FPS • Анимация", infoX + 325, y + 45, Theme::COLOR_TEXT_MUTED, 12);

        // Interactive Preview [X] and Install [A] buttons on each Video Icon row
        drawRect(890, y + 25, 135, 38, isFocused ? Theme::COLOR_FOCUS_FILL : Color{0x14, 0x1E, 0x30, 0xDD});
        drawRectOutline(890, y + 25, 135, 38, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, 1);
        drawText("[X] ▶ Превью", 904, y + 36, Theme::COLOR_FOCUS_CYAN, 13);

        if (installed) {
            drawRect(1035, y + 25, 165, 38, Theme::COLOR_SUCCESS_BADGE_FILL);
            drawRectOutline(1035, y + 25, 165, 38, Theme::COLOR_SUCCESS, 1);
            drawText("✔ УСТАНОВЛЕНО", 1054, y + 36, Theme::COLOR_SUCCESS, 12);
        } else {
            drawRect(1035, y + 25, 165, 38, isFocused ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(1035, y + 25, 165, 38, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_BORDER, 1);
            drawText("[A] Установить", 1060, y + 36, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 13);
        }

        y += 98;
    }
}

void App::renderTabCatalog() {
    if (m_catalogViewMode == CatalogViewMode::Categories) {
        renderCategoriesView();
        return;
    }

    // Detailed GameGrid inside selected category
    drawGlassCard(30, 80, 1220, 570, false, false);

    // Breadcrumb Header
    std::string navTitle = "Каталог  >  " + m_activeCategoryName;
    drawText(navTitle, 60, 95, Theme::COLOR_TEXT_PRIMARY, 22);

    // Back to Categories Pill Button
    drawPillButton(1040, 90, 185, 34, "(B) К разделам", false, Theme::COLOR_FOCUS_CYAN);

    // Search and Sort Pills
    std::string sortStr = "[X] Сорт: ";
    switch (m_catalogSortMode) {
        case CatalogSortMode::Alphabetical: sortStr += "А-Я"; break;
        case CatalogSortMode::VariantsCount: sortStr += "Варианты"; break;
        case CatalogSortMode::AudioOnly: sortStr += "Звук"; break;
        case CatalogSortMode::IconsOnly: sortStr += "Иконки"; break;
        case CatalogSortMode::InstalledOnly: sortStr += "Установленные"; break;
        case CatalogSortMode::FavoritesOnly: sortStr += "Избранное"; break;
        default: sortStr += "По умолчанию"; break;
    }
    drawPillButton(760, 90, 170, 34, sortStr, false, Theme::COLOR_TEXT_MUTED);

    std::string searchStr = m_catalogSearchQuery.empty() ? "[Y] Поиск" : ("[Y] " + m_catalogSearchQuery);
    drawPillButton(940, 90, 90, 34, searchStr, false, Theme::COLOR_TEXT_MUTED);

    int totalFiltered = static_cast<int>(m_filteredCatalogGames.size());
    if (totalFiltered == 0) {
        drawText("В этом разделе нет подходящих видеофонов.", 60, 180, Theme::COLOR_TEXT_MUTED, 16);
        drawText("Нажмите (B) для возврата к категориям каталога.", 60, 215, Theme::COLOR_FOCUS_CYAN, 14);
        return;
    }

    const int visibleCount = 5;
    if (m_catalogSelectedIndex < m_catalogScrollOffset) {
        m_catalogScrollOffset = m_catalogSelectedIndex;
    }
    if (m_catalogSelectedIndex >= m_catalogScrollOffset + visibleCount) {
        m_catalogScrollOffset = m_catalogSelectedIndex - visibleCount + 1;
    }

    int y = 145;
    int endIdx = std::min(totalFiltered, m_catalogScrollOffset + visibleCount);
    for (int i = m_catalogScrollOffset; i < endIdx; ++i) {
        const auto& game = m_filteredCatalogGames[i];
        bool isFocused = (i == m_catalogSelectedIndex);
        drawGlassCard(60, y, 1160, 80, isFocused, isFocused);

        drawText(game.title, 85, y + 14, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16, 680);
        drawText(game.titleId + "  |  " + game.publisher, 85, y + 42, Theme::COLOR_TEXT_MUTED, 13);

        int vCount = static_cast<int>(game.variants.size());
        std::string vStr = std::to_string(vCount) + " вар. видеофона";
        drawRect(780, y + 24, 160, 32, Theme::COLOR_FOCUS_FILL);
        drawRectOutline(780, y + 24, 160, 32, Theme::COLOR_FOCUS_CYAN, 1);
        drawText(vStr, 792, y + 31, Theme::COLOR_FOCUS_CYAN, 12);

        drawRect(960, y + 22, 240, 36, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(960, y + 22, 240, 36, 2);
        drawText("[A] Смотреть фон ▶", 975, y + 31, Theme::COLOR_FOCUS_CYAN, 14);

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

    refreshStorageStats();

    // Main 4IFIR Frosted Glass Container
    drawGlassCard(30, 80, 1220, 580, false, false);

    drawText(std::string("4IFIR System & Storage Manager  |  ") + Config::APP_NAME, 60, 95, Theme::COLOR_TEXT_PRIMARY, 20);

    // MicroSD Visual Dashboard Card at y = 120
    drawRect(50, 122, 1180, 100, Theme::COLOR_BG_SURFACE);
    drawRectOutline(50, 122, 1180, 100, Theme::COLOR_BORDER, 1);

    double freeGb = static_cast<double>(m_storageStats.freeSdBytes) / (1024.0 * 1024.0 * 1024.0);
    double totalGb = static_cast<double>(m_storageStats.totalSdBytes) / (1024.0 * 1024.0 * 1024.0);
    double usedGb = std::max(0.0, totalGb - freeGb);
    double usedPct = (totalGb > 0.0) ? (usedGb / totalGb * 100.0) : 0.0;

    char sdInfoBuf[128];
    snprintf(sdInfoBuf, sizeof(sdInfoBuf), "MicroSD: %.1f GB свободно из %.1f GB (%.1f%% занято)", freeGb, totalGb, usedPct);
    drawText(sdInfoBuf, 70, 132, Theme::COLOR_FOCUS_CYAN, 14);

    drawCapsuleProgressBar(70, 154, 1140, 14, usedPct);

    // Three metric badges inside dashboard
    double coversMb = static_cast<double>(m_storageStats.coversBytes) / (1024.0 * 1024.0);
    double thumbsMb = static_cast<double>(m_storageStats.thumbsBytes) / (1024.0 * 1024.0);
    double vidCacheMb = static_cast<double>(m_storageStats.vidCacheBytes) / (1024.0 * 1024.0);

    char covBuf[64], thBuf[64], vcBuf[64];
    snprintf(covBuf, sizeof(covBuf), "📁 Видеофоны: %d шт. (%.1f MB)", m_storageStats.coversCount, coversMb);
    snprintf(thBuf, sizeof(thBuf), "🖼️ Кэш превью: %d шт. (%.1f MB)", m_storageStats.thumbsCount, thumbsMb);
    snprintf(vcBuf, sizeof(vcBuf), "🎬 Кэш видео: %d шт. (%.1f MB)", m_storageStats.vidCacheCount, vidCacheMb);

    drawText(covBuf, 70, 185, Theme::COLOR_SUCCESS, 13);
    drawText(thBuf, 460, 185, Theme::COLOR_FOCUS_CYAN, 13);
    drawText(vcBuf, 850, 185, Theme::COLOR_FOCUS_PINK, 13);

    // Settings list options (7 rows)
    struct SettingRow {
        std::string title;
        std::string desc;
        std::string value;
        Color valColor;
    };

    std::vector<SettingRow> rows = {
        {"Обновление приложения (NRO)", std::string("Проверить и установить новую версию ") + Config::APP_NAME + " с GitHub", std::string("v") + Config::APP_VERSION + " [A]", Theme::COLOR_FOCUS_CYAN},
        {"Обновление каталога видеофонов", "Загрузить новейший каталог игр и обложек без обновления NRO", "GitHub Releases [A]", Theme::COLOR_FOCUS_CYAN},
        {"Очистить кэш мини-превью (галерея)", "Удалить сохраненные миниатюры обложек (thumbs/) для освобождения места", "[A] Очистить", Theme::COLOR_FOCUS_PINK},
        {"Очистить кэш видеоплеера (видео)", "Удалить временные видеофайлы предпросмотра (mp4) на SD-карте", "[A] Очистить", Theme::COLOR_FOCUS_PINK},
        {"Очистить локальный кэш каталога", "Сбросить локальный файл cache.json и пересканировать игры", "[A / X] Сброс", Theme::COLOR_WARNING},
        {"Проверка целостности фонов", "Сканирование установленных видеофонов на ошибки и битые файлы", "[A] Сканировать", Theme::COLOR_FOCUS_CYAN},
        {"Язык интерфейса / Language", "Выбор языка отображения меню и подсказок управления", (m_language == Language::Russian ? "Русский [A]" : "English [A]"), Theme::COLOR_TEXT_PRIMARY}
    };

    int rowY = 236;
    for (size_t i = 0; i < rows.size(); ++i) {
        bool isFocused = (static_cast<int>(i) == m_settingsSelectedIndex);

        if (isFocused) {
            drawRect(50, rowY, 1180, 48, Theme::COLOR_FOCUS_FILL);
            drawNeonGradientOutline(50, rowY, 1180, 48, 2);
        } else {
            drawRect(50, rowY, 1180, 48, Theme::COLOR_BG_SURFACE);
            drawRectOutline(50, rowY, 1180, 48, Theme::COLOR_BORDER, 1);
        }

        drawText(rows[i].title, 75, rowY + 7, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15, 850);
        drawText(rows[i].desc, 75, rowY + 28, Theme::COLOR_TEXT_MUTED, 11, 850);

        drawText(rows[i].value, 940, rowY + 14, rows[i].valColor, 14, 270);

        rowY += 54;
    }

    // Bottom Help Banner
    drawRect(50, 622, 1180, 32, Theme::COLOR_BG_BASE);
    drawRectOutline(50, 622, 1180, 32, Theme::COLOR_BORDER, 1);
    drawText("Навигация: [D-Pad Вверх/Вниз] Выбор   |   [A] Применить / Очистить   |   [B] Главная", 75, 629, Theme::COLOR_TEXT_MUTED, 13);
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

    bool isInstallWithIcon = (m_activeDialog == DialogType::ConfirmInstall && m_pendingActionVariant.hasIcon);
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
    SDL_Rect targetRect = fullScreenRect;
    if (m_previewIsIconSquare) {
        drawRect(0, 0, Theme::SCREEN_WIDTH, Theme::SCREEN_HEIGHT, {0x07, 0x0B, 0x12, 0xFF});
        targetRect = {440, 120, 400, 400};
        drawGlassCard(424, 104, 432, 432, true, true);
    }

    // 1. Draw Live Motion Video or Static Background Image or Dark Frosted Canvas
    if (m_videoPlayer.isPlaying()) {
        m_videoPlayer.render(m_renderer, &targetRect);

        // Status badge: LIVE VIDEO
        drawRect(30, 20, 280, 32, {0x0F, 0x17, 0x2A, 0xDD});
        drawRectOutline(30, 20, 280, 32, Theme::COLOR_SUCCESS, 1);
        drawText("▶ ЖИВОЙ ВИДЕОФОН (30 FPS)", 45, 28, Theme::COLOR_SUCCESS, 13);
    } else if (m_previewTexture) {
        SDL_RenderCopy(m_renderer, m_previewTexture, nullptr, &targetRect);

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
        drawText(specs, hudX + 25, hudY + 71, Theme::COLOR_TEXT_MUTED, 13, 255);

        // Sequential dynamic badges starting at hudX + 285
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
            drawRect(badgeX, hudY + 66, 80, 24, Theme::COLOR_ICON_BADGE_FILL);
            drawRectOutline(badgeX, hudY + 66, 80, 24, Theme::COLOR_ICON_BADGE, 1);
            drawText("ИКОНКА", badgeX + 13, hudY + 71, Theme::COLOR_ICON_BADGE, 11);
            badgeX += 88;
        } else {
            drawRect(badgeX, hudY + 66, 92, 24, Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(badgeX, hudY + 66, 92, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ИКОНКИ", badgeX + 9, hudY + 71, Theme::COLOR_TEXT_MUTED, 11);
            badgeX += 100;
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

        bool isFav = isVariantFavorite(m_previewTitleId, v.id);
        if (isFav) {
            drawRect(hudX + 690, hudY + 14, 195, 38, {0xFF, 0xD7, 0x00, 0x33});
            drawRectOutline(hudX + 690, hudY + 14, 195, 38, {0xFF, 0xD7, 0x00, 0xFF}, 1);
            drawText("★ В ИЗБРАННОМ", hudX + 710, hudY + 24, {0xFF, 0xD7, 0x00, 0xFF}, 14);
        }

        drawText("[R3/L] ★ В избранное", hudX + 680, hudY + 71, Theme::COLOR_TEXT_MUTED, 13);
        drawText("[Y] Привязать", hudX + 850, hudY + 71, Theme::COLOR_FOCUS_CYAN, 13);
        if (totalV > 1) {
            drawText("[◀/▶] Вариант", hudX + 975, hudY + 71, Theme::COLOR_FOCUS_PINK, 13);
        }
        drawText("[B] Назад", hudX + 1100, hudY + 71, Theme::COLOR_TEXT_MUTED, 13);
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
    m_previewIsIconSquare = false;
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
    m_previewIsIconSquare = false;
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
        bool isFav = isVariantFavorite(m_collectionTitleId, v.id);
        std::string titleStr = (isFav ? "★ " : "") + std::to_string(i + 1) + ". " + v.name;
        drawText(titleStr, lx + 16, cardY + 14, isFav ? Color{0xFF, 0xD7, 0x00, 0xFF} : (isSelected ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY), 16, lw - 70);

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
            drawRect(bxPos, cardY + 46, 82, 24, Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 82, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ЗВУКА", bxPos + 9, cardY + 51, Theme::COLOR_TEXT_MUTED, 10);
            bxPos += 90;
        }

        // Icon badge
        if (v.hasIcon) {
            drawRect(bxPos, cardY + 46, 75, 24, Theme::COLOR_ICON_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 75, 24, Theme::COLOR_ICON_BADGE, 1);
            drawText("ИКОНКА", bxPos + 11, cardY + 51, Theme::COLOR_ICON_BADGE, 11);
            bxPos += 83;
        } else {
            drawRect(bxPos, cardY + 46, 86, 24, Theme::COLOR_MUTED_BADGE_FILL);
            drawRectOutline(bxPos, cardY + 46, 86, 24, Theme::COLOR_BORDER, 1);
            drawText("БЕЗ ИКОНКИ", bxPos + 8, cardY + 51, Theme::COLOR_TEXT_MUTED, 10);
            bxPos += 94;
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

        // [R3 / L] Favorite Button
        bool isSelFav = isVariantFavorite(m_collectionTitleId, selVar.id);
        int b3w = 480;
        int b3h = 36;
        int b3x = px;
        int b3y = b1y + 48;
        if (isSelFav) {
            drawRect(b3x, b3y, b3w, b3h, {0xFF, 0xD7, 0x00, 0x33});
            drawRectOutline(b3x, b3y, b3w, b3h, {0xFF, 0xD7, 0x00, 0xFF}, 1);
            drawText("★ [R3 / L] В ИЗБРАННОМ (Нажмите, чтобы убрать)", b3x + 65, b3y + 10, {0xFF, 0xD7, 0x00, 0xFF}, 13);
        } else {
            drawRect(b3x, b3y, b3w, b3h, {0x16, 0x20, 0x32, 0xAA});
            drawRectOutline(b3x, b3y, b3w, b3h, Theme::COLOR_BORDER, 1);
            drawText("☆ [R3 / L] Добавить вариант в избранное", b3x + 85, b3y + 10, Theme::COLOR_TEXT_MUTED, 13);
        }

        drawText("Совет: Нажмите [A], чтобы выбрать игру на Switch для этого фона", px, b3y + 42, Theme::COLOR_TEXT_MUTED, 12, pw);
    }

    // Bottom Navigation Bar
    int footY = by + bh - 42;
    drawRect(bx + 25, footY, bw - 50, 32, {0x0D, 0x13, 0x1F, 0xDD});
    drawRectOutline(bx + 25, footY, bw - 50, 32, Theme::COLOR_BORDER, 1);
    drawText("[▲/▼] Список   |   [◀/▶] ±5   |   [A] Назначить   |   [X] Видео   |   [R3/L] ★ В избранное   |   [B] Назад",
                 bx + 40, footY + 8, Theme::COLOR_TEXT_MUTED, 12);
#endif
}


// ----------------- Catalog Filtering, Sorting & Horizon OS Keyboard -----------------

void App::rebuildCatalogFilter() {
    const auto& allGames = m_catalogManager.getAllGames();
    m_filteredCatalogGames.clear();

    std::string qLower = utf8ToLower(m_catalogSearchQuery);

    for (const auto& g : allGames) {
        // 1. Search Query filter (matches Title, Title ID, Publisher, and Variant Names in EN and RU)
        if (!qLower.empty()) {
            std::string titleLower = utf8ToLower(g.title);
            std::string tidLower = utf8ToLower(g.titleId);
            std::string pubLower = utf8ToLower(g.publisher);

            bool match = (titleLower.find(qLower) != std::string::npos) ||
                         (tidLower.find(qLower) != std::string::npos) ||
                         (pubLower.find(qLower) != std::string::npos);
            if (!match) {
                for (const auto& v : g.variants) {
                    std::string vname = utf8ToLower(v.name);
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

        // 3.1 Icons Only filter
        if (m_catalogSortMode == CatalogSortMode::IconsOnly) {
            bool hasIco = false;
            for (const auto& v : g.variants) {
                if (v.hasIcon) {
                    hasIco = true;
                    break;
                }
            }
            if (!hasIco) continue;
        }

        // 4. Favorites Only filter
        if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
            if (!hasGameFavorites(g.titleId)) {
                continue;
            }
        }

        m_filteredCatalogGames.push_back(g);
    }

    // 5. Sorting
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
    int nextMode = (static_cast<int>(m_catalogSortMode) + 1) % 7;
    m_catalogSortMode = static_cast<CatalogSortMode>(nextMode);
    rebuildCatalogFilter();

    std::string modeDesc;
    switch (m_catalogSortMode) {
        case CatalogSortMode::Default: modeDesc = "Сортировка: По умолчанию"; break;
        case CatalogSortMode::Alphabetical: modeDesc = "Сортировка: По алфавиту (А-Я)"; break;
        case CatalogSortMode::VariantsCount: modeDesc = "Сортировка: По кол-ву фонов (▼)"; break;
        case CatalogSortMode::AudioOnly: modeDesc = "Фильтр: Только со звуком [ЗВУК]"; break;
        case CatalogSortMode::IconsOnly: modeDesc = "Фильтр: Только с видеоиконками [ИКОНКА]"; break;
        case CatalogSortMode::InstalledOnly: modeDesc = "Фильтр: Только установленные игры"; break;
        case CatalogSortMode::FavoritesOnly: modeDesc = "Фильтр: ★ Только избранное"; break;
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
        swkbdConfigSetHeaderText(&kbd, Config::isAfterDark() ? "Поиск по каталогу H3H After Dark" : "Поиск по каталогу H3H Backgrounds");
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



// ----------------- Feature 1: Favorites System -----------------

void App::loadFavorites() {
    m_favoriteKeys.clear();
    std::string favFile = m_platform->getAppDirectory() + "/favorites.json";
    std::error_code ec;
    if (!std::filesystem::exists(favFile, ec)) return;

    std::ifstream ifs(favFile);
    if (!ifs.is_open()) return;

    try {
        nlohmann::json j;
        ifs >> j;
        if (j.contains("keys") && j["keys"].is_array()) {
            for (const auto& k : j["keys"]) {
                if (k.is_string()) {
                    m_favoriteKeys.insert(k.get<std::string>());
                }
            }
        }
    } catch (...) {}
}

void App::saveFavorites() {
    nlohmann::json j;
    j["version"] = 1;
    j["keys"] = nlohmann::json::array();
    for (const auto& k : m_favoriteKeys) {
        j["keys"].push_back(k);
    }

    std::string appDir = m_platform->getAppDirectory();
    std::string targetFile = appDir + "/favorites.json";
    std::string tmpFile = targetFile + ".tmp";

    std::error_code ec;
    std::filesystem::create_directories(appDir, ec);

    std::ofstream ofs(tmpFile);
    if (ofs.is_open()) {
        ofs << j.dump(2);
        ofs.flush();
        ofs.close();
        std::filesystem::rename(tmpFile, targetFile, ec);
    }
}

bool App::isVariantFavorite(const std::string& titleId, const std::string& variantId) const {
    if (variantId.empty()) return false;
    if (!titleId.empty() && m_favoriteKeys.count(titleId + ":" + variantId) > 0) return true;
    if (m_favoriteKeys.count(variantId) > 0) return true;
    return false;
}

void App::toggleFavoriteVariant(const std::string& titleId, const Variant& variant) {
    if (variant.id.empty()) return;
    std::string key = (!titleId.empty() ? (titleId + ":" + variant.id) : variant.id);
    bool currentlyFav = isVariantFavorite(titleId, variant.id);

    if (currentlyFav) {
        m_favoriteKeys.erase(key);
        m_favoriteKeys.erase(variant.id);
        if (!titleId.empty()) m_favoriteKeys.erase(titleId + ":" + variant.id);
        m_statusNotification = "Удалено из избранного: " + variant.name;
    } else {
        m_favoriteKeys.insert(key);
        m_statusNotification = "★ Добавлено в избранное: " + variant.name;
    }
    m_notificationFramesRemaining = 90;
    saveFavorites();

    if (m_catalogSortMode == CatalogSortMode::FavoritesOnly) {
        rebuildCatalogFilter();
    }
}

bool App::hasGameFavorites(const std::string& titleId) const {
    const auto* entry = m_catalogManager.findByTitleId(titleId);
    
    if (entry) {
        for (const auto& v : entry->variants) {
            if (isVariantFavorite(titleId, v.id)) return true;
        }
    }
    for (const auto& ig : m_installedGames) {
        if (ig.titleId == titleId) {
            for (const auto& v : ig.catalogEntry.variants) {
                if (isVariantFavorite(titleId, v.id)) return true;
            }
            break;
        }
    }
    return false;
}

// ----------------- Feature 6: Storage & Cache Manager -----------------

void App::refreshStorageStats() {
    m_sysInfo = m_platform->getSystemInfo();
    m_storageStats.totalSdBytes = m_sysInfo.totalStorageBytes;
    m_storageStats.freeSdBytes = m_sysInfo.freeStorageBytes;

    // Installed covers (*.mp4 in coversDir)
    std::string covDir = m_platform->getCoversDirectory();
    m_storageStats.coversCount = 0;
    m_storageStats.coversBytes = 0;
    std::error_code ec;
    if (std::filesystem::exists(covDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(covDir, ec)) {
            if (entry.is_regular_file(ec) && entry.path().extension() == ".mp4") {
                m_storageStats.coversCount++;
                m_storageStats.coversBytes += entry.file_size(ec);
            }
        }
    }

    // Cache folder (thumbs/*.jpg and thumbs/*.mp4)
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    m_storageStats.thumbsCount = 0;
    m_storageStats.thumbsBytes = 0;
    m_storageStats.vidCacheCount = 0;
    m_storageStats.vidCacheBytes = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".jpg" || ext == ".png") {
                    m_storageStats.thumbsCount++;
                    m_storageStats.thumbsBytes += entry.file_size(ec);
                } else if (ext == ".mp4" || ext == ".tmp") {
                    m_storageStats.vidCacheCount++;
                    m_storageStats.vidCacheBytes += entry.file_size(ec);
                }
            }
        }
    }
}

void App::clearThumbnailCache() {
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    int deleted = 0;
    uint64_t freed = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".jpg" || ext == ".png") {
                    freed += entry.file_size(ec);
                    std::filesystem::remove(entry.path(), ec);
                    deleted++;
                }
            }
        }
    }
    refreshStorageStats();
    double freedMb = static_cast<double>(freed) / (1024.0 * 1024.0);
    char buf[128];
    snprintf(buf, sizeof(buf), "Очищен кэш превью: %d файлов (%.1f MB)", deleted, freedMb);
    m_statusNotification = buf;
    m_notificationFramesRemaining = 120;
}

void App::clearVideoPreviewCache() {
    std::string thumbDir = m_platform->getAppDirectory() + "/thumbs";
    std::error_code ec;
    int deleted = 0;
    uint64_t freed = 0;
    if (std::filesystem::exists(thumbDir, ec)) {
        for (const auto& entry : std::filesystem::directory_iterator(thumbDir, ec)) {
            if (entry.is_regular_file(ec)) {
                auto ext = entry.path().extension();
                if (ext == ".mp4" || ext == ".tmp") {
                    freed += entry.file_size(ec);
                    std::filesystem::remove(entry.path(), ec);
                    deleted++;
                }
            }
        }
    }
    refreshStorageStats();
    double freedMb = static_cast<double>(freed) / (1024.0 * 1024.0);
    char buf[128];
    snprintf(buf, sizeof(buf), "Очищен кэш видео: %d файлов (%.1f MB)", deleted, freedMb);
    m_statusNotification = buf;
    m_notificationFramesRemaining = 120;
}

// ----------------- Feature 7: Batch Multi-Select Checklist -----------------

void App::toggleBatchSelection(const std::string& titleId) {
    if (titleId.empty()) return;
    if (m_batchSelectedTitleIds.count(titleId) > 0) {
        m_batchSelectedTitleIds.erase(titleId);
        m_statusNotification = "Снято выделение с игры";
    } else {
        m_batchSelectedTitleIds.insert(titleId);
        m_statusNotification = "✓ Игра выбрана (Всего: " + std::to_string(m_batchSelectedTitleIds.size()) + " шт.)";
    }
    m_notificationFramesRemaining = 90;
}

void App::clearBatchSelection() {
    m_batchSelectedTitleIds.clear();
    m_statusNotification = "Пакетный выбор очищен";
    m_notificationFramesRemaining = 90;
}

void App::installBatchSelected() {
    if (m_batchSelectedTitleIds.empty()) return;
    int queuedCount = 0;

    for (const auto& tid : m_batchSelectedTitleIds) {
        const auto* entry = m_catalogManager.findByTitleId(tid);
        
        if (!entry || entry->variants.empty()) continue;

        const Variant* chosenVariant = &entry->variants[0];
        for (const auto& v : entry->variants) {
            if (isVariantFavorite(tid, v.id)) {
                chosenVariant = &v;
                break;
            }
        }

        InstalledTitle targetTitle;
        bool found = false;
        for (const auto& ig : m_installedGames) {
            if (ig.titleId == tid) {
                targetTitle = ig;
                found = true;
                break;
            }
        }
        if (!found) {
            targetTitle.titleId = tid;
            targetTitle.name = entry->title;
            targetTitle.hasCatalogMatch = true;
            targetTitle.catalogEntry = *entry;
        }

        bool alreadyInQueue = false;
        {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            for (const auto& t : m_downloadQueue) {
                if (t.titleId == tid && t.state != TaskState::Failed && t.state != TaskState::Completed) {
                    alreadyInQueue = true;
                    break;
                }
            }
        }

        if (!alreadyInQueue) {
            queueDownload(targetTitle, *chosenVariant);
            queuedCount++;
        }
    }

    m_batchSelectedTitleIds.clear();
    m_activeTab = Tab::Downloads;
    m_statusNotification = "Добавлено в очередь загрузки: " + std::to_string(queuedCount) + " игр";
    m_notificationFramesRemaining = 150;
}


void App::handleTouchTap(int mx, int my) {
// If dialog is open, handle direct taps on dialog buttons
            if (m_activeDialog != DialogType::None) {
                int dw = 700;
                int dh = 270;
                int dx = (Theme::SCREEN_WIDTH - dw) / 2;
                int dy = (Theme::SCREEN_HEIGHT - dh) / 2;
                int btnY = dy + 190;

                if (m_activeDialog == DialogType::MessageAlert || m_activeDialog == DialogType::IntegrityCheckResult) {
                    if (mx >= dx + 260 && mx <= dx + 440 && my >= dy + 190 && my <= dy + 240) {
                        m_activeDialog = DialogType::None;
                    } else if (mx < dx || mx > dx + dw || my < dy || my > dy + dh) {
                        m_activeDialog = DialogType::None;
                    }
                } else if (m_activeDialog == DialogType::UpdateSuccess) {
                    if (mx >= dx + 240 && mx <= dx + 460 && my >= dy + 190 && my <= dy + 245) {
                        onButtonPress(0 /* A - Restart */);
                    }
                } else {
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
                }
                return;
            }

            // If Fullscreen Preview is active, handle touch HUD buttons and swipe/taps
            if (m_isFullscreenPreview) {
                int hudX = 40;
                int hudY = 585;
                if (mx >= hudX + 900 && mx <= hudX + 1170 && my >= hudY + 14 && my <= hudY + 52) {
                    onButtonPress(0 /* A - Install / Save */);
                } else if (mx >= hudX + 690 && mx <= hudX + 885 && my >= hudY + 14 && my <= hudY + 52) {
                    onButtonPress(9 /* L - Favorite */);
                } else if (mx >= hudX + 540 && mx <= hudX + 750 && my >= hudY + 60 && my <= hudY + 95) {
                    onButtonPress(3 /* Y - Assign */);
                } else if (mx <= 120 && my >= 200 && my <= 520) {
                    onButtonPress(13 /* DPAD_LEFT - Prev */);
                } else if (mx >= 1160 && my >= 200 && my <= 520) {
                    onButtonPress(14 /* DPAD_RIGHT - Next */);
                } else {
                    closeFullscreenPreview();
                }
                return;
            }

            // If Game Picker Modal is open, handle touch navigation and selection
            if (m_isGamePickerOpen) {
                int bw = 1140, bh = 600;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeGamePicker();
                } else if (my >= by + 95 && my <= by + 95 + 5 * 88) {
                    int clickedIdx = m_gamePickerScrollOffset + (my - (by + 95)) / 88;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_installedGames.size())) {
                        m_gamePickerSelectedIndex = clickedIdx;
                        onButtonPress(0 /* A - Select Game */);
                    }
                }
                return;
            }

            // If Recordings Browser Modal is open, handle touch
            if (m_isRecordingsBrowserOpen) {
                int bw = 1100, bh = 560;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeRecordingsBrowser();
                } else if (my >= by + 105 && my <= by + 105 + 5 * 74) {
                    int clickedIdx = m_recordingsScrollOffset + (my - (by + 105)) / 74;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_localRecordings.size())) {
                        m_recordingsSelectedIndex = clickedIdx;
                        onButtonPress(0 /* A - Install */);
                    }
                }
                return;
            }

            // If Collection Browser Modal is open, handle touch
            if (m_isCollectionBrowserOpen) {
                int bw = 1220, bh = 660;
                int bx = (Theme::SCREEN_WIDTH - bw) / 2;
                int by = (Theme::SCREEN_HEIGHT - bh) / 2;
                if (mx < bx || mx > bx + bw || my < by || my > by + bh) {
                    closeCollectionBrowser();
                } else {
                    int lx = bx + 25, ly = by + 68, lw = 635;
                    // Left Column: tapping variant item
                    if (mx >= lx && mx <= lx + lw && my >= ly && my <= ly + 5 * 96) {
                        int clickedIdx = m_collectionScrollOffset + (my - ly) / 96;
                        if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_collectionVariants.size())) {
                            m_collectionSelectedIndex = clickedIdx;
                            loadCollectionThumbnail(m_collectionVariants[clickedIdx]);
                        }
                    } else {
                        int rx = bx + 675, ry = by + 68;
                        int px = rx + 20, py = ry + 20, pw = 480, ph = 270;
                        int b1y = py + ph + 80;
                        int b3y = py + ph + 130;

                        // Tap preview thumbnail -> open fullscreen live video
                        if (mx >= px && mx <= px + pw && my >= py && my <= py + ph) {
                            onButtonPress(2 /* X - Video */);
                        }
                        // Button [A] Назначить на игру
                        else if (mx >= px && mx <= px + 230 && my >= b1y && my <= b1y + 42) {
                            onButtonPress(0 /* A - Assign */);
                        }
                        // Button [X] Видео в полный экран
                        else if (mx >= px + 245 && mx <= px + 475 && my >= b1y && my <= b1y + 42) {
                            onButtonPress(2 /* X - Video */);
                        }
                        // Button [L / R3] В избранное (full width 480)
                        else if (mx >= px && mx <= px + 480 && my >= b3y && my <= b3y + 36) {
                            onButtonPress(9 /* L - Favorite */);
                        }
                    }
                }
                return;
            }

            // Top Header tabs: y in [10, 55]
            if (my >= 10 && my <= 55) {
                if (mx >= 340 && mx < 460) m_activeTab = Tab::Home;
                else if (mx >= 460 && mx < 580) m_activeTab = Tab::MyGames;
                else if (mx >= 580 && mx < 700) m_activeTab = Tab::Catalog;
                else if (mx >= 700 && mx < 820) m_activeTab = Tab::Downloads;
                else if (mx >= 820 && mx < 940) m_activeTab = Tab::Settings;
            }
            // Home Tab: 5x Dashboard Tiles at y in [100, 320]
            else if (m_activeTab == Tab::Home && my >= 100 && my <= 320 && mx >= 40 && mx <= 1240) {
                int tileW = 225, tileGap = 14;
                int totalRowW = 5 * tileW + 4 * tileGap;
                int tileStartX = (Theme::SCREEN_WIDTH - totalRowW) / 2;
                int clickedTile = (mx - tileStartX) / (tileW + tileGap);
                if (clickedTile >= 0 && clickedTile <= 4) {
                    if (m_homeFocusedTile == clickedTile) {
                        onButtonPress(0 /* A - Activate selected tile */);
                    } else {
                        m_homeFocusedTile = clickedTile;
                    }
                }
            }
            // Home Tab: Bottom Summary Panel click (y in [368, 626])
            else if (m_activeTab == Tab::Home && my >= 368 && my <= 626 && mx >= 48 && mx <= 1232) {
                onButtonPress(0 /* A - Activate selected tile */);
            }
            // VideoIcons Tab: Search Bar click (x in [290, 910], y in [82, 120])
            else if (m_activeTab == Tab::VideoIcons && mx >= 290 && mx <= 910 && my >= 82 && my <= 120) {
                onButtonPress(3 /* Y - Open VideoIcons Search Keyboard */);
            }
            // VideoIcons Tab: Filter Pill click (x in [925, 1220], y in [82, 120])
            else if (m_activeTab == Tab::VideoIcons && mx >= 925 && mx <= 1220 && my >= 82 && my <= 120) {
                onButtonPress(4 /* Minus - Toggle Filter */);
            }
            // VideoIcons Tab: Item rows click (x in [60, 1220], y in [136, 616])
            else if (m_activeTab == Tab::VideoIcons && mx >= 60 && mx <= 1220 && my >= 136 && my <= 616) {
                int clickedIdx = m_videoIconsScrollOffset + (my - 136) / 96;
                if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_filteredVideoIcons.size())) {
                    m_videoIconsSelectedIndex = clickedIdx;
                    if (mx >= 890 && mx <= 1028) {
                        onButtonPress(2 /* X - Preview */);
                    } else if (mx >= 1035 && mx <= 1205) {
                        onButtonPress(0 /* A - Install */);
                    } else {
                        onButtonPress(2 /* X - Preview on row tap */);
                    }
                }
            }
            // Catalog Categories View: [X] Весь список button click (x in [340, 525], y in [74, 112])
            else if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::Categories && mx >= 340 && mx <= 525 && my >= 74 && my <= 112) {
                onButtonPress(2 /* X - Open Full List View */);
            }
            // Catalog Categories View: Search Bar click (x in [700, 1212], y in [74, 112])
            else if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::Categories && mx >= 700 && mx <= 1212 && my >= 74 && my <= 112) {
                onButtonPress(3 /* Y - Open Search Keyboard */);
            }
            // Catalog Categories View: Main Sections & Genre Cards click
            else if (m_activeTab == Tab::Catalog && m_catalogViewMode == CatalogViewMode::Categories && mx >= 60 && mx <= 1220 && my >= 140 && my <= 650) {
                int cardW = 270, gapX = 22;
                int col = std::clamp((mx - 60) / (cardW + gapX), 0, 3);
                if (my >= 144 && my <= 232) {
                    int idx = col;
                    if (m_categorySelectedIndex == idx) onButtonPress(0 /* A */);
                    else m_categorySelectedIndex = idx;
                } else if (my >= 272 && my <= 650) {
                    int row = (my - 272) / 98;
                    int idx = 4 + row * 4 + col;
                    if (idx >= 4 && idx < 18) {
                        if (m_categorySelectedIndex == idx) onButtonPress(0 /* A */);
                        else m_categorySelectedIndex = idx;
                    }
                }
            }
            // MyGames Tab: synchronized pixel-perfect touch zones
            else if (m_activeTab == Tab::MyGames) {
                // Left Column: Games list item selection (x in [30, 480], y in [105, 640])
                if (mx >= 30 && mx <= 480 && my >= 105 && my <= 640) {
                    int clickedIdx = m_myGamesScrollOffset + (my - 105) / 66;
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_installedGames.size())) {
                        if (m_myGamesSelectedIndex == clickedIdx) {
                            const auto& g = m_installedGames[clickedIdx];
                            if (g.titleId == "0000000000000000" || g.catalogEntry.variants.size() > 8) {
                                openCollectionBrowser(g.catalogEntry);
                            } else if (g.hasCatalogMatch && !g.catalogEntry.variants.empty()) {
                                m_myGamesActivePane = MyGamesPane::VariantsList;
                            }
                        } else {
                            m_myGamesSelectedIndex = clickedIdx;
                            m_selectedVariantIndex = 0;
                            m_variantScrollOffset = 0;
                            m_myGamesActivePane = MyGamesPane::GamesList;
                        }
                    }
                }
                // Right Column Action buttons at y in [200, 240]
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
                }
                // Right Column Variant Cards (y in [280, 600])
                else if (mx >= 525 && mx <= 1225 && my >= 280 && my <= 600) {
                    if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                        const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                        int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                        if (totalV > 0) {
                            int vClicked = m_variantScrollOffset + (my - 280) / 80;
                            if (vClicked >= 0 && vClicked < totalV) {
                                m_selectedVariantIndex = vClicked;
                                m_myGamesActivePane = MyGamesPane::VariantsList;
                                const auto& vChosen = selGame.catalogEntry.variants[vClicked];
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
                                }
                            }
                        } else {
                            // No direct variants: "Открыть каталог" button at x in [530, 1010], y in [350, 410]
                            if (mx >= 530 && mx <= 1010 && my >= 350 && my <= 410) {
                                m_activeTab = Tab::Catalog;
                            }
                        }
                    }
                }
            }
            // Downloads Tab: interactive touch controls
            else if (m_activeTab == Tab::Downloads) {
                // Footer action buttons at y in [660, 720]
                if (my >= 660 && my <= 720) {
                    if (mx >= 130 && mx <= 310) {
                        onButtonPress(0 /* A - Retry failed */);
                    } else if (mx >= 350 && mx <= 500) {
                        onButtonPress(2 /* X - Clear */);
                    } else if (mx >= 510 && mx <= 740) {
                        onButtonPress(3 /* Y - Install all missing */);
                    } else if (mx >= 750 && mx <= 860) {
                        onButtonPress(1 /* B - Back */);
                    }
                }
                // Tapping directly on a failed card or its [ Ошибка ] button to retry it: y in [160, 640]
                else if (my >= 160 && my <= 640 && mx >= 60 && mx <= 1220) {
                    int clickedIdx = m_downloadsScrollOffset + (my - 160) / 94;
                    std::lock_guard<std::mutex> lock(m_queueMutex);
                    if (clickedIdx >= 0 && clickedIdx < static_cast<int>(m_downloadQueue.size())) {
                        if (m_downloadQueue[clickedIdx].state == TaskState::Failed) {
                            m_downloadQueue[clickedIdx].state = TaskState::Pending;
                            m_downloadQueue[clickedIdx].errorMessage.clear();
                            m_statusNotification = (m_language == Language::Russian)
                                ? "Перезапуск задачи..."
                                : "Retrying task...";
                            m_notificationFramesRemaining = 90;
                        }
                    }
                }
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
            // Catalog Tab: click directly on an item in the list or batch banner
            else if (m_activeTab == Tab::Catalog && mx >= 60 && mx <= 1220 && my >= 160 && my <= 660) {
                // Check if clicked on floating action banner
                if (!m_batchSelectedTitleIds.empty() && my >= 610 && my <= 660 && mx >= 200 && mx <= 1080) {
                    if (mx >= 460 && mx <= 710) {
                        installBatchSelected();
                    } else if (mx >= 715 && mx <= 860) {
                        clearBatchSelection();
                    }
                } else {
                    int clickedIndex = m_catalogScrollOffset + (my - 160) / 94;
                    int totalGames = static_cast<int>(m_filteredCatalogGames.size());
                    if (clickedIndex >= 0 && clickedIndex < totalGames) {
                        // Tapping checkbox on left toggles batch selection
                        if (mx >= 60 && mx <= 120) {
                            toggleBatchSelection(m_filteredCatalogGames[clickedIndex].titleId);
                        } else if (m_catalogSelectedIndex == clickedIndex || mx >= 915) {
                            m_catalogSelectedIndex = clickedIndex;
                            openCollectionBrowser(m_filteredCatalogGames[clickedIndex]);
                        } else {
                            m_catalogSelectedIndex = clickedIndex;
                        }
                    }
                }
            }
            // Settings Tab: interactive setting rows at y in [230, 615]
            else if (m_activeTab == Tab::Settings && mx >= 50 && mx <= 1230 && my >= 230 && my <= 615) {
                int clickedRow = (my - 236) / 54;
                if (clickedRow >= 0 && clickedRow <= 6) {
                    m_settingsSelectedIndex = clickedRow;
                    onButtonPress(0 /* A - Activate Setting */);
                }
            }
            // Footer bar click on refresh: y in [660, 720]
            else if (my >= 660 && mx >= 1050) {
                onButtonPress(4 /* Minus / Refresh */);
            }
}

void App::handleTouchDrag(int startX, int startY, int deltaY) {
    m_touchDragAccumulator += deltaY;

    // Smooth half-row threshold (48px) for natural, fluid scrolling on Switch screen
    const int scrollThreshold = 48;

    while (m_touchDragAccumulator <= -scrollThreshold) {
        // Dragging UP -> scroll DOWN
        m_touchDragAccumulator += scrollThreshold;
        if (m_isCollectionBrowserOpen) {
            if (m_collectionScrollOffset + 5 < static_cast<int>(m_collectionVariants.size())) {
                m_collectionScrollOffset++;
                if (m_collectionSelectedIndex < m_collectionScrollOffset) {
                    m_collectionSelectedIndex = m_collectionScrollOffset;
                }
            }
        } else if (m_isGamePickerOpen) {
            if (m_gamePickerScrollOffset + 5 < static_cast<int>(m_installedGames.size())) {
                m_gamePickerScrollOffset++;
                if (m_gamePickerSelectedIndex < m_gamePickerScrollOffset) {
                    m_gamePickerSelectedIndex = m_gamePickerScrollOffset;
                }
            }
        } else if (m_isRecordingsBrowserOpen) {
            if (m_recordingsScrollOffset + 5 < static_cast<int>(m_localRecordings.size())) {
                m_recordingsScrollOffset++;
                if (m_recordingsSelectedIndex < m_recordingsScrollOffset) {
                    m_recordingsSelectedIndex = m_recordingsScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::Catalog && startY >= 130 && startY <= 670) {
            if (m_catalogScrollOffset + 5 < static_cast<int>(m_filteredCatalogGames.size())) {
                m_catalogScrollOffset++;
                if (m_catalogSelectedIndex < m_catalogScrollOffset) {
                    m_catalogSelectedIndex = m_catalogScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {
            if (m_myGamesScrollOffset + 8 < static_cast<int>(m_installedGames.size())) {
                m_myGamesScrollOffset++;
                if (m_myGamesSelectedIndex < m_myGamesScrollOffset) {
                    m_myGamesSelectedIndex = m_myGamesScrollOffset;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 500 && startX <= 1250) {
            if (m_myGamesSelectedIndex >= 0 && m_myGamesSelectedIndex < static_cast<int>(m_installedGames.size())) {
                const auto& selGame = m_installedGames[m_myGamesSelectedIndex];
                int totalV = selGame.hasCatalogMatch ? static_cast<int>(selGame.catalogEntry.variants.size()) : 0;
                if (m_variantScrollOffset + 4 < totalV) {
                    m_variantScrollOffset++;
                    if (m_selectedVariantIndex < m_variantScrollOffset) {
                        m_selectedVariantIndex = m_variantScrollOffset;
                    }
                }
            }
        }
    }

    while (m_touchDragAccumulator >= scrollThreshold) {
        // Dragging DOWN -> scroll UP
        m_touchDragAccumulator -= scrollThreshold;
        if (m_isCollectionBrowserOpen) {
            if (m_collectionScrollOffset > 0) {
                m_collectionScrollOffset--;
                if (m_collectionSelectedIndex >= m_collectionScrollOffset + 5) {
                    m_collectionSelectedIndex = m_collectionScrollOffset + 4;
                }
            }
        } else if (m_isGamePickerOpen) {
            if (m_gamePickerScrollOffset > 0) {
                m_gamePickerScrollOffset--;
                if (m_gamePickerSelectedIndex >= m_gamePickerScrollOffset + 5) {
                    m_gamePickerSelectedIndex = m_gamePickerScrollOffset + 4;
                }
            }
        } else if (m_isRecordingsBrowserOpen) {
            if (m_recordingsScrollOffset > 0) {
                m_recordingsScrollOffset--;
                if (m_recordingsSelectedIndex >= m_recordingsScrollOffset + 5) {
                    m_recordingsSelectedIndex = m_recordingsScrollOffset + 4;
                }
            }
        } else if (m_activeTab == Tab::Catalog && startY >= 130 && startY <= 670) {
            if (m_catalogScrollOffset > 0) {
                m_catalogScrollOffset--;
                if (m_catalogSelectedIndex >= m_catalogScrollOffset + 5) {
                    m_catalogSelectedIndex = m_catalogScrollOffset + 4;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 30 && startX <= 480) {
            if (m_myGamesScrollOffset > 0) {
                m_myGamesScrollOffset--;
                if (m_myGamesSelectedIndex >= m_myGamesScrollOffset + 8) {
                    m_myGamesSelectedIndex = m_myGamesScrollOffset + 7;
                }
            }
        } else if (m_activeTab == Tab::MyGames && startX >= 500 && startX <= 1250) {
            if (m_variantScrollOffset > 0) {
                m_variantScrollOffset--;
                if (m_selectedVariantIndex >= m_variantScrollOffset + 4) {
                    m_selectedVariantIndex = m_variantScrollOffset + 3;
                }
            }
        }
    }
}

void App::handleTouchSwipe(int startX, int startY, int endX, int endY) {
    int diffX = endX - startX;
    int diffY = endY - startY;

    if (m_isFullscreenPreview) {
        if (diffX < -60) {
            // Swiped Left -> Next Video
            onButtonPress(14 /* DPAD_RIGHT - Next */);
        } else if (diffX > 60) {
            // Swiped Right -> Prev Video
            onButtonPress(13 /* DPAD_LEFT - Prev */);
        } else if (diffY > 80) {
            // Swiped Down -> Close Preview
            closeFullscreenPreview();
        }
    }
}

void App::drawCircle(int cx, int cy, int r, Color col, bool fill) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    SDL_SetRenderDrawColor(m_renderer, col.r, col.g, col.b, col.a);
    if (fill) {
        for (int dy = -r; dy <= r; ++dy) {
            int dx = static_cast<int>(std::sqrt(std::max(0, r * r - dy * dy)));
            SDL_RenderDrawLine(m_renderer, cx - dx, cy + dy, cx + dx, cy + dy);
        }
    } else {
        int x = r;
        int y = 0;
        int err = 0;
        while (x >= y) {
            SDL_RenderDrawPoint(m_renderer, cx + x, cy + y);
            SDL_RenderDrawPoint(m_renderer, cx + y, cy + x);
            SDL_RenderDrawPoint(m_renderer, cx - y, cy + x);
            SDL_RenderDrawPoint(m_renderer, cx - x, cy + y);
            SDL_RenderDrawPoint(m_renderer, cx - x, cy - y);
            SDL_RenderDrawPoint(m_renderer, cx - y, cy - x);
            SDL_RenderDrawPoint(m_renderer, cx + y, cy - x);
            SDL_RenderDrawPoint(m_renderer, cx + x, cy - y);
            if (err <= 0) {
                y += 1;
                err += 2 * y + 1;
            }
            if (err > 0) {
                x -= 1;
                err -= 2 * x + 1;
            }
        }
    }
#else
    (void)cx; (void)cy; (void)r; (void)col; (void)fill;
#endif
}

void App::drawButtonBadge(int x, int y, const std::string& key, const std::string& label, Color badgeCol) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    int r = 10;
    int circleCx = x + 10;
    int circleCy = y + 10;

    // Dark circular badge plate
    drawCircle(circleCx, circleCy, r, {0x18, 0x22, 0x34, 0xFF}, true);
    drawCircle(circleCx, circleCy, r, badgeCol, false);

    // Centered button letter (+, -, A, B, X, Y)
    int keyX = (key.length() == 1) ? (circleCx - 4) : (circleCx - 7);
    drawText(key, keyX, circleCy - 7, badgeCol, 12);

    // Label text
    drawText(label, circleCx + r + 7, y + 2, Theme::COLOR_TEXT_PRIMARY, 13);
#else
    (void)x; (void)y; (void)key; (void)label; (void)badgeCol;
#endif
}

void App::drawTileIconVector(int cx, int cy, int tileIdx, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color accent = isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY;

    if (tileIdx == 0) { // Каталог: 4IFIR Cartridge + Storefront (Cyan & Magenta)
        drawRect(cx - 36, cy - 22, 24, 38, {0x13, 0x1B, 0x2E, 0xFF});
        drawRectOutline(cx - 36, cy - 22, 24, 38, Theme::COLOR_FOCUS_CYAN, 1);
        drawRect(cx - 34, cy - 20, 20, 7, Theme::COLOR_FOCUS_PINK); // 4IFIR Magenta label
        drawRect(cx - 34, cy - 10, 20, 20, {0x0B, 0x10, 0x1B, 0xFF});

        drawRect(cx - 4, cy - 14, 40, 30, {0x13, 0x1B, 0x2E, 0xFF});
        drawRectOutline(cx - 4, cy - 14, 40, 30, accent, 1);
        drawRect(cx - 6, cy - 20, 44, 7, Theme::COLOR_FOCUS_CYAN);
        for (int s = 0; s < 4; ++s) {
            drawRect(cx - 4 + s * 11, cy - 20, 5, 7, Theme::COLOR_FOCUS_PINK);
        }
        drawRect(cx + 4, cy - 3, 10, 19, {0x00, 0xD2, 0xFF, 0x55});
        drawRect(cx + 20, cy - 3, 12, 12, {0xEC, 0x48, 0x99, 0x66});
    } else if (tileIdx == 1) { // Видеоиконки: 4IFIR 1:1 Animated Square Frame
        drawRect(cx - 32, cy - 30, 64, 60, {0x11, 0x18, 0x27, 0xFF});
        drawNeonGradientOutline(cx - 32, cy - 30, 64, 60, 2);
        // Play triangle in Electric Cyan
        for (int row = -10; row <= 10; ++row) {
            int w = 14 - std::abs(row);
            drawRect(cx - 5, cy - 4 + row, w, 1, Theme::COLOR_FOCUS_CYAN);
        }
        drawRect(cx - 24, cy + 12, 48, 12, Theme::COLOR_FOCUS_PINK);
        drawText("256x256", cx - 20, cy + 13, Theme::COLOR_TEXT_PRIMARY, 9);
    } else if (tileIdx == 2) { // Менеджер игр: 4IFIR Case labeled "MY GAMES"
        drawRect(cx - 30, cy - 14, 60, 40, {0x13, 0x1B, 0x2E, 0xFF});
        drawRectOutline(cx - 30, cy - 14, 60, 40, accent, 1);
        drawRect(cx - 22, cy - 25, 18, 14, Theme::COLOR_FOCUS_PINK);
        drawRect(cx - 1, cy - 27, 18, 16, Theme::COLOR_FOCUS_CYAN);
        drawRect(cx + 12, cy - 24, 14, 13, {0xA8, 0x55, 0xF7, 0xFF});
        drawRect(cx - 20, cy + 6, 40, 12, {0x09, 0x0D, 0x16, 0xEE});
        drawRectOutline(cx - 20, cy + 6, 40, 12, Theme::COLOR_FOCUS_CYAN, 1);
        drawText("MY GAMES", cx - 18, cy + 8, Theme::COLOR_FOCUS_CYAN, 10);
    } else if (tileIdx == 3) { // Загрузки: 4IFIR Switch Console (Cyan & Magenta Joy-Cons)
        drawRect(cx - 36, cy - 14, 10, 36, Theme::COLOR_FOCUS_CYAN);
        drawCircle(cx - 31, cy - 4, 3, {0x09, 0x0D, 0x16, 0xFF}, true);
        drawRect(cx - 24, cy - 16, 48, 40, {0x0B, 0x10, 0x1B, 0xFF});
        drawRectOutline(cx - 24, cy - 16, 48, 40, Theme::COLOR_FOCUS_CYAN, 1);
        drawRect(cx + 26, cy - 14, 10, 36, Theme::COLOR_FOCUS_PINK);
        drawCircle(cx + 31, cy + 8, 3, {0x09, 0x0D, 0x16, 0xFF}, true);

        // Download Arrow pointing into screen
        drawRect(cx - 4, cy - 28, 8, 22, Theme::COLOR_FOCUS_CYAN);
        for (int row = 0; row < 10; ++row) {
            drawRect(cx - row, cy - 6 + row, 2 * row + 1, 1, Theme::COLOR_FOCUS_CYAN);
        }
    } else if (tileIdx == 4) { // Настройки: Cyber Cogwheel Gear (Screenshot 1)
        int rOut = 24;
        int rIn = 11;
        // Gear teeth (8 teeth)
        for (int i = 0; i < 8; ++i) {
            double angle = i * (3.14159265 / 4.0);
            int tx = cx + static_cast<int>(std::cos(angle) * 20);
            int ty = cy + static_cast<int>(std::sin(angle) * 20);
            drawRect(tx - 4, ty - 4, 8, 8, accent);
        }
        // Central hub
        drawCircle(cx, cy, rOut, {0x26, 0x30, 0x44, 0xFF}, true);
        drawCircle(cx, cy, rOut, accent, false);
        drawCircle(cx, cy, rIn, {0x11, 0x18, 0x27, 0xFF}, true);
        drawCircle(cx, cy, 5, Theme::COLOR_FOCUS_CYAN, true);
    }
#endif
}

void App::drawCategoryEmblem(int cx, int cy, const std::string& iconType, Color col) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    if (iconType == "all_catalog") {
        // 2x2 Rounded Grid Squares
        int s = 9, g = 4;
        for (int r = 0; r < 2; ++r) {
            for (int c = 0; c < 2; ++c) {
                int qx = cx - s - g / 2 + c * (s + g);
                int qy = cy - s - g / 2 + r * (s + g);
                drawRect(qx, qy, s, s, col);
            }
        }
    } else if (iconType == "favorites") {
        // 5-point Star
        drawCircle(cx, cy, 10, col, true);
        drawCircle(cx, cy - 8, 4, col, true);
        drawCircle(cx + 8, cy - 2, 4, col, true);
        drawCircle(cx - 8, cy - 2, 4, col, true);
        drawCircle(cx + 5, cy + 7, 4, col, true);
        drawCircle(cx - 5, cy + 7, 4, col, true);
    } else if (iconType == "new_release") {
        // 4-point Sparkle Diamond
        for (int i = 0; i <= 14; ++i) {
            int w = 14 - i;
            drawRect(cx - w / 2, cy - 14 + i, w, 1, col);
            drawRect(cx - w / 2, cy + 14 - i, w, 1, col);
        }
    } else if (iconType == "top_100") {
        // Golden Trophy
        drawRect(cx - 8, cy - 12, 16, 12, col);
        drawRect(cx - 3, cy, 6, 8, col);
        drawRect(cx - 9, cy + 8, 18, 4, col);
        drawRectOutline(cx - 12, cy - 10, 24, 7, col, 2); // handles
    } else if (iconType == "action_adventure") {
        // Crossed Broadswords
        SDL_SetRenderDrawColor(m_renderer, col.r, col.g, col.b, col.a);
        for (int d = -1; d <= 1; ++d) {
            SDL_RenderDrawLine(m_renderer, cx - 12 + d, cy - 12, cx + 12 + d, cy + 12);
            SDL_RenderDrawLine(m_renderer, cx + 12 + d, cy - 12, cx - 12 + d, cy + 12);
        }
        drawRect(cx - 9, cy - 4, 6, 6, col);
        drawRect(cx + 3, cy - 4, 6, 6, col);
    } else if (iconType == "arcade") {
        // Joystick Base + Stick + Ball
        drawRect(cx - 12, cy + 3, 24, 10, col);
        drawRect(cx - 2, cy - 8, 4, 11, col);
        drawCircle(cx, cy - 9, 6, col, true);
    } else if (iconType == "horror") {
        // Skull
        drawCircle(cx, cy - 2, 11, col, true);
        drawRect(cx - 6, cy + 4, 12, 9, col);
        // Hollow eye sockets
        drawCircle(cx - 4, cy - 2, 3, {0x14, 0x1A, 0x28, 0xFF}, true);
        drawCircle(cx + 4, cy - 2, 3, {0x14, 0x1A, 0x28, 0xFF}, true);
    } else if (iconType == "metroidvania") {
        // Concentric Radar Rings
        drawCircle(cx, cy, 14, col, false);
        drawCircle(cx, cy, 8, col, false);
        drawCircle(cx, cy, 3, col, true);
    } else if (iconType == "party_multiplayer") {
        // Dual Gamepads
        drawRect(cx - 12, cy - 8, 16, 10, col);
        drawRect(cx - 4, cy + 1, 16, 10, col);
        drawCircle(cx - 8, cy - 3, 2, {0x14, 0x1A, 0x28, 0xFF}, true);
        drawCircle(cx + 8, cy + 6, 2, {0x14, 0x1A, 0x28, 0xFF}, true);
    } else if (iconType == "platformers") {
        // Platform + Jump Arc
        drawRect(cx - 14, cy + 8, 28, 4, col);
        drawCircle(cx, cy - 2, 9, col, false);
        drawRect(cx - 10, cy - 2, 20, 10, {0x14, 0x1A, 0x28, 0xFF}); // mask lower half
    } else if (iconType == "puzzles") {
        // Jigsaw Puzzle Piece
        drawRect(cx - 9, cy - 9, 18, 18, col);
        drawCircle(cx, cy - 9, 4, col, true);
        drawCircle(cx + 9, cy, 4, col, true);
    } else if (iconType == "roguelike_roguelite") {
        // D6 Die with dots
        drawRect(cx - 10, cy - 10, 20, 20, col);
        Color dotCol = {0x14, 0x1A, 0x28, 0xFF};
        drawCircle(cx - 5, cy - 5, 2, dotCol, true);
        drawCircle(cx + 5, cy + 5, 2, dotCol, true);
        drawCircle(cx, cy, 2, dotCol, true);
        drawCircle(cx - 5, cy + 5, 2, dotCol, true);
        drawCircle(cx + 5, cy - 5, 2, dotCol, true);
    } else if (iconType == "rpg_jrpg") {
        // Cut Crystal Gem
        for (int i = 0; i <= 14; ++i) {
            int w = (i < 6) ? (8 + i * 2) : (20 - (i - 6) * 2);
            drawRect(cx - w / 2, cy - 10 + i, w, 1, col);
        }
    } else if (iconType == "shooters") {
        // Crosshair Reticle
        drawCircle(cx, cy, 12, col, false);
        SDL_SetRenderDrawColor(m_renderer, col.r, col.g, col.b, col.a);
        SDL_RenderDrawLine(m_renderer, cx - 15, cy, cx + 15, cy);
        SDL_RenderDrawLine(m_renderer, cx, cy - 15, cx, cy + 15);
        drawCircle(cx, cy, 2, col, true);
    } else if (iconType == "simulation_cozy") {
        // Leaf
        drawCircle(cx, cy, 10, col, true);
        drawRect(cx - 2, cy + 5, 4, 7, col);
    } else if (iconType == "strategy_tactics") {
        // Chess Rook / Castle Tower
        drawRect(cx - 8, cy - 10, 16, 5, col);
        drawRect(cx - 6, cy - 5, 12, 12, col);
        drawRect(cx - 9, cy + 7, 18, 4, col);
        drawRect(cx - 2, cy - 10, 4, 3, {0x14, 0x1A, 0x28, 0xFF}); // center embrasure
    } else if (iconType == "visual_novels") {
        // Open Book
        drawRect(cx - 12, cy - 7, 11, 14, col);
        drawRect(cx + 1, cy - 7, 11, 14, col);
        drawRect(cx - 1, cy - 8, 2, 16, {0x14, 0x1A, 0x28, 0xFF});
    } else { // "ports_homebrew"
        // Switch Console
        drawRect(cx - 12, cy - 7, 24, 14, col);
        drawRect(cx - 6, cy - 5, 12, 10, {0x14, 0x1A, 0x28, 0xFF});
    }
#endif
}

void App::drawDashboardTile(int x, int y, int w, int h, int tileIdx, const std::string& title, const std::string& sub, bool isFocused) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    Color bg = isFocused ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_TILE;
    drawRect(x, y, w, h, bg);

    if (isFocused) {
        drawRect(x, y, w, h, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(x, y, w, h, 2);
    } else {
        drawRectOutline(x, y, w, h, Theme::COLOR_BORDER, 1);
    }

    // Centered vector icon in upper area of tile (matching Screenshot 1)
    int iconCx = x + w / 2;
    int iconCy = y + 72;
    drawTileIconVector(iconCx, iconCy, tileIdx, isFocused);

    // Centered Title underneath (clean typography, no clutter)
    int textLen = static_cast<int>(title.length()) * 8; // approx width estimation
    int titleX = std::max(x + 10, x + (w - textLen) / 2);
    drawText(title, titleX, y + h - 36, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 16);
#else
    (void)x; (void)y; (void)w; (void)h; (void)tileIdx; (void)title; (void)sub; (void)isFocused;
#endif
}

void App::drawSummaryCard(int x, int y, int w, int h, const std::string& header, const std::string& line1, const std::string& line2, const std::string& badgeText) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    drawRect(x, y, w, h, Theme::COLOR_BG_SURFACE);
    drawRectOutline(x, y, w, h, Theme::COLOR_BORDER, 1);

    drawRect(x + 16, y + 18, 3, 16, Theme::COLOR_FOCUS_CYAN);
    drawText(header, x + 26, y + 16, Theme::COLOR_TEXT_MUTED, 13);

    drawText(line1, x + 20, y + 54, Theme::COLOR_TEXT_PRIMARY, 20);
    drawText(line2, x + 20, y + 92, Theme::COLOR_TEXT_MUTED, 13);

    if (!badgeText.empty()) {
        int badgeW = static_cast<int>(badgeText.length()) * 8 + 18;
        int badgeX = x + w - badgeW - 18;
        int badgeY = y + 16;
        drawRect(badgeX, badgeY, badgeW, 24, Theme::COLOR_FOCUS_FILL);
        drawRectOutline(badgeX, badgeY, badgeW, 24, Theme::COLOR_FOCUS_CYAN, 1);
        drawText(badgeText, badgeX + 9, badgeY + 4, Theme::COLOR_FOCUS_CYAN, 11);
    }
#else
    (void)x; (void)y; (void)w; (void)h; (void)header; (void)line1; (void)line2; (void)badgeText;
#endif
}

void App::drawCategoryCard(int x, int y, int w, int h, const std::string& iconType, const std::string& title, const std::string& desc, const std::string& countText, bool isFocused, Color accentCol) {
#ifdef HAS_SDL2
    if (!m_renderer) return;

    Color bg = isFocused ? Theme::COLOR_BG_ELEVATED : Theme::COLOR_BG_SURFACE;
    drawRect(x, y, w, h, bg);

    if (isFocused) {
        drawRect(x, y, w, h, Theme::COLOR_FOCUS_FILL);
        drawNeonGradientOutline(x, y, w, h, 2);
    } else {
        drawRectOutline(x, y, w, h, Theme::COLOR_BORDER, 1);
    }

    // Left Emblem Container (52x52 rounded box)
    int emSize = 52;
    int emX = x + 12;
    int emY = y + (h - emSize) / 2;
    drawRect(emX, emY, emSize, emSize, {0x14, 0x1A, 0x28, 0xFF});
    drawRectOutline(emX, emY, emSize, emSize, accentCol, 1);

    // Vector Emblem inside container (TorrentShopNX style)
    int emCx = emX + emSize / 2;
    int emCy = emY + emSize / 2;
    drawCategoryEmblem(emCx, emCy, iconType, accentCol);

    // Text info on the right
    int textX = emX + emSize + 12;
    drawText(title, textX, y + 12, isFocused ? Theme::COLOR_FOCUS_CYAN : Theme::COLOR_TEXT_PRIMARY, 15);
    drawText(desc, textX, y + 36, Theme::COLOR_TEXT_MUTED, 12, w - (textX - x) - 10);

    // Count Pill
    int badgeW = static_cast<int>(countText.length()) * 8 + 16;
    int badgeX = textX;
    int badgeY = y + 62;
    drawRect(badgeX, badgeY, badgeW, 22, Theme::COLOR_FOCUS_FILL);
    drawRectOutline(badgeX, badgeY, badgeW, 22, accentCol, 1);
    drawText(countText, badgeX + 8, badgeY + 3, accentCol, 11);
#else
    (void)x; (void)y; (void)w; (void)h; (void)iconType; (void)title; (void)desc; (void)countText; (void)isFocused; (void)accentCol;
#endif
}

void App::drawPillButton(int x, int y, int w, int h, const std::string& text, bool isFocused, Color textCol) {
#ifdef HAS_SDL2
    if (!m_renderer) return;
    Color bg = isFocused ? Theme::COLOR_FOCUS_FILL : Theme::COLOR_PILL_BG;
    drawRect(x, y, w, h, bg);
    if (isFocused) {
        drawNeonGradientOutline(x, y, w, h, 2);
    } else {
        drawRectOutline(x, y, w, h, Theme::COLOR_BORDER, 1);
    }
    drawText(text, x + 12, y + (h - 14) / 2, textCol, 13);
#else
    (void)x; (void)y; (void)w; (void)h; (void)text; (void)isFocused; (void)textCol;
#endif
}

bool App::isIconInstalled(const std::string& titleId) const {
    if (!m_platform) return false;
    std::string iconPath = m_platform->getIconsDirectory() + "/" + Config::getTargetIconFileName(titleId);
    std::error_code ec;
    return std::filesystem::exists(iconPath, ec);
}

void App::rebuildVideoIconsFilter() {
    m_filteredVideoIcons.clear();
    std::string q = utf8ToLower(m_videoIconsSearchQuery);

    for (const auto& entry : m_videoIconsCatalog) {
        if (m_videoIconsFilterMode == 1 && !isIconInstalled(entry.titleId)) {
            continue;
        }
        if (m_videoIconsFilterMode == 2 && isIconInstalled(entry.titleId)) {
            continue;
        }

        if (!q.empty()) {
            std::string t = utf8ToLower(entry.title);
            std::string id = utf8ToLower(entry.titleId);
            if (t.find(q) == std::string::npos && id.find(q) == std::string::npos) {
                continue;
            }
        }

        m_filteredVideoIcons.push_back(entry);
    }

    if (m_videoIconsSelectedIndex >= static_cast<int>(m_filteredVideoIcons.size())) {
        m_videoIconsSelectedIndex = std::max(0, static_cast<int>(m_filteredVideoIcons.size()) - 1);
    }
}

void App::openVideoIconsKeyboard() {
#ifdef __SWITCH__
    SwkbdConfig kbd;
    char textBuf[256] = {0};
    if (!m_videoIconsSearchQuery.empty()) {
        strncpy(textBuf, m_videoIconsSearchQuery.c_str(), sizeof(textBuf) - 1);
    }

    Result rc = swkbdCreate(&kbd, 0);
    if (R_SUCCEEDED(rc)) {
        swkbdConfigMakePresetDefault(&kbd);
        swkbdConfigSetHeaderText(&kbd, "Поиск видеоиконок 4IFIR");
        swkbdConfigSetGuideText(&kbd, "Введите название игры или TitleID");
        swkbdConfigSetOkButtonText(&kbd, "Поиск");
        swkbdConfigSetInitialText(&kbd, textBuf);
        swkbdConfigSetStringLenMax(&kbd, 64);

        rc = swkbdShow(&kbd, textBuf, sizeof(textBuf));
        if (R_SUCCEEDED(rc)) {
            m_videoIconsSearchQuery = std::string(textBuf);
            rebuildVideoIconsFilter();
        }
        swkbdClose(&kbd);
    }
#else
    m_videoIconsSearchQuery.clear();
    rebuildVideoIconsFilter();
#endif
}

void App::openFullscreenVideoIconPreview(const GameCatalogEntry& entry, int variantIndex) {
#ifdef HAS_SDL2
    if (entry.variants.empty()) return;

    std::vector<Variant> iconVars;
    for (const auto& v : entry.variants) {
        if (v.hasIcon && !v.iconUrl.empty()) {
            Variant iv = v;
            iv.url = v.iconUrl;
            iv.width = (v.iconWidth > 0) ? v.iconWidth : 256;
            iv.height = (v.iconHeight > 0) ? v.iconHeight : 256;
            if (iv.iconSizeBytes > 0) iv.sizeBytes = iv.iconSizeBytes;
            if (iv.previewUrl.empty() || iv.id.rfind("icon-", 0) != 0) {
                size_t idPos = iv.iconUrl.find("id=");
                if (idPos != std::string::npos) {
                    std::string drvId = iv.iconUrl.substr(idPos + 3);
                    size_t amp = drvId.find('&');
                    if (amp != std::string::npos) drvId = drvId.substr(0, amp);
                    iv.previewUrl = "https://drive.google.com/thumbnail?id=" + drvId + "&sz=w640";
                }
            }
            iconVars.push_back(iv);
        }
    }
    if (iconVars.empty()) {
        iconVars = entry.variants;
    }

    int vIdx = std::clamp(variantIndex, 0, static_cast<int>(iconVars.size()) - 1);

    m_previewTitleId = entry.titleId;
    m_previewGameName = entry.title;
    m_previewVariants = iconVars;
    m_previewVariantIndex = vIdx;
    m_previewIsGameInstalled = true;
    m_previewHasInstalledCover = isIconInstalled(entry.titleId);
    m_previewIsIconSquare = true;
    m_previewInstalledCoverPath = m_platform->getIconsDirectory() + "/" + Config::getTargetIconFileName(entry.titleId);
    m_isFullscreenPreview = true;
    m_previewOpenedAt = SDL_GetTicks();

    loadPreviewTexture(m_previewTitleId, m_previewVariants[m_previewVariantIndex]);
#else
    (void)entry; (void)variantIndex;
#endif
}

void App::checkForUpdates(bool manualTrigger) {
    (void)manualTrigger;
    updateApplicationNro();
}

} // namespace ui
} // namespace h3h
