#include "platform/platform_interface.hpp"
#include "core/config.hpp"
#include "core/installer.hpp"

#ifndef __SWITCH__

#include <filesystem>
#include <fstream>
#include <sstream>
#include <chrono>
#include <thread>
#include <iostream>

#ifdef _WIN32
#include <windows.h>
#include <winhttp.h>
#pragma comment(lib, "winhttp.lib")
#endif

namespace fs = std::filesystem;

namespace h3h {

class DesktopPlatform : public IPlatform {
public:
    DesktopPlatform() = default;
    ~DesktopPlatform() override = default;

    bool initialize() override {
        // Ensure local recordings/covers directory exists for simulator/testing
        std::error_code ec;
        fs::create_directories(getCoversDirectory(), ec);
        fs::create_directories(getIconsDirectory(), ec);
        fs::create_directories(getAppDirectory(), ec);
        return true;
    }

    void shutdown() override {}

    bool listInstalledTitles(std::vector<InstalledTitle>& outTitles) override {
        outTitles.clear();

        // Realistic simulated installed library for desktop testing & development
        struct MockGameDef {
            const char* titleId;
            const char* name;
            const char* author;
        };

        static const MockGameDef mockGames[] = {
            {"01005CA01580E000", "Teenage Mutant Ninja Turtles: Shredder's Revenge", "Dotemu"},
            {"01007EF00011E000", "The Legend of Zelda: Breath of the Wild", "Nintendo"},
            {"0100000000010000", "Super Mario Odyssey", "Nintendo"},
            {"01008C3003A48000", "Metroid Dread", "Nintendo"},
            {"0100F8F0000A2000", "Animal Crossing: New Horizons", "Nintendo"},
            {"01006A800016E000", "Super Smash Bros. Ultimate", "Nintendo"}
        };

        std::string coversDir = getCoversDirectory();

        for (const auto& g : mockGames) {
            InstalledTitle t;
            t.titleId = g.titleId;
            t.name = g.name;
            t.author = g.author;

            // Check SD card mock covers
            std::string coverPath;
            uint64_t coverSize = 0;
            if (Installer::findExistingCover(coversDir, t.titleId, coverPath, coverSize)) {
                t.hasInstalledCover = true;
                t.installedCoverPath = coverPath;
                t.installedCoverSizeBytes = coverSize;
                t.status = CoverStatus::Installed;
            } else {
                t.status = CoverStatus::NoCover;
            }

            // Check backup
            std::string backupPath;
            uint64_t backupSize = 0;
            if (Installer::findExistingBackup(coversDir, t.titleId, backupPath, backupSize)) {
                t.hasBackup = true;
                t.backupPath = backupPath;
                t.backupSizeBytes = backupSize;
            }

            outTitles.push_back(std::move(t));
        }

        return true;
    }

    bool loadTitleIcon(uint64_t, std::vector<uint8_t>& outJpeg) override {
        // Mock 1x1 or empty icon on desktop simulator
        outJpeg.clear();
        return false;
    }

    SystemInfo getSystemInfo() override {
        SystemInfo info;
        info.isAppletMode = false;
        info.coversDir = getCoversDirectory();
        info.batteryPercent = 95;
        info.isCharging = true;
        info.isNetworkConnected = true;

        std::error_code ec;
        fs::space_info si = fs::space(getCoversDirectory(), ec);
        if (!ec) {
            info.freeStorageBytes = si.available;
            info.totalStorageBytes = si.capacity;
        } else {
            info.freeStorageBytes = 64ULL * 1024 * 1024 * 1024;
            info.totalStorageBytes = 128ULL * 1024 * 1024 * 1024;
        }

        return info;
    }

    std::string getRecordingsDirectory() override {
        return (fs::current_path() / "recordings").string();
    }

    std::string getCoversDirectory() override {
        return "./recordings/covers";
    }

    std::string getIconsDirectory() override {
        return "./recordings/icons";
    }

    std::string getAppDirectory() override {
        return "./switch/H3H-Backgrounds";
    }

    bool fetchCatalog(const std::string& url, std::string& outJson, std::string& outError) override {
        // If local file path passed (fixture)
        if (url.rfind("file://", 0) == 0 || fs::exists(url)) {
            std::string path = url;
            if (path.rfind("file://", 0) == 0) path = path.substr(7);
            std::ifstream f(path);
            if (f.is_open()) {
                std::stringstream buffer;
                buffer << f.rdbuf();
                outJson = buffer.str();
                return true;
            }
        }

        // Check if catalog/data/catalog.json exists locally as default fallback
        if (fs::exists("catalog/data/catalog.json")) {
            std::ifstream f("catalog/data/catalog.json");
            if (f.is_open()) {
                std::stringstream buffer;
                buffer << f.rdbuf();
                outJson = buffer.str();
                return true;
            }
        }

        outError = "Desktop platform fallback catalog loaded";
        return false;
    }

    bool downloadFile(
        const std::string& url,
        const std::string& destPath,
        ProgressCallback progress,
        const std::atomic<bool>& cancelRequested,
        std::string& outError
    ) override {
        // If url is a local fixture or test file
        if (url.rfind("file://", 0) == 0 || fs::exists(url)) {
            std::string src = url;
            if (src.rfind("file://", 0) == 0) src = src.substr(7);

            std::ifstream in(src, std::ios::binary);
            std::ofstream out(destPath, std::ios::binary);
            if (!in.is_open() || !out.is_open()) {
                outError = "Could not open source/destination file";
                return false;
            }

            char buf[65536];
            uint64_t total = fs::file_size(src);
            uint64_t downloaded = 0;

            while (in.read(buf, sizeof(buf)) || in.gcount() > 0) {
                if (cancelRequested.load()) {
                    out.close();
                    fs::remove(destPath);
                    outError = "Download cancelled";
                    return false;
                }
                out.write(buf, in.gcount());
                downloaded += in.gcount();
                if (progress) progress(downloaded, total, 5000000.0);
            }
            return true;
        }

        // In simulator without live network connection to fake URLs, generate mock payload if needed
        std::ofstream out(destPath, std::ios::binary);
        if (!out.is_open()) {
            outError = "Could not create destination file: " + destPath;
            return false;
        }
        std::string mockPayload = "H3H_MOCK_VIDEO_PAYLOAD";
        out.write(mockPayload.data(), mockPayload.size());
        out.close();
        return true;
    }
};

std::unique_ptr<IPlatform> createPlatform() {
    return std::make_unique<DesktopPlatform>();
}

} // namespace h3h

#endif // !__SWITCH__
