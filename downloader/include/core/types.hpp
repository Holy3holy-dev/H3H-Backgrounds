#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include <algorithm>
#include <cctype>

namespace h3h {

enum class CoverStyle {
    Unknown,
    Cinematic,
    Gameplay,
    AnimatedArt,
    Minimal,
    Dark,
    Retro,
    Music
};

inline std::string styleToString(CoverStyle style) {
    switch (style) {
        case CoverStyle::Cinematic:   return "Cinematic";
        case CoverStyle::Gameplay:    return "Gameplay";
        case CoverStyle::AnimatedArt: return "Animated Art";
        case CoverStyle::Minimal:     return "Minimal";
        case CoverStyle::Dark:        return "Dark";
        case CoverStyle::Retro:       return "Retro";
        case CoverStyle::Music:       return "Music";
        default:                      return "All";
    }
}

inline CoverStyle stringToStyle(const std::string& str) {
    if (str == "Cinematic")    return CoverStyle::Cinematic;
    if (str == "Gameplay")     return CoverStyle::Gameplay;
    if (str == "Animated Art") return CoverStyle::AnimatedArt;
    if (str == "Minimal")      return CoverStyle::Minimal;
    if (str == "Dark")         return CoverStyle::Dark;
    if (str == "Retro")        return CoverStyle::Retro;
    if (str == "Music")        return CoverStyle::Music;
    return CoverStyle::Unknown;
}

struct Variant {
    std::string id;
    std::string name;
    CoverStyle style{CoverStyle::Unknown};
    std::string version;
    std::string url;
    std::string previewUrl;
    uint64_t sizeBytes{0};
    std::string sha256;
    double durationSec{0.0};
    std::string author;
    std::string codec{"h264"};
    int width{1280};
    int height{720};
    double fps{30.0};
    bool hasAudio{false};
    std::string notes;
    bool hasIcon{false};
    std::string iconUrl;
    uint64_t iconSizeBytes{0};
    std::string iconCodec{"hevc"};
    int iconWidth{256};
    int iconHeight{256};
};

struct GameCatalogEntry {
    std::string titleId;       // Strictly 16 hex chars (e.g. 01005CA01580E000)
    std::string title;
    std::string publisher;
    std::string iconUrl;
    std::vector<Variant> variants;
};

enum class CoverStatus {
    NoCover,
    Installed,
    UpdateAvailable,
    CustomCover
};

struct InstalledTitle {
    uint64_t titleIdNumeric{0};
    std::string titleId;       // Uppercase 16-hex string
    std::string name;
    std::string author;
    std::vector<uint8_t> iconBytes; // JPEG icon (256x256 from NACP)
    
    // Status relative to SD card
    CoverStatus status{CoverStatus::NoCover};
    bool hasInstalledCover{false};
    std::string installedCoverPath;
    uint64_t installedCoverSizeBytes{0};
    std::string installedVariantId;
    bool hasBackup{false};
    std::string backupPath;
    uint64_t backupSizeBytes{0};
    bool hasInstalledIcon{false};
    std::string installedIconPath;
    uint64_t installedIconSizeBytes{0};
    
    // Matched catalog data
    bool hasCatalogMatch{false};
    GameCatalogEntry catalogEntry;
};

enum class TaskState {
    Pending,
    Downloading,
    Verifying,
    Committing,
    Completed,
    Failed,
    Cancelled
};

struct DownloadTask {
    std::string id;
    std::string titleId;
    std::string gameTitle;
    Variant variant;
    std::string tempFilePath;
    std::string targetFilePath;
    std::string backupFilePath;
    
    TaskState state{TaskState::Pending};
    uint64_t bytesDownloaded{0};
    uint64_t totalBytes{0};
    double progressPercent{0.0};
    double downloadSpeedBps{0.0};
    std::string errorMessage;
};

struct SystemInfo {
    bool isAppletMode{false};
    uint64_t freeStorageBytes{0};
    uint64_t totalStorageBytes{0};
    int batteryPercent{100};
    bool isCharging{false};
    bool isNetworkConnected{false};
    std::string coversDir;
};


struct LocalRecording {
    std::string filename;
    std::string fullPath;
    uint64_t sizeBytes{0};
    std::string formattedSize;
    std::string dateModified;
};

struct IntegrityIssue {
    std::string titleId;
    std::string filename;
    std::string fullPath;
    uint64_t sizeBytes{0};
    std::string reason;
};

struct IntegrityReport {
    int totalChecked{0};
    int totalValid{0};
    std::vector<IntegrityIssue> issues;
};

} // namespace h3h

