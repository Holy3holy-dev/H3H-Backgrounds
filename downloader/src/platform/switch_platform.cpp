#include "platform/platform_interface.hpp"
#include "core/config.hpp"
#include "core/installer.hpp"

#ifdef __SWITCH__
#include <switch.h>
#include <curl/curl.h>
#include <sys/statvfs.h>
#include <cstdio>
#include <cstring>
#include <iomanip>
#include <sstream>
#include <chrono>
#include <filesystem>

namespace h3h {

namespace {

size_t curlStringWriteCallback(char* ptr, size_t size, size_t nmemb, void* userdata) {
    if (!userdata || !ptr) return 0;
    auto* buf = static_cast<std::string*>(userdata);
    size_t totalBytes = size * nmemb;
    buf->append(ptr, totalBytes);
    return totalBytes;
}

struct DownloadProgressContext {
    ProgressCallback callback;
    const std::atomic<bool>* cancel;
    std::chrono::steady_clock::time_point startTime;
};

int curlXferProgressCallback(void* clientp, curl_off_t dltotal, curl_off_t dlnow, curl_off_t, curl_off_t) {
    auto* ctx = static_cast<DownloadProgressContext*>(clientp);
    if (!ctx) return 0;

    if (ctx->cancel && ctx->cancel->load()) {
        return 1; // Abort transfer
    }

    if (ctx->callback && dlnow > 0) {
        auto now = std::chrono::steady_clock::now();
        double elapsedSec = std::chrono::duration<double>(now - ctx->startTime).count();
        double speed = elapsedSec > 0.0 ? static_cast<double>(dlnow) / elapsedSec : 0.0;
        ctx->callback(static_cast<uint64_t>(dlnow), static_cast<uint64_t>(dltotal), speed);
    }
    return 0;
}

} // namespace

class SwitchPlatform : public IPlatform {
public:
    SwitchPlatform() = default;
    ~SwitchPlatform() override {
        shutdown();
    }

    bool initialize() override {
        Result rc = nsInitialize();
        if (R_FAILED(rc)) {
            return false;
        }
        m_nsInitialized = true;

        rc = psmInitialize();
        if (R_SUCCEEDED(rc)) {
            m_psmInitialized = true;
        }

        rc = nifmInitialize(NifmServiceType_User);
        if (R_SUCCEEDED(rc)) {
            m_nifmInitialized = true;
        }

        // Initialize BSD socket service with high-performance buffer configuration
        // (Uses 1 MB rx / 2 MB max rx window, matching DBI & Tinfoil network performance)
        SocketInitConfig sockConf = {
            .tcp_tx_buf_size = 0x40000,          // 256 KB
            .tcp_rx_buf_size = 0x100000,         // 1 MB
            .tcp_tx_buf_max_size = 0x200000,     // 2 MB
            .tcp_rx_buf_max_size = 0x200000,     // 2 MB
            .udp_tx_buf_size = 0x2400,
            .udp_rx_buf_size = 0xA500,
            .sb_efficiency = 4,
            .num_bsd_sessions = 3,
            .bsd_service_type = BsdServiceType_Auto,
        };
        rc = socketInitialize(&sockConf);
        if (R_FAILED(rc)) {
            // Fallback to default if memory allocation fails in restricted modes
            rc = socketInitializeDefault();
        }
        if (R_SUCCEEDED(rc)) {
            m_socketInitialized = true;
        }

        rc = plInitialize(PlServiceType_User);
        if (R_SUCCEEDED(rc)) {
            m_plInitialized = true;
        }

        rc = romfsInit();
        if (R_SUCCEEDED(rc)) {
            m_romfsInitialized = true;
        }

        if (curl_global_init(CURL_GLOBAL_DEFAULT) == CURLE_OK) {
            m_curlInitialized = true;
        }

        m_initialized = true;
        return true;
    }

    void shutdown() override {
        if (m_curlInitialized) {
            curl_global_cleanup();
            m_curlInitialized = false;
        }
        if (m_romfsInitialized) {
            romfsExit();
            m_romfsInitialized = false;
        }
        if (m_plInitialized) {
            plExit();
            m_plInitialized = false;
        }
        if (m_socketInitialized) {
            socketExit();
            m_socketInitialized = false;
        }
        if (m_nifmInitialized) {
            nifmExit();
            m_nifmInitialized = false;
        }
        if (m_psmInitialized) {
            psmExit();
            m_psmInitialized = false;
        }
        if (m_nsInitialized) {
            nsExit();
            m_nsInitialized = false;
        }
        m_initialized = false;
    }

