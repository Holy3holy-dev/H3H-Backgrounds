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

namespace h3h {

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

        rc = psmInitialize();
        (void)rc; // Non-fatal if psm fails

        rc = nifmInitialize(NifmServiceType_User);
        (void)rc;

        curl_global_init(CURL_GLOBAL_DEFAULT);
        m_initialized = true;
        return true;
    }

    void shutdown() override {
        if (!m_initialized) return;
        curl_global_cleanup();
        nifmExit();
        psmExit();
        nsExit();
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

                // Load NACP metadata
                NsApplicationControlData controlData;
                size_t actualSize = 0;
                rc = nsGetApplicationControlData(
                    NsApplicationControlSource_Storage,
                    appId,
                    &controlData,
                    sizeof(controlData),
                    &actualSize
                );

                if (R_SUCCEEDED(rc)) {
                    NacpLanguageEntry* langEntry = nullptr;
                    rc = nacpGetLanguageEntry(&controlData.nacp, &langEntry);
                    if (R_SUCCEEDED(rc) && langEntry) {
                        title.name = langEntry->name;
                        title.author = langEntry->author;
                    }

                    // Extract icon (256x256 JPEG)
                    if (actualSize > sizeof(controlData.nacp)) {
                        size_t iconSize = actualSize - sizeof(controlData.nacp);
                        title.iconBytes.assign(controlData.icon, controlData.icon + iconSize);
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
        NsApplicationControlData controlData;
        size_t actualSize = 0;
        Result rc = nsGetApplicationControlData(
            NsApplicationControlSource_Storage,
            titleIdNumeric,
            &controlData,
            sizeof(controlData),
            &actualSize
        );

        if (R_SUCCEEDED(rc) && actualSize > sizeof(controlData.nacp)) {
            size_t iconSize = actualSize - sizeof(controlData.nacp);
            outJpeg.assign(controlData.icon, controlData.icon + iconSize);
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
        u32 nifmState = 0;
        if (R_SUCCEEDED(nifmGetInternetConnectionStatus(nullptr, &nifmState, nullptr))) {
            info.isNetworkConnected = (nifmState != 0);
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
        CURL* curl = curl_easy_init();
        if (!curl) {
            outError = "Failed to initialize CURL context";
            return false;
        }

        std::string responseBuffer;

        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 1L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 2L);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "H3H-Backgrounds-Downloader/1.0 (Nintendo Switch)");

        auto writeCallback = [](char* ptr, size_t size, size_t nmemb, void* userdata) -> size_t {
            auto* buf = static_cast<std::string*>(userdata);
            buf->append(ptr, size * nmemb);
            return size * nmemb;
        };

        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeCallback);
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
        FILE* fp = fopen(destPath.c_str(), "wb");
        if (!fp) {
            outError = "Could not open target file for writing: " + destPath;
            return false;
        }

        CURL* curl = curl_easy_init();
        if (!curl) {
            fclose(fp);
            outError = "Failed to initialize CURL context";
            return false;
        }

        struct ProgressContext {
            ProgressCallback callback;
            const std::atomic<bool>* cancel;
            std::chrono::steady_clock::time_point startTime;
            uint64_t lastBytes{0};
        };

        ProgressContext ctx{progress, &cancelRequested, std::chrono::steady_clock::now(), 0};

        auto xferCallback = [](void* clientp, curl_off_t dltotal, curl_off_t dlnow, curl_off_t, curl_off_t) -> int {
            auto* c = static_cast<ProgressContext*>(clientp);
            if (c->cancel && c->cancel->load()) {
                return 1; // Abort transfer
            }

            if (c->callback && dlnow > 0) {
                auto now = std::chrono::steady_clock::now();
                double elapsedSec = std::chrono::duration<double>(now - c->startTime).count();
                double speed = elapsedSec > 0 ? static_cast<double>(dlnow) / elapsedSec : 0.0;
                c->callback(static_cast<uint64_t>(dlnow), static_cast<uint64_t>(dltotal), speed);
            }
            return 0;
        };

        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, fp);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 1L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 2L);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "H3H-Backgrounds-Downloader/1.0 (Nintendo Switch)");
        curl_easy_setopt(curl, CURLOPT_XFERINFOFUNCTION, xferCallback);
        curl_easy_setopt(curl, CURLOPT_XFERINFODATA, &ctx);
        curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 0L);

        CURLcode res = curl_easy_perform(curl);
        long httpCode = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &httpCode);

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
};

std::unique_ptr<IPlatform> createPlatform() {
    return std::make_unique<SwitchPlatform>();
}

} // namespace h3h
#endif // __SWITCH__
