#pragma once

#include "core/types.hpp"
#include <vector>
#include <string>
#include <functional>
#include <memory>
#include <atomic>

namespace h3h {

using ProgressCallback = std::function<void(uint64_t bytesDownloaded, uint64_t totalBytes, double speedBps)>;

class IPlatform {
public:
    virtual ~IPlatform() = default;

    // Platform lifecycle
    virtual bool initialize() = 0;
    virtual void shutdown() = 0;

    // Title discovery
    virtual bool listInstalledTitles(std::vector<InstalledTitle>& outTitles) = 0;
    virtual bool loadTitleIcon(uint64_t titleIdNumeric, std::vector<uint8_t>& outJpeg) = 0;

    // RomFS release for self-updating
    virtual void releaseRomfs() {}
    virtual void restoreRomfs() {}

    // System diagnostics
    virtual SystemInfo getSystemInfo() = 0;
    virtual std::string getCoversDirectory() = 0;
    virtual std::string getIconsDirectory() = 0;
    virtual std::string getRecordingsDirectory() = 0;
    virtual std::string getAppDirectory() = 0;

    // Networking
    virtual bool fetchCatalog(const std::string& url, std::string& outJson, std::string& outError) = 0;
    virtual bool downloadFile(
        const std::string& url,
        const std::string& destPath,
        ProgressCallback progress,
        const std::atomic<bool>& cancelRequested,
        std::string& outError
    ) = 0;
};

// Factory function to obtain the platform instance
std::unique_ptr<IPlatform> createPlatform();

} // namespace h3h