    bool listInstalledTitles(std::vector<InstalledTitle>& outTitles) override {
        outTitles.clear();
        s32 offset = 0;
        const s32 batchSize = 32;

        std::string coversDir = getCoversDirectory();

        while (true) {
            NsApplicationRecord records[batchSize];
            s32 count = 0;
            Result rc = nsListApplicationRecord(records, batchSize, offset, &count);
            if (R_FAILED(rc) || count == 0) {
                break;
            }

            for (s32 i = 0; i < count; ++i) {
                uint64_t appId = records[i].application_id;

                // Filter out non-base applications (DLCs have offset >= 1, Updates have 0x800)
                // Base application Title IDs strictly have lower 13 bits as 0
                if ((appId & 0x1FFF) != 0) {
                    continue;
                }

                std::ostringstream ss;
                ss << std::hex << std::uppercase << std::setfill('0') << std::setw(16) << appId;
                std::string titleIdStr = ss.str();

                InstalledTitle title;
                title.titleIdNumeric = appId;
                title.titleId = titleIdStr;
                title.name = "Unknown Game";
                title.author = "Unknown Publisher";

                // Load NACP metadata (heap-allocated to prevent Switch stack overflow)
                auto controlData = std::make_unique<NsApplicationControlData>();
                size_t actualSize = 0;
                rc = nsGetApplicationControlData(
                    NsApplicationControlSource_Storage,
                    appId,
                    controlData.get(),
                    sizeof(NsApplicationControlData),
                    &actualSize
                );

                if (R_SUCCEEDED(rc)) {
                    NacpLanguageEntry* langEntry = nullptr;
                    rc = nacpGetLanguageEntry(&controlData->nacp, &langEntry);
                    if (R_SUCCEEDED(rc) && langEntry) {
                        title.name = langEntry->name;
                        title.author = langEntry->author;
                    }

                    // Extract icon (256x256 JPEG)
                    if (actualSize > sizeof(controlData->nacp)) {
                        size_t iconSize = actualSize - sizeof(controlData->nacp);
                        title.iconBytes.assign(controlData->icon, controlData->icon + iconSize);
                    }
                }

                // Check local cover on SD card
                std::string coverPath;
                uint64_t coverSize = 0;
                if (Installer::findExistingCover(coversDir, titleIdStr, coverPath, coverSize)) {
                    title.hasInstalledCover = true;
                    title.installedCoverPath = coverPath;
                    title.installedCoverSizeBytes = coverSize;
                    title.status = CoverStatus::Installed;
                } else {
                    title.status = CoverStatus::NoCover;
                }

                // Check backup
                std::string backupPath;
                uint64_t backupSize = 0;
                if (Installer::findExistingBackup(coversDir, titleIdStr, backupPath, backupSize)) {
                    title.hasBackup = true;
                    title.backupPath = backupPath;
                    title.backupSizeBytes = backupSize;
                }

                outTitles.push_back(std::move(title));
            }

            offset += count;
            if (count < batchSize) break;
        }

        return true;
    }

    bool loadTitleIcon(uint64_t titleIdNumeric, std::vector<uint8_t>& outJpeg) override {
        auto controlData = std::make_unique<NsApplicationControlData>();
        size_t actualSize = 0;
        Result rc = nsGetApplicationControlData(
            NsApplicationControlSource_Storage,
            titleIdNumeric,
            controlData.get(),
            sizeof(NsApplicationControlData),
            &actualSize
        );

        if (R_SUCCEEDED(rc) && actualSize > sizeof(controlData->nacp)) {
            size_t iconSize = actualSize - sizeof(controlData->nacp);
            outJpeg.assign(controlData->icon, controlData->icon + iconSize);
            return true;
        }
        return false;
    }

    SystemInfo getSystemInfo() override {
        SystemInfo info;
        info.coversDir = getCoversDirectory();

        // Applet Mode check
        AppletType appletType = appletGetAppletType();
        info.isAppletMode = (appletType == AppletType_LibraryApplet || appletType == AppletType_SystemApplet);

        // SD Card Storage Space
        struct statvfs vfs;
        if (statvfs("sdmc:/", &vfs) == 0) {
            info.freeStorageBytes = static_cast<uint64_t>(vfs.f_bavail) * vfs.f_frsize;
            info.totalStorageBytes = static_cast<uint64_t>(vfs.f_blocks) * vfs.f_frsize;
        }

        // Battery
        u32 battPercent = 100;
        PsmChargerType charger = PsmChargerType_Unconnected;
        if (R_SUCCEEDED(psmGetBatteryChargePercentage(&battPercent))) {
            info.batteryPercent = static_cast<int>(battPercent);
        }
        if (R_SUCCEEDED(psmGetChargerType(&charger))) {
            info.isCharging = (charger != PsmChargerType_Unconnected);
        }

        // Network
        NifmInternetConnectionType connType = NifmInternetConnectionType_WiFi;
        u32 wifiStrength = 0;
        NifmInternetConnectionStatus connStatus = NifmInternetConnectionStatus_ConnectingUnknown1;
        if (R_SUCCEEDED(nifmGetInternetConnectionStatus(&connType, &wifiStrength, &connStatus))) {
            info.isNetworkConnected = (connStatus == NifmInternetConnectionStatus_Connected);
        } else {
            // If nifm check fails, assume true so curl can attempt connection
            info.isNetworkConnected = true;
        }

        return info;
    }

    std::string getCoversDirectory() override {
        return Config::DEFAULT_SWITCH_COVERS_DIR;
    }

