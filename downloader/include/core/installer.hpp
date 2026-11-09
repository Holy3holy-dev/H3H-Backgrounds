#pragma once

#include "core/types.hpp"
#include <string>
#include <vector>
#include <functional>

namespace h3h {

struct InstallResult {
    bool success{false};
    std::string message;
    bool rollbackOccurred{false};
    std::string installedPath;
    std::string backupPath;
};

class Installer {
public:
    // Finds existing cover on disk (strictly case-insensitive match for FAT32/exFAT compatibility)    // Multi-cover variant detection (TITLEID.mp4, TITLEID_1.mp4, TITLEID_2.mp4...)
    static std::vector<InstalledCoverVariant> findInstalledCoverVariants(
        const std::string& coversDir,
        const std::string& titleId
    );

    static std::string getNextAvailableCoverPath(
        const std::string& coversDir,
        const std::string& titleId,
        int* outIndex = nullptr
    );

    // Switch active cover (atomic swap between TITLEID.mp4 and TITLEID_<targetIndex>.mp4)
    static bool switchActiveCover(
        const std::string& coversDir,
        const std::string& titleId,
        int targetIndex
    );

    // Delete single variant (or active)
    static bool deleteCoverVariant(
        const std::string& coversDir,
        const std::string& titleId,
        int index
    );

    // Delete all variants for a game
    static bool deleteAllCoverVariants(
        const std::string& coversDir,
        const std::string& titleId
    );


    static bool findExistingCover(
        const std::string& coversDir,
        const std::string& titleId,
        std::string& outCoverPath,
        uint64_t& outSizeBytes
    );

    // Finds existing backup on disk (.bak)
    static bool findExistingBackup(
        const std::string& coversDir,
        const std::string& titleId,
        std::string& outBackupPath,
        uint64_t& outSizeBytes
    );

    // Full atomic installation pipeline with validation and automatic rollback
    static InstallResult installVariant(
        const std::string& coversDir,
        const std::string& titleId,
        const std::string& tempFilePath,
        const std::string& expectedSha256,
        uint64_t expectedSizeBytes,
        bool createBackup = true
    );

    // Restores an existing backup (.bak) to active cover (.mp4)
    static InstallResult restoreBackup(
        const std::string& coversDir,
        const std::string& titleId
    );

    // Deletes an installed cover, optionally keeping or deleting backup
    static bool deleteCover(
        const std::string& coversDir,
        const std::string& titleId,
        bool deleteBackup = false
    );

    // 4IFIR Video Icon Support
    static bool findExistingIcon(
        const std::string& iconsDir,
        const std::string& titleId,
        std::string& outIconPath,
        uint64_t& outSizeBytes
    );

    static InstallResult installIcon(
        const std::string& iconsDir,
        const std::string& titleId,
        const std::string& tempFilePath,
        uint64_t expectedSizeBytes = 0,
        bool createBackup = true
    );

    static bool deleteIcon(
        const std::string& iconsDir,
        const std::string& titleId
    );

    // Feature 5: Video file validation & Integrity Scanner
    static bool validateVideoFile(const std::string& filePath, std::string& outReason);
    static IntegrityReport validateAllInstalledCovers(const std::string& coversDir);
    static int deleteCorruptedCovers(const std::vector<IntegrityIssue>& issues);

    // Feature 3: Local gameplay recordings from sdmc:/recordings/
    static std::vector<LocalRecording> listLocalRecordings(const std::string& recordingsDir);
    static InstallResult installLocalRecording(
        const std::string& coversDir,
        const std::string& titleId,
        const std::string& sourceRecordingPath,
        bool createBackup = true
    );
};

} // namespace h3h