    std::string getAppDirectory() override {
        return Config::DEFAULT_SWITCH_APP_DIR;
    }

    bool fetchCatalog(const std::string& url, std::string& outJson, std::string& outError) override {
        if (!m_socketInitialized) {
            outError = "Сетевой сервис не инициализирован (проверьте настройки сети / Wi-Fi)";
            return false;
        }

        CURL* curl = curl_easy_init();
        if (!curl) {
            outError = "Failed to initialize CURL context";
            return false;
        }

        std::string responseBuffer;

        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 10L);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 20L);
        curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 64 * 1024L);
        curl_easy_setopt(curl, CURLOPT_TCP_NODELAY, 1L);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Nintendo Switch; ShareApplet) AppleWebKit/609.4 (KHTML, like Gecko) NF/6.0.2.22.5 NintendoBrowser/5.1.0.22474");

        typedef size_t (*CurlWriteFn)(char*, size_t, size_t, void*);
        CurlWriteFn writeFn = curlStringWriteCallback;
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeFn);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &responseBuffer);

        CURLcode res = curl_easy_perform(curl);
        long httpCode = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpCode);
        curl_easy_cleanup(curl);

        if (res != CURLE_OK) {
            outError = std::string("Network transfer error: ") + curl_easy_strerror(res);
            return false;
        }

        if (httpCode != 200) {
            outError = "HTTP server returned code " + std::to_string(httpCode);
            return false;
        }

        outJson = std::move(responseBuffer);
        return true;
    }

    bool downloadFile(
        const std::string& url,
        const std::string& destPath,
        ProgressCallback progress,
        const std::atomic<bool>& cancelRequested,
        std::string& outError
    ) override {
        if (!m_socketInitialized) {
            outError = "Сетевой сервис не доступен (нет инициализации сокетов)";
            return false;
        }

        // Ensure parent directories exist before opening file
        size_t lastSlash = destPath.find_last_of("/\\");
        if (lastSlash != std::string::npos) {
            std::string parentDir = destPath.substr(0, lastSlash);
            if (!parentDir.empty()) {
                std::error_code ec;
                std::filesystem::create_directories(parentDir, ec);
            }
        }

        FILE* fp = fopen(destPath.c_str(), "wb");
        if (!fp) {
            outError = "Could not open target file for writing: " + destPath;
            return false;
        }

        // 256 KB memory buffer for MicroSD block writes (eliminates FAT32 SD-card write stalls)
        std::vector<char> fileBuffer(256 * 1024);
        setvbuf(fp, fileBuffer.data(), _IOFBF, fileBuffer.size());

        CURL* curl = curl_easy_init();
        if (!curl) {
            fclose(fp);
            outError = "Failed to initialize CURL context";
            return false;
        }

        DownloadProgressContext ctx{progress, &cancelRequested, std::chrono::steady_clock::now()};

        typedef int (*CurlXferFn)(void*, curl_off_t, curl_off_t, curl_off_t, curl_off_t);
        CurlXferFn xferFn = curlXferProgressCallback;

        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, fp);
        curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_MAXREDIRS, 10L);
        curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 15L);
        curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 256 * 1024L); // 256 KB curl receive buffer
        curl_easy_setopt(curl, CURLOPT_TCP_NODELAY, 1L);         // Disable Nagle algorithm
        curl_easy_setopt(curl, CURLOPT_TCP_KEEPALIVE, 1L);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Nintendo Switch; ShareApplet) AppleWebKit/609.4 (KHTML, like Gecko) NF/6.0.2.22.5 NintendoBrowser/5.1.0.22474");
        curl_easy_setopt(curl, CURLOPT_XFERINFOFUNCTION, xferFn);
        curl_easy_setopt(curl, CURLOPT_XFERINFODATA, &ctx);
        curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 0L);

        CURLcode res = curl_easy_perform(curl);
        long httpCode = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpCode);

        fflush(fp);
        fclose(fp);
        curl_easy_cleanup(curl);

        if (res == CURLE_ABORTED_BY_CALLBACK) {
            remove(destPath.c_str());
            outError = "Download cancelled by user";
            return false;
        }

        if (res != CURLE_OK) {
            remove(destPath.c_str());
            outError = std::string("Download failed: ") + curl_easy_strerror(res);
            return false;
        }

        if (httpCode < 200 || httpCode >= 300) {
            remove(destPath.c_str());
            outError = "Server returned HTTP status " + std::to_string(httpCode);
            return false;
        }

        return true;
    }

private:
    bool m_initialized{false};
    bool m_nsInitialized{false};
    bool m_psmInitialized{false};
    bool m_nifmInitialized{false};
    bool m_socketInitialized{false};
    bool m_plInitialized{false};
    bool m_romfsInitialized{false};
    bool m_curlInitialized{false};
};

std::unique_ptr<IPlatform> createPlatform() {
    return std::make_unique<SwitchPlatform>();
}

} // namespace h3h
#endif // __SWITCH__
